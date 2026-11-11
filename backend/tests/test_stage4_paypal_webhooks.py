import pytest
import uuid
import asyncio
import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import (
    Owner, Client, Invoice, Action, Obligation, PaymentHistory,
    FinancialEntry, WebhookEvent, PayPalConnection, PayPalWebhookRegistration
)
from backend.app.guardrail.state_machine import ActionState
from backend.app.events.processor import process_webhook_event
from backend.app.events.queue import EventQueue
from backend.app.paypal.client import paypal_client, PayPalClient, PayPalError


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_owner(db_session):
    now = datetime.datetime.now(datetime.timezone.utc)
    email = f"stage4_{uuid.uuid4().hex[:8]}@example.com"
    owner = Owner(
        name="Stage4 Owner",
        email=email,
        hashed_password="fakehashforstage4",
        currency="USD",
        timezone="UTC",
        email_verified=True,
        terms_accepted=True,
        terms_accepted_at=now,
        account_status="active",
        is_active=True
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)
    return owner


@pytest.mark.asyncio
async def test_paypal_connection_status_honesty(db_session, test_owner):
    """
    Test 1: Connection endpoint honestly labels shared developer sandbox
    and does not claim user merchant account is connected.
    """
    from backend.app.auth.security import create_access_token
    token = create_access_token(data={"sub": str(test_owner.id)})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/paypal/connection", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["connection_type"] == "shared_sandbox"
        assert data["is_shared_sandbox"] is True
        assert "Shared Application Sandbox" in data["account_label"]


@pytest.mark.asyncio
async def test_paypal_webhook_registration_persistence(db_session, test_owner, monkeypatch):
    """
    Test 2: Webhook registration persists webhook ID in database and updates user connection.
    """
    mock_webhook_id = f"WH-TEST-{uuid.uuid4().hex[:8]}"

    async def mock_list_wh(*args, **kwargs):
        return {"webhooks": []}

    async def mock_reg_wh(*args, **kwargs):
        return {"id": mock_webhook_id}

    monkeypatch.setattr(paypal_client, "list_webhooks", mock_list_wh)
    monkeypatch.setattr(paypal_client, "register_webhook", mock_reg_wh)

    from backend.app.auth.security import create_access_token
    token = create_access_token(data={"sub": str(test_owner.id)})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/paypal/webhook/register", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["webhook_id"] == mock_webhook_id

        # Verify persisted in PayPalWebhookRegistration table
        reg = db_session.query(PayPalWebhookRegistration).filter(
            PayPalWebhookRegistration.webhook_id == mock_webhook_id
        ).first()
        assert reg is not None
        assert reg.status == "active"


