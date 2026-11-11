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
    generate_payload_hash, build_canonical_payload, generate_canonical_approval_signature
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
                "transaction_id": "TX-REAL-001",
                "amount": {"value": "2000.00", "currency_code": "USD"}
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

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=1000.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))
        action.approval_hash = sig
        db.commit()

        # Attempt to approve without contractor consent -> MUST FAIL
        with pytest.raises(InvalidStateTransitionError, match="FAIL-CLOSED"):
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.APPROVED,
                actor="owner",
                approval_hash=sig
            )

        # Now record consent explicitly
        obl.split_consent_recorded = True
        obl.split_consent_source = "written_email_agreement"
        obl.split_consent_timestamp = datetime.now(timezone.utc)
        obl.split_consent_is_simulated = False
        db.commit()

        # Now approval succeeds
        action = GuardrailStateMachine.transition(
            db=db,
            action=action,
            target_state=ActionState.APPROVED,
            actor="owner",
            approval_hash=sig
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
            "currency": "USD",
            "terms_accepted": True
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
                "transaction_id": f"TX-OVER-{datetime.now().timestamp()}",
                "amount": {"value": "1500.00", "currency_code": "USD"}
            }
        }, is_simulated=False)

        db.refresh(inv_over)
        assert res_over["status"] == "flagged_manual_review"
        assert res_over["reason"] == "overpayment_detected"
        assert inv_over.status == "OVERPAID"  # Flagged OVERPAID, NOT marked PAID!
        assert inv_over.status != "PAID"

        # 2. Partial payment: webhook with $400 on $1000 invoice
        res_part = process_webhook_event(db, {
            "id": f"WH-PART-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_partial.paypal_invoice_id,
                "transaction_id": f"TX-PART-{datetime.now().timestamp()}",
                "amount": {"value": "400.00", "currency_code": "USD"}
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


# =========================================================================
# COMPREHENSIVE TESTS FOR FIXES 1 - 5
# =========================================================================

# --- FIX 1: Prevent simulated consent from authorizing real payouts ---

def test_genuine_consent_approves_real_payout():
    """Fix 1: Genuine contractor consent (is_simulated=False) approves a real payout action."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Genuine Contractor {datetime.now().timestamp()}",
            payee_email="genuine@contractor.example.com",
            amount=1500.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=4),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_source="signed_pda_form",
            split_consent_timestamp=datetime.now(timezone.utc),
            split_consent_is_simulated=False,
            status="pending"
        )
        db.add(obl)
        db.commit()

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=750.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_genuine_{datetime.now().timestamp()}",
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            is_simulated=False,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))

        approved_act = GuardrailStateMachine.transition(
            db=db,
            action=action,
            target_state=ActionState.APPROVED,
            actor="owner",
            approval_hash=sig
        )
        assert approved_act.state == ActionState.APPROVED
        assert approved_act.obligation_id == obl.id
        assert approved_act.payout_recipient_email == "genuine@contractor.example.com"
    finally:
        db.close()


def test_simulated_consent_rejects_real_payout_approval():
    """Fix 1: Simulated contractor consent (is_simulated=True) strictly rejects real payout approval."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Simulated Contractor {datetime.now().timestamp()}",
            payee_email="simulated@contractor.example.com",
            amount=1500.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=4),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_source="written_email_agreement",
            split_consent_timestamp=datetime.now(timezone.utc),
            split_consent_is_simulated=True,  # SIMULATED!
            status="pending"
        )
        db.add(obl)
        db.commit()

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=750.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_sim_reject_{datetime.now().timestamp()}",
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            is_simulated=False,  # Real action!
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))

        with pytest.raises(InvalidStateTransitionError, match="SIMULATED CONSENT REJECTED"):
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.APPROVED,
                actor="owner",
                approval_hash=sig
            )
    finally:
        db.close()


@pytest.mark.asyncio
async def test_simulated_consent_rejects_real_payout_execution():
    """Fix 1: Execution fails-closed if contractor consent is simulated."""
    from backend.app.services.execution import ActionExecutionService
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Simulated Exec Contractor {datetime.now().timestamp()}",
            payee_email="simexec@contractor.example.com",
            amount=1200.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=4),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_source="written_email_agreement",
            split_consent_timestamp=datetime.now(timezone.utc),
            split_consent_is_simulated=True,
            status="pending"
        )
        db.add(obl)
        db.commit()

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=600.0,
            currency="USD",
            state=ActionState.APPROVED,
            idempotency_key=f"act_sim_exec_{datetime.now().timestamp()}",
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            is_simulated=False,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        p_hash = generate_payload_hash(cp)
        action.approved_payload_hash = p_hash
        action.approval_hash = generate_canonical_approval_signature(p_hash)
        db.commit()

        with pytest.raises(PolicyViolationError, match="SIMULATED CONSENT REJECTED"):
            await ActionExecutionService.execute_action(db, action, actor="owner")
    finally:
        db.close()


@pytest.mark.asyncio
async def test_permission_revoked_after_approval_fails_execution():
    """Fix 1: Execution fails-closed if split permission is revoked after approval."""
    from backend.app.services.execution import ActionExecutionService
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Revoke Perm Contractor {datetime.now().timestamp()}",
            payee_email="revokeperm@contractor.example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_is_simulated=False,
            status="pending"
        )
        db.add(obl)
        db.commit()

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_rev_perm_{datetime.now().timestamp()}",
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))
        approved = GuardrailStateMachine.transition(
            db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig
        )
        assert approved.state == ActionState.APPROVED

        # Revoke permission before execution
        obl.split_allowed = False
        db.commit()

        with pytest.raises(PolicyViolationError, match="Split permission is not granted"):
            await ActionExecutionService.execute_action(db, approved, actor="owner")
    finally:
        db.close()


def test_demo_simulation_remains_available():
    """Fix 1: Demo Plan C is marked SIMULATED CONSENT — DEMO ONLY and produces simulated action."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        # Seeded Marcus Sterling has split_consent_is_simulated=True
        marcus = db.query(Obligation).filter(
            Obligation.payee_name == "Marcus Sterling",
            Obligation.owner_id == owner.id
        ).first()
        assert marcus is not None
        assert marcus.split_consent_is_simulated is True

        forecaster = ForecasterAgent(db)
        fc = forecaster.run_forecast(obligation_id=marcus.id, owner_id=owner.id)

        planner = RescuePlanEngine(db)
        comparison = planner.generate_plans_for_forecast(fc)
        plan_c = next((p for p in comparison.plans if p.plan_type == "C"), None)
        assert plan_c is not None

        # Verify explicit simulated consent warning label
        assert "SIMULATED CONSENT — DEMO ONLY" in plan_c.remaining_risk or "SIMULATED CONSENT — DEMO ONLY" in plan_c.rationale

        payout_act = plan_c.primary_action
        assert payout_act is not None
        assert payout_act.is_simulated is True
        assert payout_act.approval_version == 2
        assert payout_act.obligation_id == marcus.id
        assert payout_act.payout_recipient_email == marcus.payee_email.strip().lower()
    finally:
        db.close()


# --- FIX 2: Bind actual PayPal payout destination to owner approval ---

def test_payout_destination_bound_to_approval():
    """Fix 2: Payout destination email and obligation ID are cryptographically bound."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Bound Dest Contractor {datetime.now().timestamp()}",
            payee_email="bound.destination@contractor.example.com",
            amount=800.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_is_simulated=False,
            status="pending"
        )
        db.add(obl)
        db.commit()

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=400.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_bound_{datetime.now().timestamp()}",
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        assert cp["payout_recipient_email"] == "bound.destination@contractor.example.com"
        assert cp["obligation_id"] == obl.id
        assert cp["contractor_name"] == obl.payee_name

        sig = generate_canonical_approval_signature(generate_payload_hash(cp))
        approved = GuardrailStateMachine.transition(
            db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig
        )
        assert approved.payout_recipient_email == "bound.destination@contractor.example.com"
        assert approved.obligation_id == obl.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_change_paypal_email_after_approval_rejects_execution():
    """Fix 2: Tampering with contractor payee_email after approval rejects execution."""
    from backend.app.services.execution import ActionExecutionService
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Email Tamper Contractor {datetime.now().timestamp()}",
            payee_email="legit.payee@example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_is_simulated=False,
            status="pending"
        )
        db.add(obl)
        db.commit()

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_email_tamper_{datetime.now().timestamp()}",
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))
        approved = GuardrailStateMachine.transition(
            db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig
        )
        assert approved.state == ActionState.APPROVED

        # Attacker changes payee_email in obligations table after approval
        obl.payee_email = "attacker.destination@fraud.com"
        db.commit()

        with pytest.raises(PolicyViolationError, match="DESTINATION TAMPERED"):
            await ActionExecutionService.execute_action(db, approved, actor="owner")
    finally:
        db.close()


