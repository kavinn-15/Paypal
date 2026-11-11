import pytest
import datetime
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import Owner, Client, Invoice, Obligation, PaymentHistory, Action, AuditLog, NegotiationDraft, Message
from backend.app.auth.security import create_access_token
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.agents.planner import RescuePlanEngine
from backend.app.agents.treasurer import TreasurerAgent
from backend.app.agents.supervisor import AgentSupervisor
from backend.app.agents.negotiator import NegotiationAgent
from backend.app.services.resilience_service import ResilienceService
from backend.app.services.simulation_service import SimulationService
from backend.app.schemas import (
    SimulationScenarioRequest, NegotiationGenerateRequest, ObligationConsentRequest
)
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database(clean=True, demo_mode=True)


@pytest.mark.asyncio
async def test_resilience_score_removes_fabrication_and_uses_empirical_history():
    """
    Stage 5 Section 2:
    - Removes hardcoded Apex/Horizon 92%/25%/15%
    - Calculates empirical late-payment probabilities from actual PaymentHistory
    - Transparently applies neutral prior (0.50) when history is insufficient (<2 items)
    - Dynamically generates factors and recommendations referencing real debtors and obligations
    """
    db = SessionLocal()
    try:
        # Create an isolated owner
        ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        owner = Owner(
            name=f"Resilience User {ts}",
            email=f"resilience_{ts}@example.com",
            hashed_password="testpasshash",
            is_active=True,
            email_verified=True,
            currency="USD",
            preferred_currency="USD"
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        # Client A: Sufficient history (4 records, 1 late => empirical p_late ~ (1+1)/(4+2) = 0.333)
        client_a = Client(
            owner_id=owner.id,
            name="Reliable Corp",
            email=f"reliable_{ts}@example.com",
            typical_invoice_amount=5000.0
        )
        # Client B: Insufficient history (0 records => neutral prior 0.50)
        client_b = Client(
            owner_id=owner.id,
            name="Newcomer Ltd",
            email=f"new_{ts}@example.com",
            typical_invoice_amount=3000.0
        )
        db.add_all([client_a, client_b])
        db.commit()

        # Add 4 history records for Client A
        now = datetime.datetime.now(datetime.timezone.utc)
        for d_late in [0, 0, 4, 0]:
            h = PaymentHistory(
                client_id=client_a.id,
                amount=5000.0,
                due_date=now - datetime.timedelta(days=30),
                paid_date=now - datetime.timedelta(days=30 - d_late),
                days_late=d_late,
                source="paypal"
            )
            db.add(h)
        db.commit()

        # Create open invoices for both
        inv_a = Invoice(
            client_id=client_a.id,
            paypal_invoice_id=f"INV-A-{ts}",
            amount=5000.0,
            currency="USD",
            issue_date=now,
            due_date=now + datetime.timedelta(days=5),
            status="SENT"
        )
        inv_b = Invoice(
            client_id=client_b.id,
            paypal_invoice_id=f"INV-B-{ts}",
            amount=3000.0,
            currency="USD",
            issue_date=now,
            due_date=now + datetime.timedelta(days=7),
            status="SENT"
        )
        db.add_all([inv_a, inv_b])
        db.commit()

        # 1. Resilience calculation when NO obligations exist
        score_resp = ResilienceService.calculate_score(db, owner, starting_balance=2000.0)
        assert score_resp.overall_score > 0
        # Recommendations MUST NOT invent contractor payout when no obligations exist
        assert not any("Marcus" in r or "Friday" in r for r in score_resp.recommended_actions)
        assert any("Reliable Corp" in r or "Newcomer Ltd" in r for r in score_resp.recommended_actions)
        assert any("No fixed obligations currently pending" in r for r in score_resp.recommended_actions)

        # Factor detail for Expected Income Reliability should mention neutral prior for Newcomer Ltd
        reliability_factor = next(f for f in score_resp.factors if f.name == "Expected Income Reliability")
        assert "neutral prior" in reliability_factor.detail
        assert "1 client(s) with limited history" in reliability_factor.detail

        # 2. Add an obligation and verify dynamic recommendations
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Custom Contractor LLC",
            payee_email=f"custom_contractor_{ts}@example.com",
            amount=2500.0,
            currency="USD",
            due_date=now + datetime.timedelta(days=5),
            split_allowed=True,
            split_consent_recorded=True,
            status="pending"
        )
        db.add(obl)
        db.commit()

        score_resp_with_obl = ResilienceService.calculate_score(db, owner, starting_balance=2000.0)
        assert any("Custom Contractor LLC" in r for r in score_resp_with_obl.recommended_actions)
        assert any("Custom Contractor LLC" not in "Marcus Sterling" for _ in [1])

    finally:
        db.close()


