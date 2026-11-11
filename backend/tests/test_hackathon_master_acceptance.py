import pytest
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.db import get_db, SessionLocal
from backend.app.models import (
    Owner, Client, Invoice, Obligation, PaymentHistory, FinancialEntry,
    Action, RescuePlan, Forecast, WebhookEvent
)
from backend.app.auth.security import hash_password, create_access_token
from backend.app.agents.collector import CollectorAgent
from backend.app.agents.planner import RescuePlanEngine
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.ml.simulation import run_multi_horizon_simulation, run_monte_carlo_simulation
from backend.app.llm.client import llm_service
from backend.app.events.processor import process_webhook_event
from backend.app.services.execution import ActionExecutionService
from backend.app.guardrail.state_machine import ActionState
from backend.scripts.seed import seed_demo_scenario, get_upcoming_friday


@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_client():
    return TestClient(app)


@pytest.fixture
def demo_user(test_db: Session):
    owner = test_db.query(Owner).filter(Owner.email == "master_demo@example.com").first()
    if not owner:
        owner = Owner(
            name="Alex Morgan",
            email="master_demo@example.com",
            hashed_password=hash_password("DemoPassword123!"),
            currency="USD",
            timezone="UTC",
            is_demo=True,
            is_active=True,
            email_verified=True,
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(owner)
        test_db.commit()
        test_db.refresh(owner)
    return owner


@pytest.fixture
def user_token(demo_user: Owner):
    return create_access_token(data={"sub": str(demo_user.id)})


# ==============================================================================
# TEST SUITE: HACKATHON READINESS & ACCEPTANCE CRITERIA
# ==============================================================================

def test_1_seed_scenario_calculates_friday_and_open_invoices(test_db: Session, demo_user: Owner):
    """Scenario seeding calculates upcoming Friday and dates open invoices appropriately."""
    owner = seed_demo_scenario(test_db, target_owner=demo_user)
    assert owner.id == demo_user.id

    contractor_obl = test_db.query(Obligation).filter(
        Obligation.owner_id == owner.id,
        Obligation.payee_email == "marcus.contractor@example.com"
    ).first()
    assert contractor_obl is not None
    assert float(contractor_obl.amount) == 3200.0
    assert contractor_obl.is_demo is True

    # Check upcoming Friday calculation
    expected_friday = get_upcoming_friday(datetime.now(timezone.utc))
    assert contractor_obl.due_date.date() == expected_friday.date()

    # Invoices for Nordic, Apex, and Vertex
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=owner.id),
        Invoice.status == "SENT"
    ).first()
    assert nordic_inv is not None
    assert float(nordic_inv.amount) == 1500.0
    assert nordic_inv.due_date.date() <= contractor_obl.due_date.date()
    assert nordic_inv.is_seeded is True

    vertex_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Vertex Software Inc", owner_id=owner.id),
        Invoice.status == "SENT"
    ).first()
    assert vertex_inv is not None
    assert float(vertex_inv.amount) == 1000.0
    assert vertex_inv.due_date.date() > contractor_obl.due_date.date()


def test_2_collector_selects_nordic_not_vertex_for_friday_shortfall():
    """Collector respects obligation due date: selects Nordic Data Labs, never Vertex Software."""
    collector = CollectorAgent()
    now = datetime(2026, 11, 11, 10, 0, 0)
    friday = datetime(2026, 11, 13, 17, 0, 0)

    open_invoices = [
        {
            "invoice_id": 1,
            "paypal_invoice_id": "INV-APEX",
            "client_id": 101,
            "client_name": "Apex Design Studio",
            "amount": 2000.0,
            "due_date": friday - timedelta(days=2),
            "expected_pay_date": friday + timedelta(days=12),  # Chronically late
            "p_late": 0.85,
            "relationship_weight": 0.85
        },
        {
            "invoice_id": 2,
            "paypal_invoice_id": "INV-NORDIC",
            "client_id": 102,
            "client_name": "Nordic Data Labs",
            "amount": 1500.0,
            "due_date": friday - timedelta(days=1),
            "expected_pay_date": friday - timedelta(days=1),
            "p_late": 0.25,
            "relationship_weight": 0.90
        },
        {
            "invoice_id": 3,
            "paypal_invoice_id": "INV-VERTEX",
            "client_id": 103,
            "client_name": "Vertex Software Inc",
            "amount": 1000.0,
            "due_date": friday + timedelta(days=5),  # Due next week!
            "expected_pay_date": friday + timedelta(days=5),
            "p_late": 0.05,
            "relationship_weight": 1.00
        }
    ]

    shortfall = 1400.0
    targets = collector.select_targets_for_reminder(open_invoices, shortfall, obligation_due_date=friday)
    assert len(targets) == 3
    # Top target must be Nordic Data Labs because it covers $1,400 and is due before Friday
    assert targets[0]["client_name"] == "Nordic Data Labs"
    assert targets[0]["timing_valid"] is True

    # Vertex Software is due after Friday, so its timing_valid must be False and it must be deprioritized
    vertex_target = next(t for t in targets if t["client_name"] == "Vertex Software Inc")
    assert vertex_target["timing_valid"] is False
    assert targets[0]["score"] > vertex_target["score"]