@pytest.mark.asyncio
async def test_change_obligation_id_after_approval_rejects_execution():
    """Fix 2: Tampering with action.obligation_id after approval rejects execution."""
    from backend.app.services.execution import ActionExecutionService
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Obl ID Tamper Contractor {datetime.now().timestamp()}",
            payee_email="obl.id.tamper@example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_is_simulated=False,
            status="pending"
        )
        db.add(obl)
        db.commit()

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_obl_tamper_{datetime.now().timestamp()}",
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))
        approved = GuardrailStateMachine.transition(
            db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig
        )
        assert approved.state == ActionState.APPROVED

        # Create second obligation to tamper with
        obl2 = Obligation(
            owner_id=owner.id,
            payee_name=f"Second Contractor {datetime.now().timestamp()}",
            payee_email="second@contractor.example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_is_simulated=False,
            status="pending"
        )
        db.add(obl2)
        db.commit()

        # Tamper with obligation_id
        approved.obligation_id = obl2.id
        db.commit()

        with pytest.raises(PolicyViolationError, match="TAMPERING DETECTED"):
            await ActionExecutionService.execute_action(db, approved, actor="owner")
    finally:
        db.close()


def test_missing_or_invalid_payout_email_blocks_approval():
    """Fix 2: Missing or invalid PayPal destination email blocks transition to APPROVED."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Invalid Email Contractor {datetime.now().timestamp()}",
            payee_email="invalid-email-address-no-at-sign",  # Invalid email format!
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_is_simulated=False,
            status="pending"
        )
        db.add(obl)
        db.commit()

        action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=obl.payee_name,
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_invemail_{datetime.now().timestamp()}",
            obligation_id=obl.id,
            payout_recipient_email=obl.payee_email,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        cp = compute_action_payload(action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))

        with pytest.raises(InvalidStateTransitionError, match="INVALID PAYOUT DESTINATION"):
            GuardrailStateMachine.transition(
                db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig
            )
    finally:
        db.close()


# --- FIX 3: Remove legacy approval bypass for new actions ---

def test_new_action_receives_approval_version_2():
    """Fix 3: All newly created actions default to approval_version = 2."""
    action = Action(
        owner_id=1,
        action_type="SEND_REMINDER",
        recipient="Test Recipient",
        amount=500.0,
        currency="USD",
        state=ActionState.PROPOSED,
        idempotency_key=f"act_ver2_{datetime.now().timestamp()}"
    )
    assert action.approval_version == 2


def test_new_action_without_plan_or_message_requires_canonical_approval():
    """Fix 3: A standalone v2 action without plan or message strictly rejects compact signature."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        idemp = f"act_raw_v2_{datetime.now().timestamp()}"
        action = Action(
            owner_id=owner.id,
            action_type="SEND_REMINDER",
            recipient="Test Client Co",
            amount=1000.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            approval_version=2,
            approval_hash=""
        )
        db.add(action)
        db.commit()

        # Generate legacy 5-argument compact signature
        compact_hash = generate_approval_hash("Test Client Co", 1000.0, "USD", "SEND_REMINDER", idemp)

        # Attempt to approve v2 action with legacy signature -> MUST FAIL!
        with pytest.raises(InvalidStateTransitionError, match="TAMPERING DETECTED"):
            GuardrailStateMachine.transition(
                db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=compact_hash
            )
    finally:
        db.close()


def test_missing_approval_version_blocks_approval():
    """Fix 3: Action with approval_version=None is rejected during approval."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        idemp = f"act_no_ver_{datetime.now().timestamp()}"
        action = Action(
            owner_id=owner.id,
            action_type="SEND_REMINDER",
            recipient="Test Client Co",
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            approval_version=None,  # Missing!
            approval_hash=""
        )
        db.add(action)
        db.commit()

        # Explicitly set approval_version to None on instance before transition check
        action.approval_version = None

        with pytest.raises(InvalidStateTransitionError, match="MISSING APPROVAL VERSION"):
            GuardrailStateMachine.transition(
                db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash="any_hash"
            )
    finally:
        db.close()


def test_historical_v1_action_isolated():
    """Fix 3: Historical v1 actions can use legacy compact signatures, but reject invalid ones."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        idemp = f"act_hist_v1_{datetime.now().timestamp()}"
        action = Action(
            owner_id=owner.id,
            action_type="SEND_REMINDER",
            recipient="Historical Client",
            amount=800.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            approval_version=1,  # Historical v1!
            approval_hash=""
        )
        db.add(action)
        db.commit()

        valid_compact_hash = generate_approval_hash("Historical Client", 800.0, "USD", "SEND_REMINDER", idemp)
        invalid_compact_hash = "invalid_hash_value"

        # Invalid legacy hash fails
        with pytest.raises(InvalidStateTransitionError, match="TAMPERING DETECTED"):
            GuardrailStateMachine.transition(
                db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=invalid_compact_hash
            )

        # Valid legacy hash succeeds for v1
        approved = GuardrailStateMachine.transition(
            db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=valid_compact_hash
        )
        assert approved.state == ActionState.APPROVED
    finally:
        db.close()


# --- FIX 4: Correct cumulative partial-payment reconciliation ---

def test_cumulative_partial_payments_reconciliation():
    """Fix 4: $400 + $300 + $300 on $1,000 invoice transitions PARTIALLY_PAID -> PARTIALLY_PAID -> PAID."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-CUMULATIVE-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Step 1: $400 payment (Tx A)
        tx_a = f"TX-A-{datetime.now().timestamp()}"
        res1 = process_webhook_event(db, {
            "id": f"WH-CUM-1-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_a,
                "amount": {"value": "400.00", "currency_code": "USD"}
            }
        }, is_simulated=False)
        db.refresh(invoice)
        assert res1["status"] == "success"
        assert invoice.status == "PARTIALLY_PAID"
        assert invoice.paid_date is None

        # Step 2: $300 payment (Tx B)
        tx_b = f"TX-B-{datetime.now().timestamp()}"
        res2 = process_webhook_event(db, {
            "id": f"WH-CUM-2-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_b,
                "amount": {"value": "300.00", "currency_code": "USD"}
            }
        }, is_simulated=False)
        db.refresh(invoice)
        assert res2["status"] == "success"
        assert invoice.status == "PARTIALLY_PAID"
        assert invoice.paid_date is None

        # Step 3: $300 payment (Tx C) -> Reaches total $1,000
        tx_c = f"TX-C-{datetime.now().timestamp()}"
        res3 = process_webhook_event(db, {
            "id": f"WH-CUM-3-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_c,
                "amount": {"value": "300.00", "currency_code": "USD"}
            }
        }, is_simulated=False)
        db.refresh(invoice)
        assert res3["status"] == "success"
        assert invoice.status == "PAID"
        assert invoice.paid_date is not None

        # Step 4: Replay Tx A (duplicate delivery)
        res_replay = process_webhook_event(db, {
            "id": f"WH-REPLAY-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_a,
                "amount": {"value": "400.00", "currency_code": "USD"}
            }
        }, is_simulated=False)
        db.refresh(invoice)
        assert res_replay["status"] == "already_processed"
        assert invoice.status == "PAID"

        # Verify exactly 3 PaymentHistory records for this invoice
        count = db.query(PaymentHistory).filter(PaymentHistory.invoice_id == invoice.id).count()
        assert count == 3
    finally:
        db.close()


def test_cumulative_overpayment_flagged_for_manual_review():
    """Fix 4: Cumulative overpayment ($700 + $500 = $1,200 on $1,000) flags OVERPAID, not marked PAID."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-OVERPAY-CUM-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Payment 1: $700
        process_webhook_event(db, {
            "id": f"WH-OP-1-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": f"TX-OP-1-{datetime.now().timestamp()}",
                "amount": {"value": "700.00", "currency_code": "USD"}
            }
        }, is_simulated=False)
        db.refresh(invoice)
        assert invoice.status == "PARTIALLY_PAID"

        # Payment 2: $500 (Cumulative: $1,200)
        res_over = process_webhook_event(db, {
            "id": f"WH-OP-2-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": f"TX-OP-2-{datetime.now().timestamp()}",
                "amount": {"value": "500.00", "currency_code": "USD"}
            }
        }, is_simulated=False)
        db.refresh(invoice)
        assert res_over["status"] == "flagged_manual_review"
        assert res_over["reason"] == "overpayment_detected"
        assert res_over["excess_amount"] == 200.0
        assert invoice.status == "OVERPAID"
        assert invoice.status != "PAID"

        # Verify audit log recorded the excess amount
        audit = db.query(AuditLog).filter(
            AuditLog.event == "OVERPAYMENT_FLAGGED_FOR_MANUAL_REVIEW"
        ).order_by(AuditLog.id.desc()).first()
        assert audit is not None
        assert audit.payload["excess_amount"] == 200.0
        assert audit.payload["cumulative_received"] == 1200.0
    finally:
        db.close()


