import datetime
import hashlib
import hmac
import secrets
from typing import Tuple, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import EmailOTP


def generate_otp_code() -> str:
    """Generates a cryptographically random 6-digit numeric OTP."""
    return "".join(secrets.choice("0123456789") for _ in range(6))


def compute_otp_hash(email: str, otp: str, purpose: str) -> str:
    """
    Computes a keyed HMAC-SHA256 hash of the OTP bound to email, purpose, and server pepper.
    Plain OTP is never stored in the database.
    """
    key = settings.OTP_PEPPER.encode("utf-8")
    message = f"{email.lower().strip()}:{purpose}:{otp}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_otp_hash(email: str, otp: str, purpose: str, stored_hash: str) -> bool:
    """Constant-time verification of OTP hash."""
    expected = compute_otp_hash(email, otp, purpose)
    return hmac.compare_digest(expected, stored_hash)


def create_otp(
    db: Session,
    email: str,
    purpose: str,
    owner_id: Optional[int] = None
) -> Tuple[EmailOTP, str]:
    """
    Creates and records a new single-use OTP for email_verification or password_reset.
    Enforces resend cooldown and invalidates previous active OTPs for the same purpose.
    Returns (db_record, plain_code) so plain_code can be dispatched via email.
    """
    email_clean = email.lower().strip()
    now = datetime.datetime.utcnow()

    # 1. Enforce resend cooldown (30-60s)
    cooldown_cutoff = now - datetime.timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
    recent_otp = db.query(EmailOTP).filter(
        EmailOTP.email == email_clean,
        EmailOTP.purpose == purpose,
        EmailOTP.consumed_at == None,
        EmailOTP.created_at > cooldown_cutoff
    ).first()

    if recent_otp:
        elapsed = int((now - recent_otp.created_at).total_seconds())
        remaining = max(1, settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {remaining} seconds before requesting a new code."
        )

    # 2. Invalidate any existing unconsumed OTPs for this email & purpose
    db.query(EmailOTP).filter(
        EmailOTP.email == email_clean,
        EmailOTP.purpose == purpose,
        EmailOTP.consumed_at == None
    ).update({"consumed_at": now})

    # 3. Generate new random code and keyed HMAC hash
    plain_code = generate_otp_code()
    otp_hash = compute_otp_hash(email_clean, plain_code, purpose)
    expires_at = now + datetime.timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    db_otp = EmailOTP(
        owner_id=owner_id,
        email=email_clean,
        otp_hash=otp_hash,
        purpose=purpose,
        expires_at=expires_at,
        attempts_count=0,
        max_attempts=settings.OTP_MAX_ATTEMPTS,
        consumed_at=None,
        created_at=now
    )
    db.add(db_otp)
    db.commit()
    db.refresh(db_otp)

    return db_otp, plain_code


def verify_and_consume_otp(
    db: Session,
    email: str,
    otp: str,
    purpose: str
) -> EmailOTP:
    """
    Verifies a supplied OTP against the latest active record.
    Enforces expiration, single-use consumption, purpose binding, and attempt limits.
    """
    email_clean = email.lower().strip()
    now = datetime.datetime.utcnow()

    # Find active unconsumed OTP for this purpose
    otp_record = db.query(EmailOTP).filter(
        EmailOTP.email == email_clean,
        EmailOTP.purpose == purpose,
        EmailOTP.consumed_at == None
    ).order_by(EmailOTP.id.desc()).first()

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification code found or code already consumed. Please request a new code."
        )

    # Check expiration
    if otp_record.expires_at < now:
        otp_record.consumed_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code."
        )

    # Check attempt limit
    if otp_record.attempts_count >= otp_record.max_attempts:
        otp_record.consumed_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum verification attempts exceeded. This code has been invalidated."
        )

    # Increment attempt count
    otp_record.attempts_count += 1
    db.commit()

    # Verify cryptographic hash
    if not verify_otp_hash(email_clean, otp.strip(), purpose, otp_record.otp_hash):
        remaining = otp_record.max_attempts - otp_record.attempts_count
        if remaining <= 0:
            otp_record.consumed_at = now
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid code. Maximum attempts reached; please request a new code."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempt(s) remaining."
        )

    # Code is valid: mark consumed
    otp_record.consumed_at = now
    db.commit()

    return otp_record