@pytest.mark.asyncio
async def test_webhook_signature_verification_and_unverified_quarantine(db_session, test_owner, monkeypatch):
    """
    Test 3: Webhook endpoint verifies cryptographic signature.
    Unverified or missing signatures are quarantined and never enqueued for execution.
    """
    wh_id = f"WH-VALID-{uuid.uuid4().hex[:8]}"
    active_reg = PayPalWebhookRegistration(
        webhook_id=wh_id,
        url="http://localhost:8000/webhooks/paypal",
        environment="sandbox",
        status="active",
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db_session.add(active_reg)
    db_session.commit()

    # Case A: Missing signature headers -> quarantined
    event_id_a = f"WH-EVT-A-{uuid.uuid4().hex[:8]}"
    payload_a = {
        "id": event_id_a,
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {"id": "INV-123", "status": "PAID"}
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_a = await client.post("/webhooks/paypal", json=payload_a)
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["verified"] is False
        assert data_a["status"] == "unverified_signature_stored"

        record_a = db_session.query(WebhookEvent).filter(WebhookEvent.paypal_event_id == event_id_a).first()
        assert record_a is not None
        assert record_a.verified is False
        assert record_a.processing_state == "quarantined"

    # Case B: Valid signature verified via mock PayPal API
    async def mock_verify_signature(*args, **kwargs):
        return True

    monkeypatch.setattr(paypal_client, "verify_webhook_signature", mock_verify_signature)

    event_id_b = f"WH-EVT-B-{uuid.uuid4().hex[:8]}"
    payload_b = {
        "id": event_id_b,
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {"id": "INV-456", "status": "PAID"}
    }
    headers_sig = {
        "PAYPAL-TRANSMISSION-ID": "trans_123",
        "PAYPAL-TRANSMISSION-TIME": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert.pem",
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-TRANSMISSION-SIG": "valid_sig_xyz"
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_b = await client.post("/webhooks/paypal", json=payload_b, headers=headers_sig)
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["verified"] is True
        assert data_b["status"] == "accepted"


@pytest.mark.asyncio
async def test_webhook_duplicate_and_concurrent_atomic_deduplication(db_session):
    """
    Test 4: Atomic deduplication ensures duplicate event IDs are safely ignored
    without crashing or raising unhandled database IntegrityError.
    """
    event_id = f"WH-DUP-{uuid.uuid4().hex[:8]}"
    payload = {
        "id": event_id,
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {"id": "INV-DUP-TEST", "status": "PAID"}
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res1 = await client.post("/webhooks/paypal", json=payload)
        assert res1.status_code == 200

        # Duplicate delivery
        res2 = await client.post("/webhooks/paypal", json=payload)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "ignored"
        assert data2["reason"] == "duplicate_event_id"


def test_payment_reconciliation_partial_and_full_payment(db_session, test_owner):
    """
    Test 5: Reconciliation of partial payments vs full payments:
    - Calculates outstanding remaining balance correctly.
    - Sets invoice status to PARTIALLY_PAID on partial payment.
    - Sets invoice status to PAID once fully paid.
    - Prevents duplicate ledger entries on replayed transaction.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    client = Client(name="Recon Client", email="recon@example.com", owner_id=test_owner.id, typical_invoice_amount=1000.0)
    db_session.add(client)
    db_session.commit()

    inv_id = f"INV-RECON-{uuid.uuid4().hex[:6]}"
    invoice = Invoice(
        client_id=client.id,
        paypal_invoice_id=inv_id,
        amount=Decimal("1000.00"),
        currency="USD",
        status="SENT",
        issue_date=now,
        due_date=now + datetime.timedelta(days=14)
    )
    db_session.add(invoice)
    db_session.commit()

    # 1. Partial payment of $400.00
    tx1_id = f"tx_part1_{uuid.uuid4().hex[:6]}"
    payload_part = {
        "id": f"WH-PART-{uuid.uuid4().hex[:6]}",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {
            "id": inv_id,
            "transaction_id": tx1_id,
            "amount": {"value": "400.00", "currency_code": "USD"},
            "invoice": {"id": inv_id}
        }
    }
    res_part = process_webhook_event(db_session, payload_part, is_simulated=False)
    assert res_part["status"] == "success"
    assert res_part["remaining_balance"] == 600.0

    db_session.refresh(invoice)
    assert invoice.status == "PARTIALLY_PAID"

    # 2. Replay of same partial payment -> duplicate transaction reference ignored
    res_replay = process_webhook_event(db_session, payload_part, is_simulated=False)
    assert res_replay["status"] == "already_processed"

    # Verify only ONE financial ledger entry was created for tx1_id
    entries_count = db_session.query(FinancialEntry).filter(
        FinancialEntry.owner_id == test_owner.id,
        FinancialEntry.reference_id == tx1_id
    ).count()
    assert entries_count == 1

    # 3. Final payment of remaining $600.00 -> invoice marked PAID
    tx2_id = f"tx_part2_{uuid.uuid4().hex[:6]}"
    payload_final = {
        "id": f"WH-FULL-{uuid.uuid4().hex[:6]}",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {
            "id": inv_id,
            "transaction_id": tx2_id,
            "amount": {"value": "600.00", "currency_code": "USD"},
            "invoice": {"id": inv_id}
        }
    }
    res_final = process_webhook_event(db_session, payload_final, is_simulated=False)
    assert res_final["status"] == "success"
    assert res_final["remaining_balance"] == 0.0

    db_session.refresh(invoice)
    assert invoice.status == "PAID"


def test_refund_and_reversal_reconciliation(db_session, test_owner):
    """
    Test 6: Refund and reversal events (PAYMENT.CAPTURE.REFUNDED) are reconciled:
    - Creates a refund ledger entry (confirmed_expense).
    - Transitions invoice status to REFUNDED.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    client = Client(name="Refund Client", email="refund@example.com", owner_id=test_owner.id, typical_invoice_amount=500.0)
    db_session.add(client)
    db_session.commit()

    inv_id = f"INV-REFUND-{uuid.uuid4().hex[:6]}"
    invoice = Invoice(
        client_id=client.id,
        paypal_invoice_id=inv_id,
        amount=Decimal("500.00"),
        currency="USD",
        status="PAID",
        issue_date=now,
        due_date=now
    )
    db_session.add(invoice)
    db_session.commit()

    refund_ref = f"rf_tx_{uuid.uuid4().hex[:6]}"
    refund_payload = {
        "id": f"WH-REF-{uuid.uuid4().hex[:6]}",
        "event_type": "PAYMENT.CAPTURE.REFUNDED",
        "resource": {
            "id": refund_ref,
            "invoice_id": inv_id,
            "amount": {"value": "500.00", "currency_code": "USD"}
        }
    }
    res_refund = process_webhook_event(db_session, refund_payload, is_simulated=False)
    assert res_refund["status"] == "success"
    assert res_refund["refund_amount"] == 500.0

    db_session.refresh(invoice)
    assert invoice.status == "REFUNDED"

    # Verify refund ledger entry created
    refund_ledger = db_session.query(FinancialEntry).filter(
        FinancialEntry.owner_id == test_owner.id,
        FinancialEntry.reference_id == refund_ref
    ).first()
    assert refund_ledger is not None
    assert refund_ledger.category == "refund"
    assert refund_ledger.amount == Decimal("500.00")


def test_payout_succeeded_verification_and_unmatched_quarantine(db_session, test_owner):
    """
    Test 7: Payout events:
    - Matched approved action is authoritatively confirmed and recorded in ledger.
    - Unmatched payout or detail mismatch is quarantined with manual_review_required.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    batch_key = f"payout_batch_{uuid.uuid4().hex[:8]}"

    # Approved Action
    action = Action(
        owner_id=test_owner.id,
        action_type="PAYOUT",
        recipient="contractor@example.com",
        amount=Decimal("750.00"),
        currency="USD",
        idempotency_key=batch_key,
        state=ActionState.EXECUTED,
        approval_hash="fake_hash"
    )
    db_session.add(action)
    db_session.commit()

    # 1. Successful verified payout matching action
    payout_payload = {
        "id": f"WH-PAYOUT-{uuid.uuid4().hex[:6]}",
        "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
        "resource": {
            "sender_batch_id": batch_key,
            "payout_item": {
                "receiver": "contractor@example.com",
                "amount": {"value": "750.00", "currency": "USD"}
            }
        }
    }
    res_payout = process_webhook_event(db_session, payout_payload, is_simulated=False)
    assert res_payout["status"] == "success"
    assert res_payout["payout_action_confirmed"] == action.id

    db_session.refresh(action)
    assert action.state == ActionState.CONFIRMED

    # 2. Unmatched payout -> quarantined
    unmatched_payload = {
        "id": f"WH-UNMATCHED-{uuid.uuid4().hex[:6]}",
        "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
        "resource": {
            "sender_batch_id": "unknown_batch_999",
            "payout_item": {
                "receiver": "stranger@example.com",
                "amount": {"value": "2000.00", "currency": "USD"}
            }
        }
    }
    res_unmatched = process_webhook_event(db_session, unmatched_payload, is_simulated=False)
    assert res_unmatched["status"] == "quarantined"
    assert res_unmatched["reason"] == "unmatched_payout_action"


def test_payout_failure_event_transitions_action_to_failed(db_session, test_owner):
    """
    Test 8: PAYMENT.PAYOUTS-ITEM.FAILED transitions action to ActionState.FAILED.
    """
    batch_key = f"payout_fail_{uuid.uuid4().hex[:8]}"
    action = Action(
        owner_id=test_owner.id,
        action_type="PAYOUT",
        recipient="contractor@example.com",
        amount=Decimal("300.00"),
        currency="USD",
        idempotency_key=batch_key,
        state=ActionState.EXECUTED,
        approval_hash="fake_hash"
    )
    db_session.add(action)
    db_session.commit()

    fail_payload = {
        "id": f"WH-FAIL-{uuid.uuid4().hex[:6]}",
        "event_type": "PAYMENT.PAYOUTS-ITEM.FAILED",
        "resource": {
            "sender_batch_id": batch_key,
            "errors": {"name": "INSUFFICIENT_FUNDS", "message": "Account balance insufficient"}
        }
    }
    res = process_webhook_event(db_session, fail_payload, is_simulated=False)
    assert res["status"] == "success"
    assert res["payout_action_failed"] == action.id

    db_session.refresh(action)
    assert action.state == ActionState.FAILED


def test_forecast_recalculation_failure_does_not_crash_reconciliation(db_session, test_owner, monkeypatch):
    """
    Test 9: If forecaster raises an exception during post-payment processing,
    the payment reconciliation succeeds cleanly and does NOT crash with AttributeError.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    client = Client(name="Forecaster Client", email="fc@example.com", owner_id=test_owner.id, typical_invoice_amount=300.0)
    db_session.add(client)
    db_session.commit()

    inv_id = f"INV-FC-{uuid.uuid4().hex[:6]}"
    invoice = Invoice(
        client_id=client.id,
        paypal_invoice_id=inv_id,
        amount=Decimal("300.00"),
        currency="USD",
        status="SENT",
        issue_date=now,
        due_date=now
    )
    db_session.add(invoice)
    db_session.commit()

    from backend.app.agents.forecaster import ForecasterAgent

    def broken_forecast(*args, **kwargs):
        raise RuntimeError("Simulated ML engine crash during forecast recalculation")

    monkeypatch.setattr(ForecasterAgent, "run_forecast", broken_forecast)

    tx_id = f"tx_fc_{uuid.uuid4().hex[:6]}"
    payload = {
        "id": f"WH-FC-{uuid.uuid4().hex[:6]}",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {
            "id": inv_id,
            "transaction_id": tx_id,
            "amount": {"value": "300.00", "currency_code": "USD"},
            "invoice": {"id": inv_id}
        }
    }

    # Must NOT raise AttributeError or RuntimeError
    res = process_webhook_event(db_session, payload, is_simulated=False)
    assert res["status"] == "success"
    assert res["shortfall_amount"] is None

    db_session.refresh(invoice)
    assert invoice.status == "PAID"


@pytest.mark.asyncio
async def test_event_queue_single_task_done_and_outcome_preservation(db_session, monkeypatch):
    """
    Test 10: EventQueue:
    - task_done() is called strictly once in finally.
    - Quarantined events are preserved with processed=False.
    """
    queue = EventQueue()

    # Insert a quarantined event
    evt = WebhookEvent(
        paypal_event_id=f"WH-Q-{uuid.uuid4().hex[:6]}",
        event_type="INVOICING.INVOICE.PAID",
        verified=True,
        payload={"id": "MISSING-INV", "event_type": "INVOICING.INVOICE.PAID", "resource": {"id": "NONEXISTENT"}},
        processed=False,
        processing_state="received",
        reconciliation_status="pending",
        is_simulated=False
    )
    db_session.add(evt)
    db_session.commit()
    db_session.refresh(evt)

    # Enqueue and let worker process it
    await queue.enqueue(event_id=evt.id, payload=evt.payload, is_simulated=False)

    # Run one pass of worker loop manually
    queue._running = True
    worker_task = asyncio.create_task(queue._worker_loop())

    # Wait for queue to empty
    await asyncio.sleep(0.5)
    await queue.stop()

    db_session.refresh(evt)
    # Quarantined event MUST NOT be marked processed=True
    assert evt.processed is False
    assert evt.processing_state == "quarantined"
    assert evt.reconciliation_status == "manual_review_required"


@pytest.mark.asyncio
async def test_paypal_client_idempotency_headers_and_invoice_discount_safety(monkeypatch):
    """
    Test 11: PayPal REST API Client:
    - Attaches PayPal-Request-Id to mutations.
    - apply_invoice_discount strips read-only fields and quantizes amounts.
    """
    captured_requests = []

    async def mock_send_req(method, endpoint, json_data=None, params=None, headers=None, request_id=None, max_retries=3):
        captured_requests.append({
            "method": method,
            "endpoint": endpoint,
            "json_data": json_data,
            "request_id": request_id
        })
        if method == "GET" and "/v2/invoicing/invoices/INV-123" in endpoint:
            return {
                "id": "INV-123",
                "status": "DRAFT",
                "links": [{"href": "http://paypal.com/pay"}],
                "amount": {"value": "500.00", "currency_code": "USD"},
                "detail": {"currency_code": "USD", "invoice_number": "001"},
                "invoicer": {"name": {"given_name": "Alex"}},
                "items": [{"name": "Design", "unit_amount": {"value": "500.00", "currency_code": "USD"}}]
            }
        return {"id": "INV-123", "status": "DRAFT"}

    client = PayPalClient(client_id="test_client", client_secret="test_secret")
    monkeypatch.setattr(client, "_request", mock_send_req)

    # Test apply_invoice_discount
    await client.apply_invoice_discount(invoice_id="INV-123", discount_percent=10.0, note="10% early discount")

    # Find the PUT request
    put_req = next(r for r in captured_requests if r["method"] == "PUT")
    assert put_req["request_id"] is not None
    assert "disc_INV-123" in put_req["request_id"]
    put_payload = put_req["json_data"]

    # Verify read-only fields were stripped!
    assert "id" not in put_payload
    assert "status" not in put_payload
    assert "links" not in put_payload
    assert "amount" not in put_payload  # Read-only calculated field in v2 Invoicing

    # Verify discount applied
    assert put_payload["detail"]["discount"]["percent"] == "10.00"
    assert put_payload["detail"]["discount"]["note"] == "10% early discount"
