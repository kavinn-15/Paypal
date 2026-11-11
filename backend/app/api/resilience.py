from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner
from backend.app.auth.deps import get_verified_current_user
from backend.app.schemas import ResilienceScoreResponse
from backend.app.services.resilience_service import ResilienceService
from backend.app.services.financial_service import FinancialService

router = APIRouter(prefix="/resilience", tags=["Financial Resilience Score"])


@router.get("/score", response_model=ResilienceScoreResponse)
def get_resilience_score(
    starting_balance: Optional[float] = Query(None, description="Current cash balance (defaults to authoritative reconciled ledger)"),
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Computes explainable Financial Resilience Score (0 to 100) using 6 transparent dimensions:
    1. Cash Reserve Coverage
    2. Expected Incoming Reliability
    3. Upcoming Obligations Load
    4. Payment Concentration Risk
    5. Outstanding Receivables Exposure
    6. Unexpected Expense Shock Tolerance
    """
    if starting_balance is None:
        starting_balance = float(FinancialService.get_confirmed_balance(db, current_user))

    return ResilienceService.calculate_score(
        db=db,
        owner=current_user,
        starting_balance=starting_balance
    )

