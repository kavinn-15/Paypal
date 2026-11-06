from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.app.db import get_db
from backend.app.models import Obligation, Owner
from backend.app.schemas import ObligationCreate, ObligationOut
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/obligations", tags=["Obligations"])


@router.get("", response_model=List[ObligationOut])
def list_obligations(db: Session = Depends(get_db)):
    return db.query(Obligation).order_by(Obligation.due_date.asc()).all()


@router.post("", response_model=ObligationOut)
def create_obligation(payload: ObligationCreate, db: Session = Depends(get_db)):
    owner = db.query(Owner).first()
    if not owner:
        raise HTTPException(status_code=400, detail="Owner record not found. Please run seed script.")

    obl = Obligation(
        owner_id=owner.id,
        payee_name=payload.payee_name,
        payee_email=payload.payee_email,
        amount=payload.amount,
        currency=payload.currency.upper(),
        due_date=payload.due_date,
        split_allowed=payload.split_allowed,
        status="pending"
    )
    db.add(obl)
    db.commit()
    db.refresh(obl)

    append_audit_log(
        db=db,
        actor="owner",
        event="OBLIGATION_CREATED",
        payload={
            "obligation_id": obl.id,
            "payee_name": obl.payee_name,
            "amount": obl.amount,
            "currency": obl.currency,
            "due_date": obl.due_date.isoformat(),
            "split_allowed": obl.split_allowed
        }
    )

    return ObligationOut.model_validate(obl)