def test_simulated_payment_does_not_contribute_to_cumulative_verified_total():
    """Fix 4: Simulated payment does not add to authoritative PaymentHistory or cumulative verified total."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-SIM-ISOLATE-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Simulated payment of $400
        process_webhook_event(db, {
            "id": "WH-SIM-ISOLATE-001",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "400.00", "currency_code": "USD"}
            }
        }, is_simulated=True)
        db.refresh(invoice)
        assert invoice.is_simulated_paid is True
        assert invoice.status == "SENT"

        # Genuine payment of $400
        res_real = process_webhook_event(db, {
            "id": f"WH-REAL-ISOLATE-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": f"TX-REAL-{datetime.now().timestamp()}",
                "amount": {"value": "400.00", "currency_code": "USD"}
            }
        }, is_simulated=False)
        db.refresh(invoice)
        assert res_real["status"] == "success"
        # Since cumulative verified is $400 (not $800), invoice is PARTIALLY_PAID, NOT PAID!
        assert invoice.status == "PARTIALLY_PAID"
    finally:
        db.close()


# --- FIX 5: Database migration script & schema upgrade safety ---

def test_database_migration_schema_upgrade_safe(tmp_path):
    """Fix 5: Alembic migration upgrades existing schema cleanly without data loss."""
    import sqlite3
    from alembic.config import Config
    from alembic import command

    db_file = tmp_path / "test_migration.db"
    db_uri = f"sqlite:///{db_file.as_posix()}"

    # 1. Initialize previous schema (revision 4d5e6f7a8b9c)
    conn = sqlite3.connect(db_file.as_posix())
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE owners (
        id INTEGER PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        hashed_password VARCHAR(255) NOT NULL,
        name VARCHAR(255) NOT NULL,
        is_verified BOOLEAN DEFAULT 1,
        country VARCHAR(50) DEFAULT 'US',
        business_type VARCHAR(50) DEFAULT 'Freelancer',
        preferred_currency VARCHAR(10) DEFAULT 'USD',
        email_verified BOOLEAN DEFAULT 1,
        account_status VARCHAR(20) DEFAULT 'active',
        phone_country_code VARCHAR(8) DEFAULT '+91',
        phone_verified BOOLEAN DEFAULT 0
    );
    """)
    cur.execute("""
    CREATE TABLE obligations (
        id INTEGER PRIMARY KEY,
        owner_id INTEGER REFERENCES owners(id),
        payee_name VARCHAR(255) NOT NULL,
        payee_email VARCHAR(255) NOT NULL,
        amount NUMERIC(12, 2) NOT NULL,
        currency VARCHAR(10) NOT NULL,
        due_date DATETIME NOT NULL,
        status VARCHAR(50) NOT NULL,
        split_allowed BOOLEAN DEFAULT 0
    );
    """)
    cur.execute("""
    CREATE TABLE actions (
        id INTEGER PRIMARY KEY,
        owner_id INTEGER REFERENCES owners(id),
        action_type VARCHAR(100) NOT NULL,
        recipient VARCHAR(255) NOT NULL,
        amount NUMERIC(12, 2) NOT NULL,
        currency VARCHAR(10) NOT NULL,
        state VARCHAR(50) NOT NULL,
        idempotency_key VARCHAR(255) NOT NULL UNIQUE,
        approval_hash VARCHAR(255) NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE invoices (
        id INTEGER PRIMARY KEY,
        paypal_invoice_id VARCHAR(255) NOT NULL UNIQUE,
        amount NUMERIC(12, 2) NOT NULL,
        currency VARCHAR(10) NOT NULL,
        status VARCHAR(50) NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE payment_history (
        id INTEGER PRIMARY KEY,
        amount NUMERIC(12, 2) NOT NULL,
        source VARCHAR(50) NOT NULL
    );
    """)
    # Insert existing data
    cur.execute("INSERT INTO owners (id, email, hashed_password, name) VALUES (1, 'mig_test@example.com', 'hash', 'Mig Test');")
    cur.execute("INSERT INTO obligations (id, owner_id, payee_name, payee_email, amount, currency, due_date, status, split_allowed) VALUES (1, 1, 'Contractor Mig', 'mig@example.com', 500.0, 'USD', '2026-11-20 00:00:00', 'pending', 1);")
    cur.execute("INSERT INTO actions (id, owner_id, action_type, recipient, amount, currency, state, idempotency_key, approval_hash) VALUES (1, 1, 'SEND_REMINDER', 'Client Mig', 300.0, 'USD', 'proposed', 'idemp_mig_1', 'hash123');")
    conn.commit()
    conn.close()

    # 2. Stamp database at revision 4d5e6f7a8b9c
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_uri)
    command.stamp(alembic_cfg, "4d5e6f7a8b9c")

    # 3. Upgrade to head (revision 5e6f7a8b9c0d)
    command.upgrade(alembic_cfg, "head")

    # 4. Verify new columns exist and existing data is preserved
    conn = sqlite3.connect(db_file.as_posix())
    cur = conn.cursor()

    # Verify actions table has approval_version, obligation_id, payout_recipient_email
    act_cols = {row[1] for row in cur.execute("PRAGMA table_info(actions);").fetchall()}
    assert "approval_version" in act_cols
    assert "obligation_id" in act_cols
    assert "payout_recipient_email" in act_cols
    assert "approved_payload_hash" in act_cols
    assert "is_simulated" in act_cols

    # Verify invoices table has is_simulated_paid
    inv_cols = {row[1] for row in cur.execute("PRAGMA table_info(invoices);").fetchall()}
    assert "is_simulated_paid" in inv_cols

    # Verify obligations table has split_consent_*
    obl_cols = {row[1] for row in cur.execute("PRAGMA table_info(obligations);").fetchall()}
    assert "split_consent_recorded" in obl_cols
    assert "split_consent_is_simulated" in obl_cols

    # Verify payment_history has transaction_reference
    ph_cols = {row[1] for row in cur.execute("PRAGMA table_info(payment_history);").fetchall()}
    assert "transaction_reference" in ph_cols

    # Verify existing records preserved intact
    owner_rows = cur.execute("SELECT id, email, name FROM owners WHERE id=1;").fetchall()
    assert len(owner_rows) == 1
    assert owner_rows[0][1] == "mig_test@example.com"

    obl_rows = cur.execute("SELECT id, payee_name, split_consent_is_simulated FROM obligations WHERE id=1;").fetchall()
    assert len(obl_rows) == 1
    assert obl_rows[0][1] == "Contractor Mig"
    assert obl_rows[0][2] == 0  # Default value populated without error

    act_rows = cur.execute("SELECT id, recipient, approval_version FROM actions WHERE id=1;").fetchall()
    assert len(act_rows) == 1
    assert act_rows[0][1] == "Client Mig"
    assert act_rows[0][2] == 1  # Default value 1 applied

    conn.close()


# =========================================================================
# REGRESSION TESTS: SIMULATED PAYOUT EXECUTION VULNERABILITY PREVENTION
# =========================================================================

