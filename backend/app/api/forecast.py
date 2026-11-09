from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from backend.app.db import get_db
from backend.app.models import Forecast, RescuePlan, Action, Obligation, Owner
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.agents.planner import RescuePlanEngine
from backend.app.auth.deps import get_verified_current_user
from backend.app.services.financial_service import FinancialService
from backend.app.schemas import PlansComparisonResponse, RescuePlanOut, ActionOut, DailyProjection, ObligationOut

router = APIRouter(prefix="/forecast", tags=["Forecast & Rescue Plans"])


@router.post("/run", response_model=PlansComparisonResponse)
def run_forecast_and_plans(
    obligation_id: Optional[int] = Query(None, description="Optional obligation ID"),
    starting_balance: Optional[float] = Query(None, description="Starting cash balance (defaults to authoritative reconciled ledger)"),
    discount_pct: float = Query(3.0, description="Discount percentage for Plan B"),
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Executes end-to-end forecasting pipeline scoped strictly to the authenticated user:
    1. Derives authoritative cash balance from reconciled ledger if not overridden.
    2. Trains payment delay model on user's payment history with Empirical Bayes shrinkage.
    3. Runs Monte Carlo simulations & detects first shortfall date.
    4. Ranks driver clients & produces validated plain-language explanation.
    5. Generates three Rescue Plans (A, B, C) with cryptographic HMAC approval hashes.
    """
    # Defensive parameter normalization when invoked directly by other endpoints
    if not isinstance(obligation_id, int):
        obligation_id = None
    if not isinstance(starting_balance, (int, float)):
        starting_balance = None
    if not isinstance(discount_pct, (int, float)):
        discount_pct = 3.0

    if starting_balance is None:
        starting_balance = float(FinancialService.get_confirmed_balance(db, current_user))

    forecaster = ForecasterAgent(db)
    forecast_res = forecaster.run_forecast(
        obligation_id=obligation_id,
        starting_balance=starting_balance,
        owner_id=current_user.id
    )

    planner = RescuePlanEngine(db)
    comparison = planner.generate_plans_for_forecast(forecast_res, discount_pct=discount_pct)
    return comparison


@router.get("/latest", response_model=PlansComparisonResponse)
def get_latest_forecast(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Retrieves the most recent forecast run and rescue plans for the authenticated user."""
    forecast = db.query(Forecast).filter(
        Forecast.owner_id == current_user.id
    ).order_by(Forecast.id.desc()).first()

    if not forecast:
        return run_forecast_and_plans(
            obligation_id=None,
            starting_balance=None,
            discount_pct=3.0,
            db=db,
            current_user=current_user
        )

    obligation = db.query(Obligation).filter(
        Obligation.id == forecast.obligation_id,
        Obligation.owner_id == current_user.id
    ).first()

    if not obligation:
        obligation = db.query(Obligation).filter(Obligation.owner_id == current_user.id).first()

    if not obligation:
        raise HTTPException(status_code=404, detail="No active obligation found for current user.")

    plans_models = db.query(RescuePlan).filter(
        RescuePlan.run_id == forecast.run_id,
        RescuePlan.owner_id == current_user.id
    ).all()
    plans_out = []

    for p in plans_models:
        primary_action = p.actions[0] if p.actions else None
        if not primary_action:
            continue

        desc = ""
        cost_desc = ""
        if p.plan_type == "A":
            desc = "Send official PayPal payment reminder with live pay link to top reliable client."
            cost_desc = "$0.00 concession cost. Zero revenue lost."
        elif p.plan_type == "B":
            desc = "Apply limited early-pay discount to accelerate settlement before Friday."
            cost_desc = f"${float(p.cost):,.2f} discount cost."
        elif p.plan_type == "C":
            desc = f"Send reminder to client and split {obligation.payee_name}'s payout into two installments."
            cost_desc = "$0.00 cash cost (goodwill proxy)."

        plans_out.append(RescuePlanOut(
            id=p.id,
            run_id=p.run_id,
            plan_type=p.plan_type,
            name=f"Plan {p.plan_type}",
            description=desc,
            cost=float(p.cost),
            cost_description=cost_desc,
            incoming_needed=float(p.incoming_needed),
            selected_clients=p.selected_clients,
            rationale=p.rationale,
            forecast_with_plan=[DailyProjection(**x) for x in p.forecast_with_plan],
            forecast_without_plan=[DailyProjection(**x) for x in p.forecast_without_plan],
            late_scenario=p.late_scenario,
            remaining_risk=p.remaining_risk,
            primary_action=ActionOut.model_validate(primary_action)
        ))

    return PlansComparisonResponse(
        run_id=forecast.run_id,
        obligation=ObligationOut.model_validate(obligation),
        shortfall_amount=float(forecast.shortfall_amount),
        first_shortfall_date=forecast.first_shortfall_date.strftime("%Y-%m-%d") if forecast.first_shortfall_date else None,
        tradeoff_summary=forecast.driver_explanation or "Optimal recovery strategy based on client payment probability.",
        plans=plans_out,
        starting_balance=float(forecast.starting_balance),
        p_shortfall=float(forecast.p_shortfall)
    )


@router.get("/horizons")
def get_multi_horizon_forecast(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
) -> Dict[str, Any]:
    """
    Returns 7-day, 30-day, 60-day, and 90-day trajectory forecasts for the authenticated user.
    """
    forecaster = ForecasterAgent(db)
    return forecaster.run_multi_horizon(owner_id=current_user.id)
