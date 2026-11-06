import hmac
import hashlib
from typing import Optional, Union
from decimal import Decimal
from backend.app.config import settings


def generate_approval_hash(
    recipient: str,
    amount: Union[float, Decimal],
    currency: str,
    action_type: str,
    idempotency_key: str,
    secret: Optional[str] = None
) -> str:
    """
    Computes HMAC-SHA256 approval signature cryptographically binding:
    recipient, exact amount (2 decimal places), currency, action_type, and idempotency_key.
    Any alteration of any parameter invalidates the approval.
    """
    secret_bytes = (secret or settings.APPROVAL_SECRET).encode("utf-8")
    amt_val = float(amount)
    payload = f"{recipient.strip().lower()}|{amt_val:.2f}|{currency.strip().upper()}|{action_type.strip().upper()}|{idempotency_key.strip()}".encode("utf-8")
    return hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()


def verify_approval_hash(
    provided_hash: str,
    recipient: str,
    amount: Union[float, Decimal],
    currency: str,
    action_type: str,
    idempotency_key: str,
    secret: Optional[str] = None
) -> bool:
    """
    Verifies provided approval hash using constant-time comparison.
    Returns True if valid, False if altered or tampered.
    """
    expected_hash = generate_approval_hash(
        recipient=recipient,
        amount=amount,
        currency=currency,
        action_type=action_type,
        idempotency_key=idempotency_key,
        secret=secret
    )
    return hmac.compare_digest(provided_hash, expected_hash)

