from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import datetime
from backend.app.db import get_db
from backend.app.models import Obligation, Owner
from backend.app.schemas import ObligationCreate, ObligationOut, ObligationConsentRequest
from backend.app.auth.deps import get_verified_current_user
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/obligations", tags=["Obligations"])


@router.get("", response_model=List[ObligationOut])
def list_obligations(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Lists obligations belonging strictly to the authenticated owner."""
    return db.query(Obligation).filter(
        Obligation.owner_id == current_user.id
    ).order_by(Obligation.due_date.asc()).all()


@router.get("/{obligation_id}", response_model=ObligationOut)
def get_obligation(
    obligation_id: int,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Retrieves a single obligation with strict ownership check."""
    obl = db.query(Obligation).filter(
        Obligation.id == obligation_id,
        Obligation.owner_id == current_user.id
    ).first()
    if not obl:
        raise HTTPException(status_code=404, detail="Obligation not found.")
    return ObligationOut.model_validate(obl)


@router.post("", response_model=ObligationOut, status_code=status.HTTP_201_CREATED)
def create_obligation(
    payload: ObligationCreate,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Creates a new contractor payment obligation for the authenticated user."""
    obl = Obligation(
        owner_id=current_user.id,
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
            "amount": float(obl.amount),
            "currency": obl.currency,
            "due_date": obl.due_date.isoformat(),
            "split_allowed": obl.split_allowed
        },
        owner_id=current_user.id
    )

    return ObligationOut.model_validate(obl)


@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_obligation(
    obligation_id: int,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Deletes an obligation belonging to the authenticated owner."""
    obl = db.query(Obligation).filter(
        Obligation.id == obligation_id,
        Obligation.owner_id == current_user.id
    ).first()
    if not obl:
        raise HTTPException(status_code=404, detail="Obligation not found.")

    append_audit_log(
        db=db,
        actor="owner",
        event="OBLIGATION_DELETED",
        payload={"obligation_id": obl.id, "payee_name": obl.payee_name, "amount": float(obl.amount)},
        owner_id=current_user.id
    )
    db.delete(obl)
    db.commit()
    return None


@router.post("/{obligation_id}/consent", response_model=ObligationOut)
def record_contractor_consent(
    obligation_id: int,
    payload: ObligationConsentRequest,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Legitimately records auditable contractor consent for installment splits (Plan C requirement).
    Enforces ownership validation, captures consent source, audit timestamp, and optional terms notes.
    """
    obl = db.query(Obligation).filter(
        Obligation.id == obligation_id,
        Obligation.owner_id == current_user.id
    ).first()
    if not obl:
        raise HTTPException(status_code=404, detail="Obligation not found.")

    obl.split_allowed = payload.split_allowed
    obl.split_consent_recorded = payload.split_allowed
    obl.split_consent_source = payload.consent_source if payload.split_allowed else None
    obl.split_consent_timestamp = datetime.datetime.utcnow() if payload.split_allowed else None
    obl.split_consent_is_simulated = payload.is_simulated if payload.split_allowed else False
    if payload.split_allowed:
        obl.status = "split_agreed"
    elif obl.status == "split_agreed":
        obl.status = "pending"

    db.commit()
    db.refresh(obl)

    append_audit_log(
        db=db,
        actor="owner",
        event="CONTRACTOR_CONSENT_RECORDED",
        payload={
            "obligation_id": obl.id,
            "payee_name": obl.payee_name,
            "payee_email": obl.payee_email,
            "split_allowed": obl.split_allowed,
            "consent_source": obl.split_consent_source,
            "is_simulated": obl.split_consent_is_simulated,
            "consent_notes": payload.consent_notes,
            "timestamp": obl.split_consent_timestamp.isoformat() if obl.split_consent_timestamp else None
        },
        owner_id=current_user.id
    )

    return ObligationOut.model_validate(obl)
