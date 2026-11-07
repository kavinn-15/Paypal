import hmac
import hashlib
import secrets
import datetime
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.config import settings
from backend.app.models import PhoneOTP

# Rate limit tracker: {phone_number: [timestamp, ...]}
_PHONE_RATE_LIMITS = {}
MAX_PHONE_OTP_REQUESTS_PER_HOUR = 6


def hash_phone_otp(phone_number: str, purpose: str, plain_otp: str) -> str:
    """
    Computes a keyed HMAC-SHA256 digest of the phone OTP using server-side OTP_PEPPER.
    Binds the destination phone number, designated purpose, and plain digits together.
    """
    key = settings.OTP_PEPPER.encode("utf-8")
    payload = f"{phone_number}:{purpose}:{plain_otp}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def check_phone_rate_limit(phone_number: str) -> None:
    """
    Enforces a hard limit on OTP requests per phone number within a rolling hour.
    """
    now = datetime.datetime.utcnow()
    one_hour_ago = now - datetime.timedelta(hours=1)

    if phone_number in _PHONE_RATE_LIMITS:
        # Keep only timestamps within the last hour
        _PHONE_RATE_LIMITS[phone_number] = [
            t for t in _PHONE_RATE_LIMITS[phone_number] if t > one_hour_ago
        ]
        if len(_PHONE_RATE_LIMITS[phone_number]) >= MAX_PHONE_OTP_REQUESTS_PER_HOUR:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many SMS verification requests for this phone number. Please wait an hour before requesting a new code."
            )
    else:
        _PHONE_RATE_LIMITS[phone_number] = []


def create_phone_otp(
    db: Session,
    phone_number: str,
    purpose: str,
    owner_id: Optional[int] = None,
    enforce_cooldown: bool = True
) -> Tuple[PhoneOTP, str]:
    """
    Generates a cryptographically secure 6-digit OTP bound to a phone number and purpose.
    Invalidates any previous active OTPs for the same (phone_number, purpose).
    Returns (PhoneOTP db_record, plain_6_digit_otp).
    """
    check_phone_rate_limit(phone_number)

    now = datetime.datetime.utcnow()

    # Check resend cooldown
    if enforce_cooldown:
        latest = (
            db.query(PhoneOTP)
            .filter(
                PhoneOTP.phone_number == phone_number,
                PhoneOTP.purpose == purpose,
                PhoneOTP.consumed_at.is_(None)
            )
            .order_by(PhoneOTP.created_at.desc())
            .first()
        )
        if latest:
            elapsed = (now - latest.created_at).total_seconds()
            cooldown = settings.SMS_RESEND_COOLDOWN_SECONDS
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {remaining} seconds before requesting a new SMS verification code."
                )

    # Invalidate previous unconsumed OTPs for this phone & purpose
    db.query(PhoneOTP).filter(
        PhoneOTP.phone_number == phone_number,
        PhoneOTP.purpose == purpose,
        PhoneOTP.consumed_at.is_(None)
    ).update({"consumed_at": now})

    # Generate cryptographically secure 6-digit code
    plain_otp = "".join(secrets.choice("0123456789") for _ in range(6))
    otp_digest = hash_phone_otp(phone_number, purpose, plain_otp)

    expires_at = now + datetime.timedelta(minutes=settings.SMS_OTP_EXPIRE_MINUTES)

    db_otp = PhoneOTP(
        owner_id=owner_id,
        phone_number=phone_number,
        otp_hash=otp_digest,
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

    # Record rate limit hit
    _PHONE_RATE_LIMITS.setdefault(phone_number, []).append(now)

    return db_otp, plain_otp


def verify_and_consume_phone_otp(
    db: Session,
    phone_number: str,
    otp: str,
    purpose: str
) -> PhoneOTP:
    """
    Verifies a supplied 6-digit OTP against active records for the phone number and purpose.
    Enforces maximum attempts, single-use, and expiration.
    Returns the verified PhoneOTP record upon success.
    """
    if not otp or len(otp) != 6 or not otp.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code must be exactly 6 digits."
        )

    now = datetime.datetime.utcnow()

    # Find the latest unconsumed OTP record for this phone number and purpose
    record = (
        db.query(PhoneOTP)
        .filter(
            PhoneOTP.phone_number == phone_number,
            PhoneOTP.purpose == purpose,
            PhoneOTP.consumed_at.is_(None)
        )
        .order_by(PhoneOTP.created_at.desc())
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification code found for this phone number. Please request a new code."
        )

    # Check maximum attempt threshold
    if record.attempts_count >= record.max_attempts:
        record.consumed_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many incorrect attempts. This code has been invalidated for security. Please request a new one."
        )

    # Check expiry
    if record.expires_at < now:
        record.consumed_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification code has expired (valid for 5 minutes). Please request a new code."
        )

    # Increment attempt count
    record.attempts_count += 1
    db.commit()

    # Verify HMAC digest
    expected_hash = hash_phone_otp(phone_number, purpose, otp)
    if not hmac.compare_digest(record.otp_hash, expected_hash):
        remaining_attempts = max(0, record.max_attempts - record.attempts_count)
        if remaining_attempts == 0:
            record.consumed_at = now
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect code. Maximum attempts exceeded. Please request a new code."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect verification code. {remaining_attempts} attempt(s) remaining."
        )

    # Mark consumed (single-use)
    record.consumed_at = now
    db.commit()
    db.refresh(record)

    return record