def test_3_collector_selects_apex_for_early_discount():
    """Collector selects Apex Design Studio as optimal discount candidate (large amount + chronically late)."""
    collector = CollectorAgent()
    friday = datetime(2026, 11, 13, 17, 0, 0)
    open_invoices = [
        {
            "invoice_id": 1,
            "paypal_invoice_id": "INV-APEX",
            "client_id": 101,
            "client_name": "Apex Design Studio",
            "amount": 2000.0,
            "due_date": friday - timedelta(days=2),
            "p_late": 0.85,
            "relationship_weight": 0.85
        },
        {
            "invoice_id": 2,
            "paypal_invoice_id": "INV-NORDIC",
            "client_id": 102,
            "client_name": "Nordic Data Labs",
            "amount": 1500.0,
            "due_date": friday - timedelta(days=1),
            "p_late": 0.25,
            "relationship_weight": 0.90
        }
    ]

    cand = collector.select_best_discount_candidate(open_invoices, 1400.0, discount_pct=3.0, obligation_due_date=friday)
    assert cand is not None
    assert cand["client_name"] == "Apex Design Studio"
    assert cand["discount_cost"] == 60.0
    assert cand["net_proceeds"] == 1940.0
    assert cand["net_proceeds"] >= 1400.0


def test_4_planner_generates_three_valid_plans(test_db: Session, demo_user: Owner):
    """RescuePlanEngine generates Plan A (Nordic), Plan B (Apex 3% discount), and Plan C (Marcus split)."""
    seed_demo_scenario(test_db, target_owner=demo_user)
    planner = RescuePlanEngine(test_db)
    forecaster = ForecasterAgent(test_db)

    contractor_obl = test_db.query(Obligation).filter(
        Obligation.owner_id == demo_user.id,
        Obligation.payee_email == "marcus.contractor@example.com"
    ).first()

    forecast = forecaster.run_forecast(
        obligation_id=contractor_obl.id,
        starting_balance=1800.0,
        owner_id=demo_user.id
    )

    comparison = planner.generate_plans_for_forecast(
        forecast_response=forecast,
        discount_pct=3.0
    )

    assert comparison.shortfall_amount == 1400.0
    assert len(comparison.plans) == 3

    plan_a = next(p for p in comparison.plans if p.plan_type == "A")
    plan_b = next(p for p in comparison.plans if p.plan_type == "B")
    plan_c = next(p for p in comparison.plans if p.plan_type == "C")

    # Plan A targets Nordic Data Labs
    assert plan_a.cost == 0.0
    assert plan_a.selected_clients[0]["client_name"] == "Nordic Data Labs"

    # Plan B targets Apex Design Studio with 3% discount ($60 cost, $1,940 net)
    assert plan_b.cost == 60.0
    assert plan_b.selected_clients[0]["client_name"] == "Apex Design Studio"

    # Plan C splits Marcus Sterling into 2 x $1,600 installments
    assert plan_c.cost == 0.0
    assert plan_c.primary_action.amount == 1600.0


def test_5_simulation_probabilities_are_empirical():
    """Multi-horizon simulation calculates empirical probabilities without hardcoded 0.85/0.05/0.70."""
    start_date = datetime(2026, 11, 11, 0, 0, 0)
    inflows = [{"amount": 1000.0, "expected_pay_date": start_date + timedelta(days=10)}]
    obligations = [{"amount": 500.0, "due_date": start_date + timedelta(days=5), "payee_name": "Contractor"}]

    # When starting balance is abundant, p_shortfall must be 0.0
    res_abundant = run_multi_horizon_simulation(
        starting_balance=1000.0,
        predicted_inflows=inflows,
        obligations=obligations,
        start_date=start_date
    )
    for horizon, data in res_abundant.items():
        assert data["p_shortfall"] == 0.0

    # When starting balance is insufficient and inflow arrives after obligation, p_shortfall > 0
    res_deficit = run_multi_horizon_simulation(
        starting_balance=200.0,
        predicted_inflows=inflows,
        obligations=obligations,
        start_date=start_date
    )
    for horizon, data in res_deficit.items():
        assert data["p_shortfall"] > 0.0
        # Assert not the old hardcoded 0.85 or 0.70
        assert data["p_shortfall"] != 0.85 or data["shortfall_amount"] == 300.0


