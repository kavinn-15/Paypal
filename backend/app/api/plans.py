from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models import RescuePlan, Owner
from backend.app.schemas import RescuePlanOut, ActionOut, DailyProjection
from backend.app.auth.deps import get_current_user

router = APIRouter(prefix="/plans", tags=["Rescue Plans"])


@router.get("/{plan_id}", response_model=RescuePlanOut)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """Retrieves a specific rescue plan with user ownership validation."""
    plan = db.query(RescuePlan).filter(
        RescuePlan.id == plan_id,
        RescuePlan.owner_id == current_user.id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Rescue plan not found.")

    action = plan.actions[0] if plan.actions else None
    if not action:
        raise HTTPException(status_code=400, detail="Plan has no primary action attached.")

    from backend.app.services.region_service import CURRENCIES_DB
    user_curr = (current_user.preferred_currency or current_user.currency or "USD").upper()
    user_sym = CURRENCIES_DB.get(user_curr, {}).get("symbol", "$")

    return RescuePlanOut(
        id=plan.id,
        run_id=plan.run_id,
        plan_type=plan.plan_type,
        name=f"Plan {plan.plan_type}",
        description="Rescue plan option",
        cost=float(plan.cost),
        cost_description=f"{user_sym}{float(plan.cost):,.2f}",
        incoming_needed=float(plan.incoming_needed),
        selected_clients=plan.selected_clients,
        rationale=plan.rationale,
        forecast_with_plan=[DailyProjection(**x) for x in plan.forecast_with_plan],
        forecast_without_plan=[DailyProjection(**x) for x in plan.forecast_without_plan],
        late_scenario=plan.late_scenario,
        remaining_risk=plan.remaining_risk,
        primary_action=ActionOut.model_validate(action)
    )
