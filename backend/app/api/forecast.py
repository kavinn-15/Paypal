from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.app.db import get_db
from backend.app.models import Forecast, RescuePlan, Action, Obligation
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.agents.planner import RescuePlanEngine
from backend.app.schemas import PlansComparisonResponse, RescuePlanOut, ActionOut, DailyProjection, ObligationOut

router = APIRouter(prefix="/forecast", tags=["Forecast & Rescue Plans"])


@router.post("/run", response_model=PlansComparisonResponse)
def run_forecast_and_plans(
    obligation_id: Optional[int] = Query(None, description="Optional obligation ID"),
    starting_balance: float = Query(1800.0, description="Starting cash balance"),
    discount_pct: float = Query(3.0, description="Discount percentage for Plan B"),
    db: Session = Depends(get_db)
):
    """
    Executes end-to-end forecasting pipeline:
    1. Trains payment delay model on historical data.
    2. Runs Monte Carlo simulations & detects first shortfall date.
    3. Ranks driver clients & produces validated plain-language explanation.
    4. Generates exactly three Rescue Plans (A, B, C) with approval hashes.
    """
    forecaster = ForecasterAgent(db)
    forecast_res = forecaster.run_forecast(obligation_id=obligation_id, starting_balance=starting_balance)

    planner = RescuePlanEngine(db)
    comparison = planner.generate_plans_for_forecast(forecast_res, discount_pct=discount_pct)
    return comparison


@router.get("/latest", response_model=PlansComparisonResponse)
def get_latest_forecast(db: Session = Depends(get_db)):
    """Retrieves the most recent forecast run and rescue plans from the database."""
    forecast = db.query(Forecast).order_by(Forecast.id.desc()).first()
    if not forecast:
        # Run default forecast if none exists
        return run_forecast_and_plans(db=db)

    obligation = db.query(Obligation).filter(Obligation.id == forecast.obligation_id).first()
    if not obligation:
        obligation = db.query(Obligation).first()

    plans_models = db.query(RescuePlan).filter(RescuePlan.run_id == forecast.run_id).all()
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
            cost_desc = f"${p.cost:,.2f} discount cost."
        elif p.plan_type == "C":
            desc = f"Send reminder to client and split {obligation.payee_name}'s payout into two installments."
            cost_desc = "$0.00 cash cost (goodwill proxy)."

        plans_out.append(RescuePlanOut(
            id=p.id,
            run_id=p.run_id,
            plan_type=p.plan_type,
            name=f"Plan {p.plan_type}: {('Collect Without Concessions' if p.plan_type == 'A' else 'Limited Early-Pay Discount' if p.plan_type == 'B' else 'Collect Plus Agreed Contractor Split')}",
            description=desc,
            cost=p.cost,
            cost_description=cost_desc,
            incoming_needed=p.incoming_needed,
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
        shortfall_amount=forecast.shortfall_amount,
        first_shortfall_date=forecast.first_shortfall_date.strftime("%Y-%m-%d") if forecast.first_shortfall_date else None,
        tradeoff_summary=forecast.driver_explanation or "Review the three rescue plans below.",
        plans=plans_out
    )


@router.get("/horizons")
def get_multi_horizon_forecast(
    starting_balance: float = Query(1800.0, description="Starting cash balance"),
    db: Session = Depends(get_db)
):
    """
    Computes deterministic multi-horizon cash flow projections (7d, 30d, 60d, 90d)
    with minimum projected balance, shortfall risks, and runway coverage.
    """
    forecaster = ForecasterAgent(db)
    return forecaster.run_multi_horizon(starting_balance=starting_balance)