@pytest.mark.asyncio
async def test_simulated_plan_c_execution_never_calls_paypal_payout_api(monkeypatch):
    """
    REGRESSION TEST:
    1. Create an actual simulated Plan C action using the existing planner.
    2. Attempt to execute it.
    3. Assert that paypal_client.create_payout() is NEVER called.
    4. Verify that the demo simulation still works locally.
    """
    from backend.app.services.execution import ActionExecutionService
    from backend.app.paypal.client import paypal_client

    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        marcus = db.query(Obligation).filter(
            Obligation.payee_name == "Marcus Sterling",
            Obligation.owner_id == owner.id
        ).first()
        assert marcus is not None
        assert marcus.split_consent_is_simulated is True

        # Generate actual Plan C via RescuePlanEngine
        forecaster = ForecasterAgent(db)
        fc = forecaster.run_forecast(obligation_id=marcus.id, owner_id=owner.id)

        planner = RescuePlanEngine(db)
        comparison = planner.generate_plans_for_forecast(fc)
        plan_c = next((p for p in comparison.plans if p.plan_type == "C"), None)
        assert plan_c is not None

        # Primary action is the simulated payout split
        action = db.query(Action).filter(Action.id == plan_c.primary_action.id).first()
        assert action is not None
        assert action.is_simulated is True
        assert action.state == ActionState.PROPOSED

        # Owner approves canonical signature for demo action
        cp = compute_action_payload(action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))
        approved = GuardrailStateMachine.transition(
            db=db, action=action, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig
        )
        assert approved.state == ActionState.APPROVED

        # Track any invocation of paypal_client.create_payout
        payout_api_called = False

        async def mock_create_payout(*args, **kwargs):
            nonlocal payout_api_called
            payout_api_called = True
            raise RuntimeError("CRITICAL VULNERABILITY: paypal_client.create_payout() was invoked for a simulated action!")

        monkeypatch.setattr(paypal_client, "create_payout", mock_create_payout)

        # Execute the approved simulated action
        executed = await ActionExecutionService.execute_action(db, approved, actor="owner")

        # ASSERTION 1: Real PayPal API was NEVER invoked
        assert payout_api_called is False, "CRITICAL VULNERABILITY: paypal_client.create_payout() must NEVER be called for simulated actions!"

        # ASSERTION 2: Demo simulation works locally
        assert executed.state == ActionState.EXECUTED
        assert executed.is_simulated is True
        assert executed.paypal_ref.startswith("SIM-PAYOUT-")

        # ASSERTION 3: Explicit audit log recorded for local simulation
        sim_audit = db.query(AuditLog).filter(
            AuditLog.event == "ACTION_SIMULATED_PAYOUT_EXECUTED_LOCALLY",
            AuditLog.owner_id == owner.id
        ).order_by(AuditLog.id.desc()).first()
        assert sim_audit is not None
        assert sim_audit.payload["action_id"] == executed.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_genuine_action_follows_real_execution_path(monkeypatch):
    """
    REGRESSION TEST:
    Verify that a genuinely approved, non-simulated action with real consent follows
    the existing real execution path and dispatches through PayPal client.
    """
    from backend.app.services.execution import ActionExecutionService
    from backend.app.paypal.client import paypal_client

    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()

        # Genuine contractor with authentic, non-simulated consent
        genuine_obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Genuine Exec Contractor {datetime.now().timestamp()}",
            payee_email="genuine.payout@contractor.example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_source="signed_written_agreement",
            split_consent_timestamp=datetime.now(timezone.utc),
            split_consent_is_simulated=False,  # GENUINE!
            status="pending"
        )
        db.add(genuine_obl)
        db.commit()

        # Non-simulated action
        real_action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=genuine_obl.payee_name,
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_real_payout_{datetime.now().timestamp()}",
            obligation_id=genuine_obl.id,
            payout_recipient_email=genuine_obl.payee_email,
            approval_version=2,
            is_simulated=False,
            approval_hash=""
        )
        db.add(real_action)
        db.commit()

        cp = compute_action_payload(real_action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))
        approved = GuardrailStateMachine.transition(
            db=db, action=real_action, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig
        )
        assert approved.state == ActionState.APPROVED

        # Track call to paypal_client.create_payout
        payout_called_with = None

        async def mock_real_create_payout(recipient_email, amount, currency, sender_batch_id, note):
            nonlocal payout_called_with
            payout_called_with = {
                "recipient_email": recipient_email,
                "amount": amount,
                "currency": currency,
                "sender_batch_id": sender_batch_id
            }
            return {
                "batch_header": {
                    "payout_batch_id": "REAL-PAYPAL-BATCH-88888",
                    "batch_status": "PENDING"
                }
            }

        monkeypatch.setattr(paypal_client, "create_payout", mock_real_create_payout)

        # Execute genuine action
        executed = await ActionExecutionService.execute_action(db, approved, actor="owner")

        # Verify real PayPal API was called with exact parameters
        assert payout_called_with is not None
        assert payout_called_with["recipient_email"] == "genuine.payout@contractor.example.com"
        assert payout_called_with["amount"] == 500.0
        assert executed.state == ActionState.EXECUTED
        assert executed.paypal_ref == "REAL-PAYPAL-BATCH-88888"
        assert executed.is_simulated is False
    finally:
        db.close()


@pytest.mark.asyncio
async def test_simulated_consent_strictly_cannot_authorize_real_payout(monkeypatch):
    """
    REGRESSION TEST:
    Verify that simulated contractor consent cannot authorize a real payout under any condition:
    - Attempting to approve a real action with simulated consent fails at state machine.
    - Attempting to execute a real action with simulated consent fails-closed at execution service.
    - paypal_client.create_payout() is NEVER called.
    """
    from backend.app.services.execution import ActionExecutionService
    from backend.app.paypal.client import paypal_client

    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()

        # Contractor with simulated consent
        sim_obl = Obligation(
            owner_id=owner.id,
            payee_name=f"Sim Consent Contractor {datetime.now().timestamp()}",
            payee_email="sim.consent@contractor.example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_source="written_email_agreement",
            split_consent_timestamp=datetime.now(timezone.utc),
            split_consent_is_simulated=True,  # SIMULATED CONSENT!
            status="pending"
        )
        db.add(sim_obl)
        db.commit()

        # Real action (not simulated)
        real_action = Action(
            owner_id=owner.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient=sim_obl.payee_name,
            amount=500.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=f"act_real_with_sim_consent_{datetime.now().timestamp()}",
            obligation_id=sim_obl.id,
            payout_recipient_email=sim_obl.payee_email,
            approval_version=2,
            is_simulated=False,  # REAL ACTION!
            approval_hash=""
        )
        db.add(real_action)
        db.commit()

        cp = compute_action_payload(real_action)
        sig = generate_canonical_approval_signature(generate_payload_hash(cp))

        # 1. Approval MUST be rejected by state machine
        with pytest.raises(InvalidStateTransitionError, match="SIMULATED CONSENT REJECTED"):
            GuardrailStateMachine.transition(
                db=db, action=real_action, target_state=ActionState.APPROVED, actor="owner", approval_hash=sig
            )

        # 2. Even if action was forcefully marked APPROVED, execution service MUST fail-closed
        real_action.state = ActionState.APPROVED
        real_action.approved_payload_hash = generate_payload_hash(cp)
        real_action.approval_hash = sig
        db.commit()

        payout_called = False

        async def mock_fail_create_payout(*args, **kwargs):
            nonlocal payout_called
            payout_called = True
            raise RuntimeError("CRITICAL VULNERABILITY: Payout API called with simulated consent!")

        monkeypatch.setattr(paypal_client, "create_payout", mock_fail_create_payout)

        with pytest.raises(PolicyViolationError, match="SIMULATED CONSENT REJECTED"):
            await ActionExecutionService.execute_action(db, real_action, actor="owner")

        assert payout_called is False
    finally:
        db.close()


# =========================================================================
# Payment Reconciliation & Database Hardening Tests
# =========================================================================

