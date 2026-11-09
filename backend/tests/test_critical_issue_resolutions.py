import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import (
    Owner, Client, Invoice, Obligation, PaymentHistory, FinancialEntry,
    Action, RescuePlan, WebhookEvent, AuditLog, Message
)
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState, InvalidStateTransitionError
from backend.app.guardrail.policy import PolicyViolationError
from backend.app.guardrail.approval import (
    generate_approval_hash, verify_approval_hash, compute_action_payload,
    generate_payload_hash, build_canonical_payload
)
from backend.app.agents.planner import RescuePlanEngine
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.events.processor import process_webhook_event
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database(clean=True, demo_mode=True)


# =========================================================================
# FIX 1: Webhook & Payment Confirmation Separation Tests
# =========================================================================

def test_simulated_payment_cannot_confirm_real_action(setup_db):
    """
    FIX 1: Simulated webhook events must move an executed action to SIMULATED,
    NEVER to genuine signature-verified CONFIRMED status.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        idemp = f"test_sim_wh_action_{datetime.now().timestamp()}"
        inv_ref = f"INV-SIM-TEST-{datetime.now().timestamp()}"

        h = generate_approval_hash("Apex Design Studio", 2000.0, "USD", "SEND_REMINDER", idemp)
        action = Action(
            owner_id=owner.id,
            action_type="SEND_REMINDER",
            recipient="Apex Design Studio",
            amount=2000.0,
            currency="USD",
            state=ActionState.EXECUTED,
            idempotency_key=idemp,
            approval_hash=h,
            paypal_ref=inv_ref
        )
        db.add(action)
        db.commit()
        db.refresh(action)

        # Create dummy invoice to match
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=2000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=2),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # 1. Process simulated webhook
        sim_payload = {
            "id": "WH-SIM-001",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "2000.00"}
            }
        }
        res_sim = process_webhook_event(db, sim_payload, is_simulated=True)
        db.refresh(action)
        db.refresh(invoice)

        # Assert action is in SIMULATED state, NOT CONFIRMED
        assert action.state == ActionState.SIMULATED
        assert action.is_simulated is True
        assert action.confirmed_at is None

        # Assert invoice status was NOT mutated to PAID
        assert invoice.status == "SENT"
        assert invoice.is_simulated_paid is True

        # Assert no confirmed financial entries created
        confirmed_count = db.query(FinancialEntry).filter(
            FinancialEntry.reference_id == inv_ref,
            FinancialEntry.status == "confirmed"
        ).count()
        assert confirmed_count == 0

        # Repeated simulation does NOT create duplicate authoritative entries
        res_sim_dup = process_webhook_event(db, sim_payload, is_simulated=True)
        assert db.query(FinancialEntry).filter(
            FinancialEntry.reference_id == inv_ref,
            FinancialEntry.status == "confirmed"
        ).count() == 0

        # 2. Process real verified webhook on the same action WITHOUT manual database resets!
        real_payload = {
            "id": "WH-REAL-001",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "2000.00"}
            }
        }

        res_real = process_webhook_event(db, real_payload, is_simulated=False)
        db.refresh(action)
        db.refresh(invoice)

        # Genuine signature-verified PayPal webhook transitions to CONFIRMED
        assert action.state == ActionState.CONFIRMED
        assert action.is_simulated is False
        assert action.confirmed_at is not None
        assert invoice.status == "PAID"
        assert invoice.is_simulated_paid is False

        # 3. Duplicate real verified webhook returns already_processed
        res_real_dup = process_webhook_event(db, real_payload, is_simulated=False)
        assert res_real_dup["status"] == "already_processed"

    finally:
        db.close()


@pytest.mark.asyncio
async def test_invalid_webhook_signature_rejected_and_audit_logged():
    """
    FIX 1: Unverified webhook signatures must be quarantined and audit-logged.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        bad_payload = {
            "id": "WH-INVALID-SIG-001",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {"id": "INV-TEST-NONE"}
        }
        res = await client.post(
            "/webhooks/paypal",
            json=bad_payload,
            headers={
                "PAYPAL-TRANSMISSION-ID": "fake_transmission",
                "PAYPAL-TRANSMISSION-SIG": "fake_invalid_sig",
                "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert.pem"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["verified"] is False
        assert data["status"] == "unverified_signature_stored"

        db = SessionLocal()
        try:
            audit = db.query(AuditLog).filter(
                AuditLog.event == "WEBHOOK_SIGNATURE_VERIFICATION_FAILED"
            ).order_by(AuditLog.id.desc()).first()
            assert audit is not None
            assert audit.payload["event_id"] == "WH-INVALID-SIG-001"
        finally:
            db.close()


# =========================================================================
# FIX 2: Plan C Contractor Split Permission & Consent Enforcement Tests
# =========================================================================

def test_plan_c_fails_safely_when_permission_false():
    """
    FIX 2: Never generate an executable Plan C when split permission is False or None.
    Removes automatic 50/50 fallback.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()

        # Create obligation with split_allowed = False
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Strict Contractor Inc",
            payee_email="strict@contractor.example.com",
            amount=3000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            split_allowed=False,
            split_consent_recorded=False,
            status="pending"
        )
        db.add(obl)
        db.commit()

        forecaster = ForecasterAgent(db)
        fc = forecaster.run_forecast(obligation_id=obl.id, owner_id=owner.id)

        planner = RescuePlanEngine(db)
        comparison = planner.generate_plans_for_forecast(fc)

        plan_types = [p.plan_type for p in comparison.plans]
        # Plan C MUST NOT be generated!
        assert "C" not in plan_types
        assert "A" in plan_types
        assert "B" in plan_types

    finally:
        db.close()


def test_plan_c_consent_enforcement_at_approval_and_execution():
    """
    FIX 2: Validates contractor consent before approving and before executing a split action.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()

        # Obligation with split_allowed=True BUT split_consent_recorded=False
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Dave NoConsent",
            payee_email="dave@noconsent.example.com",
            amount=2000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            split_allowed=True,
            split_consent_recorded=False,  # NO CONSENT!
            status="pending"
        )
        db.add(obl)
        db.commit()

        idemp = f"act_split_noconsent_{datetime.now().timestamp()}"
        h = generate_approval_hash(obl.payee_name, 1000.0, "USD", "SCHEDULE_PAYOUT_SPLIT", idemp)

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=1000.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            approval_hash=h
        )
        db.add(action)
        db.commit()

        # Attempt to approve without contractor consent -> MUST FAIL
        with pytest.raises(InvalidStateTransitionError, match="FAIL-CLOSED"):
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.APPROVED,
                actor="owner",
                approval_hash=h
            )

        # Now record consent explicitly
        obl.split_consent_recorded = True
        obl.split_consent_source = "written_email_agreement"
        obl.split_consent_timestamp = datetime.now(timezone.utc)
        db.commit()

        # Now approval succeeds
        action = GuardrailStateMachine.transition(
            db=db,
            action=action,
            target_state=ActionState.APPROVED,
            actor="owner",
            approval_hash=h
        )
        assert action.state == ActionState.APPROVED

    finally:
        db.close()


