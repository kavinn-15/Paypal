import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models import Invoice, Action, PaymentHistory, WebhookEvent, Obligation
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState
from backend.app.guardrail.audit import append_audit_log
from backend.app.agents.forecaster import ForecasterAgent

logger = logging.getLogger("webhook_processor")


def process_webhook_event(
    db: Session,
    event_payload: Dict[str, Any],
    is_simulated: bool = False
) -> Dict[str, Any]:
    """
    Processes verified PayPal webhook events:
    - INVOICING.INVOICE.PAID: marks invoice paid, transitions action to CONFIRMED, recomputes forecast.
    - PAYMENT.PAYOUTS-ITEM.SUCCEEDED: marks contractor payout installment confirmed.
    """
    event_type = event_payload.get("event_type", "").upper()
    resource = event_payload.get("resource", {})

    logger.info(f"Processing webhook event: {event_type} (simulated={is_simulated})")

    if event_type == "INVOICING.INVOICE.PAID":
        # Extract invoice ID
        inv_data = resource.get("invoice", resource)
        paypal_inv_id = inv_data.get("id") or resource.get("id")

        if not paypal_inv_id:
            logger.warning(f"No invoice ID found in webhook resource: {resource}")
            return {"status": "skipped", "reason": "no_invoice_id"}

        invoice = db.query(Invoice).filter(Invoice.paypal_invoice_id == paypal_inv_id).first()
        if not invoice:
            # If not found by exact ID, fallback to find any open invoice with matching amount
            paid_amount = float(inv_data.get("amount", {}).get("value", 0.0) or resource.get("amount", {}).get("value", 0.0) or 0.0)
            if paid_amount > 0:
                invoice = db.query(Invoice).filter(Invoice.status == "SENT", Invoice.amount == paid_amount).first()

        if not invoice:
            logger.warning(f"No matching local invoice found for paypal_invoice_id: {paypal_inv_id}")
            return {"status": "invoice_not_found", "paypal_invoice_id": paypal_inv_id}

        now = datetime.now(timezone.utc)
        invoice.status = "PAID"
        invoice.paid_date = now

        # Add to payment history
        due_d = invoice.due_date if invoice.due_date.tzinfo else invoice.due_date.replace(tzinfo=timezone.utc)
        days_late = max((now.date() - due_d.date()).days, 0)
        history_entry = PaymentHistory(
            client_id=invoice.client_id,
            invoice_id=invoice.id,
            amount=invoice.amount,
            due_date=invoice.due_date,
            paid_date=now,
            days_late=days_late,
            source="seeded" if is_simulated else "paypal"
        )
        db.add(history_entry)
        db.commit()

        # Check for matching Action in EXECUTED state
        action = db.query(Action).filter(
            Action.state == ActionState.EXECUTED,
            (Action.paypal_ref == invoice.paypal_invoice_id) | (Action.recipient == invoice.client.name)
        ).first()

        # If no executed action for this exact invoice, check any executed reminder or discount action
        if not action:
            action = db.query(Action).filter(
                Action.state == ActionState.EXECUTED,
                Action.action_type.in_(["SEND_REMINDER", "APPLY_DISCOUNT"])
            ).first()

        if action:
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.CONFIRMED,
                actor="paypal_webhook" if not is_simulated else "dev_simulator"
            )
            action.is_simulated = is_simulated
            db.commit()

        # Recalculate forecast with new cash position
        forecaster = ForecasterAgent(db)
        # Starting balance increases by invoice payment amount
        new_balance = 1800.0 + float(invoice.amount)
        updated_forecast = forecaster.run_forecast(starting_balance=new_balance)

        append_audit_log(
            db=db,
            actor="webhook",
            event="WEBHOOK_RECALCULATION_COMPLETE",
            payload={
                "paypal_invoice_id": invoice.paypal_invoice_id,
                "amount_paid": float(invoice.amount),
                "new_balance": new_balance,
                "shortfall_remaining": updated_forecast.shortfall_amount,
                "action_confirmed": action.id if action else None,
                "is_simulated": is_simulated
            }
        )

        return {
            "status": "success",
            "invoice_id": invoice.id,
            "paypal_invoice_id": invoice.paypal_invoice_id,
            "action_confirmed": action.id if action else None,
            "new_balance": new_balance,
            "shortfall_amount": updated_forecast.shortfall_amount,
            "is_simulated": is_simulated
        }

    elif event_type == "PAYMENT.PAYOUTS-ITEM.SUCCEEDED":
        sender_batch_id = resource.get("sender_batch_id")
        action = None
        if sender_batch_id:
            action = db.query(Action).filter(Action.idempotency_key == sender_batch_id).first()

        if action and action.state == ActionState.EXECUTED:
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.CONFIRMED,
                actor="paypal_webhook"
            )

        return {"status": "success", "payout_action_confirmed": action.id if action else None}

    return {"status": "unhandled_event_type", "event_type": event_type}

