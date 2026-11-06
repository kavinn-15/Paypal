from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from backend.app.db import get_db
from backend.app.models import Client, Invoice, PaymentHistory

router = APIRouter(prefix="/clients", tags=["Clients & Payment Patterns"])


@router.get("")
def list_clients_with_patterns(db: Session = Depends(get_db)):
    """
    Returns clients with open invoices, historical average delay,
    reliability metrics, and badges.
    """
    clients = db.query(Client).all()
    results = []

    for c in clients:
        open_invs = db.query(Invoice).filter(
            Invoice.client_id == c.id,
            Invoice.status == "SENT"
        ).all()

        history = db.query(PaymentHistory).filter(PaymentHistory.client_id == c.id).all()
        delays = [h.days_late for h in history]
        avg_delay = sum(delays) / len(delays) if delays else 0.0
        p_late = sum(1 for d in delays if d > 0) / len(delays) if delays else 0.5
        is_seeded = any(h.source == "seeded" for h in history)

        results.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "country": c.country,
            "typical_invoice_amount": c.typical_invoice_amount,
            "relationship_weight": c.relationship_weight,
            "avg_delay_days": round(avg_delay, 1),
            "p_late": round(p_late, 2),
            "history_count": len(history),
            "is_seeded": is_seeded,
            "open_invoices": [
                {
                    "id": inv.id,
                    "paypal_invoice_id": inv.paypal_invoice_id,
                    "amount": inv.amount,
                    "currency": inv.currency,
                    "due_date": inv.due_date.strftime("%Y-%m-%d"),
                    "status": inv.status,
                    "discount_applied": inv.discount_applied,
                    "pay_link": inv.pay_link
                }
                for inv in open_invs
            ]
        })

    return results

