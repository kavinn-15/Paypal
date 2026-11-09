import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from backend.app.db import get_db
from backend.app.config import settings
from backend.app.auth.deps import get_current_user
from backend.app.models import WebhookEvent, Invoice, Owner
from backend.app.paypal.client import paypal_client
from backend.app.events.queue import event_queue
from backend.app.events.processor import process_webhook_event
from backend.app.schemas import SimulateWebhookRequest, WebhookEventOut
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(tags=["PayPal Webhooks"])


@router.post("/webhooks/paypal")
async def receive_paypal_webhook(
    request: Request,
    paypal_transmission_id: Optional[str] = Header(None, alias="PAYPAL-TRANSMISSION-ID"),
    paypal_transmission_time: Optional[str] = Header(None, alias="PAYPAL-TRANSMISSION-TIME"),
    paypal_cert_url: Optional[str] = Header(None, alias="PAYPAL-CERT-URL"),
    paypal_auth_algo: Optional[str] = Header(None, alias="PAYPAL-AUTH-ALGO"),
    paypal_transmission_sig: Optional[str] = Header(None, alias="PAYPAL-TRANSMISSION-SIG"),
    db: Session = Depends(get_db)
):
    """
    Public webhook endpoint receiving PayPal Sandbox events.
    Verifies cryptographic signature against PayPal API before queue processing.
    Deduplicates by paypal_event_id.
    """
    body_json = await request.json()
    event_id = body_json.get("id")
    event_type = body_json.get("event_type", "UNKNOWN")

    if not event_id:
        raise HTTPException(status_code=400, detail="Missing webhook event id")

    # 1. Deduplication check
    existing = db.query(WebhookEvent).filter(WebhookEvent.paypal_event_id == event_id).first()
    if existing:
        return {"status": "ignored", "reason": "duplicate_event_id", "event_id": event_id}

    # 2. Verify webhook signature through PayPal API
    webhook_id = settings.PAYPAL_WEBHOOK_ID or "sandbox_wh_id"
    is_verified = False

    if paypal_transmission_id and paypal_transmission_sig and paypal_cert_url:
        is_verified = await paypal_client.verify_webhook_signature(
            transmission_id=paypal_transmission_id,
            transmission_time=paypal_transmission_time or datetime.now(timezone.utc).isoformat(),
            cert_url=paypal_cert_url,
            auth_algo=paypal_auth_algo or "SHA256withRSA",
            transmission_sig=paypal_transmission_sig,
            webhook_id=webhook_id,
            webhook_event_payload=body_json
        )
    else:
        is_verified = False

    # Persist event with durable tracking state
    evt_record = WebhookEvent(
        paypal_event_id=event_id,
        event_type=event_type,
        verified=is_verified,
        payload=body_json,
        processed=False,
        processing_state="received" if is_verified else "quarantined",
        reconciliation_status="pending" if is_verified else "unverified_signature",
        is_simulated=False
    )
    db.add(evt_record)
    db.commit()
    db.refresh(evt_record)

    append_audit_log(
        db=db,
        actor="paypal_webhook",
        event=f"WEBHOOK_RECEIVED_{event_type.replace('.', '_')}",
        payload={"event_id": event_id, "event_type": event_type, "verified": is_verified}
    )

    if not is_verified:
        append_audit_log(
            db=db,
            actor="paypal_webhook",
            event="WEBHOOK_SIGNATURE_VERIFICATION_FAILED",
            payload={"event_id": event_id, "event_type": event_type, "reason": "invalid_or_missing_signature"}
        )
        return {"status": "unverified_signature_stored", "verified": False, "event_id": event_id}

    # 3. Enqueue verified event for processing
    await event_queue.enqueue(event_id=evt_record.id, payload=body_json, is_simulated=False)
    return {"status": "accepted", "verified": True, "event_id": event_id}


@router.post("/dev/simulate-webhook")
def simulate_webhook_event(
    payload: SimulateWebhookRequest,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    DEV_MODE ONLY: Simulates a confirmed client payment event for the authenticated user.
    Visibly stamped as 'is_simulated=True' and labeled in UI.
    """
    if not settings.DEV_MODE or not settings.ALLOW_DEMO_ENDPOINTS:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Webhook simulation endpoint is disabled in production."
        )

    # Find target invoice owned by current_user
    inv_query = db.query(Invoice).join(Invoice.client).filter(Invoice.client.has(owner_id=current_user.id))
    if payload.invoice_id:
        invoice = inv_query.filter(Invoice.id == payload.invoice_id).first()
    elif payload.paypal_invoice_id:
        invoice = inv_query.filter(Invoice.paypal_invoice_id == payload.paypal_invoice_id).first()
    else:
        invoice = inv_query.filter(Invoice.status.in_(["SENT", "DRAFT"])).first()

    if not invoice:
        raise HTTPException(status_code=400, detail="No open invoice available for current user to simulate payment on.")

    sim_event_id = f"WH-SIM-{uuid.uuid4().hex[:12]}"
    amount_paid = payload.amount or invoice.amount

    simulated_payload = {
        "id": sim_event_id,
        "event_version": "1.0",
        "create_time": datetime.now(timezone.utc).isoformat(),
        "resource_type": "invoices",
        "event_type": "INVOICING.INVOICE.PAID",
        "summary": f"Simulated Payment for Invoice #{invoice.paypal_invoice_id}",
        "resource": {
            "id": invoice.paypal_invoice_id,
            "status": "PAID",
            "amount": {"currency_code": invoice.currency, "value": f"{amount_paid:.2f}"},
            "invoice": {"id": invoice.paypal_invoice_id}
        }
    }

    # Record in WebhookEvent table visibly marked as simulated and bound to user
    # Simulated events must NEVER be represented as signature-verified PayPal events
    evt_record = WebhookEvent(
        owner_id=current_user.id,
        paypal_event_id=sim_event_id,
        event_type="INVOICING.INVOICE.PAID",
        verified=False,
        payload=simulated_payload,
        processed=True,
        processing_state="processed_simulation",
        reconciliation_status="simulated",
        is_simulated=True
    )
    db.add(evt_record)
    db.commit()

    # Process immediately with simulation flag preserved
    result = process_webhook_event(db, simulated_payload, is_simulated=True, webhook_event_id=evt_record.id)

    return {
        "success": True,
        "simulated": True,
        "message": "Simulated payment processed successfully. Demo forecast recalculated. This is not a verified PayPal payment.",
        "result": result
    }

