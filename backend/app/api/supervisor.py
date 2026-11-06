from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner, AgentWorkflowRun
from backend.app.auth.deps import get_current_user
from backend.app.agents.supervisor import AgentSupervisor
from backend.app.schemas import SupervisorRunResponse

router = APIRouter(prefix="/supervisor", tags=["Agent Orchestrator / Supervisor"])


@router.post("/run", response_model=SupervisorRunResponse)
def run_supervisor_workflow(
    obligation_id: Optional[int] = Query(None, description="Target obligation ID"),
    starting_balance: Optional[float] = Query(None, description="Current starting balance (defaults to authoritative reconciled ledger)"),
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
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
    supervisor = AgentSupervisor(db)
    return supervisor.orchestrate_rescue_workflow(
        owner=current_user,
        obligation_id=obligation_id,
        starting_balance=starting_balance
    )


@router.get("/runs")
def list_supervisor_runs(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
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
    current_user: Owner = Depends(get_current_user)
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

