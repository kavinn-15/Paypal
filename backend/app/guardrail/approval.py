import hmac
import hashlib
import json
from typing import Optional, Union, Dict, Any, List
from decimal import Decimal
from backend.app.config import settings


def build_canonical_payload(
    action_type: str,
    recipient: str,
    amount: Union[float, Decimal],
    currency: str,
    idempotency_key: str,
    action_id: Optional[int] = None,
    paypal_recipient: Optional[str] = None,
    invoice_id: Optional[str] = None,
    message_body: Optional[str] = None,
    discount_pct: Optional[float] = None,
    updated_invoice_amount: Optional[float] = None,
    due_date: Optional[str] = None,
    payment_schedule: Optional[str] = None,
    installment_amounts: Optional[List[float]] = None,
    installment_dates: Optional[List[str]] = None,
    extra_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Constructs a complete canonical dictionary of all relevant action execution details.
    """
    amt_val = round(float(amount), 2)
    payload: Dict[str, Any] = {
        "action_type": action_type.strip().upper(),
        "recipient": recipient.strip(),
        "amount": f"{amt_val:.2f}",
        "currency": currency.strip().upper(),
        "idempotency_key": idempotency_key.strip(),
    }

    if action_id is not None:
        payload["action_id"] = action_id
    if paypal_recipient is not None:
        payload["paypal_recipient"] = paypal_recipient.strip()
    if invoice_id is not None:
        payload["invoice_id"] = str(invoice_id).strip()
    if message_body is not None:
        payload["message_body"] = message_body.strip()
    if discount_pct is not None:
        payload["discount_pct"] = round(float(discount_pct), 2)
    if updated_invoice_amount is not None:
        payload["updated_invoice_amount"] = round(float(updated_invoice_amount), 2)
    if due_date is not None:
        payload["due_date"] = str(due_date).strip()
    if payment_schedule is not None:
        payload["payment_schedule"] = str(payment_schedule).strip()
    if installment_amounts is not None:
        payload["installment_amounts"] = [round(float(a), 2) for a in installment_amounts]
    if installment_dates is not None:
        payload["installment_dates"] = [str(d).strip() for d in installment_dates]
    if extra_params:
        payload["extra_params"] = extra_params

    return payload


def serialize_canonical_payload(payload: Dict[str, Any]) -> str:
    """Serializes canonical payload deterministically using sorted keys and compact JSON separators."""
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def generate_payload_hash(payload: Dict[str, Any]) -> str:
    """Computes SHA-256 hash of deterministically serialized canonical payload."""
    serialized = serialize_canonical_payload(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def generate_canonical_approval_signature(payload_hash: str, secret: Optional[str] = None) -> str:
    """Generates HMAC-SHA256 signature over the payload hash using server-side approval secret."""
    secret_bytes = (secret or settings.APPROVAL_SECRET).encode("utf-8")
    return hmac.new(secret_bytes, payload_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def compute_action_payload(action: Any, override_message: Optional[str] = None) -> Dict[str, Any]:
    """Reconstructs the full canonical execution payload from an Action model instance."""
    msg_body = override_message
    if msg_body is None and hasattr(action, "messages") and action.messages:
        msg_body = action.messages[0].body

    details = {}
    if hasattr(action, "plan") and action.plan and hasattr(action.plan, "details") and action.plan.details:
        details = action.plan.details

    # Correctly distinguish invoice identifier from payout recipient identifier
    if action.action_type in ("SEND_REMINDER", "APPLY_DISCOUNT"):
        inv_id = str(action.paypal_ref) if action.paypal_ref else None
        p_recip = action.recipient
        discount_pct = details.get("discount_pct")
        updated_inv = details.get("discount_cost")
        due_date = details.get("due_date") or details.get("deadline_str")
        payment_schedule = None
        inst_amounts = None
        inst_dates = None
    elif action.action_type in ("SCHEDULE_PAYOUT_SPLIT", "PAYOUT"):
        inv_id = None
        p_recip = action.recipient
        discount_pct = None
        updated_inv = None
        due_date = details.get("installment_2_date")
        payment_schedule = details.get("installment_2_status")
        inst_amounts = None
        if "installment_1" in details and "installment_2" in details:
            inst_amounts = [float(details["installment_1"]), float(details["installment_2"])]
        inst_dates = None
        if "installment_2_date" in details:
            inst_dates = [str(details["installment_2_date"])]
    else:
        inv_id = str(action.paypal_ref) if action.paypal_ref else None
        p_recip = action.recipient
        discount_pct = details.get("discount_pct")
        updated_inv = details.get("discount_cost")
        due_date = details.get("installment_2_date") or details.get("due_date")
        payment_schedule = details.get("installment_2_status")
        inst_amounts = None
        if "installment_1" in details and "installment_2" in details:
            inst_amounts = [float(details["installment_1"]), float(details["installment_2"])]
        inst_dates = [str(details["installment_2_date"])] if "installment_2_date" in details else None

    return build_canonical_payload(
        action_type=action.action_type,
        recipient=action.recipient,
        amount=action.amount,
        currency=action.currency,
        idempotency_key=action.idempotency_key,
        action_id=action.id,
        paypal_recipient=p_recip,
        invoice_id=inv_id,
        message_body=msg_body,
        discount_pct=discount_pct,
        updated_invoice_amount=updated_inv,
        due_date=due_date,
        payment_schedule=payment_schedule,
        installment_amounts=inst_amounts,
        installment_dates=inst_dates
    )


def generate_approval_hash(
    recipient: str,
    amount: Union[float, Decimal],
    currency: str,
    action_type: str,
    idempotency_key: str,
    secret: Optional[str] = None,
    action_id: Optional[int] = None,
    paypal_recipient: Optional[str] = None,
    invoice_id: Optional[str] = None,
    message_body: Optional[str] = None,
    discount_pct: Optional[float] = None,
    updated_invoice_amount: Optional[float] = None,
    due_date: Optional[str] = None,
    payment_schedule: Optional[str] = None,
    installment_amounts: Optional[List[float]] = None,
    installment_dates: Optional[List[str]] = None,
    extra_params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Computes HMAC-SHA256 approval signature cryptographically binding all relevant action execution details.
    When detailed parameters are supplied, computes canonical JSON SHA-256 payload hash and signs with HMAC.
    Maintains backward compatibility with legacy 5-tuple format.
    """
    has_extended = any(
        x is not None for x in [
            message_body, discount_pct, updated_invoice_amount, due_date,
            payment_schedule, installment_amounts, installment_dates,
            extra_params
        ]
    )

    if has_extended:
        payload = build_canonical_payload(
            action_type=action_type,
            recipient=recipient,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
            action_id=action_id,
            paypal_recipient=paypal_recipient,
            invoice_id=invoice_id,
            message_body=message_body,
            discount_pct=discount_pct,
            updated_invoice_amount=updated_invoice_amount,
            due_date=due_date,
            payment_schedule=payment_schedule,
            installment_amounts=installment_amounts,
            installment_dates=installment_dates,
            extra_params=extra_params
        )
        p_hash = generate_payload_hash(payload)
        return generate_canonical_approval_signature(p_hash, secret=secret)

    # Standard compact format
    secret_bytes = (secret or settings.APPROVAL_SECRET).encode("utf-8")
    amt_val = float(amount)
    payload_str = f"{recipient.strip().lower()}|{amt_val:.2f}|{currency.strip().upper()}|{action_type.strip().upper()}|{idempotency_key.strip()}".encode("utf-8")
    return hmac.new(secret_bytes, payload_str, hashlib.sha256).hexdigest()


def verify_approval_hash(
    provided_hash: str,
    recipient: str,
    amount: Union[float, Decimal],
    currency: str,
    action_type: str,
    idempotency_key: str,
    secret: Optional[str] = None,
    allow_compact_fallback: bool = False,
    **extended_kwargs: Any
) -> bool:
    """
    Verifies provided approval hash using constant-time comparison against expected hash.
    For canonical payloads, requires the exact HMAC of the canonical payload hash.
    Legacy compact signature fallback is isolated and only permitted if allow_compact_fallback=True.
    """
    expected_hash = generate_approval_hash(
        recipient=recipient,
        amount=amount,
        currency=currency,
        action_type=action_type,
        idempotency_key=idempotency_key,
        secret=secret,
        **extended_kwargs
    )
    if hmac.compare_digest(provided_hash, expected_hash):
        return True

    # If action has a canonical payload in database matching idempotency_key:
    if idempotency_key:
        try:
            from backend.app.db import SessionLocal
            from backend.app.models import Action
            db_session = SessionLocal()
            try:
                db_action = db_session.query(Action).filter(Action.idempotency_key == idempotency_key).first()
                if db_action:
                    c_payload = compute_action_payload(db_action)
                    c_p_hash = generate_payload_hash(c_payload)
                    c_sig = generate_canonical_approval_signature(c_p_hash, secret=secret)
                    if hmac.compare_digest(provided_hash, c_sig):
                        return True
            finally:
                db_session.close()
        except Exception:
            pass

    # Fallback to legacy compact verification ONLY if explicitly enabled for backward compatibility
    if extended_kwargs and allow_compact_fallback:
        legacy_hash = generate_approval_hash(
            recipient=recipient,
            amount=amount,
            currency=currency,
            action_type=action_type,
            idempotency_key=idempotency_key,
            secret=secret
        )
        return hmac.compare_digest(provided_hash, legacy_hash)

    return False