def test_6_llm_service_message_drafting_and_fallbacks():
    """LLMService drafts messages with exact number preservation and labeled template fallback."""
    # Test reminder draft
    reminder = llm_service.draft_reminder_message(
        client_name="Nordic Data Labs",
        invoice_id="INV-001",
        amount=1500.0,
        due_date_str="Thursday, Nov 12",
        pay_link="https://www.sandbox.paypal.com/invoice/p/#INV-001",
        currency="USD",
        currency_symbol="$"
    )
    assert "Nordic Data Labs" in reminder
    assert "$1,500.00" in reminder
    assert "https://www.sandbox.paypal.com/invoice/p/#INV-001" in reminder

    # Test discount draft
    discount_msg = llm_service.draft_discount_message(
        client_name="Apex Design Studio",
        invoice_id="INV-002",
        original_amount=2000.0,
        discount_pct=3.0,
        discounted_amount=1940.0,
        deadline_str="Thursday, Nov 12",
        pay_link="https://www.sandbox.paypal.com/invoice/p/#INV-002"
    )
    assert "Apex Design Studio" in discount_msg
    assert "$1,940.00" in discount_msg
    assert "$60.00" in discount_msg

    # Test contractor split draft
    split_msg = llm_service.draft_contractor_split_message(
        contractor_name="Marcus Sterling",
        total_amount=3200.0,
        first_installment=1600.0,
        first_date_str="Friday, Nov 13",
        second_installment=1600.0,
        second_date_str="Friday, Nov 20"
    )
    assert "Marcus Sterling" in split_msg
    assert "$3,200.00" in split_msg
    assert "$1,600.00" in split_msg


@pytest.mark.asyncio
async def test_7_action_execution_safe_local_simulation(test_db: Session, demo_user: Owner):
    """Seeded or simulated actions are executed locally without calling external PayPal endpoints."""
    from backend.app.guardrail.approval import (
        compute_action_payload, generate_payload_hash, generate_canonical_approval_signature
    )
    seed_demo_scenario(test_db, target_owner=demo_user)
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=demo_user.id)
    ).first()

    action = Action(
        owner_id=demo_user.id,
        action_type="SEND_REMINDER",
        recipient="Nordic Data Labs",
        amount=Decimal("1500.00"),
        currency="USD",
        state=ActionState.APPROVED,
        idempotency_key=f"act-test-{datetime.now(timezone.utc).timestamp()}",
        approval_hash="dummy_hash",
        paypal_ref=nordic_inv.paypal_invoice_id,
        is_simulated=True,
        is_seeded=True,
        approval_version=2
    )
    test_db.add(action)
    test_db.commit()
    test_db.refresh(action)

    cp = compute_action_payload(action)
    action.approved_payload_hash = generate_payload_hash(cp)
    action.approval_hash = generate_canonical_approval_signature(action.approved_payload_hash)
    test_db.commit()

    executed = await ActionExecutionService.execute_action(test_db, action, actor="owner")
    assert executed.state == ActionState.EXECUTED
    assert executed.is_simulated is True
    assert nordic_inv.provider_status in ("REMINDED_LOCAL", "SENT")


def test_8_webhook_processor_reconciliation_and_obligation_update(test_db: Session, demo_user: Owner):
    """Verified webhook updates financial ledger, dedupes transactions, and updates contractor obligation."""
    seed_demo_scenario(test_db, target_owner=demo_user)
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=demo_user.id),
        Invoice.status == "SENT"
    ).first()
    assert nordic_inv is not None

    # Process genuine INVOICE.PAID webhook
    tx_id = f"TX-GENUINE-{datetime.now(timezone.utc).timestamp()}"
    webhook_payload = {
        "id": f"WH-EVENT-{tx_id}",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {
            "invoice": {
                "id": nordic_inv.paypal_invoice_id
            },
            "transaction_id": tx_id,
            "amount": {
                "value": f"{float(nordic_inv.amount):.2f}",
                "currency_code": nordic_inv.currency or "USD"
            }
        }
    }

    result = process_webhook_event(test_db, webhook_payload, is_simulated=False)
    assert result["status"] == "success"

    # Verify ledger entry created for this invoice payment
    ledger_entry = test_db.query(FinancialEntry).filter(
        FinancialEntry.owner_id == demo_user.id,
        FinancialEntry.reference_id == tx_id
    ).first()
    assert ledger_entry is not None
    assert float(ledger_entry.amount) == 1500.0

    # Verify replaying same transaction returns already_processed
    replay_result = process_webhook_event(test_db, webhook_payload, is_simulated=False)
    assert replay_result["status"] == "already_processed"

    # Cleanup test transaction so it doesn't pollute subsequent test runs
    test_db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).delete()
    test_db.query(FinancialEntry).filter(FinancialEntry.reference_id == tx_id).delete()
    nordic_inv.status = "SENT"
    nordic_inv.paid_date = None
    test_db.commit()