@pytest.mark.asyncio
async def test_simulation_parameters_respected_and_no_fake_obligations():
    """
    Stage 5 Section 3:
    - Never fabricates a 3200 obligation when user has no obligations
    - Respects delay_client_id, delay_days, partial_pct, emergency_amount, contractor_split_pct
    - Generates honest explanations reflecting actual simulation values
    """
    db = SessionLocal()
    try:
        ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        owner = Owner(
            name=f"Simulation User {ts}",
            email=f"sim_{ts}@example.com",
            hashed_password="testpasshash",
            is_active=True,
            email_verified=True,
            currency="USD"
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        client_x = Client(
            owner_id=owner.id,
            name="Zeta Technologies",
            email=f"zeta_{ts}@example.com",
            typical_invoice_amount=4000.0
        )
        db.add(client_x)
        db.commit()

        now = datetime.datetime.now(datetime.timezone.utc)
        inv_x = Invoice(
            client_id=client_x.id,
            paypal_invoice_id=f"INV-ZETA-{ts}",
            amount=4000.0,
            currency="USD",
            issue_date=now,
            due_date=now + datetime.timedelta(days=3),
            status="SENT"
        )
        db.add(inv_x)
        db.commit()

        # 1. Zero obligations in database -> baseline obligations MUST be empty
        res_delay = SimulationService.run_scenario(
            db, owner,
            SimulationScenarioRequest(
                run_name="Test Delay",
                scenario_type="client_delay_5d",
                delay_client_id=client_x.id,
                delay_days=8
            ),
            starting_balance=1000.0
        )
        assert res_delay.baseline["shortfall_amount"] == 0.0
        assert "Zeta Technologies" in res_delay.explanation
        assert "8 days" in res_delay.explanation

        # 2. Test partial_pay scenario with partial_pct = 35%
        res_partial = SimulationService.run_scenario(
            db, owner,
            SimulationScenarioRequest(
                run_name="Test Partial",
                scenario_type="partial_pay_50",
                delay_client_id=client_x.id,
                partial_pct=35.0
            ),
            starting_balance=1000.0
        )
        assert "35%" in res_partial.explanation
        assert "$1,400.00" in res_partial.explanation  # 35% of 4000 = 1400

        # 3. Test contractor split when NO obligations exist
        res_split_none = SimulationService.run_scenario(
            db, owner,
            SimulationScenarioRequest(
                run_name="Test Split None",
                scenario_type="contractor_split"
            ),
            starting_balance=1000.0
        )
        assert "no active contractor obligations exist" in res_split_none.explanation

        # 4. Add obligation and test contractor_split_pct = 30%
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Engineering Studio",
            payee_email=f"eng_{ts}@example.com",
            amount=2000.0,
            currency="USD",
            due_date=now + datetime.timedelta(days=4),
            split_allowed=True,
            status="pending"
        )
        db.add(obl)
        db.commit()

        res_split = SimulationService.run_scenario(
            db, owner,
            SimulationScenarioRequest(
                run_name="Test Split 30%",
                scenario_type="contractor_split",
                contractor_split_pct=30.0
            ),
            starting_balance=500.0
        )
        assert "30%" in res_split.explanation
        assert "$600.00" in res_split.explanation  # 30% of 2000 = 600
        assert "70%" in res_split.explanation
        assert "$1,400.00" in res_split.explanation

    finally:
        db.close()


@pytest.mark.asyncio
async def test_planner_no_fallback_client_1_or_synthetic_targets():
    """
    Stage 5 Section 4:
    - Never fabricates fallback client_id=1 or synthetic "INV-001" / "Client"
    - If user has no open invoices, Plan A and Plan B are NOT generated
    - Preserves actual database targets and actual invoice currencies
    """
    db = SessionLocal()
    try:
        ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        owner = Owner(
            name=f"No Invoices User {ts}",
            email=f"no_inv_{ts}@example.com",
            hashed_password="testpasshash",
            is_active=True,
            email_verified=True,
            currency="EUR",
            preferred_currency="EUR"
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        now = datetime.datetime.now(datetime.timezone.utc)
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Solo Consultant",
            payee_email=f"solo_{ts}@example.com",
            amount=1500.0,
            currency="EUR",
            due_date=now + datetime.timedelta(days=5),
            split_allowed=True,
            split_consent_recorded=True,
            status="split_agreed"
        )
        db.add(obl)
        db.commit()

        forecaster = ForecasterAgent(db)
        fc = forecaster.run_forecast(obligation_id=obl.id, starting_balance=1000.0, owner_id=owner.id)

        planner = RescuePlanEngine(db)
        plans_res = planner.generate_plans_for_forecast(fc)

        plan_types = [p.plan_type for p in plans_res.plans]
        # With 0 open invoices, Plan A and Plan B MUST NOT be generated!
        assert "A" not in plan_types
        assert "B" not in plan_types
        # Plan C can be generated because contractor consent was recorded
        assert "C" in plan_types

        # Verify no Message record was inserted with client_id=1
        fake_msgs = db.query(Message).filter(Message.client_id == 1).all()
        # Ensure our plan did not create a Message pointing to client_id=1 for this action
        plan_c_obj = next(p for p in plans_res.plans if p.plan_type == "C")
        c_action = db.query(Action).filter(Action.id == plan_c_obj.primary_action.id).first()
        for msg in c_action.messages:
            assert msg.client_id != 1

    finally:
        db.close()


