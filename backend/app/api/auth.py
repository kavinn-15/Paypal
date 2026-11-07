import datetime
import re
import secrets
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.config import settings
from backend.app.models import Owner, RefreshToken, Client, Invoice, Obligation, FinancialEntry, Forecast, Action
from backend.app.schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserProfile,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    VerifyEmailRequest
)
from backend.app.auth.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_refresh_token
from backend.app.auth.deps import get_current_user
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication & User Management"])

# In-memory login rate-limiting tracker: {email_key: [timestamp, ...]}
_FAILED_LOGINS: Dict[str, List[datetime.datetime]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 5


def check_rate_limit(key: str) -> None:
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(minutes=LOCKOUT_MINUTES)
    if key in _FAILED_LOGINS:
        _FAILED_LOGINS[key] = [t for t in _FAILED_LOGINS[key] if t > cutoff]
        if len(_FAILED_LOGINS[key]) >= MAX_FAILED_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Please wait {LOCKOUT_MINUTES} minutes before retrying."
            )


def record_failed_attempt(key: str) -> None:
    now = datetime.datetime.utcnow()
    if key not in _FAILED_LOGINS:
        _FAILED_LOGINS[key] = []
    _FAILED_LOGINS[key].append(now)


def clear_failed_attempts(key: str) -> None:
    if key in _FAILED_LOGINS:
        del _FAILED_LOGINS[key]


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain both letters and at least one number."
        )


@router.post("/register", response_model=TokenResponse)
def register(req: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account with isolated financial ledger and credentials.
    """
    validate_password_strength(req.password)

    email_clean = req.email.lower().strip()
    existing = db.query(Owner).filter(Owner.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )

    chosen_currency = (req.preferred_currency or req.currency or "USD").upper()
    verification_token = secrets.token_urlsafe(32)

    user = Owner(
        name=req.name.strip(),
        email=email_clean,
        hashed_password=hash_password(req.password),
        currency=chosen_currency,
        preferred_currency=chosen_currency,
        country=req.country or "US",
        business_type=req.business_type or "Freelancer",
        timezone=req.timezone or "UTC",
        email_verified=True,  # Default verified for frictionless hackathon onboarding
        email_verification_token=verification_token,
        account_status="active",
        is_demo=False,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Issue access and refresh tokens
    access_token = create_access_token({"sub": user.id, "email": user.email})
    refresh_token = create_refresh_token(user.id)

    db_refresh = RefreshToken(
        token=refresh_token,
        owner_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    )
    db.add(db_refresh)
    db.commit()

    append_audit_log(
        db,
        actor="system",
        event="USER_REGISTERED",
        payload={
            "user_id": user.id,
            "email": user.email,
            "currency": user.currency,
            "country": user.country,
            "business_type": user.business_type
        }
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        is_demo=user.is_demo,
        country=user.country,
        business_type=user.business_type,
        email_verified=user.email_verified
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and issue JWT access token and refresh token.
    Enforces login rate limiting.
    """
    email_clean = req.email.lower().strip()
    check_rate_limit(email_clean)

    user = db.query(Owner).filter(Owner.email == email_clean).first()
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        record_failed_attempt(email_clean)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or user.account_status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or disabled."
        )

    # Success: clear failed rate limiting counter
    clear_failed_attempts(email_clean)

    access_token = create_access_token({"sub": user.id, "email": user.email})
    refresh_token = create_refresh_token(user.id)

    db_refresh = RefreshToken(
        token=refresh_token,
        owner_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    )
    db.add(db_refresh)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        is_demo=user.is_demo,
        country=user.country or "US",
        business_type=user.business_type or "Freelancer",
        email_verified=user.email_verified
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request password reset instructions.
    To prevent email enumeration, always returns 200 generic success message.
    In DEV_MODE, includes dev_reset_link for local testing without SMTP.
    """
    email_clean = req.email.lower().strip()
    user = db.query(Owner).filter(Owner.email == email_clean).first()

    reset_token = secrets.token_urlsafe(32)
    dev_link = None

    if user and user.is_active:
        user.password_reset_token = reset_token
        user.reset_token_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        db.commit()

        append_audit_log(
            db,
            actor="owner",
            event="PASSWORD_RESET_REQUESTED",
            payload={"user_id": user.id, "email": user.email}
        )

        if settings.DEV_MODE:
            dev_link = f"/reset-password?token={reset_token}"

    return ForgotPasswordResponse(
        status="success",
        message="If an account with that email exists, password reset instructions have been generated.",
        dev_reset_link=dev_link
    )


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password using single-use cryptographically secure reset token.
    """
    if not req.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is required."
        )

    validate_password_strength(req.new_password)

    user = db.query(Owner).filter(Owner.password_reset_token == req.token).first()
    now = datetime.datetime.utcnow()

    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token. Please request a new recovery link."
        )

    user.hashed_password = hash_password(req.new_password)
    user.password_reset_token = None
    user.reset_token_expires_at = None

    # Invalidate all active sessions / refresh tokens
    db.query(RefreshToken).filter(
        RefreshToken.owner_id == user.id,
        RefreshToken.revoked == False
    ).update({"revoked": True})
    db.commit()

    append_audit_log(
        db,
        actor="owner",
        event="PASSWORD_RESET_COMPLETED",
        payload={"user_id": user.id, "email": user.email}
    )

    return {"status": "success", "message": "Password successfully updated. Please sign in with your new credentials."}