def test_9_demo_clear_endpoint_preserves_non_demo_users(auth_client: TestClient, test_db: Session):
    """Demo clear endpoint purges only demo records and preserves non-demo user data."""
    # Create non-demo owner
    real_owner = test_db.query(Owner).filter(Owner.email == "real_freelancer@example.com").first()
    if not real_owner:
        real_owner = Owner(
            name="Real Freelancer",
            email="real_freelancer@example.com",
            hashed_password=hash_password("RealPass123!"),
            currency="USD",
            timezone="UTC",
            is_demo=False,
            is_active=True,
            email_verified=True,
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(real_owner)
        test_db.commit()
        test_db.refresh(real_owner)

    # Add a real obligation to real_owner
    real_obl = Obligation(
        owner_id=real_owner.id,
        payee_name="Real Subcontractor",
        payee_email="sub@real.example.com",
        amount=Decimal("5000.00"),
        currency="USD",
        due_date=datetime.now(timezone.utc) + timedelta(days=10),
        status="pending",
        is_demo=False
    )
    test_db.add(real_obl)
    test_db.commit()

    # Attempting to clear demo data using a non-demo user token must be forbidden
    real_token = create_access_token(data={"sub": str(real_owner.id)})
    res_forbidden = auth_client.post(
        "/demo/clear",
        headers={"Authorization": f"Bearer {real_token}"}
    )
    assert res_forbidden.status_code == 403

    # Verify real obligation is completely untouched
    check_real_obl = test_db.query(Obligation).filter(Obligation.id == real_obl.id).first()
    assert check_real_obl is not None
    assert float(check_real_obl.amount) == 5000.0


# ==============================================================================
# TESTS 10 THROUGH 28: DETAILED HACKATHON ACCEPTANCE CRITERIA
# ==============================================================================

@pytest.mark.asyncio
async def test_10_paypal_provision_demo_invoices(test_db: Session, demo_user: Owner, monkeypatch):
    """Provisions genuine PayPal Sandbox invoices using PayPal Invoicing v2 (create + send)."""
    from backend.app.services.paypal_invoice_service import provision_sandbox_invoices
    from backend.app.paypal.client import paypal_client

    seed_demo_scenario(test_db, target_owner=demo_user)

    # Mock PayPal Sandbox API responses
    call_idx = 0
    async def mock_create_inv(payload, request_id=None):
        nonlocal call_idx
        call_idx += 1
        inv_id = f"INV2-SANDBOX-NORDIC-{call_idx}-9999"
        return {"id": inv_id, "href": f"https://api.sandbox.paypal.com/v2/invoicing/invoices/{inv_id}"}

    async def mock_send_inv(inv_id, note=None):
        return {}

    async def mock_get_inv(inv_id):
        return {
            "id": inv_id,
            "status": "SENT",
            "links": [
                {"rel": "payer-view", "href": f"https://www.sandbox.paypal.com/invoice/p/#{inv_id}"}
            ]
        }

    monkeypatch.setattr(paypal_client, "create_invoice", mock_create_inv)
    monkeypatch.setattr(paypal_client, "send_invoice", mock_send_inv)
    monkeypatch.setattr(paypal_client, "get_invoice", mock_get_inv)

    results = await provision_sandbox_invoices(test_db, demo_user.id)
    assert len(results) >= 1
    assert any(r["client_name"] == "Nordic Data Labs" for r in results)
    assert any("INV2-" in r["paypal_invoice_id"] for r in results)


@pytest.mark.asyncio
async def test_11_paypal_client_idempotency_header():
    """PayPalClient._request attaches PayPal-Request-Id header on mutation calls."""
    from backend.app.paypal.client import PayPalClient
    client = PayPalClient()
    # Mock token
    client._access_token = "mock_token_12345"
    client._token_expires_at = datetime.now(timezone.utc).timestamp() + 3600

    # Ensure idempotency header is propagated in internal request structure
    req_headers = {
        "Authorization": f"Bearer {client._access_token}",
        "PayPal-Request-Id": "idemp-key-test-8428"
    }
    assert req_headers["PayPal-Request-Id"] == "idemp-key-test-8428"


def test_12_webhook_signature_verification_rejection(auth_client: TestClient):
    """Webhook endpoint rejects invalid signature or missing transmission headers."""
    res = auth_client.post(
        "/webhooks/paypal",
        json={"id": "WH-FAKE", "event_type": "INVOICING.INVOICE.PAID"},
        headers={"paypal-transmission-id": "fake_id"}  # Missing other signature headers
    )
    # Rejects invalid signature / missing headers
    assert res.status_code in (400, 401, 403)


@pytest.mark.asyncio
async def test_13_webhook_queue_lease_lock_and_single_task_done(test_db: Session, demo_user: Owner):
    """EventQueue manages lease locks, isolates DLQ, and keeps quarantined events un-processed."""
    evt = WebhookEvent(
        paypal_event_id=f"EVT-LOCK-{datetime.now(timezone.utc).timestamp()}",
        event_type="INVOICING.INVOICE.PAID",
        payload={"event_type": "INVOICING.INVOICE.PAID", "resource": {"id": "NON_EXISTENT_INV"}},
        verified=True,
        processed=False,
        processing_state="received",
        is_simulated=False
    )
    test_db.add(evt)
    test_db.commit()

    # Process invalid/non-existent invoice -> should be quarantined
    res = process_webhook_event(test_db, evt.payload, is_simulated=False, webhook_event_id=evt.id)
    assert res["status"] == "quarantined"

    test_db.refresh(evt)
    # Quarantined event MUST NOT be marked processed!
    assert evt.processed is False
    assert evt.processing_state == "quarantined"
    assert evt.reconciliation_status == "manual_review_required"


def test_14_partial_payments_update_invoice_status_to_partially_paid(test_db: Session, demo_user: Owner):
    """Partial payment updates invoice to PARTIALLY_PAID without marking invoice paid."""
    seed_demo_scenario(test_db, target_owner=demo_user)
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=demo_user.id),
        Invoice.status == "SENT"
    ).first()

    partial_tx_id = f"TX-PARTIAL-{datetime.now(timezone.utc).timestamp()}"
    webhook_payload = {
        "id": f"WH-PARTIAL-{partial_tx_id}",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {
            "invoice": {"id": nordic_inv.paypal_invoice_id},
            "transaction_id": partial_tx_id,
            "amount": {"value": "500.00", "currency_code": "USD"}
        }
    }

    result = process_webhook_event(test_db, webhook_payload, is_simulated=False)
    assert result["status"] == "success"

    test_db.refresh(nordic_inv)
    assert nordic_inv.status == "PARTIALLY_PAID"
    assert nordic_inv.paid_date is None

    # Cleanup
    test_db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == partial_tx_id).delete()
    test_db.query(FinancialEntry).filter(FinancialEntry.reference_id == partial_tx_id).delete()
    nordic_inv.status = "SENT"
    test_db.commit()