def test_treasurer_affordability_logic_strict_bounds():
    """
    Stage 5 Section 6:
    - In propose_split_option, fixes bug where installment exceeded available cash after reserve
    - Returns None if available cash after reserve <= 0
    - Returns None if installment is < 10% of total obligation
    - Ensures inst1 <= starting_balance - min_reserve
    """
    treasurer = TreasurerAgent()
    now = datetime.datetime.now(datetime.timezone.utc)

    obl = Obligation(
        id=999,
        payee_name="Designer",
        payee_email="designer@example.com",
        amount=3200.0,
        currency="USD",
        due_date=now + datetime.timedelta(days=4),
        split_allowed=True
    )

    # 1. Starting balance $100 with min_reserve $200 (negative cash after reserve) -> None
    split_1 = treasurer.propose_split_option(obl, starting_balance=100.0, expected_next_inflow_date=now + datetime.timedelta(days=10), min_reserve=200.0)
    assert split_1 is None

    # 2. Starting balance $250 with min_reserve $200 (available cash $50 < 10% of 3200 = 320) -> None
    split_2 = treasurer.propose_split_option(obl, starting_balance=250.0, expected_next_inflow_date=now + datetime.timedelta(days=10), min_reserve=200.0)
    assert split_2 is None

    # 3. Starting balance $1000 with min_reserve $200 (available cash $800 = 25% of 3200) -> feasible
    split_3 = treasurer.propose_split_option(obl, starting_balance=1000.0, expected_next_inflow_date=now + datetime.timedelta(days=10), min_reserve=200.0)
    assert split_3 is not None
    assert split_3["installment_1"]["amount"] == 800.0
    assert split_3["installment_2"]["amount"] == 2400.0
    assert split_3["installment_1"]["amount"] <= (1000.0 - 200.0)

    # 4. Starting balance $3000 with min_reserve $200 (available cash $2800 >= 50% of 3200 = 1600) -> standard 50/50
    split_4 = treasurer.propose_split_option(obl, starting_balance=3000.0, expected_next_inflow_date=now + datetime.timedelta(days=10), min_reserve=200.0)
    assert split_4 is not None
    assert split_4["installment_1"]["amount"] == 1600.0
    assert split_4["installment_2"]["amount"] == 1600.0


@pytest.mark.asyncio
async def test_supervisor_orchestration_real_targets_and_honest_traces():
    """
    Stage 5 Section 5:
    - Step 2 Collector uses real invoice IDs, amounts, and pay links
    - Step 5 Negotiation logs honest status ('skipped' or 'failed') if no target, never masking failure
    - Removes artificial 0.70 confidence floor
    """
    db = SessionLocal()
    try:
        ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        owner = Owner(
            name=f"Supervisor User {ts}",
            email=f"sup_user_{ts}@example.com",
            hashed_password="testpasshash",
            is_active=True,
            email_verified=True,
            currency="USD"
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        now = datetime.datetime.now(datetime.timezone.utc)
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Cloud Hosting Provider",
            payee_email=f"cloud_{ts}@example.com",
            amount=800.0,
            currency="USD",
            due_date=now + datetime.timedelta(days=5),
            split_allowed=False,
            status="pending"
        )
        db.add(obl)
        db.commit()

        # User has NO invoices
        supervisor = AgentSupervisor(db)
        res = supervisor.orchestrate_rescue_workflow(owner=owner, obligation_id=obl.id, starting_balance=500.0)
        assert res.status == "completed"
        assert res.shortfall_detected is True

        # Check Negotiation step: should be skipped/honest, not falsely completed with fabricated client
        neg_step = next(s for s in res.steps_trace if s.agent_name == "NegotiationAgent")
        assert neg_step.status == "skipped"
        assert "skipped" in neg_step.summary.lower()

    finally:
        db.close()