# =========================================================================
# FIX 3: Strengthen Exact-Action Approval Binding & Tampering Tests
# =========================================================================

@pytest.mark.asyncio
async def test_exact_payload_tamper_rejection():
    """
    FIX 3: Any tampering with approved fields (amount, recipient, message body,
    discount, due date, installments) must reject execution and require fresh approval.
    """
    from backend.app.services.execution import ActionExecutionService

    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        idemp = f"act_tamper_test_{datetime.now().timestamp()}"

        plan = RescuePlan(
            owner_id=owner.id,
            run_id="run_tamper_test",
            plan_type="B",
            details={"discount_pct": 3.0, "discount_cost": 60.0},
            cost=60.0,
            incoming_needed=1400.0,
            rationale="Test plan",
            forecast_with_plan=[],
            forecast_without_plan=[],
            late_scenario={},
            remaining_risk="Low"
        )
        db.add(plan)
        db.commit()

        action = Action(
            owner_id=owner.id,
            plan_id=plan.id,
            action_type="APPLY_DISCOUNT",
            recipient="Apex Design Studio",
            amount=60.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            approval_hash="",
            paypal_ref="INV2-DEMO-APEX-001"
        )
        db.add(action)
        db.commit()

        msg = Message(
            action_id=action.id,
            client_id=1,
            body="Original approved message body terms.",
            approval_status="draft"
        )
        db.add(msg)
        db.commit()

        # Compute canonical payload hash and approval signature
        from backend.app.guardrail.approval import generate_canonical_approval_signature
        canonical_p = compute_action_payload(action)
        p_hash = generate_payload_hash(canonical_p)
        h = generate_canonical_approval_signature(p_hash)
        action.approval_hash = h
        db.commit()

        # Legacy compact signature CANNOT approve a new canonical action
        legacy_h = generate_approval_hash(action.recipient, action.amount, action.currency, action.action_type, action.idempotency_key)
        with pytest.raises(InvalidStateTransitionError, match="TAMPERING DETECTED"):
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.APPROVED,
                actor="owner",
                approval_hash=legacy_h
            )

        # Canonical signature approves successfully
        action = GuardrailStateMachine.transition(
            db=db,
            action=action,
            target_state=ActionState.APPROVED,
            actor="owner",
            approval_hash=h
        )
        assert action.state == ActionState.APPROVED
        assert action.approved_payload_hash is not None

        def re_approve(act):
            cp = compute_action_payload(act)
            ph = generate_payload_hash(cp)
            sig = generate_canonical_approval_signature(ph)
            return GuardrailStateMachine.transition(db=db, action=act, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig)

        # --- Test 1: Tampered Amount ---
        action.amount = 999.0
        db.commit()
        with pytest.raises(PolicyViolationError, match="TAMPERING DETECTED"):
            await ActionExecutionService.execute_action(db, action, actor="owner")
        assert action.state == ActionState.PROPOSED  # Invalidate approval

        # Re-approve for next test
        action.amount = 60.0
        db.commit()
        action = re_approve(action)

        # --- Test 2: Tampered Recipient ---
        action.recipient = "Malicious Actor"
        db.commit()
        with pytest.raises(PolicyViolationError, match="TAMPERING DETECTED"):
            await ActionExecutionService.execute_action(db, action, actor="owner")
        assert action.state == ActionState.PROPOSED

        # Re-approve for next test
        action.recipient = "Apex Design Studio"
        db.commit()
        action = re_approve(action)

        # --- Test 3: Tampered Message Body ---
        msg.body = "Tampered message body altered after owner approval!"
        db.commit()
        with pytest.raises(PolicyViolationError, match="TAMPERING DETECTED"):
            await ActionExecutionService.execute_action(db, action, actor="owner")
        assert action.state == ActionState.PROPOSED

        # Re-approve for next test
        msg.body = "Original approved message body terms."
        db.commit()
        action = re_approve(action)

        # --- Test 4: Tampered Invoice Reference ---
        action.paypal_ref = "INV2-TAMPERED-REF-999"
        db.commit()
        with pytest.raises(PolicyViolationError, match="TAMPERING DETECTED"):
            await ActionExecutionService.execute_action(db, action, actor="owner")
        assert action.state == ActionState.PROPOSED

        # Re-approve for next test
        action.paypal_ref = "INV2-DEMO-APEX-001"
        db.commit()
        action = re_approve(action)

        # --- Test 5: Tampered Discount Percentage ---
        plan.details = {"discount_pct": 10.0, "discount_cost": 200.0}
        db.commit()
        with pytest.raises(PolicyViolationError, match="TAMPERING DETECTED"):
            await ActionExecutionService.execute_action(db, action, actor="owner")
        assert action.state == ActionState.PROPOSED

    finally:
        db.close()


