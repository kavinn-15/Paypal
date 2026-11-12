from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner, AgentWorkflowRun
from backend.app.auth.deps import get_verified_current_user
from backend.app.agents.supervisor import AgentSupervisor
from backend.app.schemas import SupervisorRunResponse

router = APIRouter(prefix="/supervisor", tags=["Agent Orchestrator / Supervisor"])


@router.post("/run", response_model=SupervisorRunResponse)
def run_supervisor_workflow(
    obligation_id: Optional[int] = Query(None, description="Target obligation ID"),
    starting_balance: Optional[float] = Query(None, description="Current starting balance (defaults to authoritative reconciled ledger)"),
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Triggers the Autonomous Agent Orchestrator:
    1. Forecaster Agent -> cash shortage & risk driver identification
    2. Collector Agent -> invoice collection opportunity ranking
    3. Treasurer Agent -> obligation urgency & installment evaluation
    4. Planner Agent -> mathematical Plan A, B, C synthesis
    5. Negotiation Agent -> multi-tone communication drafting
    6. Supervisory Evaluation -> optimal plan selection & conflict resolution
    """
    from backend.app.models import Obligation
    obl_exists = db.query(Obligation).filter(Obligation.owner_id == current_user.id).first()
    if not obl_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active contractor obligation found to protect. Please create an obligation to orchestrate multi-agent rescue workflows."
        )

    supervisor = AgentSupervisor(db)
    try:
        return supervisor.orchestrate_rescue_workflow(
            owner=current_user,
            obligation_id=obligation_id,
            starting_balance=starting_balance
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "obligation" in str(e).lower() else status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/runs")
def list_supervisor_runs(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    List past supervisory workflow runs and agent execution traces.
    """
    runs = db.query(AgentWorkflowRun).filter(
        AgentWorkflowRun.owner_id == current_user.id
    ).order_by(AgentWorkflowRun.id.desc()).all()
    return runs


@router.get("/runs/{run_id}")
def get_supervisor_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Retrieve specific supervisor workflow run trace for authenticated user.
    """
    run = db.query(AgentWorkflowRun).filter(
        AgentWorkflowRun.run_id == run_id,
        AgentWorkflowRun.owner_id == current_user.id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Supervisor run not found.")
    return run