def test_cumulative_payment_reconciliation_400_300_300(setup_db):
    """
    Test 1: $400 + $300 + $300 on a $1,000 invoice accumulates to $1,000 and transitions to PAID.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-CUMULATIVE-1000-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Step 1: $400
        p1 = {
            "id": f"WH-CUM-1-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "400.00", "currency_code": "USD"},
                "transaction_id": f"TX-CUM-P1-{datetime.now().timestamp()}"
            }
        }
        res1 = process_webhook_event(db, p1, is_simulated=False)
        db.refresh(invoice)
        assert invoice.status == "PARTIALLY_PAID"

        # Step 2: $300
        p2 = {
            "id": f"WH-CUM-2-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "300.00", "currency_code": "USD"},
                "transaction_id": f"TX-CUM-P2-{datetime.now().timestamp()}"
            }
        }
        res2 = process_webhook_event(db, p2, is_simulated=False)
        db.refresh(invoice)
        assert invoice.status == "PARTIALLY_PAID"

        # Step 3: $300 (total = $1000.00)
        p3 = {
            "id": f"WH-CUM-3-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "300.00", "currency_code": "USD"},
                "transaction_id": f"TX-CUM-P3-{datetime.now().timestamp()}"
            }
        }
        res3 = process_webhook_event(db, p3, is_simulated=False)
        db.refresh(invoice)
        assert invoice.status == "PAID"
        assert invoice.paid_date is not None

        # Verify exactly 3 PaymentHistory records
        history_count = db.query(PaymentHistory).filter(PaymentHistory.invoice_id == invoice.id).count()
        assert history_count == 3
    finally:
        db.close()


def test_cumulative_overpayment_700_500(setup_db):
    """
    Test 2: $700 + $500 on a $1,000 invoice totals $1,200.
    Must mark invoice OVERPAID, flag for manual review, and quarantine webhook event.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-OVERPAY-700-500-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Step 1: $700
        p1 = {
            "id": f"WH-OVP-1-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "700.00", "currency_code": "USD"},
                "transaction_id": f"TX-OVP-P1-{datetime.now().timestamp()}"
            }
        }
        process_webhook_event(db, p1, is_simulated=False)
        db.refresh(invoice)
        assert invoice.status == "PARTIALLY_PAID"

        # Step 2: $500 (total = $1,200 > $1,000)
        p2 = {
            "id": f"WH-OVP-2-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "500.00", "currency_code": "USD"},
                "transaction_id": f"TX-OVP-P2-{datetime.now().timestamp()}"
            }
        }
        evt_rec = WebhookEvent(
            owner_id=owner.id,
            paypal_event_id=p2["id"],
            event_type="INVOICING.INVOICE.PAID",
            verified=True,
            payload=p2
        )
        db.add(evt_rec)
        db.commit()

        res2 = process_webhook_event(db, p2, is_simulated=False, webhook_event_id=evt_rec.id)
        db.refresh(invoice)
        db.refresh(evt_rec)

        assert invoice.status == "OVERPAID"
        assert res2["status"] == "flagged_manual_review"
        assert res2["excess_amount"] == 200.0

        # Verify webhook event record was quarantined with manual_review_required
        assert evt_rec.reconciliation_status == "manual_review_required"
        assert evt_rec.processing_state == "quarantined"
    finally:
        db.close()


def test_invoice_already_paid_receiving_additional_200_payment(setup_db):
    """
    Test 3: $1,000 invoice marked PAID receives an additional genuine $200 transaction.
    Transitions PAID -> OVERPAID, records excess in AuditLog, flags manual review.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-PAID-THEN-ADDITIONAL-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Step 1: Genuine payment of $1,000 -> Marks PAID
        p1 = {
            "id": f"WH-FULL-1000-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "1000.00", "currency_code": "USD"},
                "transaction_id": f"TX-FULL-1000-{datetime.now().timestamp()}"
            }
        }
        res1 = process_webhook_event(db, p1, is_simulated=False)
        db.refresh(invoice)
        assert invoice.status == "PAID"

        # Step 2: Customer mistakenly pays an extra $200 with new transaction reference
        extra_tx = f"TX-EXTRA-200-{datetime.now().timestamp()}"
        p2 = {
            "id": f"WH-EXTRA-200-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "200.00", "currency_code": "USD"},
                "transaction_id": extra_tx
            }
        }
        res2 = process_webhook_event(db, p2, is_simulated=False)
        db.refresh(invoice)

        # Invoice MUST transition to OVERPAID and flag manual review
        assert invoice.status == "OVERPAID"
        assert res2["status"] == "flagged_manual_review"
        assert res2["excess_amount"] == 200.0

        # Check AuditLog for overpayment record
        log = db.query(AuditLog).filter(
            AuditLog.event == "OVERPAYMENT_FLAGGED_FOR_MANUAL_REVIEW"
        ).order_by(AuditLog.id.desc()).first()
        assert log is not None
        assert log.payload.get("excess_amount") == 200.0
        assert log.payload.get("transaction_reference") == extra_tx
    finally:
        db.close()


def test_same_transaction_different_webhook_ids(setup_db):
    """
    Test 4: Same transaction delivered through two different webhook event IDs.
    Second event returns already_processed, and exactly 1 PaymentHistory record is created.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-DUP-WEBHOOK-{datetime.now().timestamp()}"
        shared_tx = f"TX-SHARED-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=500.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Webhook delivery 1
        wh1 = {
            "id": f"WH-DELIVERY-1-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "500.00", "currency_code": "USD"},
                "transaction_id": shared_tx
            }
        }
        res1 = process_webhook_event(db, wh1, is_simulated=False)
        assert res1["status"] in ("success", "reconciled", "already_processed")

        # Webhook delivery 2 with different webhook ID but identical transaction_id
        wh2 = {
            "id": f"WH-DELIVERY-2-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "500.00", "currency_code": "USD"},
                "transaction_id": shared_tx
            }
        }
        res2 = process_webhook_event(db, wh2, is_simulated=False)
        assert res2["status"] == "already_processed"
        assert res2["reason"] == "duplicate_transaction_reference"

        # Assert exactly 1 PaymentHistory and 1 FinancialEntry created for this tx
        ph_count = db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == shared_tx).count()
        assert ph_count == 1

        fe_count = db.query(FinancialEntry).filter(FinancialEntry.reference_id == shared_tx).count()
        assert fe_count == 1
    finally:
        db.close()