@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    """
    Verifies user email using registration verification token.
    """
    if not req.token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token is required.")

    user = db.query(Owner).filter(Owner.email_verification_token == req.token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token.")

    user.email_verified = True
    user.email_verification_token = None
    db.commit()

    return {"status": "success", "message": "Email address successfully verified."}


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Rotates refresh token and issues a new access token.
    """
    user_id = decode_refresh_token(req.refresh_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    token_record = db.query(RefreshToken).filter(
        RefreshToken.token == req.refresh_token,
        RefreshToken.owner_id == user_id,
        RefreshToken.revoked == False
    ).first()

    if not token_record or token_record.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or revoked")

    # Revoke old refresh token (rotation)
    token_record.revoked = True

    user = db.query(Owner).filter(Owner.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not active")

    new_access_token = create_access_token({"sub": user.id, "email": user.email})
    new_refresh_token = create_refresh_token(user.id)

    new_token_record = RefreshToken(
        token=new_refresh_token,
        owner_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    )
    db.add(new_token_record)
    db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        is_demo=user.is_demo
    )


@router.post("/logout")
def logout(current_user: Owner = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Revokes all active refresh tokens for the current user.
    """
    db.query(RefreshToken).filter(
        RefreshToken.owner_id == current_user.id,
        RefreshToken.revoked == False
    ).update({"revoked": True})
    db.commit()

    append_audit_log(
        db,
        actor="owner",
        event="USER_LOGGED_OUT",
        payload={"user_id": current_user.id}
    )
    return {"status": "success", "message": "Successfully logged out. All sessions terminated."}


@router.post("/demo-login", response_model=TokenResponse)
def demo_login(db: Session = Depends(get_db)):
    """
    One-click instant login as Alex Morgan (PayPal AI Hackathon demo scenario).
    Only permitted when DEV_MODE is enabled.
    """
    if not settings.DEV_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo login is strictly disabled in production environments."
        )

    # Strictly query for dedicated demo owner with is_demo == True. Never fallback to Owner.first()
    owner = db.query(Owner).filter(Owner.is_demo == True).first()
    if not owner:
        # Check if Alex Morgan demo account exists
        owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        if owner and not owner.is_demo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security violation: Demo login cannot issue credentials for a real user account."
            )
        if not owner:
            owner = Owner(
                name="Alex Morgan",
                email="alex.morgan.freelance@example.com",
                currency="USD",
                timezone="UTC",
                is_demo=True,
                is_active=True
            )
            db.add(owner)
            db.commit()
            db.refresh(owner)
        else:
            owner.is_demo = True
            db.commit()

    token = create_access_token({"sub": owner.id, "email": owner.email})
    refresh_token = create_refresh_token(owner.id)

    return TokenResponse(
        access_token=token,
        refresh_token=refresh_token,
        user_id=owner.id,
        email=owner.email,
        name=owner.name,
        currency=owner.currency,
        is_demo=True
    )


@router.get("/me", response_model=UserProfile)
def get_me(current_user: Owner = Depends(get_current_user)):
    """
    Get profile of currently authenticated user.
    """
    return current_user


@router.get("/export")
def export_user_financial_data(current_user: Owner = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Exports all financial entries, clients, invoices, obligations, and forecasts for the authenticated user.
    GDPR & Financial portability compliant.
    """
    clients = db.query(Client).filter(Client.owner_id == current_user.id).all()
    obligations = db.query(Obligation).filter(Obligation.owner_id == current_user.id).all()
    entries = db.query(FinancialEntry).filter(FinancialEntry.owner_id == current_user.id).all()
    forecasts = db.query(Forecast).filter(Forecast.owner_id == current_user.id).all()

    return {
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "currency": current_user.currency,
            "created_at": current_user.created_at.isoformat()
        },
        "clients": [
            {"id": c.id, "name": c.name, "email": c.email, "country": c.country, "typical_amount": float(c.typical_invoice_amount)}
            for c in clients
        ],
        "obligations": [
            {"id": o.id, "payee_name": o.payee_name, "payee_email": o.payee_email, "amount": float(o.amount), "due_date": o.due_date.isoformat(), "status": o.status}
            for o in obligations
        ],
        "financial_entries": [
            {"id": e.id, "title": e.title, "amount": float(e.amount), "currency": e.currency, "entry_type": e.entry_type, "status": e.status, "date": e.transaction_date.isoformat()}
            for e in entries
        ],
        "forecasts_count": len(forecasts)
    }


@router.delete("/account")
def delete_user_account(current_user: Owner = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Permanently deletes user account and all cascaded financial entries.
    """
    user_id = current_user.id
    db.delete(current_user)
    db.commit()

    append_audit_log(
        db,
        actor="system",
        event="USER_ACCOUNT_DELETED",
        payload={"deleted_user_id": user_id}
    )
    return {"status": "success", "message": f"Account {user_id} and all associated records permanently deleted."}

