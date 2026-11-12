import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.config import settings
from backend.app.models import (
    Owner, Client, Invoice, Obligation, PaymentHistory, FinancialEntry,
    Forecast, RescuePlan, Action, ClientPrediction, Message, NegotiationDraft, SimulationRun
)
from backend.app.auth.deps import get_current_user
from backend.scripts.seed import seed_demo_scenario
from backend.app.guardrail.audit import append_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["Demo Management & Data Separation"])


def _check_demo_allowed():
    """
    Guarantees that demo endpoints are strictly prohibited when DEV_MODE is False
    or ALLOW_DEMO_ENDPOINTS is False (e.g. production environments).
    """
    if not settings.DEV_MODE or not settings.ALLOW_DEMO_ENDPOINTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo management endpoints are strictly disabled in production environments."
        )


def _require_demo_authority(current_user: Owner):
    """
    Restricts access to demo endpoints:
    - Rejects production environments.
    - Requires authenticated user.
    - Rejects ordinary users (is_demo == False and not admin).
    - Only permits authorized demo accounts or administrators.
    """
    _check_demo_allowed()

    is_admin = getattr(current_user, "account_status", "") == "admin"
    if not current_user.is_demo and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Ordinary authenticated user accounts cannot trigger demo data operations."
        )


@router.post("/load")
async def load_demo_scenario(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Loads or resets the Alex Morgan hackathon scenario (6 seeded client behavioral personas,
    12-month transaction history, open invoices, and Marcus Sterling contractor payout).
    Strictly isolated and scoped to the authorized demo owner.
    Non-destructive: NEVER deletes database tables or real user accounts.
    Automatically provisions fresh, live, payable PayPal Sandbox invoices if credentials are configured.
    """
    _require_demo_authority(current_user)

    logger.info(f"Loading demo scenario requested by owner_id={current_user.id} (is_demo={current_user.is_demo})")

    # Seed specifically for the current demo owner (or canonical Alex Morgan if admin)
    seeded_owner = seed_demo_scenario(db=db, target_owner=current_user if current_user.is_demo else None)

    # Automatically provision fresh live PayPal Sandbox invoices so they are immediately payable
    if settings.PAYPAL_CLIENT_ID and "placeholder" not in settings.PAYPAL_CLIENT_ID.lower() and "your_paypal" not in settings.PAYPAL_CLIENT_ID.lower():
        try:
            from backend.app.services.paypal_invoice_service import provision_sandbox_invoices
            await provision_sandbox_invoices(db=db, owner_id=seeded_owner.id)
            logger.info("Automatically provisioned fresh live PayPal Sandbox invoices for demo scenario reset.")
        except Exception as e:
            logger.warning(f"Live PayPal invoice provisioning during demo reset skipped: {e}")

    append_audit_log(
        db,
        actor="system",
        event="DEMO_SCENARIO_LOADED",
        payload={
            "persona": seeded_owner.name,
            "starting_balance": 1800.0,
            "shortfall_target": 1400.0,
            "target_owner_id": seeded_owner.id
        },
        owner_id=current_user.id
    )

    return {
        "status": "success",
        "message": f"Demo scenario loaded successfully for {seeded_owner.name}: 6 clients and Friday Marcus Sterling obligation.",
        "is_demo_active": True
    }


@router.post("/clear")
def clear_demo_scenario(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Purges demo records strictly belonging to the current authorized demo owner.
    Never deletes records belonging to other users (demo or authentic).
    Uses scoped queries with full rollback safety.
    """
    _require_demo_authority(current_user)

    if not current_user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security violation: Demo clearing is restricted strictly to demo accounts."
        )

    target_owner_id = current_user.id
    logger.info(f"Clearing demo scenario records strictly for owner_id={target_owner_id}")

    try:
        # Find demo clients belonging to this owner
        demo_clients = db.query(Client).filter(
            Client.owner_id == target_owner_id,
            Client.is_seeded == True
        ).all()
        client_ids = [c.id for c in demo_clients]

        if client_ids:
            # 1. Delete payment history for these clients
            db.query(PaymentHistory).filter(
                PaymentHistory.client_id.in_(client_ids)
            ).delete(synchronize_session=False)

            # 2. Delete messages associated with actions targeting these clients
            db.query(Message).filter(
                Message.client_id.in_(client_ids)
            ).delete(synchronize_session=False)

            # 3. Delete client predictions for these clients
            db.query(ClientPrediction).filter(
                ClientPrediction.client_id.in_(client_ids)
            ).delete(synchronize_session=False)

            # 4. Delete negotiation drafts targeting these clients
            db.query(NegotiationDraft).filter(
                NegotiationDraft.owner_id == target_owner_id,
                NegotiationDraft.client_id.in_(client_ids)
            ).delete(synchronize_session=False)

            # 5. Delete invoices for these clients
            db.query(Invoice).filter(
                Invoice.client_id.in_(client_ids)
            ).delete(synchronize_session=False)

            # 6. Delete the clients themselves
            db.query(Client).filter(
                Client.id.in_(client_ids),
                Client.owner_id == target_owner_id
            ).delete(synchronize_session=False)

        # 7. Delete contractor obligations strictly belonging to this demo scenario
        db.query(Obligation).filter(
            Obligation.owner_id == target_owner_id,
            Obligation.is_demo == True
        ).delete(synchronize_session=False)

        # 8. Delete demo financial entries strictly belonging to this owner
        db.query(FinancialEntry).filter(
            FinancialEntry.owner_id == target_owner_id,
            FinancialEntry.is_demo == True
        ).delete(synchronize_session=False)

        # 9. Delete demo actions, plans, forecasts, simulations strictly belonging to this owner
        db.query(Action).filter(
            Action.owner_id == target_owner_id,
            (Action.is_demo == True) | (Action.is_seeded == True)
        ).delete(synchronize_session=False)

        db.query(RescuePlan).filter(
            RescuePlan.owner_id == target_owner_id,
            RescuePlan.is_demo == True
        ).delete(synchronize_session=False)

        db.query(Forecast).filter(
            Forecast.owner_id == target_owner_id,
            Forecast.is_demo == True
        ).delete(synchronize_session=False)

        db.query(SimulationRun).filter(
            SimulationRun.owner_id == target_owner_id
        ).delete(synchronize_session=False)

        db.commit()

        append_audit_log(
            db,
            actor="system",
            event="DEMO_DATA_CLEARED",
            payload={"action": "clean_slate_reset", "owner_id": target_owner_id},
            owner_id=target_owner_id
        )

        return {
            "status": "success",
            "message": "Demo records for the current account have been cleared. Ready for authentic user data onboarding.",
            "is_demo_active": False
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear demo data for owner_id={target_owner_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear demo data due to an internal error."
        )


@router.get("/status")
def get_demo_status(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_current_user)
):
    """
    Checks if the demo scenario is currently populated for the authenticated user.
    """
    _check_demo_allowed()

    has_seeded = db.query(Client).filter(
        Client.owner_id == current_user.id,
        Client.is_seeded == True
    ).first() is not None

    return {
        "is_demo_active": has_seeded,
        "persona": "Alex Morgan" if (has_seeded or current_user.is_demo) else None
    }