def test_missing_genuine_transaction_reference_quarantined(setup_db):
    """
    Test 5: Webhook with no transaction_id, capture_id, or payment_id is quarantined for manual review.
    Does NOT manufacture a transaction reference like 'tx_{event_id}'.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-MISSING-TX-{datetime.now().timestamp()}"
        ev_id = f"WH-NO-TX-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=500.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Webhook with no payments array and no transaction/capture IDs
        payload = {
            "id": ev_id,
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "500.00", "currency_code": "USD"}
            }
        }
        res = process_webhook_event(db, payload, is_simulated=False)

        assert res["status"] == "quarantined"
        assert res["reason"] == "missing_transaction_reference"

        # Assert no PaymentHistory was created with manufactured ID
        fake_ph = db.query(PaymentHistory).filter(
            PaymentHistory.transaction_reference == f"tx_{ev_id}"
        ).first()
        assert fake_ph is None

        # Verify audit log
        log = db.query(AuditLog).filter(
            AuditLog.event == "WEBHOOK_MISSING_TRANSACTION_REF_QUARANTINED"
        ).order_by(AuditLog.id.desc()).first()
        assert log is not None
        assert log.payload.get("event_id") == ev_id
    finally:
        db.close()


def test_concurrent_duplicate_transaction_processing(setup_db):
    """
    Test 6: Concurrent duplicate transaction processing is safely caught by database-level
    uniqueness constraint and returns already_processed without crashing.
    """
    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        owner = db1.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db1.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-RACE-{datetime.now().timestamp()}"
        shared_tx = f"TX-RACE-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=500.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db1.add(invoice)
        db1.commit()

        # Insert directly in db1 to simulate first concurrent worker completing flush
        ph1 = PaymentHistory(
            client_id=client.id,
            invoice_id=invoice.id,
            amount=500.0,
            due_date=invoice.due_date,
            paid_date=datetime.now(timezone.utc),
            days_late=0,
            source="paypal",
            transaction_reference=shared_tx
        )
        db1.add(ph1)
        db1.commit()

        # Now simulate a second concurrent webhook attempting to process the same tx_ref
        wh = {
            "id": f"WH-RACE-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "500.00", "currency_code": "USD"},
                "transaction_id": shared_tx
            }
        }
        res2 = process_webhook_event(db2, wh, is_simulated=False)
        assert res2["status"] == "already_processed"
        assert res2["reason"] == "duplicate_transaction_reference"
    finally:
        db1.close()
        db2.close()


@pytest.mark.asyncio
async def test_cross_owner_obligation_id_rejected_before_dispatch(setup_db, monkeypatch):
    """
    Test 7: Action owned by Owner 1 referencing Obligation owned by Owner 2.
    Must be rejected with PolicyViolationError before any PayPal payout API dispatch.
    """
    from backend.app.services.execution import ActionExecutionService
    from backend.app.paypal.client import paypal_client

    db = SessionLocal()
    try:
        # Create Owner 1 and Owner 2
        owner1 = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        owner2 = Owner(
            email=f"owner2_{datetime.now().timestamp()}@example.com",
            hashed_password="hashed_pass_test",
            name="Second Owner",
            email_verified=True
        )
        db.add(owner2)
        db.commit()

        # Obligation belongs to Owner 2
        obl2 = Obligation(
            owner_id=owner2.id,
            payee_name="Marcus Sterling",
            payee_email="marcus.sterling.dev@example.com",
            amount=1000.0,
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=2),
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_source="written_agreement",
            split_consent_timestamp=datetime.now(timezone.utc),
            split_consent_is_simulated=False
        )
        db.add(obl2)
        db.commit()

        # Action is created by Owner 1 pointing to Owner 2's obligation
        action_malicious = Action(
            owner_id=owner1.id,
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Marcus Sterling",
            amount=500.0,
            currency="USD",
            state=ActionState.APPROVED,
            idempotency_key=f"idemp_malicious_{datetime.now().timestamp()}",
            obligation_id=obl2.id,
            payout_recipient_email="marcus.sterling.dev@example.com",
            approval_version=2,
            is_simulated=False,
            approval_hash=""
        )
        db.add(action_malicious)
        db.commit()
        db.refresh(action_malicious)

        cp = compute_action_payload(action_malicious)
        ph = generate_payload_hash(cp)
        sig = generate_canonical_approval_signature(ph)
        action_malicious.approved_payload_hash = ph
        action_malicious.approval_hash = sig
        db.commit()

        payout_api_called = False

        async def mock_fail_create_payout(*args, **kwargs):
            nonlocal payout_api_called
            payout_api_called = True
            raise RuntimeError("CRITICAL FLAW: PayPal Payout API was called for cross-tenant obligation!")

        monkeypatch.setattr(paypal_client, "create_payout", mock_fail_create_payout)

        # Execution MUST fail-closed with PolicyViolationError
        with pytest.raises(PolicyViolationError, match="OWNERSHIP MISMATCH"):
            await ActionExecutionService.execute_action(db, action_malicious, actor="owner")

        assert payout_api_called is False
    finally:
        db.close()


def test_migration_upgrade_preserves_financial_records(setup_db):
    """
    Test 8: Database migration sets approval_version=1 for historical records
    and establishes a unique index on payment_history.transaction_reference.
    """
    from backend.app.db import engine
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    indices = inspector.get_indexes("payment_history")
    tx_indices = [idx for idx in indices if "transaction_reference" in idx.get("column_names", [])]

    assert len(tx_indices) > 0
    assert tx_indices[0].get("unique") in (1, True)

    # Check columns and default on actions table
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(actions);")).fetchall()
        cols = {row[1]: row for row in res}
        assert "approval_version" in cols
        assert "obligation_id" in cols
        assert "is_simulated" in cols
        assert "approved_payload_hash" in cols


# =========================================================================
# Final Payment & Migration Validation Tests
# =========================================================================

def test_alembic_fresh_database_initialization_reaches_head(tmp_path):
    """
    Test 1A: Fresh database initialization from scratch via Alembic reaches head
    without calling create_all(), creating all tables and matching final schema.
    """
    import sqlite3
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import create_engine, inspect, text

    db_file = tmp_path / "fresh_alembic.db"
    db_uri = f"sqlite:///{db_file.as_posix()}"

    # Empty sqlite file
    conn = sqlite3.connect(db_file.as_posix())
    conn.close()

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_uri)
    command.upgrade(cfg, "head")

    eng = create_engine(db_uri)
    insp = inspect(eng)
    tables = insp.get_table_names()
    assert "alembic_version" in tables
    assert "owners" in tables
    assert "invoices" in tables
    assert "actions" in tables
    assert "payment_history" in tables

    with eng.connect() as c:
        current_rev = c.execute(text("SELECT version_num FROM alembic_version;")).scalar()
        assert current_rev in ["6f7a8b9c0d1e", "7a8b9c0d1e2f"]


def test_paypal_webhook_extracts_individual_payment_amount_not_invoice_total(setup_db):
    """
    Test 2A: When an invoice has total amount $1000.00, but a webhook reports
    an individual payment of $400.00 in payments array, the paid_amount recorded
    in PaymentHistory and financial entry is exactly $400.00, NOT $1000.00.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-PAY-INDIVIDUAL-{datetime.now().timestamp()}"
        tx_id = f"PAY-INDIV-400-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # PayPal webhook where resource.amount is invoice total ($1000), but payments[0].amount is $400
        webhook_payload = {
            "id": f"WH-INDIV-400-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "1000.00", "currency_code": "USD"},
                "payments": [
                    {
                        "payment_id": tx_id,
                        "amount": {"value": "400.00", "currency_code": "USD"}
                    }
                ]
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        # Invoice should be PARTIALLY_PAID because $400 < $1000
        assert invoice.status == "PARTIALLY_PAID"

        # PaymentHistory record must record $400.00, NOT $1000.00
        ph = db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first()
        assert ph is not None
        assert float(ph.amount) == 400.0

        # Ledger entry must record $400.00
        le = db.query(FinancialEntry).filter(FinancialEntry.reference_id == tx_id).first()
        assert le is not None
        assert float(le.amount) == 400.0
    finally:
        db.close()


def test_paypal_webhook_quarantines_missing_payment_amount(setup_db):
    """
    Test 2B: Genuine PayPal webhook with no payment amount is quarantined
    and NEVER defaults to invoice.amount.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-NO-AMT-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-NO-AMT-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": f"TX-VALID-{datetime.now().timestamp()}"
                # NO amount specified in resource or payments!
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] == "quarantined"
        assert res["reason"] == "missing_payment_amount"
        assert invoice.status == "SENT"  # Must remain untouched!
    finally:
        db.close()


def test_paypal_webhook_quarantines_ambiguous_payment_records(setup_db):
    """
    Test 2C: Payload containing multiple unrecorded payment records without
    an explicit transaction reference is quarantined as ambiguous.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-AMBIGUOUS-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-AMBIGUOUS-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "payments": [
                    {"payment_id": f"TX-1-{datetime.now().timestamp()}", "amount": {"value": "200.00", "currency_code": "USD"}},
                    {"payment_id": f"TX-2-{datetime.now().timestamp()}", "amount": {"value": "300.00", "currency_code": "USD"}}
                ]
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        assert res["status"] == "quarantined"
        assert res["reason"] == "ambiguous_payment_records"
    finally:
        db.close()


def test_concurrent_sessions_process_same_transaction(setup_db, tmp_path):
    """
    Test 3: Two independent database sessions simultaneously processing the exact same genuine
    transaction reference. Verified via ThreadPoolExecutor. Exactly one PaymentHistory and
    one FinancialEntry record are created, and unique constraint conflicts are handled cleanly.
    """
    from concurrent.futures import ThreadPoolExecutor
    import sqlalchemy as sa

    db_path = tmp_path / "concurrent_test.db"
    test_db_url = f"sqlite:///{db_path.as_posix()}"

    test_engine = sa.create_engine(
        test_db_url,
        connect_args={"check_same_thread": False, "timeout": 30.0}
    )
    with test_engine.connect() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=WAL;"))
        conn.commit()

    TestSession = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Migrate test database to head
    from alembic.config import Config
    from alembic import command
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")

    setup_session = TestSession()
    owner = Owner(name="Concurrent Owner", email=f"conc_{datetime.now().timestamp()}@example.com", currency="USD")
    setup_session.add(owner)
    setup_session.commit()

    client = Client(owner_id=owner.id, name="Conc Client", email="conc_client@example.com", typical_invoice_amount=500.0)
    setup_session.add(client)
    setup_session.commit()

    obligation = Obligation(
        owner_id=owner.id,
        payee_name="Conc Contractor",
        payee_email="contractor@example.com",
        amount=300.0,
        currency="USD",
        due_date=datetime.now(timezone.utc) + timedelta(days=7),
        status="pending"
    )
    setup_session.add(obligation)
    setup_session.commit()

    inv_ref = f"INV-CONC-RACE-{datetime.now().timestamp()}"
    shared_tx = f"TX-CONC-SHARED-{datetime.now().timestamp()}"

    invoice = Invoice(
        client_id=client.id,
        paypal_invoice_id=inv_ref,
        amount=500.0,
        currency="USD",
        issue_date=datetime.now(timezone.utc),
        due_date=datetime.now(timezone.utc) + timedelta(days=5),
        status="SENT"
    )
    setup_session.add(invoice)
    setup_session.commit()
    setup_session.close()

    def worker_process(worker_id):
        worker_db = TestSession()
        try:
            wh_payload = {
                "id": f"WH-WORKER-{worker_id}-{datetime.now().timestamp()}",
                "event_type": "INVOICING.INVOICE.PAID",
                "resource": {
                    "id": inv_ref,
                    "transaction_id": shared_tx,
                    "amount": {"value": "500.00", "currency_code": "USD"}
                }
            }
            return process_webhook_event(worker_db, wh_payload, is_simulated=False)
        finally:
            worker_db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_process, 1)
        f2 = executor.submit(worker_process, 2)
        r1 = f1.result()
        r2 = f2.result()

    statuses = [r1.get("status"), r2.get("status")]
    # One worker must succeed/reconcile, the other must safely return already_processed
    assert "already_processed" in statuses or "success" in statuses

    # Verify exactly one PaymentHistory and FinancialEntry
    verify_session = TestSession()
    try:
        ph_count = verify_session.query(PaymentHistory).filter(PaymentHistory.transaction_reference == shared_tx).count()
        assert ph_count == 1

        fe_count = verify_session.query(FinancialEntry).filter(FinancialEntry.reference_id == shared_tx).count()
        assert fe_count == 1
    finally:
        verify_session.close()


