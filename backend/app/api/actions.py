from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.app.db import get_db
from backend.app.models import Action
from backend.app.schemas import ActionOut, ApprovalRequest, ExecuteRequest
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState, InvalidStateTransitionError
from backend.app.guardrail.policy import PolicyViolationError
from backend.app.services.execution import ActionExecutionService

router = APIRouter(prefix="/actions", tags=["Guardrail Actions & Approvals"])


@router.get("", response_model=List[ActionOut])
def list_actions(db: Session = Depends(get_db)):
    return db.query(Action).order_by(Action.id.desc()).all()


@router.get("/{action_id}", response_model=ActionOut)
def get_action(action_id: int, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found.")
    return ActionOut.model_validate(action)


@router.post("/{action_id}/approve", response_model=ActionOut)
def approve_action(
    action_id: int,
    payload: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Owner UI Approval endpoint:
    Requires the exact HMAC approval_hash calculated over recipient, amount, currency, and action_type.
    Strictly deterministic - the LLM or background agents can NEVER approve.
    """
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found.")

    try:
        updated = GuardrailStateMachine.transition(
            db=db,
            action=action,
            target_state=ActionState.APPROVED,
            actor="owner",
            approval_hash=payload.approval_hash
        )
        return ActionOut.model_validate(updated)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{action_id}/execute", response_model=ActionOut)
async def execute_action(
    action_id: int,
    payload: ExecuteRequest,
    db: Session = Depends(get_db)
):
    """
    Executes an approved action through the PayPal Sandbox.
    Enforces idempotency, state transitions, and safety policy bounds.
    """
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found.")

    if action.idempotency_key != payload.idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency key mismatch. Execution request rejected."
        )

    # Double-click safe: If already executed or confirmed, return current action without repeating call
    if action.state in (ActionState.EXECUTED, ActionState.CONFIRMED):
        return ActionOut.model_validate(action)

    try:
        updated = await ActionExecutionService.execute_action(db, action, actor="owner")
        return ActionOut.model_validate(updated)
    except (InvalidStateTransitionError, PolicyViolationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