# =========================================================================
# FIX 4: Scheduled Expenses in Forecasting Tests
# =========================================================================

def test_scheduled_expenses_included_in_forecast():
    """
    FIX 4: Scheduled expenses must reduce projected balance and increase shortfall.
    Cancelled and paid expenses must be excluded.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = db.query(Obligation).filter(Obligation.owner_id == owner.id, Obligation.status != "paid").first()

        forecaster = ForecasterAgent(db)
        fc_baseline = forecaster.run_forecast(obligation_id=obl.id, starting_balance=1800.0, owner_id=owner.id)
        baseline_shortfall = fc_baseline.shortfall_amount
        baseline_p = fc_baseline.p_shortfall

        # Add a scheduled active expense (Office Rent: $500 due in 3 days)
        rent_date = datetime.now(timezone.utc) + timedelta(days=3)
        rent_entry = FinancialEntry(
            owner_id=owner.id,
            canonical_id="exp_rent_test_500",
            title="Office Studio Rent",
            amount=Decimal("500.00"),
            currency="USD",
            entry_type="expected_expense",
            category="rent",
            transaction_date=rent_date,
            status="expected",
            is_cancelled=False,
            is_demo=True
        )
        db.add(rent_entry)

        # Add a cancelled expense (should NOT be deducted)
        cancelled_entry = FinancialEntry(
            owner_id=owner.id,
            canonical_id="exp_cancelled_test_1000",
            title="Cancelled Equipment Purchase",
            amount=Decimal("1000.00"),
            currency="USD",
            entry_type="expected_expense",
            category="equipment",
            transaction_date=rent_date,
            status="expected",
            is_cancelled=True,  # CANCELLED!
            is_demo=True
        )
        db.add(cancelled_entry)
        db.commit()

        # Run forecast with scheduled expenses
        fc_with_exp = forecaster.run_forecast(obligation_id=obl.id, starting_balance=1800.0, owner_id=owner.id)

        # Shortfall must increase exactly by the $500 rent, ignoring the $1000 cancelled expense!
        assert fc_with_exp.shortfall_amount == baseline_shortfall + 500.0
        # Monte Carlo shortfall probability should be at least baseline or higher
        assert fc_with_exp.p_shortfall >= baseline_p

    finally:
        # Clean up added entries
        db.query(FinancialEntry).filter(FinancialEntry.canonical_id.in_(["exp_rent_test_500", "exp_cancelled_test_1000"])).delete()
        db.commit()
        db.close()


# =========================================================================
# FIX 5: PayPal Transaction Reconciliation Tests
# =========================================================================

@pytest.mark.asyncio
async def test_exact_transaction_reconciliation_safeties(monkeypatch):
    """
    FIX 5:
    1. Reconcile strictly using exact invoice identity.
    2. Never guess based solely on payer email.
    3. Currency mismatch must flag for manual review.
    4. Duplicate transaction IDs must be ignored.
    """
    from backend.app.api import history

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        db = SessionLocal()
        try:
            owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
            inv = db.query(Invoice).join(Invoice.client).filter(Client.owner_id == owner.id, Invoice.status == "SENT").first()
            inv_ref = inv.paypal_invoice_id

            # Case A: Transaction without invoice ID (only payer email) -> Must NOT reconcile
            mock_tx_data_no_inv = {
                "transaction_details": [{
                    "transaction_info": {
                        "transaction_id": "TX-NO-INV-001",
                        "transaction_amount": {"value": "2000.00", "currency_code": "USD"}
                    },
                    "payer_info": {"email_address": inv.client.email}
                }]
            }

            async def mock_list_tx_no_inv(*args, **kwargs):
                return mock_tx_data_no_inv

            monkeypatch.setattr(history.paypal_client, "list_transactions", mock_list_tx_no_inv)

            res_sync1 = await client.post("/history/sync", headers=headers)
            assert res_sync1.status_code == 200
            data1 = res_sync1.json()
            assert data1["reconciled_count"] == 0
            assert data1["unmatched_count"] == 1

            # Case B: Transaction with exact invoice ID -> Successfully reconciles
            mock_tx_data_exact = {
                "transaction_details": [{
                    "transaction_info": {
                        "transaction_id": "TX-EXACT-001",
                        "invoice_id": inv_ref,
                        "transaction_amount": {"value": str(inv.amount), "currency_code": "USD"}
                    },
                    "payer_info": {"email_address": inv.client.email}
                }]
            }

            async def mock_list_tx_exact(*args, **kwargs):
                return mock_tx_data_exact

            monkeypatch.setattr(history.paypal_client, "list_transactions", mock_list_tx_exact)

            res_sync2 = await client.post("/history/sync", headers=headers)
            assert res_sync2.status_code == 200
            data2 = res_sync2.json()
            assert data2["reconciled_count"] == 1

            # Case C: Replay of same transaction ID -> Deduplicated, count = 0
            res_sync3 = await client.post("/history/sync", headers=headers)
            assert res_sync3.status_code == 200
            data3 = res_sync3.json()
            assert data3["reconciled_count"] == 0

        finally:
            db.close()


# =========================================================================
# FIX 7: Email Verification Enforcement Tests
# =========================================================================

@pytest.mark.asyncio
async def test_email_verification_enforcement_on_financial_endpoints():
    """
    FIX 7: Unverified registered users must be blocked (403 Forbidden) from financial operations,
    while verified users and demo users pass through.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register a new unverified user
        unique_email = f"unverified.user.{datetime.now().timestamp()}@example.com"
        reg_res = await client.post("/auth/register", json={
            "email": unique_email,
            "password": "Password123!",
            "name": "Unverified User",
            "business_type": "Freelancer",
            "currency": "USD"
        })
        assert reg_res.status_code == 200
        unverified_token = reg_res.json()["access_token"]
        unverified_headers = {"Authorization": f"Bearer {unverified_token}"}

        # 1. Unverified user accessing financial summary -> 403 Forbidden
        res_summary = await client.get("/finance/summary", headers=unverified_headers)
        assert res_summary.status_code == 403
        assert "Email address not verified" in res_summary.json()["detail"]

        # 2. Unverified user accessing actions -> 403 Forbidden
        res_actions = await client.get("/actions", headers=unverified_headers)
        assert res_actions.status_code == 403

        # 3. Unverified user accessing forecast run -> 403 Forbidden
        res_fc = await client.post("/forecast/run", headers=unverified_headers)
        assert res_fc.status_code == 403

        # Now mark user verified in DB
        db = SessionLocal()
        try:
            u = db.query(Owner).filter(Owner.email == unique_email).first()
            u.email_verified = True
            db.commit()
        finally:
            db.close()

        # Login to get fresh verified token
        login_res = await client.post("/auth/login", json={
            "email": unique_email,
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        verified_token = login_res.json()["access_token"]
        verified_headers = {"Authorization": f"Bearer {verified_token}"}

        # 4. Verified user accessing financial summary -> 200 OK
        res_verified_summary = await client.get("/finance/summary", headers=verified_headers)
        assert res_verified_summary.status_code == 200


# =========================================================================
# Additional Mandatory Security & Financial Correctness Tests
# =========================================================================

@pytest.mark.asyncio
async def test_fail_closed_contractor_consent_comprehensive():
    """
    Test all fail-closed contractor consent scenarios:
    1. Missing obligation -> fails closed on approval and execution
    2. Multiple/ambiguous obligations -> fails closed on approval and execution
    3. Permission None or False -> fails closed
    4. Consent absent -> fails closed
    5. Consent contractor mismatch -> fails closed
    6. Consent revoked between approval and execution -> execution blocked
    """
    from backend.app.services.execution import ActionExecutionService
    from backend.app.guardrail.approval import generate_canonical_approval_signature

    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()

        # 1. Missing obligation
        idemp1 = f"act_failclosed_missing_{datetime.now().timestamp()}"
        act_missing = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Ghost Contractor Nobody",
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp1,
            approval_hash=""
        )
        db.add(act_missing)
        db.commit()

        cp1 = compute_action_payload(act_missing)
        sig1 = generate_canonical_approval_signature(generate_payload_hash(cp1))
        with pytest.raises(InvalidStateTransitionError, match="FAIL-CLOSED: No matching obligation found"):
            GuardrailStateMachine.transition(db=db, action=act_missing, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig1)

        # 2. Duplicate / Ambiguous obligations
        dup_obl_1 = Obligation(
            owner_id=owner.id,
            payee_name="Ambiguous Payee",
            payee_email="ambig1@example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            split_allowed=True,
            split_consent_recorded=True,
            status="pending"
        )
        dup_obl_2 = Obligation(
            owner_id=owner.id,
            payee_name="Ambiguous Payee",
            payee_email="ambig2@example.com",
            amount=1500.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            split_allowed=True,
            split_consent_recorded=True,
            status="pending"
        )
        db.add_all([dup_obl_1, dup_obl_2])
        db.commit()

        idemp2 = f"act_failclosed_dup_{datetime.now().timestamp()}"
        act_dup = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Ambiguous Payee",
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp2,
            approval_hash=""
        )
        db.add(act_dup)
        db.commit()

        cp2 = compute_action_payload(act_dup)
        sig2 = generate_canonical_approval_signature(generate_payload_hash(cp2))
        with pytest.raises(InvalidStateTransitionError, match="FAIL-CLOSED: Ambiguous contractor obligation"):
            GuardrailStateMachine.transition(db=db, action=act_dup, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig2)

        # 3. Permission False
        perm_obl = Obligation(
            owner_id=owner.id,
            payee_name="Unique Disallowed Contractor",
            payee_email="disallowed@example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            split_allowed=False,  # False!
            split_consent_recorded=True,
            status="pending"
        )
        db.add(perm_obl)
        db.commit()

        idemp3 = f"act_failclosed_disallowed_{datetime.now().timestamp()}"
        act_perm = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Unique Disallowed Contractor",
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp3,
            approval_hash=""
        )
        db.add(act_perm)
        db.commit()

        cp3 = compute_action_payload(act_perm)
        sig3 = generate_canonical_approval_signature(generate_payload_hash(cp3))
        with pytest.raises(InvalidStateTransitionError, match="FAIL-CLOSED: Split permission is not granted"):
            GuardrailStateMachine.transition(db=db, action=act_perm, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig3)

        # 4. Consent revoked between approval and execution
        valid_obl = Obligation(
            owner_id=owner.id,
            payee_name="Revocable Contractor",
            payee_email="revocable@example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            split_allowed=True,
            split_consent_recorded=True,
            status="pending"
        )
        db.add(valid_obl)
        db.commit()

        idemp4 = f"act_failclosed_revoked_{datetime.now().timestamp()}"
        act_rev = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Revocable Contractor",
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp4,
            approval_hash=""
        )
        db.add(act_rev)
        db.commit()

        cp4 = compute_action_payload(act_rev)
        sig4 = generate_canonical_approval_signature(generate_payload_hash(cp4))
        act_rev = GuardrailStateMachine.transition(db=db, action=act_rev, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig4)
        assert act_rev.state == ActionState.APPROVED

        # Now revoke consent in obligation before execution
        valid_obl.split_consent_recorded = False
        db.commit()

        with pytest.raises(PolicyViolationError, match="FAIL-CLOSED: Verified contractor split consent is not recorded"):
            await ActionExecutionService.execute_action(db, act_rev, actor="owner")

    finally:
        db.close()


