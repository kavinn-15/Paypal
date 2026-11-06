import logging
from sqlalchemy.orm import Session
from backend.app.models import Action, Invoice
from backend.app.paypal.client import paypal_client, PayPalError
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState, InvalidStateTransitionError
from backend.app.guardrail.policy import validate_action_against_policy, PolicyViolationError
from backend.app.guardrail.audit import append_audit_log

logger = logging.getLogger("action_executor")


import logging
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models import Action, Invoice, Obligation
from backend.app.paypal.client import paypal_client, PayPalError
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState, InvalidStateTransitionError
from backend.app.guardrail.policy import validate_action_against_policy, PolicyViolationError
from backend.app.guardrail.audit import append_audit_log

logger = logging.getLogger("action_executor")


class ActionExecutionService:
    """
    Executes approved actions through the PayPal Sandbox:
    - Invoicing v2: Reminders, Discount updates
    - Payouts: Batch payouts with idempotency key
    Zero fake batch IDs, zero swallowed errors, strict recipient & policy validation.
    """

    @staticmethod
    async def execute_action(db: Session, action: Action, actor: str = "owner") -> Action:
        # 1. State check: must be in APPROVED state
        if action.state != ActionState.APPROVED:
            raise InvalidStateTransitionError(
                f"Action {action.id} cannot be executed. Current state is '{action.state}'. Must be '{ActionState.APPROVED}'."
            )

        # 2. Safety Policy check
        validate_action_against_policy(action, db)

        # 3. Execution routing
        try:
            if action.action_type == "SEND_REMINDER":
                inv_id = action.paypal_ref
                if not inv_id:
                    raise ValueError(f"Action {action.id} has no associated invoice reference.")

                # Verify invoice exists and belongs to this owner
                inv_query = db.query(Invoice).filter(Invoice.paypal_invoice_id == inv_id)
                if action.owner_id:
                    inv_query = inv_query.join(Invoice.client).filter(Invoice.client.has(owner_id=action.owner_id))
                invoice = inv_query.first()
                if not invoice:
                    raise ValueError(f"Associated invoice {inv_id} not found or does not belong to owner.")

                msg = action.messages[0].body if action.messages else "Please find payment link attached."

                # Dispatches real request to PayPal Sandbox API; raises PayPalError on failure
                await paypal_client.send_invoice_reminder(
                    invoice_id=inv_id,
                    subject="Payment Reminder: Upcoming Invoice Settlement",
                    note=msg
                )

                GuardrailStateMachine.transition(
                    db=db,
                    action=action,
                    target_state=ActionState.EXECUTED,
                    actor=actor,
                    paypal_ref=inv_id
                )

            elif action.action_type == "APPLY_DISCOUNT":
                inv_id = action.paypal_ref
                if not inv_id:
                    raise ValueError(f"Action {action.id} has no associated invoice reference.")

                inv_query = db.query(Invoice).filter(Invoice.paypal_invoice_id == inv_id)
                if action.owner_id:
                    inv_query = inv_query.join(Invoice.client).filter(Invoice.client.has(owner_id=action.owner_id))
                invoice = inv_query.first()
                if not invoice:
                    raise ValueError(f"Associated invoice {inv_id} not found or does not belong to owner.")

                disc_pct = float(action.plan.details.get("discount_pct", 3.0)) if action.plan and action.plan.details else 3.0

                # Dispatches real request to PayPal Sandbox API; raises PayPalError on failure
                await paypal_client.apply_invoice_discount(
                    invoice_id=inv_id,
                    discount_percent=disc_pct,
                    note="Early payment discount applied."
                )

                # Only update local database upon verified PayPal API success
                invoice.discount_applied = disc_pct
                db.commit()

                GuardrailStateMachine.transition(
                    db=db,
                    action=action,
                    target_state=ActionState.EXECUTED,
                    actor=actor,
                    paypal_ref=inv_id
                )

            elif action.action_type in ("SCHEDULE_PAYOUT_SPLIT", "PAYOUT"):
                # Determine and validate recipient contractor email
                recipient_email = None
                recip_clean = action.recipient.strip()
                if "@" in recip_clean:
                    recipient_email = recip_clean
                else:
                    # Look up obligation for this owner
                    obl = db.query(Obligation).filter(
                        Obligation.owner_id == action.owner_id,
                        (Obligation.payee_name.ilike(recip_clean)) | (Obligation.payee_email.ilike(recip_clean))
                    ).first()
                    if obl and obl.payee_email:
                        recipient_email = obl.payee_email.strip()

                if not recipient_email or "@" not in recipient_email:
                    raise ValueError(
                        f"Cannot resolve verified recipient email for payout recipient '{action.recipient}'. Execution aborted."
                    )

                # Dispatches real request to PayPal Sandbox API; raises PayPalError on failure
                res = await paypal_client.create_payout(
                    recipient_email=recipient_email,
                    amount=float(action.amount),
                    currency=action.currency,
                    sender_batch_id=action.idempotency_key,
                    note=f"Contractor Payout - Ref {action.idempotency_key[:8]}"
                )

                # Extract and validate real PayPal payout batch ID
                batch_id = res.get("batch_header", {}).get("payout_batch_id")
                if not batch_id:
                    raise PayPalError(f"PayPal create_payout response missing valid payout_batch_id: {res}")

                batch_status = res.get("batch_header", {}).get("batch_status", "PENDING")
                logger.info(f"PayPal Payout batch created: {batch_id} with status {batch_status}")

                GuardrailStateMachine.transition(
                    db=db,
                    action=action,
                    target_state=ActionState.EXECUTED,
                    actor=actor,
                    paypal_ref=batch_id
                )
            else:
                raise ValueError(f"Unknown action type: {action.action_type}")

        except Exception as e:
            logger.error(f"Execution failed for action {action.id}: {e}")
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.FAILED,
                actor=actor,
                error_message=str(e)
            )
            append_audit_log(
                db=db,
                actor="system",
                event="ACTION_EXECUTION_FAILED",
                payload={"action_id": action.id, "error": str(e)},
                owner_id=action.owner_id
            )
            raise e

        return action

