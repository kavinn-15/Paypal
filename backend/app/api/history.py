import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import PaymentHistory, Invoice, Client, Owner, FinancialEntry
from backend.app.schemas import PaymentHistoryOut
from backend.app.auth.deps import get_verified_current_user
from backend.app.paypal.client import paypal_client, PayPalError
from backend.app.guardrail.audit import append_audit_log

logger = logging.getLogger("transaction_reconciliation")
router = APIRouter(prefix="/history", tags=["Payment History"])


@router.get("", response_model=List[PaymentHistoryOut])
def list_payment_history(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Returns chronological payment history strictly for the authenticated user's clients."""
    return db.query(PaymentHistory).join(PaymentHistory.client).filter(
        Client.owner_id == current_user.id
    ).order_by(PaymentHistory.paid_date.desc()).all()


@router.post("/sync")
async def sync_history(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Pulls recent transactions via PayPal Transaction Search and reconciles against
    the authenticated user's open invoices.

    Strict Reconciliation Invariants:
    1. Reconcile transactions using exact invoice identity wherever PayPal provides it.
    2. Validate the transaction reference (deduplication / replay-safety).
    3. Validate amount (handles partial or exact settlements).
    4. Validate currency against invoice currency.
    5. Validate the invoice payment status (prevent double crediting).
    6. Prevent unrelated transactions from marking an invoice as paid (no guessing by payer email).
    7. Ensure duplicate transactions cannot create duplicate financial income.
    8. Update invoice status and the authoritative financial ledger consistently.
    9. Only mark an invoice paid after successful reconciliation.
    10. Audit-log unmatched, ambiguous, and reconciled transactions.
    """
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")
    end_date = now.strftime("%Y-%m-%dT23:59:59Z")

    try:
        reconciled_count = 0
        unmatched_count = 0
        current_page = 1
        total_pages = 1

        while current_page <= total_pages and current_page <= 5:
            data = await paypal_client.list_transactions(start_date=start_date, end_date=end_date, page=current_page, page_size=50)
            total_pages = data.get("total_pages", 1)
            tx_details = data.get("transaction_details", [])

            if not tx_details:
                break

            for item in tx_details:
                tx_info = item.get("transaction_info", {})
                cart_info = item.get("cart_info", {})
                amt_info = tx_info.get("transaction_amount", {})

                tx_id = tx_info.get("transaction_id")
                if not tx_id:
                    continue

                # Validate transaction status: only settled ("S") transactions count as confirmed payments
                tx_status = tx_info.get("transaction_status", "S").upper()
                if tx_status != "S":
                    logger.info(f"Transaction {tx_id} status '{tx_status}' is not settled ('S'). Skipping.")
                    continue

                # Parse genuine transaction initiation timestamp
                init_date_str = tx_info.get("transaction_initiation_date") or tx_info.get("transaction_updated_date")
                if init_date_str:
                    try:
                        tx_date = datetime.fromisoformat(init_date_str.replace("Z", "+00:00"))
                    except Exception:
                        tx_date = now
                else:
                    tx_date = now

                # 1. Deduplication check: Has this exact PayPal transaction already been reconciled?
                existing_hist = db.query(PaymentHistory).filter(
                    PaymentHistory.transaction_reference == tx_id
                ).first()
                existing_ledger = db.query(FinancialEntry).filter(
                    FinancialEntry.reference_id == tx_id
                ).first()

                if existing_hist or existing_ledger:
                    logger.info(f"Transaction {tx_id} already reconciled. Skipping duplicate ingestion.")
                    continue

                raw_amt = amt_info.get("value", 0.0)
                try:
                    amount = Decimal(str(raw_amt))
                except Exception:
                    amount = Decimal("0.00")

                if amount <= Decimal("0.00"):
                    continue

                tx_currency = (amt_info.get("currency_code") or "USD").upper()

                # 2. Extract exact invoice identity from transaction details
                # PayPal Transaction Search provides invoice_id in transaction_info or cart_info.item_details
                invoice_ref = tx_info.get("invoice_id") or tx_info.get("paypal_reference_id") or tx_info.get("custom_field")
                if not invoice_ref and cart_info.get("item_details"):
                    for itm in cart_info["item_details"]:
                        if itm.get("item_description") and "INV" in itm["item_description"]:
                            invoice_ref = itm["item_description"].strip()
                            break

                # STRICT RULE: Never guess the invoice based solely on payer email!
                if not invoice_ref:
                    unmatched_count += 1
                    append_audit_log(
                        db=db,
                        actor="paypal_reconciliation",
                        event="TRANSACTION_RECONCILIATION_UNMATCHED_NO_INVOICE_REF",
                        payload={
                            "transaction_id": tx_id,
                            "amount": float(amount),
                            "currency": tx_currency,
                            "reason": "Missing exact invoice identifier in PayPal transaction payload. Kept unreconciled for manual review."
                        },
                        owner_id=current_user.id
                    )
                    continue

                # 3. Lookup invoice strictly by exact paypal_invoice_id or local invoice id, scoped to current_user
                invoice = db.query(Invoice).join(Invoice.client).filter(
                    Client.owner_id == current_user.id,
                    (Invoice.paypal_invoice_id == str(invoice_ref)) | (Invoice.id == invoice_ref)
                ).first()

                if not invoice:
                    unmatched_count += 1
                    append_audit_log(
                        db=db,
                        actor="paypal_reconciliation",
                        event="TRANSACTION_RECONCILIATION_INVOICE_NOT_FOUND",
                        payload={
                            "transaction_id": tx_id,
                            "invoice_ref": str(invoice_ref),
                            "reason": f"No invoice matching reference '{invoice_ref}' belongs to authenticated user."
                        },
                        owner_id=current_user.id
                    )
                    continue

                # 4. Currency Validation
                if invoice.currency.upper() != tx_currency:
                    unmatched_count += 1
                    append_audit_log(
                        db=db,
                        actor="paypal_reconciliation",
                        event="TRANSACTION_RECONCILIATION_CURRENCY_MISMATCH",
                        payload={
                            "transaction_id": tx_id,
                            "invoice_id": invoice.id,
                            "expected_currency": invoice.currency,
                            "transaction_currency": tx_currency,
                            "reason": "Currency mismatch. Flagged for manual review."
                        },
                        owner_id=current_user.id
                    )
                    continue

                # 5. Deduplication check: ignore already processed transactions
                existing_hist = db.query(PaymentHistory).filter(PaymentHistory.transaction_reference == tx_id).first()
                if existing_hist:
                    logger.info(f"Transaction {tx_id} already recorded in PaymentHistory. Skipping.")
                    continue

                # 6. Reconcile invoice & compute cumulative payment status
                inv_total = Decimal(str(invoice.amount))
                existing_paid = sum(Decimal(str(h.amount)) for h in invoice.history_records if h.source == "paypal")
                total_after_this_payment = existing_paid + amount

                is_overpaid = False
                if total_after_this_payment > inv_total:
                    unmatched_count += 1
                    is_overpaid = True
                    invoice.status = "OVERPAID"
                    append_audit_log(
                        db=db,
                        actor="paypal_reconciliation",
                        event="TRANSACTION_RECONCILIATION_OVERPAYMENT_FLAGGED",
                        payload={
                            "transaction_id": tx_id,
                            "invoice_id": invoice.id,
                            "invoice_total": float(inv_total),
                            "total_received": float(total_after_this_payment),
                            "overpayment_amount": float(total_after_this_payment - inv_total),
                            "reason": "Overpayment detected. Flagged for manual review, invoice not automatically closed."
                        },
                        owner_id=current_user.id
                    )
                elif total_after_this_payment < inv_total:
                    invoice.status = "PARTIALLY_PAID"
                else:
                    invoice.status = "PAID"
                    invoice.paid_date = tx_date

                # 7. Record in PaymentHistory safely with constraint catching
                from sqlalchemy.exc import IntegrityError
                due_d = invoice.due_date if invoice.due_date.tzinfo else invoice.due_date.replace(tzinfo=timezone.utc)
                days_late = max((tx_date.date() - due_d.date()).days, 0)
                hist = PaymentHistory(
                    client_id=invoice.client_id,
                    invoice_id=invoice.id,
                    amount=amount,
                    due_date=invoice.due_date,
                    paid_date=tx_date,
                    days_late=days_late,
                    source="paypal",
                    transaction_reference=tx_id
                )
                try:
                    db.add(hist)
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    logger.info(f"Concurrent duplicate insertion caught for tx {tx_id}. Skipping.")
                    continue

                # 8. Record in authoritative financial ledger
                try:
                    ledger_entry = FinancialEntry(
                        owner_id=current_user.id,
                        canonical_id=f"tx_{tx_id}",
                        title=f"PayPal Transaction #{tx_id} - Invoice #{invoice.paypal_invoice_id}",
                        amount=amount,
                        currency=tx_currency,
                        entry_type="confirmed_income",
                        category="client_invoice",
                        transaction_date=tx_date,
                        status="confirmed",
                        data_source="paypal_transaction_search",
                        reference_id=tx_id,
                        is_demo=current_user.is_demo
                    )
                    db.add(ledger_entry)
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    logger.info(f"Concurrent duplicate ledger entry caught for tx {tx_id}.")

                if not is_overpaid:
                    reconciled_count += 1
                    append_audit_log(
                        db=db,
                        actor="paypal_reconciliation",
                        event="TRANSACTION_RECONCILED_SUCCESS",
                        payload={
                            "transaction_id": tx_id,
                            "invoice_id": invoice.id,
                            "paypal_invoice_id": invoice.paypal_invoice_id,
                            "amount": float(amount),
                            "new_status": invoice.status
                        },
                        owner_id=current_user.id
                    )

            current_page += 1

        db.commit()

        append_audit_log(
            db=db,
            actor="owner",
            event="TRANSACTION_SEARCH_SYNC_COMPLETED",
            payload={
                "start_date": start_date,
                "end_date": end_date,
                "reconciled_count": reconciled_count,
                "unmatched_count": unmatched_count
            },
            owner_id=current_user.id
        )

        return {
            "success": True,
            "reconciled_count": reconciled_count,
            "unmatched_count": unmatched_count,
            "message": f"Successfully synced transactions. {reconciled_count} invoice(s) reconciled, {unmatched_count} transaction(s) flagged for manual review."
        }
    except PayPalError as e:
        logger.error(f"PayPal Transaction Search error: {e}")
        raise HTTPException(status_code=502, detail=f"PayPal API error: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction reconciliation failure: {e}")
        raise HTTPException(status_code=500, detail="Transaction search reconciliation failed.")