def test_paypal_webhook_payments_as_object_containing_transactions(setup_db):
    """
    Test 4A: PayPal invoice webhook where 'payments' is an object containing
    a 'transactions' array: {"payments": {"transactions": [...]}}
    Extracts individual payment amount and genuine payment reference accurately.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-OBJ-TX-{datetime.now().timestamp()}"
        tx_id = f"PAY-TX-OBJ-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-OBJ-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "1000.00", "currency_code": "USD"},
                "payments": {
                    "transactions": [
                        {
                            "payment_id": tx_id,
                            "type": "PAYPAL",
                            "amount": {"value": "350.00", "currency_code": "USD"},
                            "payment_date": "2026-11-09T10:00:00Z"
                        }
                    ]
                }
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] in ["success", "reconciled", "processed"]
        assert invoice.status == "PARTIALLY_PAID"

        # Payment history must record $350.00, NEVER $1000.00 invoice total
        ph = db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first()
        assert ph is not None
        assert float(ph.amount) == 350.0

        fe = db.query(FinancialEntry).filter(FinancialEntry.reference_id == tx_id).first()
        assert fe is not None
        assert float(fe.amount) == 350.0
    finally:
        db.close()


def test_paypal_webhook_multiple_transactions_with_identifiable_target(setup_db):
    """
    Test 4B: Payload contains multiple transactions, but has an identifiable
    target transaction matching resource.transaction_id.
    Extracts that target's amount ($450.00), not the other transaction, not invoice total.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-MULTI-TARGET-{datetime.now().timestamp()}"
        target_tx = f"PAY-TARGET-{datetime.now().timestamp()}"
        other_tx = f"PAY-OTHER-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-MULTI-TGT-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": target_tx,
                "amount": {"value": "1000.00", "currency_code": "USD"},
                "payments": {
                    "transactions": [
                        {
                            "payment_id": other_tx,
                            "amount": {"value": "100.00", "currency_code": "USD"}
                        },
                        {
                            "payment_id": target_tx,
                            "amount": {"value": "450.00", "currency_code": "USD"}
                        }
                    ]
                }
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] in ["success", "reconciled", "processed"]
        assert invoice.status == "PARTIALLY_PAID"

        ph = db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == target_tx).first()
        assert ph is not None
        assert float(ph.amount) == 450.0
    finally:
        db.close()


def test_paypal_webhook_missing_individual_transaction_amount_with_invoice_total_present(setup_db):
    """
    Test 4C: Target transaction record is missing its amount key entirely, while
    resource.amount (the invoice total: $1000.00) is present.
    Must quarantine with missing_payment_amount and strictly refuse to substitute
    the invoice total for the individual payment.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-MISS-INDIV-AMT-{datetime.now().timestamp()}"
        tx_id = f"PAY-NO-AMT-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-MISS-AMT-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "1000.00", "currency_code": "USD"},
                "payments": [
                    {
                        "payment_id": tx_id
                        # Amount field omitted
                    }
                ]
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] == "quarantined"
        assert res["reason"] == "missing_payment_amount"

        # Assert no PaymentHistory was created using the invoice total
        assert db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first() is None
        assert invoice.status == "SENT"
    finally:
        db.close()


def test_paypal_webhook_incorrect_currency_quarantined(setup_db):
    """
    Test 4D: Payment record specifies EUR when invoice is in USD.
    Must be quarantined with currency_mismatch and no payment applied.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-WRONG-CURR-{datetime.now().timestamp()}"
        tx_id = f"PAY-EUR-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=500.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-EUR-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "payments": [
                    {
                        "payment_id": tx_id,
                        "amount": {"value": "500.00", "currency_code": "EUR"}
                    }
                ]
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] == "quarantined"
        assert res["reason"] == "currency_mismatch"
        assert invoice.status == "SENT"
        assert db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first() is None
    finally:
        db.close()


def test_migration_legacy_schema_non_unique_index_replaced_with_unique(tmp_path):
    """
    Test 4E: Migration safely inspects and replaces a legacy non-unique index with
    a unique index on payment_history(transaction_reference), preserving all financial
    records and historical NULL references.
    """
    import sqlalchemy as sa
    from alembic.config import Config
    from alembic import command

    db_path = tmp_path / "legacy_migration.db"
    test_db_url = f"sqlite:///{db_path.as_posix()}"

    test_engine = sa.create_engine(test_db_url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_db_url)

    # 1. Migrate up to 4d5e6f7a8b9c (before 5e6f7a8b9c0d)
    command.upgrade(cfg, "4d5e6f7a8b9c")

    # 2. Simulate legacy schema: add column and create a NON-UNIQUE index on transaction_reference
    with test_engine.connect() as conn:
        conn.execute(sa.text("ALTER TABLE payment_history ADD COLUMN transaction_reference VARCHAR(255);"))
        conn.execute(sa.text("CREATE INDEX ix_payment_history_transaction_reference ON payment_history (transaction_reference);"))
        
        # Populate client for foreign key
        conn.execute(sa.text("""
            INSERT INTO owners (id, name, email, currency) VALUES (1, 'Legacy Owner', 'legacy@example.com', 'USD');
        """))
        conn.execute(sa.text("""
            INSERT INTO clients (id, owner_id, name, email) VALUES (1, 1, 'Legacy Client', 'client@example.com');
        """))

        # Insert 2 rows with distinct non-null transaction references
        conn.execute(sa.text("""
            INSERT INTO payment_history (client_id, amount, due_date, paid_date, days_late, source, transaction_reference)
            VALUES (1, 100.0, '2026-01-01', '2026-01-02', 1, 'paypal', 'TX-LEGACY-001'),
                   (1, 200.0, '2026-01-01', '2026-01-02', 1, 'paypal', 'TX-LEGACY-002');
        """))

        # Insert 2 rows with NULL references (testing historical NULL preservation)
        conn.execute(sa.text("""
            INSERT INTO payment_history (client_id, amount, due_date, paid_date, days_late, source, transaction_reference)
            VALUES (1, 300.0, '2026-01-01', '2026-01-02', 1, 'paypal', NULL),
                   (1, 400.0, '2026-01-01', '2026-01-02', 1, 'paypal', NULL);
        """))
        conn.commit()

    # Verify that the index is currently non-unique
    insp_before = sa.inspect(test_engine)
    before_indexes = [
        idx for idx in insp_before.get_indexes("payment_history")
        if idx.get("name") == "ix_payment_history_transaction_reference"
    ]
    assert len(before_indexes) == 1
    assert before_indexes[0]["unique"] is False or before_indexes[0]["unique"] == 0

    # 3. Upgrade to head (runs 5e6f7a8b9c0d)
    command.upgrade(cfg, "head")

    # 4. Verify index is now UNIQUE
    insp_after = sa.inspect(test_engine)
    after_indexes = [
        idx for idx in insp_after.get_indexes("payment_history")
        if idx.get("name") == "ix_payment_history_transaction_reference"
    ]
    assert len(after_indexes) == 1
    assert after_indexes[0]["unique"] is True or after_indexes[0]["unique"] == 1

    # 5. Verify all 4 financial records remain intact
    with test_engine.connect() as conn:
        count = conn.execute(sa.text("SELECT COUNT(*) FROM payment_history;")).scalar()
        assert count == 4

        null_count = conn.execute(sa.text("SELECT COUNT(*) FROM payment_history WHERE transaction_reference IS NULL;")).scalar()
        assert null_count == 2