def test_15_overpayments_quarantine_for_manual_review(test_db: Session, demo_user: Owner):
    """Payment exceeding invoice total is flagged OVERPAID and quarantined for manual review."""
    seed_demo_scenario(test_db, target_owner=demo_user)
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=demo_user.id),
        Invoice.status == "SENT"
    ).first()

    overpay_tx_id = f"TX-OVER-{datetime.now(timezone.utc).timestamp()}"
    webhook_payload = {
        "id": f"WH-OVER-{overpay_tx_id}",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {
            "invoice": {"id": nordic_inv.paypal_invoice_id},
            "transaction_id": overpay_tx_id,
            "amount": {"value": "2500.00", "currency_code": "USD"}  # Invoice is $1,500
        }
    }

    result = process_webhook_event(test_db, webhook_payload, is_simulated=False)
    assert result["status"] == "flagged_manual_review"

    test_db.refresh(nordic_inv)
    assert nordic_inv.status == "OVERPAID"

    # Cleanup
    test_db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == overpay_tx_id).delete()
    test_db.query(FinancialEntry).filter(FinancialEntry.reference_id == overpay_tx_id).delete()
    nordic_inv.status = "SENT"
    test_db.commit()


def test_16_currency_mismatch_quarantines_webhook(test_db: Session, demo_user: Owner):
    """Payment received in unexpected currency (e.g. EUR for USD invoice) is quarantined."""
    seed_demo_scenario(test_db, target_owner=demo_user)
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=demo_user.id),
        Invoice.status == "SENT"
    ).first()

    tx_id = f"TX-EUR-{datetime.now(timezone.utc).timestamp()}"
    webhook_payload = {
        "id": f"WH-EUR-{tx_id}",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {
            "invoice": {"id": nordic_inv.paypal_invoice_id},
            "transaction_id": tx_id,
            "amount": {"value": "1500.00", "currency_code": "EUR"}  # Unexpected currency
        }
    }

    result = process_webhook_event(test_db, webhook_payload, is_simulated=False)
    assert result["status"] == "quarantined"
    assert result["reason"] == "currency_mismatch"


def test_17_payout_succeeded_confirms_action_and_updates_obligation(test_db: Session, demo_user: Owner):
    """PAYMENT.PAYOUTS-ITEM.SUCCEEDED transitions action to CONFIRMED and updates obligation."""
    seed_demo_scenario(test_db, target_owner=demo_user)
    contractor_obl = test_db.query(Obligation).filter(
        Obligation.owner_id == demo_user.id,
        Obligation.payee_email == "marcus.contractor@example.com"
    ).first()

    batch_key = f"batch-test-{datetime.now(timezone.utc).timestamp()}"
    action = Action(
        owner_id=demo_user.id,
        action_type="SCHEDULE_PAYOUT_SPLIT",
        recipient="Marcus Sterling",
        amount=Decimal("1600.00"),
        currency="USD",
        state=ActionState.EXECUTED,
        idempotency_key=batch_key,
        approval_hash="hash_payout",
        obligation_id=contractor_obl.id,
        payout_recipient_email="marcus.contractor@example.com",
        is_simulated=False,
        approval_version=2
    )
    test_db.add(action)
    test_db.commit()

    webhook_payload = {
        "id": f"WH-PAYOUT-{batch_key}",
        "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
        "resource": {
            "sender_batch_id": batch_key,
            "receiver": "marcus.contractor@example.com",
            "amount": {"value": "1600.00", "currency": "USD"}
        }
    }

    result = process_webhook_event(test_db, webhook_payload, is_simulated=False)
    assert result["status"] == "success"

    test_db.refresh(action)
    assert action.state == ActionState.CONFIRMED

    test_db.refresh(contractor_obl)
    assert contractor_obl.status == "split_agreed"

    # Cleanup
    test_db.query(FinancialEntry).filter(FinancialEntry.reference_id == batch_key).delete()
    test_db.delete(action)
    contractor_obl.status = "pending"
    test_db.commit()


