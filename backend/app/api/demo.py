from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.config import settings
from backend.app.models import Owner, Client, Invoice, Obligation, PaymentHistory, FinancialEntry, Forecast, RescuePlan, Action
from backend.app.auth.deps import get_current_user
from backend.scripts.seed import seed_database
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/demo", tags=["Demo Management & Data Separation"])


def _check_demo_allowed():
    if not settings.DEV_MODE or not settings.ALLOW_DEMO_ENDPOINTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo management endpoints are strictly disabled in production environments."
        )


@router.post("/load")
def load_demo_scenario(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Loads or resets the Alex Morgan hackathon scenario (6 seeded client behavioral personas,
    12-month transaction history, open invoices, and Marcus Sterling contractor payout).
    Protected by authentication and DEV_MODE guard.
    """
    _check_demo_allowed()
    seed_database(db)
    append_audit_log(
        db,
        actor="system",
        event="DEMO_SCENARIO_LOADED",
        payload={"persona": "Alex Morgan", "starting_balance": 1800.0, "shortfall_target": 1400.0},
        owner_id=current_user.id
    )
    return {
        "status": "success",
        "message": "Demo scenario loaded successfully: Alex Morgan persona with 6 clients and Friday Marcus Sterling obligation.",
        "is_demo_active": True
    }


@router.post("/clear")
def clear_demo_scenario(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Purges demo records for the demo persona to provide a clean slate for testing.
    Never deletes authentic user records.
    """
    _check_demo_allowed()

    # Strictly target ONLY dedicated demo owners (where is_demo == True).
    # Real, non-demo users' records are NEVER touched or deleted.
    demo_owners = db.query(Owner).filter(Owner.is_demo == True).all()
    demo_owner_ids = [o.id for o in demo_owners]

    if not demo_owner_ids:
        return {
            "status": "success",
            "message": "No demo records found to clear.",
            "is_demo_active": False
        }

    # Delete only seeded/demo clients and their associated data
    demo_clients = db.query(Client).filter(
        Client.owner_id.in_(demo_owner_ids),
        Client.is_seeded == True
    ).all()
    demo_client_ids = [c.id for c in demo_clients]

    if demo_client_ids:
        db.query(PaymentHistory).filter(PaymentHistory.client_id.in_(demo_client_ids)).delete(synchronize_session=False)
        db.query(Invoice).filter(Invoice.client_id.in_(demo_client_ids)).delete(synchronize_session=False)
        db.query(Client).filter(Client.id.in_(demo_client_ids)).delete(synchronize_session=False)

    # Strictly delete only demo obligations belonging to demo owners
    db.query(Obligation).filter(
        Obligation.owner_id.in_(demo_owner_ids)
    ).delete(synchronize_session=False)

    # Delete demo financial entries
    db.query(FinancialEntry).filter(
        FinancialEntry.owner_id.in_(demo_owner_ids),
        FinancialEntry.is_demo == True
    ).delete(synchronize_session=False)

    # Delete demo actions, plans, and forecasts strictly belonging to demo owners
    db.query(Action).filter(Action.owner_id.in_(demo_owner_ids)).delete(synchronize_session=False)
    db.query(RescuePlan).filter(RescuePlan.owner_id.in_(demo_owner_ids)).delete(synchronize_session=False)
    db.query(Forecast).filter(Forecast.owner_id.in_(demo_owner_ids)).delete(synchronize_session=False)
    db.commit()

    append_audit_log(
        db,
        actor="system",
        event="DEMO_DATA_CLEARED",
        payload={"action": "clean_slate_reset", "owner_ids": demo_owner_ids},
        owner_id=current_user.id
    )
    return {
        "status": "success",
        "message": "Demo records have been cleared. Ready for authentic user data onboarding.",
        "is_demo_active": False
    }


@router.get("/status")
def get_demo_status(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Checks if the demo scenario is currently populated for the authenticated user.
    """
    has_seeded = db.query(Client).filter(
        Client.owner_id == current_user.id,
        Client.is_seeded == True
    ).first() is not None

    return {
        "is_demo_active": has_seeded,
        "persona": "Alex Morgan" if (has_seeded or current_user.is_demo) else None
    }
