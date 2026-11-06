from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner
from backend.app.auth.deps import get_current_user
from backend.app.schemas import SimulationScenarioRequest, WhatIfComparisonResponse
from backend.app.services.simulation_service import SimulationService

router = APIRouter(prefix="/simulation", tags=["What-If Financial Simulation Engine"])


@router.post("/run", response_model=WhatIfComparisonResponse)
def run_simulation(
    req: SimulationScenarioRequest,
    starting_balance: float = Query(1800.0, description="Starting cash balance"),
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Run an intelligent What-If financial simulation:
    - Client delays payment by 5 or 10 days
    - Client pays only 50% partial
    - Dual client delay
    - Emergency expense shock
    - Expense increase
    - Contractor split agreement
    Compares baseline vs simulated metrics side-by-side without modifying database records.
    """
    return SimulationService.run_scenario(
        db=db,
        owner=current_user,
        req=req,
        starting_balance=starting_balance
    )


@router.get("/presets")
def get_simulation_presets():
    """
    Returns pre-configured What-If scenarios for one-click testing in UI.
    """
    return [
        {
            "id": "client_delay_5d",
            "name": "Client 5-Day Delay",
            "scenario_type": "client_delay_5d",
            "description": "Horizon Dynamics pays 5 days late due to international clearance.",
            "impact_hint": "Moderate risk of shortfall"
        },
        {
            "id": "client_delay_10d",
            "name": "Client 10-Day Severe Delay",
            "scenario_type": "client_delay_10d",
            "description": "Horizon Dynamics delays 10 days past contractor Friday deadline.",
            "impact_hint": "Critical cash shortfall"
        },
        {
            "id": "partial_pay_50",
            "name": "Partial Client Payment (50%)",
            "scenario_type": "partial_pay_50",
            "description": "Client settles only half of invoice amount this week.",
            "impact_hint": "Immediate cash compression"
        },
        {
            "id": "dual_delay",
            "name": "Simultaneous Dual-Client Delay",
            "scenario_type": "dual_delay",
            "description": "Both Apex Design and Horizon delay concurrently by 7 days.",
            "impact_hint": "Severe liquidity crisis"
        },
        {
            "id": "emergency_expense",
            "name": "Emergency Tool/Hardware Shock ($500)",
            "scenario_type": "emergency_expense",
            "description": "Unexpected critical equipment repair or software renewal.",
            "impact_hint": "Eats into cash buffer"
        },
        {
            "id": "contractor_split",
            "name": "Contractor Split Agreement (50/50)",
            "scenario_type": "contractor_split",
            "description": "Contractor accepts 50% now and remaining 50% in 14 days.",
            "impact_hint": "Completely protects cashflow"
        }
    ]