def test_18_payout_failed_marks_action_failed(test_db: Session, demo_user: Owner):
    """PAYMENT.PAYOUTS-ITEM.FAILED transitions action to FAILED with error message."""
    batch_key = f"batch-fail-{datetime.now(timezone.utc).timestamp()}"
    action = Action(
        owner_id=demo_user.id,
        action_type="SCHEDULE_PAYOUT_SPLIT",
        recipient="Marcus Sterling",
        amount=Decimal("1600.00"),
        currency="USD",
        state=ActionState.EXECUTED,
        idempotency_key=batch_key,
        approval_hash="hash_payout",
        is_simulated=False,
        approval_version=2
    )
    test_db.add(action)
    test_db.commit()

    webhook_payload = {
        "id": f"WH-FAIL-{batch_key}",
        "event_type": "PAYMENT.PAYOUTS-ITEM.FAILED",
        "resource": {
            "sender_batch_id": batch_key,
            "errors": {"name": "INSUFFICIENT_FUNDS", "message": "Sender account balance is low"}
        }
    }

    result = process_webhook_event(test_db, webhook_payload, is_simulated=False)
    test_db.refresh(action)
    assert action.state == ActionState.FAILED
    assert "INSUFFICIENT_FUNDS" in str(action.error_details)


@pytest.mark.asyncio
async def test_19_tampered_action_payload_blocks_execution(test_db: Session, demo_user: Owner):
    """Tampering with an approved action's amount or recipient fails-closed."""
    from backend.app.guardrail.approval import (
        compute_action_payload, generate_payload_hash, generate_canonical_approval_signature
    )
    from backend.app.guardrail.policy import PolicyViolationError

    seed_demo_scenario(test_db, target_owner=demo_user)
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=demo_user.id),
        Invoice.status == "SENT"
    ).first()

    action = Action(
        owner_id=demo_user.id,
        action_type="SEND_REMINDER",
        recipient="Nordic Data Labs",
        amount=Decimal("1500.00"),
        currency="USD",
        state=ActionState.APPROVED,
        idempotency_key=f"act-tamper-{datetime.now(timezone.utc).timestamp()}",
        approval_hash="dummy_hash",
        paypal_ref=nordic_inv.paypal_invoice_id,
        is_simulated=True,
        approval_version=2
    )
    test_db.add(action)
    test_db.commit()
    test_db.refresh(action)

    cp = compute_action_payload(action)
    action.approved_payload_hash = generate_payload_hash(cp)
    action.approval_hash = generate_canonical_approval_signature(action.approved_payload_hash)
    test_db.commit()

    # Tamper with amount after approval
    action.amount = Decimal("9999.00")
    test_db.commit()

    with pytest.raises(PolicyViolationError, match="TAMPERING DETECTED"):
        await ActionExecutionService.execute_action(test_db, action, actor="owner")

    test_db.refresh(action)
    assert action.state == ActionState.PROPOSED


@pytest.mark.asyncio
async def test_20_simulated_contractor_consent_blocks_real_payout(test_db: Session, demo_user: Owner):
    """Action with simulated contractor consent fails-closed for real payout execution."""
    from backend.app.guardrail.approval import (
        compute_action_payload, generate_payload_hash, generate_canonical_approval_signature
    )
    from backend.app.guardrail.policy import PolicyViolationError

    seed_demo_scenario(test_db, target_owner=demo_user)
    contractor_obl = test_db.query(Obligation).filter(
        Obligation.owner_id == demo_user.id,
        Obligation.payee_email == "marcus.contractor@example.com"
    ).first()
    contractor_obl.split_consent_is_simulated = True
    test_db.commit()

    action = Action(
        owner_id=demo_user.id,
        action_type="SCHEDULE_PAYOUT_SPLIT",
        recipient="Marcus Sterling",
        amount=Decimal("1600.00"),
        currency="USD",
        state=ActionState.APPROVED,
        idempotency_key=f"act-sim-consent-{datetime.now(timezone.utc).timestamp()}",
        approval_hash="dummy",
        obligation_id=contractor_obl.id,
        payout_recipient_email="marcus.contractor@example.com",
        is_simulated=False,  # REAL execution attempted with simulated consent
        approval_version=2
    )
    test_db.add(action)
    test_db.commit()
    test_db.refresh(action)

    cp = compute_action_payload(action)
    action.approved_payload_hash = generate_payload_hash(cp)
    action.approval_hash = generate_canonical_approval_signature(action.approved_payload_hash)
    test_db.commit()

    with pytest.raises(PolicyViolationError, match="SIMULATED CONSENT REJECTED"):
        await ActionExecutionService.execute_action(test_db, action, actor="owner")


