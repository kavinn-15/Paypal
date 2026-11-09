from typing import Optional
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.models import Action, Obligation, Client, Invoice


class PolicyViolationError(Exception):
    pass


def validate_action_against_policy(action: Action, db: Session):
    """
    Enforces deterministic safety and financial policy bounds:
    1. Allowed currencies check
    2. Maximum payout limit check
    3. Maximum discount concession check
    4. Whitelisted recipients check (must match registered contractor or client)
    """
    # 1. Currency Check
    if action.currency.upper() not in settings.allowed_currencies_list:
        raise PolicyViolationError(
            f"POLICY VIOLATION: Currency '{action.currency}' is not in allowed currencies list: "
            f"{settings.allowed_currencies_list}"
        )

    # 2. Maximum Payout Limit Check
    if action.action_type in ("SCHEDULE_PAYOUT_SPLIT", "PAYOUT"):
        if float(action.amount) > settings.MAX_PAYOUT_AMOUNT:
            raise PolicyViolationError(
                f"POLICY VIOLATION: Payout amount ${float(action.amount):,.2f} exceeds configured maximum limit of "
                f"${settings.MAX_PAYOUT_AMOUNT:,.2f}"
            )

    # 3. Maximum Discount Concession Check
    if action.action_type == "APPLY_DISCOUNT":
        # Check against plan details or max discount cap
        if action.plan and action.plan.details:
            pct = action.plan.details.get("discount_pct", 0.0)
            if pct > settings.MAX_DISCOUNT_PCT:
                raise PolicyViolationError(
                    f"POLICY VIOLATION: Discount {pct:.1f}% exceeds maximum permitted cap of "
                    f"{settings.MAX_DISCOUNT_PCT:.1f}%"
                )

    # 4. Whitelisted Recipients Check (strictly scoped to this owner)
    recip = action.recipient.strip().lower()
    owner_filter = [Obligation.owner_id == action.owner_id] if action.owner_id else []
    client_filter = [Client.owner_id == action.owner_id] if action.owner_id else []

    valid_contractors = [
        o.payee_name.strip().lower() for o in db.query(Obligation).filter(*owner_filter).all()
    ] + [
        o.payee_email.strip().lower() for o in db.query(Obligation).filter(*owner_filter).all()
    ]

    valid_clients = [
        c.name.strip().lower() for c in db.query(Client).filter(*client_filter).all()
    ] + [
        c.email.strip().lower() for c in db.query(Client).filter(*client_filter).all()
    ]

    is_whitelisted = (recip in valid_contractors) or (recip in valid_clients)
    if not is_whitelisted:
        raise PolicyViolationError(
            f"SAFETY VIOLATION: Recipient '{action.recipient}' is not a recognized contractor or client! "
            f"Execution strictly blocked."
        )

