from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner, Client, Invoice, Obligation, PaymentHistory, FinancialEntry, Forecast, RescuePlan, Action
from backend.app.auth.deps import get_current_user
from backend.scripts.seed import seed_database
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/demo", tags=["Demo Management & Data Separation"])


@router.post("/load")
def load_demo_scenario(db: Session = Depends(get_db)):
    """
    Loads or resets the Alex Morgan hackathon scenario (6 seeded client behavioral personas,
    12-month transaction history, open invoices, and Marcus Sterling contractor payout).
    All records are explicitly tagged as demo data.
    """
    seed_database(db)
    append_audit_log(
        db,
        actor="system",
        event="DEMO_SCENARIO_LOADED",
        payload={"persona": "Alex Morgan", "starting_balance": 1800.0, "shortfall_target": 1400.0}
    )
    return {
        "status": "success",
        "message": "Demo scenario loaded successfully: Alex Morgan persona with 6 clients and Friday Marcus Sterling obligation.",
        "is_demo_active": True
    }


@router.post("/clear")
def clear_demo_scenario(db: Session = Depends(get_db)):
    """
    Purges demo records to provide a clean slate for genuine user testing.
    """
    # Delete seeded payment histories, open invoices, obligations, plans
    db.query(PaymentHistory).filter(PaymentHistory.source == "seeded").delete()
    db.query(Obligation).delete()
    db.query(Invoice).delete()
    db.query(Client).filter(Client.is_seeded == True).delete()
    db.query(RescuePlan).delete()
    db.query(Action).delete()
    db.query(Forecast).delete()
    db.commit()

    append_audit_log(
        db,
        actor="system",
        event="DEMO_DATA_CLEARED",
        payload={"action": "clean_slate_reset"}
    )
    return {
        "status": "success",
        "message": "All demo records have been cleared. Ready for authentic user data onboarding.",
        "is_demo_active": False
    }


@router.get("/status")
def get_demo_status(db: Session = Depends(get_db)):
    """
    Checks if the demo scenario is currently populated.
    """
    has_seeded = db.query(PaymentHistory).filter(PaymentHistory.source == "seeded").first() is not None
    return {
        "is_demo_active": has_seeded,
        "persona": "Alex Morgan" if has_seeded else None
    }