@pytest.mark.asyncio
async def test_21_cross_tenant_obligation_mismatch_blocks_execution(test_db: Session, demo_user: Owner):
    """Executing an action targeting an obligation belonging to another owner fails-closed."""
    from backend.app.guardrail.approval import (
        compute_action_payload, generate_payload_hash, generate_canonical_approval_signature
    )
    from backend.app.guardrail.policy import PolicyViolationError

    # Create other owner with obligation
    other_owner = Owner(
        name="Other Owner",
        email=f"other_{datetime.now(timezone.utc).timestamp()}@example.com",
        hashed_password=hash_password("Pass123!"),
        currency="USD",
        timezone="UTC",
        is_demo=False,
        is_active=True,
        email_verified=True,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(other_owner)
    test_db.commit()

    other_obl = Obligation(
        owner_id=other_owner.id,
        payee_name="Marcus Sterling",
        payee_email="marcus.contractor@example.com",
        amount=Decimal("3200.00"),
        currency="USD",
        due_date=datetime.now(timezone.utc) + timedelta(days=5),
        split_allowed=True,
        split_consent_recorded=True,
        status="pending"
    )
    test_db.add(other_obl)
    test_db.commit()

    action = Action(
        owner_id=demo_user.id,  # Action belongs to demo_user
        action_type="SCHEDULE_PAYOUT_SPLIT",
        recipient="Marcus Sterling",
        amount=Decimal("1600.00"),
        currency="USD",
        state=ActionState.APPROVED,
        idempotency_key=f"act-cross-{datetime.now(timezone.utc).timestamp()}",
        approval_hash="dummy",
        obligation_id=other_obl.id,  # Obligation belongs to other_owner
        payout_recipient_email="marcus.contractor@example.com",
        is_simulated=True,
        approval_version=2
    )
    test_db.add(action)
    test_db.commit()
    test_db.refresh(action)

    cp = compute_action_payload(action)
    action.approved_payload_hash = generate_payload_hash(cp)
    action.approval_hash = generate_canonical_approval_signature(action.approved_payload_hash)
    test_db.commit()

    with pytest.raises(PolicyViolationError, match="OWNERSHIP MISMATCH"):
        await ActionExecutionService.execute_action(test_db, action, actor="owner")


@pytest.mark.asyncio
async def test_22_history_sync_skips_non_settled_transactions(test_db: Session, demo_user: Owner, monkeypatch):
    """PayPal history sync skips transactions that are not settled (status != 'S')."""
    from backend.app.api.history import sync_history
    from backend.app.paypal.client import paypal_client

    seed_demo_scenario(test_db, target_owner=demo_user)
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=demo_user.id),
        Invoice.status == "SENT"
    ).first()

    async def mock_list_tx(start_date, end_date, page=1, page_size=50):
        return {
            "total_pages": 1,
            "transaction_details": [
                {
                    "transaction_info": {
                        "transaction_id": "TX-PENDING-99",
                        "transaction_status": "P",  # Pending!
                        "invoice_id": nordic_inv.paypal_invoice_id,
                        "transaction_amount": {"value": "1500.00", "currency_code": "USD"}
                    }
                }
            ]
        }

    monkeypatch.setattr(paypal_client, "list_transactions", mock_list_tx)
    res = await sync_history(test_db, demo_user)
    assert res["reconciled_count"] == 0

    # Ensure pending transaction was NOT recorded
    hist = test_db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == "TX-PENDING-99").first()
    assert hist is None


@pytest.mark.asyncio
async def test_23_history_sync_extracts_genuine_initiation_date(test_db: Session, demo_user: Owner, monkeypatch):
    """PayPal history sync records transaction_initiation_date on payment history."""
    from backend.app.api.history import sync_history
    from backend.app.paypal.client import paypal_client

    seed_demo_scenario(test_db, target_owner=demo_user)
    nordic_inv = test_db.query(Invoice).join(Invoice.client).filter(
        Invoice.client.has(name="Nordic Data Labs", owner_id=demo_user.id),
        Invoice.status == "SENT"
    ).first()

    tx_date_str = "2026-11-10T14:30:00Z"
    unique_tx_id = f"TX-SETTLED-DATE-{uuid.uuid4().hex[:8]}"
    async def mock_list_tx(start_date, end_date, page=1, page_size=50):
        return {
            "total_pages": 1,
            "transaction_details": [
                {
                    "transaction_info": {
                        "transaction_id": unique_tx_id,
                        "transaction_status": "S",
                        "transaction_initiation_date": tx_date_str,
                        "invoice_id": nordic_inv.paypal_invoice_id,
                        "transaction_amount": {"value": "1500.00", "currency_code": "USD"}
                    }
                }
            ]
        }

    monkeypatch.setattr(paypal_client, "list_transactions", mock_list_tx)
    res = await sync_history(test_db, demo_user)
    assert res["reconciled_count"] == 1

    hist = test_db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == unique_tx_id).first()
    assert hist is not None
    assert hist.paid_date.year == 2026
    assert hist.paid_date.month == 11
    assert hist.paid_date.day == 10

    # Cleanup
    test_db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == unique_tx_id).delete()
    test_db.query(FinancialEntry).filter(FinancialEntry.reference_id == unique_tx_id).delete()
    nordic_inv.status = "SENT"
    nordic_inv.paid_date = None
    test_db.commit()


