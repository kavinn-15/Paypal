from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner, FinancialEntry
from backend.app.schemas import (
    FinancialEntryCreate, FinancialEntryOut, FinancialSummaryResponse
)
from backend.app.auth.deps import get_current_user
from backend.app.services.financial_service import FinancialService
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/finance", tags=["Financial Management & Timeline"])


@router.get("/summary", response_model=FinancialSummaryResponse)
def get_financial_summary(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Get authoritative cash summary: confirmed balance, 30d expected inflows/outflows,
    and emergency reserve ratio. Never conflates expected income with confirmed cash.
    """
    return FinancialService.get_summary(db, current_user)


@router.get("/timeline")
def get_financial_timeline(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Get chronological cash flow timeline distinguishing:
    - Confirmed money
    - Expected money
    - Estimated money
    - Simulated money
    """
    return FinancialService.get_timeline(db, current_user)


@router.post("/entries", response_model=FinancialEntryOut, status_code=status.HTTP_201_CREATED)
def create_financial_entry(
    req: FinancialEntryCreate,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Create a new financial record (rent, salary, subscription, tax, loan, reserve fund, income).
    """
    entry = FinancialService.create_entry(db, current_user, req)
    return entry


@router.get("/entries", response_model=List[FinancialEntryOut])
def list_financial_entries(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    List all financial records for the authenticated user.
    """
    return db.query(FinancialEntry).filter(
        FinancialEntry.owner_id == current_user.id
    ).order_by(FinancialEntry.transaction_date.desc()).all()


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_financial_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Delete a user's financial record with audit logging.
    """
    entry = db.query(FinancialEntry).filter(
        FinancialEntry.id == entry_id,
        FinancialEntry.owner_id == current_user.id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Financial record not found")

    append_audit_log(
        db,
        actor="owner",
        event="FINANCIAL_ENTRY_DELETED",
        payload={"entry_id": entry.id, "title": entry.title, "amount": float(entry.amount)}
    )

    db.delete(entry)
    db.commit()
    return None
