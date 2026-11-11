from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from backend.app.db import get_db
from backend.app.models import Client, Invoice, PaymentHistory, Owner
from backend.app.auth.deps import get_verified_current_user

router = APIRouter(prefix="/clients", tags=["Clients & Payment Patterns"])


@router.get("")
def list_clients_with_patterns(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Returns clients and behavioral payment metrics scoped strictly to the authenticated user.
    """
    clients = db.query(Client).filter(Client.owner_id == current_user.id).all()
    results = []

    for c in clients:
        open_invs = db.query(Invoice).filter(
            Invoice.client_id == c.id,
            Invoice.status.in_(["SENT", "DRAFT"])
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
            "typical_invoice_amount": float(c.typical_invoice_amount),
            "relationship_weight": c.relationship_weight,
            "avg_delay_days": round(avg_delay, 1),
            "p_late": round(p_late, 2),
            "history_count": len(history),
            "is_seeded": is_seeded,
            "open_invoices": [
                {
                    "id": inv.id,
                    "paypal_invoice_id": inv.paypal_invoice_id,
                    "amount": float(inv.amount),
                    "currency": inv.currency,
                    "due_date": inv.due_date.strftime("%Y-%m-%d"),
                    "status": inv.status,
                    "discount_applied": float(inv.discount_applied),
                    "pay_link": inv.pay_link
                }
                for inv in open_invs
            ]
        })

    return results


@router.get("/{client_id}")
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Retrieves a single client profile with strict ownership verification."""
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.owner_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return {
        "id": client.id,
        "name": client.name,
        "email": client.email,
        "country": client.country,
        "typical_invoice_amount": float(client.typical_invoice_amount),
        "relationship_weight": client.relationship_weight,
        "is_seeded": client.is_seeded
    }
