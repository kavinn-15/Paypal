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

        # Locate payment records in payload
        # Support:
        # 1. payments as an array of payment records: [{"payment_id": "...", "amount": ...}]
        # 2. payments as an object containing a transactions array: {"transactions": [{"payment_id": "...", ...}]}
        # 3. payments as an object containing a payments array
        # 4. transactions array at resource or inv_data level
        raw_payments = inv_data.get("payments")
        if raw_payments is None:
            raw_payments = resource.get("payments")

        payments_list = []
        has_payments_structure = False

        if isinstance(raw_payments, list):
            payments_list = [p for p in raw_payments if isinstance(p, dict)]
            has_payments_structure = True
        elif isinstance(raw_payments, dict):
            has_payments_structure = True
            txs = raw_payments.get("transactions")
            if txs is None:
                txs = raw_payments.get("payments")
            if isinstance(txs, list):
                payments_list = [p for p in txs if isinstance(p, dict)]
        elif isinstance(inv_data.get("transactions"), list):
            payments_list = [p for p in inv_data.get("transactions") if isinstance(p, dict)]
            has_payments_structure = True
        elif isinstance(resource.get("transactions"), list):
            payments_list = [p for p in resource.get("transactions") if isinstance(p, dict)]
            has_payments_structure = True

        def get_record_ref(item: dict) -> Optional[str]:
            return (
                item.get("payment_id")
                or item.get("transaction_id")
                or item.get("capture_id")
            )

        target_payment = None
        tx_ref = None

        # Check if an explicit transaction / payment reference was specified at resource level
        explicit_ref = (
            resource.get("transaction_id")
            or resource.get("capture_id")
            or resource.get("payment_id")
        )
        if not explicit_ref:
            res_id = resource.get("id")
            if res_id and res_id != paypal_inv_id:
                explicit_ref = res_id

        if has_payments_structure:
            if explicit_ref:
                # Find matching payment record by explicit ref
                matching = [
                    p for p in payments_list
                    if get_record_ref(p) == explicit_ref
                ]
                if len(matching) == 1:
                    target_payment = matching[0]
                    tx_ref = explicit_ref
                elif len(matching) > 1:
                    logger.warning(f"Ambiguous payments in invoice {paypal_inv_id}: multiple matches for reference {explicit_ref}")
                    if evt_record:
                        evt_record.processing_state = "quarantined"
                        evt_record.reconciliation_status = "manual_review_required"
                        evt_record.error_details = f"Ambiguous payments: multiple payment records match reference {explicit_ref}"
                        db.commit()
                    return {"status": "quarantined", "reason": "ambiguous_payment_records", "paypal_invoice_id": paypal_inv_id}
                elif len(matching) == 0 and len(payments_list) > 1:
                    logger.warning(f"Ambiguous payments in invoice {paypal_inv_id}: reference {explicit_ref} matched none of {len(payments_list)} payments")
                    if evt_record:
                        evt_record.processing_state = "quarantined"
                        evt_record.reconciliation_status = "manual_review_required"
                        evt_record.error_details = f"Ambiguous payments: explicit reference {explicit_ref} did not match any of {len(payments_list)} transactions"
                        db.commit()
                    return {"status": "quarantined", "reason": "ambiguous_payment_records", "paypal_invoice_id": paypal_inv_id}

            if not target_payment:
                if len(payments_list) == 1:
                    target_payment = payments_list[0]
                    tx_ref = get_record_ref(target_payment) or explicit_ref
                elif len(payments_list) > 1:
                    # Filter for unrecorded payments
                    unrecorded = []
                    for p in payments_list:
                        p_id = get_record_ref(p)
                        if p_id:
                            exists = db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == p_id).first()
                            if not exists:
                                unrecorded.append((p, p_id))
                    if len(unrecorded) == 1:
                        target_payment, tx_ref = unrecorded[0]
                    elif len(unrecorded) > 1:
                        # Ambiguous: multiple unrecorded payment records present in a single webhook without an identifiable target
                        logger.warning(f"Ambiguous payments in invoice {paypal_inv_id}: {len(unrecorded)} unrecorded payment entries in payload")
                        if evt_record:
                            evt_record.processing_state = "quarantined"
                            evt_record.reconciliation_status = "manual_review_required"
                            evt_record.error_details = f"Ambiguous payments: payload contains {len(unrecorded)} unrecorded payment records without identifiable target"
                            db.commit()
                        return {"status": "quarantined", "reason": "ambiguous_payment_records", "paypal_invoice_id": paypal_inv_id}
                    elif len(unrecorded) == 0 and len(payments_list) > 0:
                        # All payments in the list were already processed
                        tx_ref = get_record_ref(payments_list[-1]) or explicit_ref
                        return {
                            "status": "already_processed",
                            "reason": "duplicate_transaction_reference",
                            "transaction_reference": tx_ref,
                            "paypal_invoice_id": paypal_inv_id
                        }
        else:
            # No payments structure; use resource-level explicit reference
            tx_ref = explicit_ref

        if not tx_ref:
            if is_simulated:
                tx_ref = resource.get("transaction_id") or f"sim_tx_{event_id}"
            else:
                logger.warning(
                    f"Webhook event {event_id} for invoice {paypal_inv_id} lacks genuine transaction reference. Quarantining for manual review."
                )
                if evt_record:
                    evt_record.processing_state = "quarantined"
                    evt_record.processed = False
                    evt_record.reconciliation_status = "manual_review_required"
                    evt_record.error_details = "Missing genuine PayPal transaction reference (no payment_id, transaction_id, or capture_id found)"
                    evt_record.processed_at = now
                    db.commit()
                append_audit_log(
                    db=db,
                    actor="paypal_webhook",
                    event="WEBHOOK_MISSING_TRANSACTION_REF_QUARANTINED",
                    payload={"paypal_invoice_id": paypal_inv_id, "event_id": event_id},
                    owner_id=owner.id if owner else None
                )
                return {
                    "status": "quarantined",
                    "reason": "missing_transaction_reference",
                    "paypal_invoice_id": paypal_inv_id,
                    "event_id": event_id
                }

        # Extract actual individual payment amount and currency
        raw_amt = None
        raw_currency = None

        if target_payment:
            # When an individual transaction has been identified:
            # Amount and currency MUST come from target_payment.
            # Never substitute invoice total or resource-level invoice amount!
            p_amt = target_payment.get("amount")
            if isinstance(p_amt, dict):
                raw_amt = p_amt.get("value")
                raw_currency = p_amt.get("currency_code")
            elif p_amt is not None:
                raw_amt = p_amt

            if not raw_currency:
                raw_currency = target_payment.get("currency_code") or target_payment.get("currency")

            # CRITICAL: If an identified payment record is missing its amount,
            # NEVER fall back to resource.amount or invoice total!
            if raw_amt is None:
                logger.warning(
                    f"Identified payment transaction {tx_ref} in invoice {paypal_inv_id} lacks an individual payment amount. "
                    "Refusing to substitute invoice total."
                )
                if evt_record:
                    evt_record.processing_state = "quarantined"
                    evt_record.reconciliation_status = "manual_review_required"
                    evt_record.error_details = (
                        f"Payment transaction {tx_ref} missing individual payment amount. "
                        "Fallback to invoice total is strictly disallowed."
                    )
                    db.commit()
                append_audit_log(
                    db=db,
                    actor="paypal_webhook" if not is_simulated else "dev_simulator",
                    event="WEBHOOK_MISSING_PAYMENT_AMOUNT_QUARANTINED",
                    payload={"paypal_invoice_id": paypal_inv_id, "event_id": event_id, "transaction_ref": tx_ref},
                    owner_id=owner.id if owner else None
                )
                return {
                    "status": "quarantined",
                    "reason": "missing_payment_amount",
                    "paypal_invoice_id": paypal_inv_id,
                    "transaction_reference": tx_ref
                }

            # CRITICAL: When target_payment has been identified, obtain currency exclusively
            # from that individual payment record.
            # If its currency is missing, invalid, or ambiguous, quarantine the webhook for manual review.
            # Do NOT substitute currency from inv_data.amount, resource.amount, or invoice.currency!
            if not is_simulated:
                if not raw_currency or not isinstance(raw_currency, str) or not raw_currency.strip():
                    logger.warning(
                        f"Identified payment transaction {tx_ref} in invoice {paypal_inv_id} lacks its own currency. "
                        "Refusing to infer currency from invoice or resource."
                    )
                    if evt_record:
                        evt_record.processing_state = "quarantined"
                        evt_record.reconciliation_status = "manual_review_required"
                        evt_record.error_details = (
                            f"Payment transaction {tx_ref} missing individual currency. "
                            "Fallback to invoice currency is strictly disallowed."
                        )
                        db.commit()
                    append_audit_log(
                        db=db,
                        actor="paypal_webhook",
                        event="WEBHOOK_MISSING_PAYMENT_CURRENCY_QUARANTINED",
                        payload={"paypal_invoice_id": paypal_inv_id, "event_id": event_id, "transaction_ref": tx_ref},
                        owner_id=owner.id if owner else None
                    )
                    return {
                        "status": "quarantined",
                        "reason": "missing_payment_currency",
                        "paypal_invoice_id": paypal_inv_id,
                        "transaction_reference": tx_ref
                    }
        else:
            if has_payments_structure:
                # Payments structure was present, but no target payment could be established
                logger.warning(f"Payload has payments structure but no valid target payment could be determined.")
                if evt_record:
                    evt_record.processing_state = "quarantined"
                    evt_record.reconciliation_status = "manual_review_required"
                    evt_record.error_details = "Ambiguous payments structure without identifiable target payment"
                    db.commit()
                return {"status": "quarantined", "reason": "ambiguous_payment_records", "paypal_invoice_id": paypal_inv_id}

            # Flat event structure without nested payments array (e.g. direct capture or simulated event)
            res_amt = resource.get("amount")
            if isinstance(res_amt, dict):
                raw_amt = res_amt.get("value")
                raw_currency = res_amt.get("currency_code")
            elif res_amt is not None:
                raw_amt = res_amt

            if not raw_currency:
                raw_currency = resource.get("currency_code") or resource.get("currency")

        # Inferred / missing amounts MUST NOT be assumed from invoice.amount for genuine webhooks
        if raw_amt is None:
            if is_simulated:
                raw_amt = invoice.amount
            else:
                logger.warning(f"Webhook event {event_id} for invoice {paypal_inv_id} lacks verified payment amount. Quarantining.")
                if evt_record:
                    evt_record.processing_state = "quarantined"
                    evt_record.reconciliation_status = "manual_review_required"
                    evt_record.error_details = "Missing verified payment amount. Inferred invoice total is strictly disallowed."
                    db.commit()
                append_audit_log(
                    db=db,
                    actor="paypal_webhook",
                    event="WEBHOOK_MISSING_PAYMENT_AMOUNT_QUARANTINED",
                    payload={"paypal_invoice_id": paypal_inv_id, "event_id": event_id},
                    owner_id=owner.id if owner else None
                )
                return {"status": "quarantined", "reason": "missing_payment_amount", "paypal_invoice_id": paypal_inv_id}

        try:
            paid_amount = Decimal(str(raw_amt))
            if paid_amount <= 0:
                raise ValueError("Payment amount must be greater than zero")
        except Exception as e:
            if evt_record:
                evt_record.processing_state = "quarantined"
                evt_record.reconciliation_status = "manual_review_required"
                evt_record.error_details = f"Invalid payment amount '{raw_amt}': {e}"
                db.commit()
            return {"status": "quarantined", "reason": "invalid_payment_amount", "paypal_invoice_id": paypal_inv_id}

        # Currency validation
        if is_simulated:
            # Preserve simulated payment behavior
            if not raw_currency or not isinstance(raw_currency, str) or not raw_currency.strip():
                raw_currency = invoice.currency
        else:
            # Genuine payment events: BOTH individual payment records AND flat structures
            # require an explicit, valid string currency.
            # Never substitute invoice.currency or infer currency when missing.
            # Quarantine missing, empty, malformed, or non-string currencies for manual review.
            if not isinstance(raw_currency, str) or not raw_currency.strip() or not raw_currency.strip().isalpha():
                logger.warning(
                    f"Genuine payment event for invoice {invoice.paypal_invoice_id} lacks a valid string currency (got: {repr(raw_currency)}). "
                    "Quarantining for manual review."
                )
                if evt_record:
                    evt_record.processing_state = "quarantined"
                    evt_record.reconciliation_status = "manual_review_required"
                    evt_record.error_details = (
                        f"Missing or malformed payment currency (got: {repr(raw_currency)}). "
                        "Fallback to invoice currency is strictly disallowed."
                    )
                    db.commit()
                append_audit_log(
                    db=db,
                    actor="paypal_webhook",
                    event="WEBHOOK_MISSING_PAYMENT_CURRENCY_QUARANTINED",
                    payload={"paypal_invoice_id": invoice.paypal_invoice_id, "event_id": event_id, "currency": str(raw_currency)},
                    owner_id=owner.id if owner else None
                )
                return {
                    "status": "quarantined",
                    "reason": "missing_payment_currency",
                    "paypal_invoice_id": invoice.paypal_invoice_id,
                    "currency": raw_currency
                }

        # Safe type-checked currency comparison (guaranteed string here)
        clean_currency = raw_currency.strip().upper()
        if clean_currency != invoice.currency.upper():
            logger.warning(
                f"Currency mismatch on invoice {invoice.paypal_invoice_id}: expected {invoice.currency}, got {clean_currency}"
            )
            if evt_record:
                evt_record.processing_state = "quarantined"
                evt_record.reconciliation_status = "manual_review_required"
                evt_record.error_details = f"Currency mismatch: expected {invoice.currency}, received {clean_currency}"
                db.commit()
            append_audit_log(
                db=db,
                actor="paypal_webhook" if not is_simulated else "dev_simulator",
                event="CURRENCY_MISMATCH_QUARANTINED",
                payload={"paypal_invoice_id": invoice.paypal_invoice_id, "expected_currency": invoice.currency, "received_currency": clean_currency},
                owner_id=owner.id if owner else None
            )
            return {
                "status": "quarantined",
                "reason": "currency_mismatch",
                "expected_currency": invoice.currency,
                "received_currency": clean_currency
            }

        due_d = invoice.due_date if invoice.due_date.tzinfo else invoice.due_date.replace(tzinfo=timezone.utc)
        days_late = max((now.date() - due_d.date()).days, 0)
        inv_total = Decimal(str(invoice.amount))

        if is_simulated:
            # SIMULATED PAYMENTS: NEVER mutate authoritative invoice payment state to PAID or create authoritative PaymentHistory
            invoice.is_simulated_paid = True
            total_cumulative = Decimal(str(paid_amount))
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
            # GENUINE PAYPAL WEBHOOK:
            from sqlalchemy.exc import IntegrityError

            # 1. Unique transaction reference deduplication / replay check
            existing_tx = db.query(PaymentHistory).filter(
                PaymentHistory.transaction_reference == tx_ref
            ).first()
            if existing_tx:
                logger.info(f"Transaction reference {tx_ref} already recorded for invoice {invoice.paypal_invoice_id}. Ignoring duplicate delivery.")
                if evt_record:
                    evt_record.processing_state = "processed"
                    evt_record.processed = True
                    if evt_record.reconciliation_status != "manual_review_required":
                        evt_record.reconciliation_status = "reconciled"
                    evt_record.processed_at = now
                    db.commit()
                return {
                    "status": "already_processed",
                    "reason": "duplicate_transaction_reference",
                    "transaction_reference": tx_ref,
                    "invoice_id": invoice.id,
                    "paypal_invoice_id": invoice.paypal_invoice_id
                }

            # 2. Record genuine PaymentHistory safely with constraint catching
            try:
                history_entry = PaymentHistory(
                    client_id=invoice.client_id,
                    invoice_id=invoice.id,
                    amount=paid_amount,
                    due_date=invoice.due_date,
                    paid_date=now,
                    days_late=days_late,
                    source="paypal",
                    transaction_reference=tx_ref
                )
                db.add(history_entry)
                db.flush()
            except IntegrityError:
                db.rollback()
                logger.info(f"Concurrent duplicate insertion caught for tx_ref {tx_ref}. Treating as already processed.")
                if evt_record:
                    evt_record.processing_state = "processed"
                    evt_record.processed = True
                    if evt_record.reconciliation_status != "manual_review_required":
                        evt_record.reconciliation_status = "reconciled"
                    evt_record.processed_at = now
                    db.commit()
                return {
                    "status": "already_processed",
                    "reason": "duplicate_transaction_reference",
                    "transaction_reference": tx_ref,
                    "invoice_id": invoice.id,
                    "paypal_invoice_id": invoice.paypal_invoice_id
                }

            # 3. Calculate cumulative verified receipts for this invoice
            from sqlalchemy import func
            total_cumulative = db.query(func.coalesce(func.sum(PaymentHistory.amount), Decimal("0.00"))).filter(
                PaymentHistory.invoice_id == invoice.id,
                PaymentHistory.source == "paypal"
            ).scalar()
            inv_total = Decimal(str(invoice.amount))

            # 4. Authoritative status update based on cumulative verified total
            if total_cumulative > inv_total:
                excess = total_cumulative - inv_total
                logger.warning(
                    f"Overpayment detected for invoice {invoice.paypal_invoice_id}: cumulative {total_cumulative} > total {inv_total} (excess {excess}). Flagging for manual review."
                )
                invoice.status = "OVERPAID"
                if evt_record:
                    evt_record.processing_state = "quarantined"
                    evt_record.reconciliation_status = "manual_review_required"
                    evt_record.error_details = f"Overpayment detected: cumulative verified {total_cumulative} exceeds invoice total {inv_total} by {excess}"
                append_audit_log(
                    db=db,
                    actor="paypal_webhook",
                    event="OVERPAYMENT_FLAGGED_FOR_MANUAL_REVIEW",
                    payload={
                        "paypal_invoice_id": invoice.paypal_invoice_id,
                        "invoice_amount": float(inv_total),
                        "cumulative_received": float(total_cumulative),
                        "excess_amount": float(excess),
                        "transaction_reference": tx_ref
                    },
                    owner_id=owner.id if owner else None
                )
            elif total_cumulative < inv_total:
                invoice.status = "PARTIALLY_PAID"
            else:
                invoice.status = "PAID"
                invoice.paid_date = now
                invoice.is_simulated_paid = False

            # 5. Authoritative confirmed income entry in financial ledger (deduplicated by tx_ref)
            if owner:
                existing_ledger = db.query(FinancialEntry).filter(
                    FinancialEntry.owner_id == owner.id,
                    (FinancialEntry.canonical_id == f"pay_{tx_ref}") | (FinancialEntry.reference_id == tx_ref)
                ).first()
                if not existing_ledger:
                    try:
                        ledger_entry = FinancialEntry(
                            owner_id=owner.id,
                            canonical_id=f"pay_{tx_ref}",
                            title=f"PayPal Invoice Payment #{invoice.paypal_invoice_id} ({invoice.client.name}) - Ref {tx_ref[:10]}",
                            amount=paid_amount,
                            currency=invoice.currency,
                            entry_type="confirmed_income",
                            category="client_invoice",
                            transaction_date=now,
                            status="confirmed",
                            data_source="paypal_webhook",
                            reference_id=tx_ref,
                            is_demo=False
                        )
                        db.add(ledger_entry)
                        db.flush()
                    except IntegrityError:
                        db.rollback()
                        logger.info(f"Concurrent duplicate ledger entry caught for tx_ref {tx_ref}.")

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
        updated_forecast = None
        try:
            forecaster = ForecasterAgent(db)
            updated_forecast = forecaster.run_forecast(
                obligation_id=None,
                starting_balance=reconciled_balance,
                owner_id=owner.id if owner else None
            )
        except Exception as e:
            logger.warning(f"Forecast recalculation skipped after payment: {e}")
            updated_forecast = None

        shortfall_remaining = updated_forecast.shortfall_amount if updated_forecast is not None else None

        if not is_simulated and total_cumulative > inv_total:
            excess = total_cumulative - inv_total
            if evt_record:
                evt_record.processing_state = "quarantined"
                evt_record.processed = False
                evt_record.reconciliation_status = "manual_review_required"
                evt_record.processed_at = now
                db.commit()
            return {
                "status": "flagged_manual_review",
                "reason": "overpayment_detected",
                "invoice_id": invoice.id,
                "paypal_invoice_id": invoice.paypal_invoice_id,
                "invoice_amount": float(inv_total),
                "cumulative_received": float(total_cumulative),
                "excess_amount": float(excess),
                "reconciled_balance": reconciled_balance,
                "is_simulated": is_simulated
            }

        if evt_record:
            if evt_record.reconciliation_status != "manual_review_required":
                evt_record.reconciliation_status = "reconciled"
                evt_record.processing_state = "processed"
                evt_record.processed = True
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
                "shortfall_remaining": shortfall_remaining,
                "action_confirmed": action.id if action else None,
                "is_simulated": is_simulated
            },
            owner_id=owner.id if owner else None
        )

        remaining_balance = float(max(inv_total - total_cumulative, Decimal("0.00")))
        return {
            "status": "success",
            "invoice_id": invoice.id,
            "paypal_invoice_id": invoice.paypal_invoice_id,
            "action_confirmed": action.id if action else None,
            "reconciled_balance": reconciled_balance,
            "shortfall_amount": shortfall_remaining,
            "remaining_balance": remaining_balance,
            "is_simulated": is_simulated
        }

    elif event_type == "PAYMENT.PAYOUTS-ITEM.SUCCEEDED":
        sender_batch_id = (
            resource.get("sender_batch_id")
            or resource.get("payout_batch_id")
            or resource.get("batch_header", {}).get("sender_batch_header", {}).get("sender_batch_id")
        )
        sender_item_id = resource.get("payout_item", {}).get("sender_item_id") or resource.get("sender_item_id")

        action = None
        if sender_batch_id:
            action = db.query(Action).filter(Action.idempotency_key == sender_batch_id).first()
        if not action and sender_item_id:
            action = db.query(Action).filter(
                (Action.idempotency_key == sender_item_id) | (Action.paypal_ref == sender_item_id)
            ).first()

        # Extract payout item amount, currency, recipient
        p_item = resource.get("payout_item") or resource
        raw_p_amount = None
        raw_p_currency = None
        amt_obj = p_item.get("amount") or resource.get("amount")
        if isinstance(amt_obj, dict):
            raw_p_amount = amt_obj.get("value")
            raw_p_currency = amt_obj.get("currency") or amt_obj.get("currency_code")
        elif amt_obj is not None:
            raw_p_amount = amt_obj

        p_receiver = p_item.get("receiver") or resource.get("receiver")

        # Validate action matching and verification rules
        is_matched = False
        mismatch_reason = None

        if not action:
            mismatch_reason = f"No corresponding Action found for sender_batch_id '{sender_batch_id}'"
        elif action.state not in (ActionState.APPROVED, ActionState.EXECUTING, ActionState.EXECUTED, ActionState.SIMULATED):
            mismatch_reason = f"Action {action.id} is in invalid state '{action.state}' for confirmation"
        elif not action.owner_id:
            mismatch_reason = f"Action {action.id} has no assigned owner_id"
        else:
            # Check amount, currency, recipient
            if raw_p_amount is not None:
                p_amt_dec = Decimal(str(raw_p_amount))
                act_amt_dec = Decimal(str(action.amount))
                if abs(p_amt_dec - act_amt_dec) > Decimal("0.01"):
                    mismatch_reason = f"Payout amount mismatch: action={act_amt_dec}, payout={p_amt_dec}"

            if not mismatch_reason and raw_p_currency and action.currency:
                if raw_p_currency.upper().strip() != action.currency.upper().strip():
                    mismatch_reason = f"Payout currency mismatch: action={action.currency}, payout={raw_p_currency}"

            if not mismatch_reason and p_receiver and action.recipient:
                if p_receiver.strip().lower() != action.recipient.strip().lower():
                    act_email = getattr(action, "payout_recipient_email", None)
                    if not act_email or p_receiver.strip().lower() != act_email.strip().lower():
                        mismatch_reason = f"Payout receiver mismatch: action={action.recipient}, payout={p_receiver}"

            if not mismatch_reason:
                is_matched = True

        if not is_matched:
            logger.warning(f"Unmatched or conflicting payout event {event_id}: {mismatch_reason}. Quarantining.")
            if evt_record:
                evt_record.processing_state = "quarantined"
                evt_record.reconciliation_status = "manual_review_required"
                evt_record.error_details = mismatch_reason
                evt_record.processed = False
                evt_record.processed_at = now
                if action and action.owner_id:
                    evt_record.owner_id = action.owner_id
                db.commit()
            append_audit_log(
                db=db,
                actor="paypal_webhook" if not is_simulated else "dev_simulator",
                event="UNMATCHED_PAYOUT_QUARANTINED",
                payload={
                    "event_id": event_id,
                    "sender_batch_id": sender_batch_id,
                    "reason": mismatch_reason,
                    "action_id": action.id if action else None
                },
                owner_id=action.owner_id if action else None
            )
            return {
                "status": "quarantined",
                "reason": "unmatched_payout_action",
                "details": mismatch_reason
            }

        # Transition Action state
        if is_simulated:
            GuardrailStateMachine.transition(
                db=db,
                action=action,
                target_state=ActionState.SIMULATED,
                actor="dev_simulator"
            )
            action.is_simulated = True
            action.confirmed_at = None
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
            evt_record.reconciliation_status = "reconciled"
            evt_record.processing_state = "processed"
            evt_record.processed = True
            evt_record.processed_at = now
            evt_record.owner_id = action.owner_id
            db.commit()

        append_audit_log(
            db=db,
            actor="paypal_webhook" if not is_simulated else "dev_simulator",
            event="PAYOUT_CONFIRMED_RECONCILED",
            payload={
                "action_id": action.id,
                "amount": float(action.amount),
                "recipient": action.recipient,
                "sender_batch_id": sender_batch_id,
                "is_simulated": is_simulated
            },
            owner_id=action.owner_id
        )

        return {"status": "success", "payout_action_confirmed": action.id}

    elif event_type in (
        "PAYMENT.PAYOUTS-ITEM.FAILED",
        "PAYMENT.PAYOUTS-ITEM.CANCELED",
        "PAYMENT.PAYOUTS-ITEM.DENIED",
        "PAYMENT.PAYOUTS-ITEM.BLOCKED"
    ):
        sender_batch_id = (
            resource.get("sender_batch_id")
            or resource.get("payout_batch_id")
            or resource.get("batch_header", {}).get("sender_batch_header", {}).get("sender_batch_id")
        )
        action = None
        if sender_batch_id:
            action = db.query(Action).filter(Action.idempotency_key == sender_batch_id).first()

        error_data = resource.get("errors") or resource.get("payout_item_fee") or resource.get("transaction_status")
        err_msg = str(error_data) if error_data else f"Payout failed: {event_type}"

        if action and action.state in (ActionState.APPROVED, ActionState.EXECUTING, ActionState.EXECUTED, ActionState.SIMULATED):
            try:
                GuardrailStateMachine.transition(
                    db=db,
                    action=action,
                    target_state=ActionState.FAILED,
                    actor="paypal_webhook",
                    error_message=err_msg
                )
                action.error_details = err_msg
                db.commit()
            except Exception as tr_err:
                logger.warning(f"Error transitioning action {action.id} to FAILED: {tr_err}")

        if evt_record:
            evt_record.processing_state = "processed"
            evt_record.processed = True
            evt_record.reconciliation_status = "payout_failed"
            evt_record.error_details = err_msg
            evt_record.processed_at = now
            if action and action.owner_id:
                evt_record.owner_id = action.owner_id
            db.commit()

        append_audit_log(
            db=db,
            actor="paypal_webhook",
            event="PAYOUT_EXECUTION_FAILED",
            payload={
                "event_id": event_id,
                "event_type": event_type,
                "sender_batch_id": sender_batch_id,
                "error": err_msg,
                "action_id": action.id if action else None
            },
            owner_id=action.owner_id if action else None
        )
        return {"status": "success", "payout_action_failed": action.id if action else None, "event_type": event_type}

    elif event_type in (
        "PAYMENT.CAPTURE.REFUNDED",
        "PAYMENT.CAPTURE.REVERSED",
        "INVOICING.INVOICE.REFUNDED"
    ):
        paypal_inv_id = (
            resource.get("invoice_id")
            or resource.get("custom_id")
            or resource.get("invoice", {}).get("id")
        )
        refund_tx_ref = resource.get("id") or resource.get("refund_id") or f"ref_{event_id}"
        amt_obj = resource.get("amount") or resource.get("total_refunded_amount")
        refund_amt_raw = amt_obj.get("value") if isinstance(amt_obj, dict) else amt_obj
        refund_curr = amt_obj.get("currency_code") or amt_obj.get("currency") if isinstance(amt_obj, dict) else None

        invoice = None
        if paypal_inv_id:
            invoice = db.query(Invoice).filter(Invoice.paypal_invoice_id == paypal_inv_id).first()

        if not invoice:
            logger.warning(f"Refund event {event_id} cannot be matched to an invoice (id={paypal_inv_id}). Quarantining.")
            if evt_record:
                evt_record.processing_state = "quarantined"
                evt_record.reconciliation_status = "manual_review_required"
                evt_record.error_details = f"Refund event cannot be matched to invoice '{paypal_inv_id}'"
                evt_record.processed = False
                evt_record.processed_at = now
                db.commit()
            append_audit_log(
                db=db,
                actor="paypal_webhook",
                event="UNMATCHED_REFUND_QUARANTINED",
                payload={"event_id": event_id, "paypal_invoice_id": paypal_inv_id, "resource": resource}
            )
            return {"status": "quarantined", "reason": "invoice_not_found_for_refund", "paypal_invoice_id": paypal_inv_id}

        owner = invoice.client.owner if invoice.client else None
        if evt_record and owner:
            evt_record.owner_id = owner.id

        refund_amt = Decimal(str(refund_amt_raw)) if refund_amt_raw else Decimal(str(invoice.amount))

        # Check for duplicate refund processing by transaction reference
        existing_refund_entry = None
        if owner:
            existing_refund_entry = db.query(FinancialEntry).filter(
                FinancialEntry.owner_id == owner.id,
                FinancialEntry.reference_id == refund_tx_ref
            ).first()

        if not existing_refund_entry and owner:
            refund_entry = FinancialEntry(
                owner_id=owner.id,
                canonical_id=f"refund_{refund_tx_ref}",
                title=f"Refund/Reversal for Invoice #{invoice.paypal_invoice_id} ({invoice.client.name})",
                amount=refund_amt,
                currency=refund_curr or invoice.currency,
                entry_type="confirmed_expense",
                category="refund",
                transaction_date=now,
                status="confirmed",
                data_source="paypal_webhook",
                reference_id=refund_tx_ref,
                is_demo=False
            )
            db.add(refund_entry)

        # Update invoice status
        inv_amt = Decimal(str(invoice.amount))
        if refund_amt >= inv_amt:
            invoice.status = "REFUNDED"
        else:
            invoice.status = "PARTIALLY_REFUNDED"
        db.commit()

        if evt_record:
            evt_record.processing_state = "processed"
            evt_record.processed = True
            evt_record.reconciliation_status = "reconciled"
            evt_record.processed_at = now
            db.commit()

        append_audit_log(
            db=db,
            actor="paypal_webhook",
            event="WEBHOOK_REFUND_RECONCILED",
            payload={
                "paypal_invoice_id": invoice.paypal_invoice_id,
                "refund_amount": float(refund_amt),
                "status": invoice.status,
                "transaction_ref": refund_tx_ref
            },
            owner_id=owner.id if owner else None
        )
        return {
            "status": "success",
            "invoice_id": invoice.id,
            "paypal_invoice_id": invoice.paypal_invoice_id,
            "refund_amount": float(refund_amt),
            "invoice_status": invoice.status
        }

    if evt_record:
        evt_record.processing_state = "quarantined"
        evt_record.reconciliation_status = "unhandled_type"
        db.commit()

    return {"status": "unhandled_event_type", "event_type": event_type}