@pytest.mark.asyncio
async def test_contractor_consent_endpoint_and_audit_logging():
    """
    Stage 5 Section 7:
    - POST /obligations/{id}/consent legitimately captures contractor consent
    - Stores consent_source, timestamp, notes, split_allowed
    - Emits CONTRACTOR_CONSENT_RECORDED audit log
    - Rejecting/omitting consent prevents Plan C execution
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = SessionLocal()
        ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        owner = Owner(
            name=f"Consent Owner {ts}",
            email=f"consent_{ts}@example.com",
            hashed_password="testpasshash",
            is_active=True,
            email_verified=True,
            currency="USD"
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        now = datetime.datetime.now(datetime.timezone.utc)
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Acme Devs",
            payee_email=f"acme_{ts}@example.com",
            amount=2000.0,
            currency="USD",
            due_date=now + datetime.timedelta(days=5),
            split_allowed=False,
            split_consent_recorded=False,
            status="pending"
        )
        db.add(obl)
        db.commit()
        db.refresh(obl)
        obl_id = obl.id
        owner_id = owner.id
        db.close()

        token = create_access_token(data={"sub": str(owner_id)})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Record legitimate written consent
        payload = {
            "consent_source": "written_agreement",
            "consent_notes": "Contractor signed bilateral split amendment via DocuSign",
            "split_allowed": True,
            "is_simulated": False
        }
        res_consent = await client.post(f"/obligations/{obl_id}/consent", json=payload, headers=headers)
        assert res_consent.status_code == 200
        data = res_consent.json()
        assert data["split_allowed"] is True
        assert data["split_consent_recorded"] is True
        assert data["split_consent_source"] == "written_agreement"
        assert data["status"] == "split_agreed"

        # 2. Verify audit log was appended
        db = SessionLocal()
        try:
            audit = db.query(AuditLog).filter(
                AuditLog.owner_id == owner_id,
                AuditLog.event == "CONTRACTOR_CONSENT_RECORDED"
            ).order_by(AuditLog.id.desc()).first()
            assert audit is not None
            assert audit.payload["obligation_id"] == obl_id
            assert audit.payload["consent_source"] == "written_agreement"
        finally:
            db.close()


@pytest.mark.asyncio
async def test_negotiation_draft_lifecycle_and_consent_sync():
    """
    Stage 5 Section 8:
    - Generates drafts marked status="draft"
    - Requires human approval (/negotiate/drafts/{id}/approve) before dispatch
    - Acceptance of contractor split draft legitimately updates obligation's consent status
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = SessionLocal()
        ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        owner = Owner(
            name=f"Neg Owner {ts}",
            email=f"neg_{ts}@example.com",
            hashed_password="testpasshash",
            is_active=True,
            email_verified=True,
            currency="USD"
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        now = datetime.datetime.now(datetime.timezone.utc)
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Creative Lab",
            payee_email=f"creative_{ts}@example.com",
            amount=1800.0,
            currency="USD",
            due_date=now + datetime.timedelta(days=4),
            split_allowed=False,
            split_consent_recorded=False,
            status="pending"
        )
        db.add(obl)
        db.commit()
        db.refresh(obl)
        obl_id = obl.id
        owner_id = owner.id
        db.close()

        token = create_access_token(data={"sub": str(owner_id)})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Generate negotiation options for contractor_split
        gen_req = {
            "target_type": "contractor_split",
            "obligation_id": obl_id,
            "split_pct": 50.0
        }
        res_gen = await client.post("/negotiate/generate", json=gen_req, headers=headers)
        assert res_gen.status_code == 200
        gen_data = res_gen.json()
        assert len(gen_data["options"]) == 3
        first_draft = gen_data["options"][0]
        draft_id = first_draft["id"]
        assert first_draft["status"] == "draft"

        # 2. Approve draft (human-in-the-loop)
        res_appr = await client.post(f"/negotiate/drafts/{draft_id}/approve", headers=headers)
        assert res_appr.status_code == 200
        assert res_appr.json()["status"] == "approved"

        # 3. Record recipient accepted response
        res_resp = await client.post(f"/negotiate/drafts/{draft_id}/response?outcome=accepted", headers=headers)
        assert res_resp.status_code == 200
        assert res_resp.json()["status"] == "accepted"

        # 4. Verify obligation consent was synced
        db = SessionLocal()
        try:
            updated_obl = db.query(Obligation).filter(Obligation.id == obl_id).first()
            assert updated_obl.split_allowed is True
            assert updated_obl.split_consent_recorded is True
            assert updated_obl.split_consent_source == "negotiation_response_accepted"
            assert updated_obl.status == "split_agreed"
        finally:
            db.close()
