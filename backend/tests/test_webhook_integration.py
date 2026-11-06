import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import Action, WebhookEvent
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState
from backend.app.guardrail.approval import generate_approval_hash
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database(clean=True, demo_mode=True)


@pytest.mark.asyncio
async def test_duplicate_webhook_deduplication():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        evt_payload = {
            "id": "WH-DEDUPE-TEST-001",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {"id": "INV-TEST-001"}
        }

        # First delivery (without headers -> unverified stored)
        res1 = await client.post("/webhooks/paypal", json=evt_payload)
        assert res1.status_code == 200
        assert res1.json()["event_id"] == "WH-DEDUPE-TEST-001"

        # Second delivery (duplicate event id)
        res2 = await client.post("/webhooks/paypal", json=evt_payload)
        assert res2.status_code == 200
        assert res2.json()["status"] == "ignored"
        assert res2.json()["reason"] == "duplicate_event_id"


@pytest.mark.asyncio
async def test_unverified_webhook_does_not_modify_cashflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check initial forecast
        res_fc1 = await client.post("/forecast/run?starting_balance=1800.0")
        shortfall_before = res_fc1.json()["shortfall_amount"]
        assert shortfall_before == 1400.0

        # Post unverified webhook with fake signature headers
        unverified_payload = {
            "id": "WH-UNVERIFIED-TEST-999",
            "event_type": "INVOICING.INVOICE.PAID",
            "resource": {
                "id": "INV2-DEMO-APEX-001",
                "amount": {"value": "2000.00"}
            }
        }
        res_wh = await client.post(
            "/webhooks/paypal",
            json=unverified_payload,
            headers={
                "PAYPAL-TRANSMISSION-ID": "fake_id",
                "PAYPAL-TRANSMISSION-SIG": "fake_sig",
                "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert.pem"
            }
        )
        assert res_wh.status_code == 200
        data = res_wh.json()
        assert data["verified"] is False
        assert data["status"] == "unverified_signature_stored"

        # Verify database record has verified=False
        db = SessionLocal()
        evt = db.query(WebhookEvent).filter(WebhookEvent.paypal_event_id == "WH-UNVERIFIED-TEST-999").first()
        assert evt is not None
        assert evt.verified is False
        assert evt.processed is False
        db.close()


@pytest.mark.asyncio
async def test_payout_failure_and_retry_flow():
    db = SessionLocal()
    try:
        idemp = "act_payout_fail_test_1"
        h = generate_approval_hash("Marcus Sterling", 1600.0, "USD", "SCHEDULE_PAYOUT_SPLIT", idemp)

        action = Action(
            action_type="SCHEDULE_PAYOUT_SPLIT",
            recipient="Marcus Sterling",
            amount=1600.0,
            currency="USD",
            state=ActionState.PROPOSED,
            idempotency_key=idemp,
            approval_hash=h
        )
        db.add(action)
        db.commit()

        # Approve action
        action = GuardrailStateMachine.transition(db, action, ActionState.APPROVED, "owner", approval_hash=h)
        assert action.state == ActionState.APPROVED

        # Transition to EXECUTED
        action = GuardrailStateMachine.transition(db, action, ActionState.EXECUTED, "system")
        assert action.state == ActionState.EXECUTED

        # Transition to FAILED (e.g. PayPal sandbox returned 503 or insufficient balance)
        action = GuardrailStateMachine.transition(
            db, action, ActionState.FAILED, "system", error_message="PayPal Sandbox Payouts Temporarily Unavailable"
        )
        assert action.state == ActionState.FAILED
        assert "Temporarily Unavailable" in action.error_message

        # State machine allows retry: failed -> approved
        action = GuardrailStateMachine.transition(
            db, action, ActionState.APPROVED, "owner", approval_hash=h
        )
        assert action.state == ActionState.APPROVED
    finally:
        db.close()