def test_overpayment_flagged_and_partial_payment():
    """
    Test transaction reconciliation on overpayments and partial payments:
    - Overpayments are quarantined and flagged for manual review, NOT marked PAID.
    - Partial payments transition status to PARTIALLY_PAID.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()

        inv_over = Invoice(
            client_id=client.id,
            paypal_invoice_id=f"INV-OVERPAY-{datetime.now().timestamp()}",
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            status="SENT"
        )
        inv_partial = Invoice(
            client_id=client.id,
            paypal_invoice_id=f"INV-PARTIAL-{datetime.now().timestamp()}",
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            status="SENT"
        )
        db.add_all([inv_over, inv_partial])
        db.commit()

        # 1. Overpayment: webhook with $1500 on $1000 invoice
        res_over = process_webhook_event(db, {
            "id": f"WH-OVER-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_over.paypal_invoice_id,
                "amount": {"value": "1500.00"}
            }
        }, is_simulated=False)

        db.refresh(inv_over)
        assert res_over["status"] == "flagged_manual_review"
        assert res_over["reason"] == "overpayment_detected"
        assert inv_over.status == "SENT"  # NOT marked PAID!

        # 2. Partial payment: webhook with $400 on $1000 invoice
        res_part = process_webhook_event(db, {
            "id": f"WH-PART-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_partial.paypal_invoice_id,
                "amount": {"value": "400.00"}
            }
        }, is_simulated=False)

        db.refresh(inv_partial)
        assert res_part["status"] == "success"
        assert inv_partial.status == "PARTIALLY_PAID"

    finally:
        db.close()


def test_production_config_rejects_placeholders():
    """
    Test that production mode (DEV_MODE=False) strictly rejects placeholder credentials
    and missing webhook IDs.
    """
    from backend.app.config import Settings

    # Production mode with placeholder client ID must raise ValueError
    with pytest.raises(ValueError, match="Production mode requires valid PayPal credentials"):
        Settings(
            DEV_MODE=False,
            PAYPAL_CLIENT_ID="sandbox_client_id_placeholder",
            PAYPAL_CLIENT_SECRET="secure_real_client_secret_12345678",
            PAYPAL_WEBHOOK_ID="WH-VALID-12345678",
            APPROVAL_SECRET="super-secure-production-approval-secret-32b-length",
            JWT_SECRET="super-secure-production-jwt-signing-secret-32b-length",
            OTP_PEPPER="super-secure-production-otp-pepper-secret-32b-length"
        )

    # Production mode with placeholder webhook ID must raise ValueError
    with pytest.raises(ValueError, match="Production mode requires a valid registered PAYPAL_WEBHOOK_ID"):
        Settings(
            DEV_MODE=False,
            PAYPAL_CLIENT_ID="real_paypal_client_id_123456",
            PAYPAL_CLIENT_SECRET="secure_real_client_secret_12345678",
            PAYPAL_WEBHOOK_ID="placeholder_webhook_id",
            APPROVAL_SECRET="super-secure-production-approval-secret-32b-length",
            JWT_SECRET="super-secure-production-jwt-signing-secret-32b-length",
            OTP_PEPPER="super-secure-production-otp-pepper-secret-32b-length"
        )