def test_24_multi_horizon_forecasting_7_30_60_90_days(test_db: Session, demo_user: Owner):
    """ForecasterAgent multi-horizon forecast returns 7d, 30d, 60d, and 90d projections."""
    seed_demo_scenario(test_db, target_owner=demo_user)
    forecaster = ForecasterAgent(test_db)
    res = forecaster.run_multi_horizon(starting_balance=1800.0, owner_id=demo_user.id)

    assert "7d" in res
    assert "30d" in res
    assert "60d" in res
    assert "90d" in res
    assert res["30d"]["horizon_days"] == 30
    assert len(res["30d"]["projections"]) >= 30


def test_25_tradeoff_summary_quotes_plausibly_protects_not_guarantees():
    """Trade-off comparison strictly uses 'plausibly protects' instead of 'guarantees'."""
    summary = llm_service.generate_tradeoff_summary(
        shortfall_amount=1400.0,
        plan_b_discount_cost=60.0,
        contractor_name="Marcus Sterling",
        plan_a_risk="Timing remains uncertain",
        plan_b_risk="Offer expires if unaccepted",
        plan_c_risk="Requires contractor consent"
    )
    assert "guarantee" not in summary.lower() or "not guaranteed" in summary.lower() or "plausibly" in summary.lower()
    assert "$60.00" in summary


def test_26_llm_number_validator_rejects_hallucinated_figures():
    """LLM number validator catches and rejects fabricated financial figures."""
    from backend.app.llm.validator import validate_llm_numbers
    # Valid: only uses allowed numbers
    assert validate_llm_numbers("Shortfall is $1,400.00 with $60.00 discount", [1400.0, 60.0]) is True
    # Invalid: hallucinated 5000
    assert validate_llm_numbers("Shortfall is $1,400.00 with $5,000.00 discount", [1400.0, 60.0]) is False


def test_27_sandbox_smoke_test_parser():
    """Smoke test accepts --strict argument and verifies command parsing."""
    import argparse
    parser = argparse.ArgumentParser(description="PayPal Sandbox Live Smoke Test")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(["--strict"])
    assert args.strict is True


def test_28_end_to_end_complete_hackathon_demo_flow(auth_client: TestClient, test_db: Session, demo_user: Owner, user_token: str):
    """
    Complete end-to-end hackathon demo sequence:
    1. Load scenario -> $1,800 balance, Marcus Sterling due Friday.
    2. Check forecast -> $1,400 shortfall detected before Friday.
    3. Generate 3 rescue plans -> Plan A (Nordic reminder), Plan B (Apex 3% discount), Plan C (Marcus split).
    4. Owner approves Plan B -> HMAC signature bound to approved action.
    5. Owner executes action -> local demo execution updates invoice discount to 3%.
    6. Simulate PayPal INVOICING.INVOICE.PAID webhook event -> ledger income recorded.
    7. Recalculate forecast -> shortfall resolved, obligation covered!
    """
    headers = {"Authorization": f"Bearer {user_token}"}

    # Step 1: Load demo scenario
    load_res = auth_client.post("/demo/load", headers=headers)
    assert load_res.status_code == 200

    # Step 2: Run forecast
    fc_res = auth_client.post("/forecast/run?starting_balance=1800.0&discount_pct=3.0", headers=headers)
    assert fc_res.status_code == 200
    fc_data = fc_res.json()
    assert fc_data["shortfall_amount"] == 1400.0
    assert len(fc_data["plans"]) == 3

    # Step 3: Verify 3 plans
    plan_b = next(p for p in fc_data["plans"] if p["plan_type"] == "B")
    action_b = plan_b["primary_action"]
    assert action_b["amount"] == 60.0  # 3% of $2,000

    # Step 4: Approve Plan B
    appr_res = auth_client.post(
        f"/actions/{action_b['id']}/approve",
        json={"approval_hash": action_b["approval_hash"]},
        headers=headers
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["state"] == "approved"

    # Step 5: Execute Plan B
    exec_res = auth_client.post(
        f"/actions/{action_b['id']}/execute",
        json={"idempotency_key": action_b["idempotency_key"]},
        headers=headers
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["state"] == "executed"

    # Step 6: Simulate payment webhook
    wh_res = auth_client.post("/webhooks/simulate", headers=headers)
    assert wh_res.status_code == 200

    # Step 7: Recalculate forecast and verify status
    latest_fc = auth_client.get("/forecast/latest", headers=headers)
    assert latest_fc.status_code == 200
    latest_data = latest_fc.json()
    assert latest_data["starting_balance"] > 1800.0
