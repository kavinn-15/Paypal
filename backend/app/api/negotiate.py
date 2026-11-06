from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner, NegotiationDraft
from backend.app.auth.deps import get_current_user
from backend.app.agents.negotiator import NegotiationAgent
from backend.app.schemas import (
    NegotiationGenerateRequest, NegotiationTonesResponse, NegotiationDraftOut, NegotiationDraftUpdate
)
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/negotiate", tags=["Financial Negotiation Agent"])


@router.post("/generate", response_model=NegotiationTonesResponse)
def generate_negotiation_options(
    req: NegotiationGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Generate personalized negotiation messages across 3 distinct tone styles:
    - Professional (standard business etiquette)
    - Friendly (collaborative relationship tone)
    - Urgent but Respectful (critical deadline focus)
    For early invoice discounts (clients) or payment installments (contractors).
    """
    agent = NegotiationAgent(db)
    return agent.generate_options(owner=current_user, req=req)


@router.get("/drafts", response_model=List[NegotiationDraftOut])
def list_drafts(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Retrieve all negotiation message drafts for the authenticated user.
    """
    return db.query(NegotiationDraft).filter(
        NegotiationDraft.owner_id == current_user.id
    ).order_by(NegotiationDraft.id.desc()).all()


@router.put("/drafts/{draft_id}", response_model=NegotiationDraftOut)
def update_draft(
    draft_id: int,
    req: NegotiationDraftUpdate,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Allows user to edit and customize a negotiation draft before approving or sending.
    """
    draft = db.query(NegotiationDraft).filter(
        NegotiationDraft.id == draft_id,
        NegotiationDraft.owner_id == current_user.id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Negotiation draft not found")

    if req.subject is not None:
        draft.subject = req.subject
    if req.body is not None:
        draft.body = req.body
    if req.offered_incentive is not None:
        draft.offered_incentive = req.offered_incentive

    db.commit()
    db.refresh(draft)
    return draft


@router.post("/drafts/{draft_id}/approve", response_model=NegotiationDraftOut)
def approve_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Human-in-the-loop approval of a negotiation draft before dispatch.
    """
    draft = db.query(NegotiationDraft).filter(
        NegotiationDraft.id == draft_id,
        NegotiationDraft.owner_id == current_user.id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Negotiation draft not found")

    draft.status = "approved"
    db.commit()
    db.refresh(draft)

    append_audit_log(
        db,
        actor="owner",
        event="NEGOTIATION_DRAFT_APPROVED",
        payload={"draft_id": draft.id, "recipient": draft.recipient_email, "tone": draft.tone},
        owner_id=current_user.id
    )
    return draft


@router.post("/drafts/{draft_id}/response", response_model=NegotiationDraftOut)
def record_negotiation_response(
    draft_id: int,
    outcome: str = "accepted",  # accepted | declined
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Records recipient response to an approved negotiation proposal (accepted or declined).
    Updates forecast accordingly.
    """
    draft = db.query(NegotiationDraft).filter(
        NegotiationDraft.id == draft_id,
        NegotiationDraft.owner_id == current_user.id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Negotiation draft not found")

    if outcome not in ("accepted", "declined"):
        raise HTTPException(status_code=400, detail="Outcome must be 'accepted' or 'declined'")

    draft.status = outcome
    db.commit()
    db.refresh(draft)

    append_audit_log(
        db,
        actor="owner",
        event="NEGOTIATION_RESPONSE_RECORDED",
        payload={"draft_id": draft.id, "outcome": outcome},
        owner_id=current_user.id
    )
    return draft

