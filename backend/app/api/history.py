from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import List
from backend.app.db import get_db
from backend.app.models import PaymentHistory, Invoice, Client
from backend.app.schemas import PaymentHistoryOut
from backend.app.paypal.client import paypal_client, PayPalError
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/history", tags=["Payment History"])


@router.get("", response_model=List[PaymentHistoryOut])
def list_payment_history(db: Session = Depends(get_db)):
    return db.query(PaymentHistory).order_by(PaymentHistory.paid_date.desc()).all()


@router.post("/sync")
async def sync_history(db: Session = Depends(get_db)):
    """Pulls recent transactions via PayPal Transaction Search and reconciles against invoices."""
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")
    end_date = now.strftime("%Y-%m-%dT23:59:59Z")

    try:
        data = await paypal_client.list_transactions(start_date=start_date, end_date=end_date)
        tx_details = data.get("transaction_details", [])
        reconciled_count = 0

        for item in tx_details:
            tx_info = item.get("transaction_info", {})
            payer_info = item.get("payer_info", {})
            amt_info = tx_info.get("transaction_amount", {})

            amount = float(amt_info.get("value", 0.0))
            if amount <= 0:
                continue

            payer_email = payer_info.get("email_address", "").lower()
            matching_client = db.query(Client).filter(Client.email == payer_email).first()
            if matching_client:
                # Find matching unpaid invoice
                inv = db.query(Invoice).filter(
                    Invoice.client_id == matching_client.id,
                    Invoice.status == "SENT"
                ).first()

                if inv:
                    inv.status = "PAID"
                    inv.paid_date = now
                    hist = PaymentHistory(
                        client_id=matching_client.id,
                        invoice_id=inv.id,
                        amount=amount,
                        due_date=inv.due_date,
                        paid_date=now,
                        days_late=max((now.date() - inv.due_date.date()).days, 0),
                        source="paypal"  # Real sandbox ingestion
                    )
                    db.add(hist)
                    reconciled_count += 1

        db.commit()

        append_audit_log(
            db=db,
            actor="system",
            event="TRANSACTION_HISTORY_SYNCED",
            payload={"transactions_found": len(tx_details), "reconciled_invoices": reconciled_count}
        )

        return {"success": True, "reconciled_count": reconciled_count, "transactions_pulled": len(tx_details)}
    except PayPalError as e:
        # In sandbox or demo mode if reporting endpoint is unavailable, return graceful explanation
        return {
            "success": False,
            "message": f"Sandbox reporting synchronization unavailable: {str(e)}. Relying on seeded history."
        }

