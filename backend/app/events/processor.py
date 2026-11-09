import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models import Invoice, Action, PaymentHistory, WebhookEvent, Obligation, FinancialEntry
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState
from backend.app.guardrail.audit import append_audit_log
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.services.financial_service import FinancialService

logger = logging.getLogger("webhook_processor")


def process_webhook_event(
    db: Session,
    event_payload: Dict[str, Any],
    is_simulated: bool = False,
    webhook_event_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Processes verified PayPal webhook events:
    - INVOICING.INVOICE.PAID:
        * Matches invoice strictly by exact paypal_invoice_id (zero fallback to random invoices).
        * Replay safe: checks if already paid to prevent double-crediting balances.
        * Supports partial payments.
        * Matches action strictly by exact paypal_ref and owner_id.
        * Updates authoritative financial ledger and recomputes forecast.
    - PAYMENT.PAYOUTS-ITEM.SUCCEEDED:
        * Authoritatively confirms contractor payout installment.
    """
    event_id = event_payload.get("id", "UNKNOWN")
    event_type = event_payload.get("event_type", "").upper()
    resource = event_payload.get("resource", {})

    logger.info(f"Processing webhook event: {event_type} (id={event_id}, simulated={is_simulated})")

    # Locate WebhookEvent record for durable state tracking
    evt_record = None
    if webhook_event_id:
        evt_record = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_event_id).first()
    elif event_id != "UNKNOWN":
        evt_record = db.query(WebhookEvent).filter(WebhookEvent.paypal_event_id == event_id).first()

    now = datetime.now(timezone.utc)

    if event_type == "INVOICING.INVOICE.PAID":
        inv_data = resource.get("invoice", resource)
        paypal_inv_id = inv_data.get("id") or resource.get("id")

        if not paypal_inv_id:
            logger.warning(f"No invoice ID found in webhook resource: {resource}")
            if evt_record:
                evt_record.processing_state = "quarantined"
                evt_record.error_details = "Missing invoice ID in resource payload"
                evt_record.reconciliation_status = "manual_review_required"
                db.commit()
            return {"status": "quarantined", "reason": "missing_invoice_id"}

        # Exact invoice lookup (NO GUESSING BY AMOUNT)
        invoice = db.query(Invoice).filter(Invoice.paypal_invoice_id == paypal_inv_id).first()
        if not invoice:
            logger.warning(f"No matching local invoice for paypal_invoice_id: {paypal_inv_id}. Quarantining event.")
            if evt_record:
                evt_record.processing_state = "quarantined"
                evt_record.error_details = f"Invoice {paypal_inv_id} not found in database"
                evt_record.reconciliation_status = "manual_review_required"
                db.commit()
            return {"status": "quarantined", "reason": "invoice_not_found", "paypal_invoice_id": paypal_inv_id}

        # Associate owner with webhook event
        owner = invoice.client.owner if invoice.client else None
        if evt_record and owner:
            evt_record.owner_id = owner.id

        # Replay / Idempotency Check: if invoice is already marked PAID, prevent balance double-crediting
        if not is_simulated and invoice.status == "PAID":
            logger.info(f"Invoice {paypal_inv_id} is already marked PAID. Ignoring duplicate payment event.")
            if evt_record:
                evt_record.processing_state = "processed"
                evt_record.processed = True
                evt_record.reconciliation_status = "reconciled"
                evt_record.processed_at = now
                db.commit()
            return {
                "status": "already_processed",
                "invoice_id": invoice.id,
                "paypal_invoice_id": paypal_inv_id,
                "reason": "duplicate_payment_event_ignored"
            }

        # Parse payment amount and handle partial/over payments
        raw_amt = inv_data.get("amount", {}).get("value") or resource.get("amount", {}).get("value")
        paid_amount = Decimal(str(raw_amt)) if raw_amt else Decimal(str(invoice.amount))

        # Check for overpayment -> flag for manual review, do NOT automatically mark PAID
        if paid_amount > Decimal(str(invoice.amount)):
            logger.warning(
                f"Overpayment detected for invoice {invoice.paypal_invoice_id}: paid {paid_amount} > total {invoice.amount}. Flagging for manual review."
            )
            if evt_record:
                evt_record.processing_state = "quarantined"
                evt_record.reconciliation_status = "manual_review_required"
                evt_record.error_details = f"Overpayment detected: paid {paid_amount} exceeds invoice total {invoice.amount}"
                db.commit()
            append_audit_log(
                db=db,
                actor="paypal_webhook" if not is_simulated else "dev_simulator",
                event="OVERPAYMENT_FLAGGED_FOR_MANUAL_REVIEW",
                payload={"paypal_invoice_id": invoice.paypal_invoice_id, "invoice_amount": float(invoice.amount), "paid_amount": float(paid_amount)},
                owner_id=owner.id if owner else None
            )
            return {
                "status": "flagged_manual_review",
                "reason": "overpayment_detected",
                "invoice_id": invoice.id,
                "paypal_invoice_id": invoice.paypal_invoice_id,
                "invoice_amount": float(invoice.amount),
                "paid_amount": float(paid_amount)
            }

        due_d = invoice.due_date if invoice.due_date.tzinfo else invoice.due_date.replace(tzinfo=timezone.utc)
        days_late = max((now.date() - due_d.date()).days, 0)

        if is_simulated:
            # SIMULATED PAYMENTS: NEVER mutate authoritative invoice payment state to PAID
            invoice.is_simulated_paid = True
            # Keep invoice.status as SENT or PARTIALLY_PAID (authoritative state untouched)

            # Record or update non-authoritative simulation ledger entry
            if owner:
                sim_entry = db.query(FinancialEntry).filter(
                    FinancialEntry.owner_id == owner.id,
                    FinancialEntry.reference_id == invoice.paypal_invoice_id,
                    FinancialEntry.is_demo == True
                ).first()
                if sim_entry:
                    sim_entry.amount = paid_amount
                    sim_entry.transaction_date = now
                    sim_entry.status = "simulated"
                else:
                    sim_entry = FinancialEntry(
                        owner_id=owner.id,
                        canonical_id=f"sim_pay_{invoice.paypal_invoice_id}_{event_id}",
                        title=f"[SIMULATED] PayPal Invoice Payment #{invoice.paypal_invoice_id} ({invoice.client.name})",
                        amount=paid_amount,
                        currency=invoice.currency,
                        entry_type="simulated_income",
                        category="client_invoice",
                        transaction_date=now,
                        status="simulated",
                        data_source="dev_simulator",
                        reference_id=invoice.paypal_invoice_id,
                        is_demo=True
                    )
                    db.add(sim_entry)
        else:
            # GENUINE PAYPAL WEBHOOK: Reconcile authoritative invoice payment state
            if paid_amount < Decimal(str(invoice.amount)):
                invoice.status = "PARTIALLY_PAID"
            else:
                invoice.status = "PAID"
                invoice.paid_date = now
                invoice.is_simulated_paid = False

            # Authoritative PaymentHistory record
            existing_hist = db.query(PaymentHistory).filter(
                PaymentHistory.invoice_id == invoice.id,
                PaymentHistory.source == "paypal"
            ).first()
            if not existing_hist:
                history_entry = PaymentHistory(
                    client_id=invoice.client_id,
                    invoice_id=invoice.id,
                    amount=paid_amount,
                    due_date=invoice.due_date,
                    paid_date=now,
                    days_late=days_late,
                    source="paypal",
                    transaction_reference=event_id
                )
                db.add(history_entry)

            # Authoritative confirmed income entry in financial ledger (deduplicated)
            if owner:
                existing_ledger = db.query(FinancialEntry).filter(
                    FinancialEntry.owner_id == owner.id,
                    FinancialEntry.reference_id == invoice.paypal_invoice_id,
                    FinancialEntry.status == "confirmed"
                ).first()
                if not existing_ledger:
                    ledger_entry = FinancialEntry(
                        owner_id=owner.id,
                        canonical_id=f"pay_{invoice.paypal_invoice_id}_{event_id}",
                        title=f"PayPal Invoice Payment #{invoice.paypal_invoice_id} ({invoice.client.name})",
                        amount=paid_amount,
                        currency=invoice.currency,
                        entry_type="confirmed_income",
                        category="client_invoice",
                        transaction_date=now,
                        status="confirmed",
                        data_source="paypal_webhook",
                        reference_id=invoice.paypal_invoice_id,
                        is_demo=False
                    )
                    db.add(ledger_entry)

        db.commit()

        # Match Action strictly by exact paypal_ref and owner_id
        action_query = db.query(Action).filter(
            Action.state.in_([ActionState.EXECUTED, ActionState.SIMULATED]),
            Action.paypal_ref == invoice.paypal_invoice_id
        )
        if owner:
            action_query = action_query.filter(Action.owner_id == owner.id)
        action = action_query.first()

        if action:
            if is_simulated:
                # Simulated events must NEVER transition an action into genuine CONFIRMED status
                GuardrailStateMachine.transition(
                    db=db,
                    action=action,
                    target_state=ActionState.SIMULATED,
                    actor="dev_simulator"
                )
                action.is_simulated = True
                action.confirmed_at = None
                db.commit()
            else:
                # Genuine signature-verified PayPal webhook transitions to CONFIRMED
                GuardrailStateMachine.transition(
                    db=db,
                    action=action,
                    target_state=ActionState.CONFIRMED,
                    actor="paypal_webhook"
                )
                action.is_simulated = False
                action.confirmed_at = now
                db.commit()

        # Recalculate forecast using actual reconciled balance
        reconciled_balance = float(FinancialService.get_confirmed_balance(db, owner)) if owner else 1800.0 + float(paid_amount)
        forecaster = ForecasterAgent(db)
        updated_forecast = forecaster.run_forecast(
            obligation_id=None,
            starting_balance=reconciled_balance,
            owner_id=owner.id if owner else None
        )

        if evt_record:
            evt_record.processing_state = "processed"
            evt_record.processed = True
            evt_record.reconciliation_status = "reconciled"
            evt_record.processed_at = now
            db.commit()

        append_audit_log(
            db=db,
            actor="paypal_webhook" if not is_simulated else "dev_simulator",
            event="WEBHOOK_INVOICE_PAID_RECONCILED",
            payload={
                "paypal_invoice_id": invoice.paypal_invoice_id,
                "paid_amount": float(paid_amount),
                "reconciled_balance": reconciled_balance,
                "shortfall_remaining": updated_forecast.shortfall_amount,
                "action_confirmed": action.id if action else None,
                "is_simulated": is_simulated
            },
            owner_id=owner.id if owner else None
        )

        return {
            "status": "success",
            "invoice_id": invoice.id,
            "paypal_invoice_id": invoice.paypal_invoice_id,
            "action_confirmed": action.id if action else None,
            "reconciled_balance": reconciled_balance,
            "shortfall_amount": updated_forecast.shortfall_amount,
            "is_simulated": is_simulated
        }

    elif event_type == "PAYMENT.PAYOUTS-ITEM.SUCCEEDED":
        sender_batch_id = resource.get("sender_batch_id")
        action = None
        if sender_batch_id:
            action = db.query(Action).filter(Action.idempotency_key == sender_batch_id).first()

        if action and action.state in [ActionState.EXECUTED, ActionState.SIMULATED]:
            if is_simulated:
                GuardrailStateMachine.transition(
                    db=db,
                    action=action,
                    target_state=ActionState.SIMULATED,
                    actor="dev_simulator"
                )
                action.is_simulated = True
                action.confirmed_at = None
                db.commit()
            else:
                GuardrailStateMachine.transition(
                    db=db,
                    action=action,
                    target_state=ActionState.CONFIRMED,
                    actor="paypal_webhook"
                )
                action.is_simulated = False
                action.confirmed_at = now
                db.commit()

            # Record financial entry in ledger (distinguishing simulated from confirmed)
            if action.owner_id:
                if is_simulated:
                    sim_outflow = db.query(FinancialEntry).filter(
                        FinancialEntry.owner_id == action.owner_id,
                        FinancialEntry.reference_id == sender_batch_id,
                        FinancialEntry.is_demo == True
                    ).first()
                    if sim_outflow:
                        sim_outflow.amount = Decimal(str(action.amount))
                        sim_outflow.transaction_date = now
                    else:
                        sim_outflow = FinancialEntry(
                            owner_id=action.owner_id,
                            canonical_id=f"sim_payout_{sender_batch_id}_{event_id}",
                            title=f"[SIMULATED] Contractor Payout ({action.recipient})",
                            amount=Decimal(str(action.amount)),
                            currency=action.currency,
                            entry_type="simulated_expense",
                            category="contractor",
                            transaction_date=now,
                            status="simulated",
                            data_source="dev_simulator",
                            reference_id=sender_batch_id,
                            is_demo=True
                        )
                        db.add(sim_outflow)
                    db.commit()
                else:
                    existing_outflow = db.query(FinancialEntry).filter(
                        FinancialEntry.owner_id == action.owner_id,
                        FinancialEntry.reference_id == sender_batch_id,
                        FinancialEntry.status == "confirmed"
                    ).first()
                    if not existing_outflow:
                        outflow_entry = FinancialEntry(
                            owner_id=action.owner_id,
                            canonical_id=f"payout_{sender_batch_id}_{event_id}",
                            title=f"Contractor Payout Confirmed ({action.recipient})",
                            amount=Decimal(str(action.amount)),
                            currency=action.currency,
                            entry_type="confirmed_expense",
                            category="contractor",
                            transaction_date=now,
                            status="confirmed",
                            data_source="paypal_webhook",
                            reference_id=sender_batch_id,
                            is_demo=False
                        )
                        db.add(outflow_entry)
                        db.commit()

        if evt_record:
            evt_record.processing_state = "processed"
            evt_record.processed = True
            evt_record.reconciliation_status = "reconciled"
            evt_record.processed_at = now
            db.commit()

        return {"status": "success", "payout_action_confirmed": action.id if action else None}

    if evt_record:
        evt_record.processing_state = "quarantined"
        evt_record.reconciliation_status = "unhandled_type"
        db.commit()

    return {"status": "unhandled_event_type", "event_type": event_type}