def test_migration_stops_with_error_on_duplicate_transaction_references(tmp_path):
    """
    Test 4F: If legacy database contains duplicate non-null transaction references,
    migration stops with a clear actionable ValueError and preserves all records.
    """
    import sqlalchemy as sa
    from alembic.config import Config
    from alembic import command

    db_path = tmp_path / "dup_migration.db"
    test_db_url = f"sqlite:///{db_path.as_posix()}"

    test_engine = sa.create_engine(test_db_url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_db_url)

    command.upgrade(cfg, "4d5e6f7a8b9c")

    with test_engine.connect() as conn:
        conn.execute(sa.text("ALTER TABLE payment_history ADD COLUMN transaction_reference VARCHAR(255);"))
        conn.execute(sa.text("""
            INSERT INTO owners (id, name, email, currency) VALUES (1, 'Legacy Owner', 'legacy@example.com', 'USD');
        """))
        conn.execute(sa.text("""
            INSERT INTO clients (id, owner_id, name, email) VALUES (1, 1, 'Legacy Client', 'client@example.com');
        """))

        # Insert duplicate non-null transaction references
        conn.execute(sa.text("""
            INSERT INTO payment_history (client_id, amount, due_date, paid_date, days_late, source, transaction_reference)
            VALUES (1, 100.0, '2026-01-01', '2026-01-02', 1, 'paypal', 'TX-DUPLICATE-999'),
                   (1, 200.0, '2026-01-01', '2026-01-02', 1, 'paypal', 'TX-DUPLICATE-999');
        """))
        conn.commit()

    # Attempt upgrade to head - must raise ValueError without modifying data
    with pytest.raises(ValueError) as excinfo:
        command.upgrade(cfg, "head")

    assert "Cannot apply unique index" in str(excinfo.value)
    assert "TX-DUPLICATE-999" in str(excinfo.value)

    # Records must be strictly preserved
    with test_engine.connect() as conn:
        count = conn.execute(sa.text("SELECT COUNT(*) FROM payment_history WHERE transaction_reference = 'TX-DUPLICATE-999';")).scalar()
        assert count == 2


# =========================================================================
# Targeted Regression Tests — Missing Payment Currency
# =========================================================================

def test_paypal_webhook_individual_payment_valid_amount_usd_processed(setup_db):
    """
    Individual payment with valid amount and USD currency against a USD invoice
    must be processed successfully.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-VALID-USD-{datetime.now().timestamp()}"
        tx_id = f"PAY-USD-VALID-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-USD-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "amount": {"value": "1000.00", "currency_code": "USD"},
                "payments": [
                    {
                        "payment_id": tx_id,
                        "amount": {"value": "300.00", "currency_code": "USD"}
                    }
                ]
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] in ["success", "reconciled", "processed"]
        assert invoice.status == "PARTIALLY_PAID"

        ph = db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first()
        assert ph is not None
        assert float(ph.amount) == 300.0
    finally:
        db.close()


def test_paypal_webhook_individual_payment_valid_amount_missing_currency_quarantined(setup_db):
    """
    Individual payment with valid amount but missing currency in the payment record
    must be quarantined for manual review, refusing to infer currency from invoice.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-MISS-CURR-{datetime.now().timestamp()}"
        tx_id = f"PAY-MISS-CURR-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # payment record has amount value but NO currency_code
        webhook_payload = {
            "id": f"WH-NOCURR-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "payments": [
                    {
                        "payment_id": tx_id,
                        "amount": {"value": "300.00"}
                    }
                ]
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] == "quarantined"
        assert res["reason"] == "missing_payment_currency"
        assert invoice.status == "SENT"
        assert db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first() is None
    finally:
        db.close()


# =========================================================================
# Regression Tests — Flat PayPal Payment Currency Validation
# =========================================================================

def test_paypal_webhook_flat_payment_with_explicit_usd_succeeds(setup_db):
    """
    Flat payment with genuine explicit USD currency must succeed.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-FLAT-USD-{datetime.now().timestamp()}"
        tx_id = f"TX-FLAT-USD-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-FLAT-USD-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_id,
                "amount": {"value": "400.00", "currency_code": "USD"}
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] in ["success", "reconciled", "processed"]
        assert invoice.status == "PARTIALLY_PAID"

        ph = db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first()
        assert ph is not None
        assert float(ph.amount) == 400.0
    finally:
        db.close()


def test_paypal_webhook_flat_payment_with_missing_currency_quarantined(setup_db):
    """
    Flat payment with genuine amount but missing currency must be quarantined.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-FLAT-NO-CURR-{datetime.now().timestamp()}"
        tx_id = f"TX-FLAT-NO-CURR-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=1000.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # Flat webhook payload without currency_code
        webhook_payload = {
            "id": f"WH-FLAT-NO-CURR-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_id,
                "amount": {"value": "400.00"}
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] == "quarantined"
        assert res["reason"] == "missing_payment_currency"
        assert invoice.status == "SENT"
        assert db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first() is None
    finally:
        db.close()


def test_paypal_webhook_flat_payment_missing_currency_invoice_has_usd_still_quarantined(setup_db):
    """
    Flat payment with missing currency while invoice.currency is USD must STILL be quarantined.
    Must never silently substitute invoice.currency.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-FLAT-NOSUB-USD-{datetime.now().timestamp()}"
        tx_id = f"TX-FLAT-NOSUB-USD-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=500.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        webhook_payload = {
            "id": f"WH-FLAT-NOSUB-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_id,
                "amount": "250.00"  # Flat amount string without currency
            }
        }

        res = process_webhook_event(db, webhook_payload, is_simulated=False)
        db.refresh(invoice)

        assert res["status"] == "quarantined"
        assert res["reason"] == "missing_payment_currency"
        assert invoice.status == "SENT"
        assert db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first() is None
    finally:
        db.close()


def test_paypal_webhook_flat_payment_numeric_or_malformed_currency_quarantined_no_exception(setup_db):
    """
    Flat payment with numeric or malformed currency must be quarantined
    for manual review cleanly without raising an unhandled AttributeError/exception.
    """
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        client = db.query(Client).filter(Client.owner_id == owner.id).first()
        inv_ref = f"INV-FLAT-MALFORMED-{datetime.now().timestamp()}"
        tx_id = f"TX-FLAT-MALFORMED-{datetime.now().timestamp()}"

        invoice = Invoice(
            client_id=client.id,
            paypal_invoice_id=inv_ref,
            amount=500.0,
            currency="USD",
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=5),
            status="SENT"
        )
        db.add(invoice)
        db.commit()

        # 1. Numeric currency code
        webhook_payload_numeric = {
            "id": f"WH-FLAT-NUM-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_id,
                "amount": {"value": "250.00", "currency_code": 123}
            }
        }

        res_numeric = process_webhook_event(db, webhook_payload_numeric, is_simulated=False)
        assert res_numeric["status"] == "quarantined"
        assert res_numeric["reason"] == "missing_payment_currency"

        # 2. Malformed symbol currency code
        tx_id2 = f"TX-FLAT-SYM-{datetime.now().timestamp()}"
        webhook_payload_symbols = {
            "id": f"WH-FLAT-SYM-{datetime.now().timestamp()}",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": inv_ref,
                "transaction_id": tx_id2,
                "amount": {"value": "250.00", "currency_code": "$$$"}
            }
        }

        res_sym = process_webhook_event(db, webhook_payload_symbols, is_simulated=False)
        assert res_sym["status"] == "quarantined"
        assert res_sym["reason"] == "missing_payment_currency"

        assert invoice.status == "SENT"
        assert db.query(PaymentHistory).filter(PaymentHistory.invoice_id == invoice.id).count() == 0
    finally:
        db.close()







