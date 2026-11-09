import datetime
import re
import secrets
import jwt
from typing import Dict, List, Optional
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
    EmailVerifyOtpRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    PasswordResetVerifyOTPRequest,
    PasswordResetVerifyOTPResponse,
    PasswordResetConfirmRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    GoogleAuthUrlResponse,
    GoogleTokenRequest,
    PhoneVerificationRequest,
    PhoneVerifyOtpRequest,
    PhoneResendOtpRequest,
    PhoneLoginOtpRequest,
    PhoneLoginVerifyOtpRequest,
    PhoneLoginPasswordRequest,
    PhonePasswordResetRequest,
    PhonePasswordResetVerifyRequest,
    PhoneChangeRequest,
    PhoneChangeVerifyRequest,
    PhoneAuthResponse
)
from backend.app.models import Owner, RefreshToken, Client, Invoice, Obligation, FinancialEntry, Forecast, Action, PhoneOTP
from backend.app.auth.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_refresh_token
from backend.app.auth.deps import get_current_user, get_current_user_optional
from backend.app.guardrail.audit import append_audit_log
from backend.app.services.otp_service import create_otp, verify_and_consume_otp
from backend.app.auth.phone import normalize_phone_number, is_valid_phone_number, mask_phone_number, get_phone_country_code
from backend.app.services.phone_otp_service import create_phone_otp, verify_and_consume_phone_otp
from backend.app.services.sms_service import (
    dispatch_sms,
    render_phone_verification_sms,
    render_phone_login_sms,
    render_password_reset_sms,
    render_security_alert_sms
)
from backend.app.services.email_service import (
    send_email,
    render_verification_email,
    render_password_reset_email,
    render_password_changed_email,
    render_oauth_login_alert_email
)
from backend.app.services.oauth_service import (
    get_google_auth_url,
    verify_google_id_token,
    exchange_google_code,
    link_or_create_oauth_user
)

router = APIRouter(prefix="/auth", tags=["Authentication & User Management"])

# In-memory rate limiting tracker for failed logins: {email_key: [timestamp, ...]}
_FAILED_LOGINS: Dict[str, List[datetime.datetime]] = {}
_USED_RESET_JTIS: set = set()
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
    Generates a 6-digit email verification OTP and sends verification email.
    """
    validate_password_strength(req.password)

    email_clean = req.email.lower().strip()
    existing = db.query(Owner).filter(Owner.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )

    normalized_phone = None
    if req.phone_number and req.phone_number.strip():
        region = req.country if (req.country and len(req.country) == 2) else "IN"
        normalized_phone = normalize_phone_number(req.phone_number, default_region=region)
        phone_existing = db.query(Owner).filter(Owner.phone_number == normalized_phone).first()
        if phone_existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this phone number already exists"
            )

    chosen_currency = (req.preferred_currency or req.currency or "USD").upper()

    user = Owner(
        name=req.name.strip(),
        email=email_clean,
        hashed_password=hash_password(req.password),
        currency=chosen_currency,
        preferred_currency=chosen_currency,
        country=req.country or "US",
        locale=req.locale or "en-US",
        region_detection_enabled=True,
        region_preference_source=req.region_preference_source or "detected",
        business_type=req.business_type or "Freelancer",
        timezone=req.timezone or "UTC",
        email_verified=False,  # Unverified until 6-digit OTP is verified
        phone_number=normalized_phone,
        phone_country_code=req.phone_country_code or (get_phone_country_code(normalized_phone) if normalized_phone else "+91"),
        phone_verified=False,
        account_status="active",
        is_demo=False,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate 6-digit Email Verification OTP
    db_otp, plain_otp = create_otp(
        db=db,
        email=user.email,
        purpose="email_verification",
        owner_id=user.id
    )

    # Dispatch verification email
    html_content = render_verification_email(user.name, plain_otp)
    send_email(
        to_email=user.email,
        subject="Verify Your Email — Cashflow Lifeline",
        html_content=html_content
    )

    # If phone registered, dispatch SMS OTP
    if normalized_phone:
        _, plain_sms_otp = create_phone_otp(
            db=db,
            phone_number=normalized_phone,
            purpose="phone_verification",
            owner_id=user.id
        )
        dispatch_sms(
            to_phone=normalized_phone,
            message=render_phone_verification_sms(plain_sms_otp)
        )

    # Issue access and refresh tokens
    access_token = create_access_token({"sub": user.id, "email": user.email, "email_verified": False})
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
            "business_type": user.business_type,
            "email_verified": False
        }
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        preferred_currency=user.preferred_currency or user.currency,
        locale=user.locale or "en-US",
        region_detection_enabled=user.region_detection_enabled,
        is_demo=user.is_demo,
        country=user.country,
        business_type=user.business_type,
        email_verified=False,
        phone_number=user.phone_number,
        phone_country_code=user.phone_country_code,
        phone_verified=user.phone_verified
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

    access_token = create_access_token({"sub": user.id, "email": user.email, "email_verified": user.email_verified})
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
        preferred_currency=user.preferred_currency or user.currency,
        locale=user.locale or "en-US",
        region_detection_enabled=user.region_detection_enabled,
        is_demo=user.is_demo,
        country=user.country or "US",
        business_type=user.business_type or "Freelancer",
        email_verified=user.email_verified,
        phone_number=user.phone_number,
        phone_country_code=user.phone_country_code,
        phone_verified=user.phone_verified
    )


@router.post("/email/verify")
def verify_email_otp(req: EmailVerifyOtpRequest, db: Session = Depends(get_db)):
    """
    Verifies user email using a single-use 6-digit OTP code.
    Enforces expiration, attempt limits, and single-use invalidation.
    """
    email_clean = req.email.lower().strip()
    verify_and_consume_otp(db=db, email=email_clean, otp=req.otp, purpose="email_verification")

    user = db.query(Owner).filter(Owner.email == email_clean).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    now = datetime.datetime.utcnow()
    user.email_verified = True
    user.email_verified_at = now
    db.commit()

    append_audit_log(
        db,
        actor="owner",
        event="EMAIL_VERIFIED_VIA_OTP",
        payload={"user_id": user.id, "email": user.email}
    )

    # Issue updated access token reflecting verified status
    access_token = create_access_token({"sub": user.id, "email": user.email, "email_verified": True})

    return {
        "status": "success",
        "message": "Email address successfully verified. Full dashboard access unlocked.",
        "access_token": access_token
    }


@router.post("/email/verification/resend")
def resend_verification_otp(req: ResendVerificationRequest, db: Session = Depends(get_db)):
    """
    Resends 6-digit email verification OTP code.
    Enforces 60-second cooldown and invalidates previous active OTPs.
    """
    email_clean = req.email.lower().strip()
    user = db.query(Owner).filter(Owner.email == email_clean).first()

    if user and not user.email_verified:
        db_otp, plain_otp = create_otp(
            db=db,
            email=user.email,
            purpose="email_verification",
            owner_id=user.id
        )
        html_content = render_verification_email(user.name, plain_otp)
        send_email(
            to_email=user.email,
            subject="Your New Verification Code — Cashflow Lifeline",
            html_content=html_content
        )

    return {
        "status": "success",
        "message": "If an unverified account exists for this email, a new verification code has been dispatched."
    }


# Legacy compatibility route
@router.post("/verify-email")
def legacy_verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    if len(req.token) == 6 and req.token.isdigit():
        # Handle 6-digit token if passed
        user = db.query(Owner).filter(Owner.email_verification_token == req.token).first()
        if user:
            user.email_verified = True
            user.email_verified_at = datetime.datetime.utcnow()
            db.commit()
            return {"status": "success", "message": "Email address successfully verified."}
    return verify_email_otp(EmailVerifyOtpRequest(email="test@test.org", otp=req.token[:6]), db)


@router.post("/password-reset/request", response_model=ForgotPasswordResponse)
def request_password_reset(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Initiates password recovery by emailing a single-use 6-digit OTP code.
    To prevent user enumeration, always returns 200 with generic success message.
    """
    email_clean = req.email.lower().strip()
    user = db.query(Owner).filter(Owner.email == email_clean).first()

    dev_link = None
    if user and user.is_active:
        db_otp, plain_otp = create_otp(
            db=db,
            email=user.email,
            purpose="password_reset",
            owner_id=user.id
        )

        html_content = render_password_reset_email(user.name, plain_otp)
        send_email(
            to_email=user.email,
            subject="Reset Your Password — Cashflow Lifeline",
            html_content=html_content
        )

        append_audit_log(
            db,
            actor="owner",
            event="PASSWORD_RESET_REQUESTED",
            payload={"user_id": user.id, "email": user.email}
        )

        if settings.DEV_MODE:
            now = datetime.datetime.now(datetime.timezone.utc)
            dev_expire = now + datetime.timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
            dev_payload = {
                "sub": str(user.id),
                "email": user.email,
                "purpose": "password_reset_auth",
                "exp": dev_expire,
                "iat": now,
                "jti": secrets.token_hex(16)
            }
            dev_token = jwt.encode(dev_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
            dev_link = f"/reset-password?token={dev_token}"

    return ForgotPasswordResponse(
        status="success",
        message="If an account with that email exists, password reset instructions have been generated.",
        dev_reset_link=dev_link
    )


# Alias for compatibility with previous route
@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def legacy_forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return request_password_reset(req, db)


@router.post("/password-reset/verify-otp", response_model=PasswordResetVerifyOTPResponse)
def verify_password_reset_otp(req: PasswordResetVerifyOTPRequest, db: Session = Depends(get_db)):
    """
    Verifies the 6-digit password reset OTP.
    If valid, issues a short-lived single-use authorization token for setting the new password.
    """
    email_clean = req.email.lower().strip()
    verify_and_consume_otp(db=db, email=email_clean, otp=req.otp, purpose="password_reset")

    user = db.query(Owner).filter(Owner.email == email_clean).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    now = datetime.datetime.now(datetime.timezone.utc)
    expire = now + datetime.timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "purpose": "password_reset_auth",
        "exp": expire,
        "iat": now,
        "jti": secrets.token_hex(16)
    }
    reset_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    return PasswordResetVerifyOTPResponse(
        status="success",
        reset_token=reset_token,
        message="Code verified successfully. Please enter your new password."
    )


@router.post("/password-reset/confirm")
def confirm_password_reset(req: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    """
    Validates reset authorization token, hashes new password with Argon2id,
    and invalidates all previous sessions and refresh tokens.
    """
    try:
        payload = jwt.decode(req.reset_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("purpose") not in ["password_reset_auth", "password_reset"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token purpose.")
        jti = payload.get("jti")
        if jti and jti in _USED_RESET_JTIS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password reset token has already been used.")
        user_id = int(payload.get("sub"))
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset authorization token. Please request a new code."
        )

    validate_password_strength(req.new_password)

    user = db.query(Owner).filter(Owner.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    user.hashed_password = hash_password(req.new_password)
    if jti:
        _USED_RESET_JTIS.add(jti)

    # Invalidate all active refresh tokens / sessions
    db.query(RefreshToken).filter(
        RefreshToken.owner_id == user.id,
        RefreshToken.revoked == False
    ).update({"revoked": True})
    db.commit()

    # Dispatch security confirmation email
    html_confirm = render_password_changed_email(user.name)
    send_email(
        to_email=user.email,
        subject="Password Successfully Changed — Cashflow Lifeline",
        html_content=html_confirm
    )

    append_audit_log(
        db,
        actor="owner",
        event="PASSWORD_RESET_COMPLETED",
        payload={"user_id": user.id, "email": user.email}
    )

    return {
        "status": "success",
        "message": "Password successfully updated. Please sign in with your new credentials."
    }


# Alias for legacy compatibility
@router.post("/reset-password")
def legacy_reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    return confirm_password_reset(PasswordResetConfirmRequest(reset_token=req.token, new_password=req.new_password), db)


# =========================================================================
# Google OAuth 2.0 / OpenID Connect Endpoints
# =========================================================================

@router.get("/google/start", response_model=GoogleAuthUrlResponse)
def google_auth_start():
    """
    Initiates Google OAuth 2.0 flow.
    Returns authorization URL with state and configured client_id.
    """
    state = secrets.token_urlsafe(32)
    auth_url = get_google_auth_url(state=state)
    return GoogleAuthUrlResponse(auth_url=auth_url, state=state, client_id=settings.GOOGLE_CLIENT_ID)


@router.get("/google/callback", response_model=TokenResponse)
async def google_auth_callback(code: str, state: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handles Google OAuth redirect with authorization code.
    Exchanges code for tokens, verifies identity, and establishes authenticated session.
    """
    tokens = await exchange_google_code(code=code)
    id_token_str = tokens.get("id_token")
    if not id_token_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No ID token returned by Google.")

    id_info = await verify_google_id_token(id_token_str)
    sub = id_info["sub"]
    email = id_info.get("email")
    name = id_info.get("name", "")

    owner = link_or_create_oauth_user(
        db=db,
        provider="google",
        provider_user_id=sub,
        email=email,
        name=name
    )

    access_token = create_access_token({"sub": owner.id, "email": owner.email, "email_verified": True})
    refresh_token = create_refresh_token(owner.id)

    db_refresh = RefreshToken(
        token=refresh_token,
        owner_id=owner.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    )
    db.add(db_refresh)
    db.commit()

    append_audit_log(
        db,
        actor="owner",
        event="GOOGLE_OAUTH_LOGIN",
        payload={"user_id": owner.id, "google_sub": sub, "email": owner.email}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=owner.id,
        email=owner.email,
        name=owner.name,
        currency=owner.currency,
        is_demo=False,
        country=owner.country,
        business_type=owner.business_type,
        email_verified=True
    )


@router.post("/google/token", response_model=TokenResponse)
async def google_auth_token(req: GoogleTokenRequest, db: Session = Depends(get_db)):
    """
    One-Tap or Google Identity Services credential verification.
    Directly validates ID token, links/creates user, and issues authenticated session.
    """
    id_info = await verify_google_id_token(req.credential)
    sub = id_info["sub"]
    email = id_info.get("email")
    name = id_info.get("name", "")

    owner = link_or_create_oauth_user(
        db=db,
        provider="google",
        provider_user_id=sub,
        email=email,
        name=name
    )

    access_token = create_access_token({"sub": owner.id, "email": owner.email, "email_verified": True})
    refresh_token = create_refresh_token(owner.id)

    db_refresh = RefreshToken(
        token=refresh_token,
        owner_id=owner.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    )
    db.add(db_refresh)
    db.commit()

    append_audit_log(
        db,
        actor="owner",
        event="GOOGLE_TOKEN_LOGIN",
        payload={"user_id": owner.id, "google_sub": sub, "email": owner.email}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=owner.id,
        email=owner.email,
        name=owner.name,
        currency=owner.currency,
        is_demo=False,
        country=owner.country,
        business_type=owner.business_type,
        email_verified=True
    )


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

    new_access_token = create_access_token({"sub": user.id, "email": user.email, "email_verified": user.email_verified})
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
        is_demo=user.is_demo,
        country=user.country,
        business_type=user.business_type,
        email_verified=user.email_verified
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

    owner = db.query(Owner).filter(Owner.is_demo == True).first()
    if not owner:
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
                is_active=True,
                email_verified=True
            )
            db.add(owner)
            db.commit()
            db.refresh(owner)
        else:
            owner.is_demo = True
            owner.email_verified = True
            db.commit()

    token = create_access_token({"sub": owner.id, "email": owner.email, "email_verified": True})
    refresh_token = create_refresh_token(owner.id)

    return TokenResponse(
        access_token=token,
        refresh_token=refresh_token,
        user_id=owner.id,
        email=owner.email,
        name=owner.name,
        currency=owner.currency,
        is_demo=True,
        email_verified=True
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
            "email_verified": current_user.email_verified,
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


# =========================================================================
# Mobile Phone Number & SMS OTP Authentication Endpoints
# =========================================================================

@router.post("/phone/verification/request", response_model=PhoneAuthResponse)
def request_phone_verification(
    req: PhoneVerificationRequest,
    db: Session = Depends(get_db),
    current_user: Optional[Owner] = Depends(get_current_user_optional)
):
    """
    Dispatches a 6-digit SMS OTP to verify ownership of a mobile phone number.
    Enforces rate limits and 60-second cooldown.
    """
    normalized_phone = normalize_phone_number(req.phone_number, default_region=req.country_code or "IN")

    existing = db.query(Owner).filter(Owner.phone_number == normalized_phone).first()
    if existing and (not current_user or existing.id != current_user.id) and existing.phone_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already registered and verified on another account."
        )

    owner_id = current_user.id if current_user else (existing.id if existing else None)

    db_otp, plain_otp = create_phone_otp(
        db=db,
        phone_number=normalized_phone,
        purpose="phone_verification",
        owner_id=owner_id,
        enforce_cooldown=True
    )

    msg = render_phone_verification_sms(plain_otp)
    dispatch_sms(to_phone=normalized_phone, message=msg)

    append_audit_log(
        db,
        actor="owner" if current_user else "anonymous",
        event="PHONE_VERIFICATION_REQUESTED",
        payload={"phone_number": mask_phone_number(normalized_phone)}
    )

    return PhoneAuthResponse(
        status="success",
        message="Verification code dispatched via SMS. Valid for 5 minutes.",
        phone_number=normalized_phone,
        cooldown_seconds=settings.SMS_RESEND_COOLDOWN_SECONDS
    )


@router.post("/phone/verification/verify", response_model=PhoneAuthResponse)
def verify_phone_number(
    req: PhoneVerifyOtpRequest,
    db: Session = Depends(get_db),
    current_user: Optional[Owner] = Depends(get_current_user_optional)
):
    """
    Validates the 6-digit SMS OTP and marks the phone number as verified.
    """
    normalized_phone = normalize_phone_number(req.phone_number)
    verify_and_consume_phone_otp(
        db=db,
        phone_number=normalized_phone,
        otp=req.otp,
        purpose="phone_verification"
    )

    now = datetime.datetime.utcnow()

    if current_user:
        current_user.phone_number = normalized_phone
        current_user.phone_country_code = get_phone_country_code(normalized_phone)
        current_user.phone_verified = True
        current_user.phone_verified_at = now
        db.commit()
    else:
        owner = db.query(Owner).filter(Owner.phone_number == normalized_phone).first()
        if owner:
            owner.phone_verified = True
            owner.phone_verified_at = now
            db.commit()

    append_audit_log(
        db,
        actor="owner" if current_user else "anonymous",
        event="PHONE_VERIFIED",
        payload={"phone_number": mask_phone_number(normalized_phone)}
    )

    return PhoneAuthResponse(
        status="success",
        message="Phone number successfully verified.",
        phone_number=normalized_phone
    )


@router.post("/phone/verification/resend", response_model=PhoneAuthResponse)
def resend_phone_verification(
    req: PhoneResendOtpRequest,
    db: Session = Depends(get_db),
    current_user: Optional[Owner] = Depends(get_current_user_optional)
):
    """
    Resends a 6-digit SMS verification code, enforcing cooldown and attempt constraints.
    """
    normalized_phone = normalize_phone_number(req.phone_number)
    owner_id = current_user.id if current_user else None

    db_otp, plain_otp = create_phone_otp(
        db=db,
        phone_number=normalized_phone,
        purpose="phone_verification",
        owner_id=owner_id,
        enforce_cooldown=True
    )

    msg = render_phone_verification_sms(plain_otp)
    dispatch_sms(to_phone=normalized_phone, message=msg)

    return PhoneAuthResponse(
        status="success",
        message="A fresh verification code has been dispatched via SMS.",
        phone_number=normalized_phone,
        cooldown_seconds=settings.SMS_RESEND_COOLDOWN_SECONDS
    )


@router.post("/phone/login/request-otp", response_model=PhoneAuthResponse)
def request_phone_login_otp(req: PhoneLoginOtpRequest, db: Session = Depends(get_db)):
    """
    Requests a passwordless sign-in SMS OTP.
    Only works for registered and verified phone numbers.
    """
    normalized_phone = normalize_phone_number(req.phone_number)
    user = db.query(Owner).filter(Owner.phone_number == normalized_phone).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is not registered with an account."
        )

    if not user.phone_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number has not been verified. Please sign in with email and verify your number."
        )

    if not user.is_active or user.account_status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated or disabled."
        )

    db_otp, plain_otp = create_phone_otp(
        db=db,
        phone_number=normalized_phone,
        purpose="phone_login",
        owner_id=user.id,
        enforce_cooldown=True
    )

    msg = render_phone_login_sms(plain_otp)
    dispatch_sms(to_phone=normalized_phone, message=msg)

    append_audit_log(
        db,
        actor="owner",
        event="PHONE_LOGIN_OTP_REQUESTED",
        payload={"user_id": user.id, "phone_number": mask_phone_number(normalized_phone)}
    )

    return PhoneAuthResponse(
        status="success",
        message="Sign-in code dispatched via SMS. Valid for 5 minutes.",
        phone_number=normalized_phone,
        cooldown_seconds=settings.SMS_RESEND_COOLDOWN_SECONDS
    )


@router.post("/phone/login/verify-otp", response_model=TokenResponse)
def verify_phone_login_otp(req: PhoneLoginVerifyOtpRequest, db: Session = Depends(get_db)):
    """
    Verifies SMS login OTP, authenticates the Owner account, and issues session tokens.
    """
    normalized_phone = normalize_phone_number(req.phone_number)
    verify_and_consume_phone_otp(
        db=db,
        phone_number=normalized_phone,
        otp=req.otp,
        purpose="phone_login"
    )

    user = db.query(Owner).filter(Owner.phone_number == normalized_phone).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account not found or inactive."
        )

    access_token = create_access_token({"sub": user.id, "email": user.email, "email_verified": user.email_verified})
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
        actor="owner",
        event="LOGIN_PHONE_OTP_SUCCESS",
        payload={"user_id": user.id, "phone_number": mask_phone_number(normalized_phone)}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        preferred_currency=user.preferred_currency or user.currency,
        locale=user.locale or "en-US",
        region_detection_enabled=user.region_detection_enabled,
        is_demo=user.is_demo,
        country=user.country or "US",
        business_type=user.business_type or "Freelancer",
        email_verified=user.email_verified,
        phone_number=user.phone_number,
        phone_country_code=user.phone_country_code,
        phone_verified=user.phone_verified
    )


@router.post("/phone/login/password", response_model=TokenResponse)
def login_with_phone_password(req: PhoneLoginPasswordRequest, db: Session = Depends(get_db)):
    """
    Authenticates an existing Owner using registered mobile phone number and password.
    """
    normalized_phone = normalize_phone_number(req.phone_number)
    check_rate_limit(normalized_phone)

    user = db.query(Owner).filter(Owner.phone_number == normalized_phone).first()
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        record_failed_attempt(normalized_phone)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or user.account_status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or disabled."
        )

    clear_failed_attempts(normalized_phone)

    access_token = create_access_token({"sub": user.id, "email": user.email, "email_verified": user.email_verified})
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
        actor="owner",
        event="LOGIN_PHONE_PASSWORD_SUCCESS",
        payload={"user_id": user.id, "phone_number": mask_phone_number(normalized_phone)}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        preferred_currency=user.preferred_currency or user.currency,
        locale=user.locale or "en-US",
        region_detection_enabled=user.region_detection_enabled,
        is_demo=user.is_demo,
        country=user.country or "US",
        business_type=user.business_type or "Freelancer",
        email_verified=user.email_verified,
        phone_number=user.phone_number,
        phone_country_code=user.phone_country_code,
        phone_verified=user.phone_verified
    )


@router.post("/phone/password-reset/request", response_model=PhoneAuthResponse)
def request_phone_password_reset(req: PhonePasswordResetRequest, db: Session = Depends(get_db)):
    """
    Requests a password recovery OTP via SMS.
    Uses generic anti-enumeration response for registered and unregistered numbers.
    """
    normalized_phone = normalize_phone_number(req.phone_number)
    user = db.query(Owner).filter(Owner.phone_number == normalized_phone).first()

    if user and user.is_active:
        db_otp, plain_otp = create_phone_otp(
            db=db,
            phone_number=normalized_phone,
            purpose="password_reset",
            owner_id=user.id,
            enforce_cooldown=True
        )
        msg = render_password_reset_sms(plain_otp)
        dispatch_sms(to_phone=normalized_phone, message=msg)

        append_audit_log(
            db,
            actor="owner",
            event="PHONE_PASSWORD_RESET_REQUESTED",
            payload={"user_id": user.id, "phone_number": mask_phone_number(normalized_phone)}
        )

    return PhoneAuthResponse(
        status="success",
        message="If an account with this phone number exists, password recovery instructions have been sent.",
        phone_number=normalized_phone,
        cooldown_seconds=settings.SMS_RESEND_COOLDOWN_SECONDS
    )


@router.post("/phone/password-reset/verify-otp", response_model=PasswordResetVerifyOTPResponse)
def verify_phone_password_reset_otp(req: PhonePasswordResetVerifyRequest, db: Session = Depends(get_db)):
    """
    Verifies 6-digit phone recovery OTP and issues a short-lived single-use password-reset authorization token.
    """
    normalized_phone = normalize_phone_number(req.phone_number)
    verify_and_consume_phone_otp(
        db=db,
        phone_number=normalized_phone,
        otp=req.otp,
        purpose="password_reset"
    )

    user = db.query(Owner).filter(Owner.phone_number == normalized_phone).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    now = datetime.datetime.now(datetime.timezone.utc)
    expire = now + datetime.timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "phone": normalized_phone,
        "purpose": "password_reset_auth",
        "exp": expire,
        "iat": now,
        "jti": secrets.token_hex(16)
    }
    reset_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    return PasswordResetVerifyOTPResponse(
        status="success",
        reset_token=reset_token,
        message="Code verified successfully. Please enter your new password."
    )


@router.post("/phone/password-reset/confirm")
def confirm_phone_password_reset(req: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    """
    Alias for password reset confirmation, updating password and invalidating sessions.
    """
    return confirm_password_reset(req, db)


@router.post("/phone/change/request", response_model=PhoneAuthResponse)
def request_phone_change(
    req: PhoneChangeRequest,
    current_user: Owner = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reauthenticates with current password and dispatches SMS verification OTP to new phone number.
    Does not replace the existing number until the new one is verified.
    """
    if not current_user.hashed_password or not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password. Reauthentication required to modify phone number."
        )

    normalized_new = normalize_phone_number(req.new_phone_number, default_region=req.country_code or "IN")
    if normalized_new == current_user.phone_number and current_user.phone_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is already your verified phone number."
        )

    existing = db.query(Owner).filter(Owner.phone_number == normalized_new).first()
    if existing and existing.id != current_user.id and existing.phone_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already registered and verified on another account."
        )

    db_otp, plain_otp = create_phone_otp(
        db=db,
        phone_number=normalized_new,
        purpose="phone_change",
        owner_id=current_user.id,
        enforce_cooldown=True
    )

    msg = render_phone_verification_sms(plain_otp)
    dispatch_sms(to_phone=normalized_new, message=msg)

    append_audit_log(
        db,
        actor="owner",
        event="PHONE_CHANGE_REQUESTED",
        payload={"user_id": current_user.id, "new_phone": mask_phone_number(normalized_new)}
    )

    return PhoneAuthResponse(
        status="success",
        message="Verification code dispatched to your new phone number. Valid for 5 minutes.",
        phone_number=normalized_new,
        cooldown_seconds=settings.SMS_RESEND_COOLDOWN_SECONDS
    )


@router.post("/phone/change/verify", response_model=PhoneAuthResponse)
def verify_phone_change(
    req: PhoneChangeVerifyRequest,
    current_user: Owner = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifies OTP for the new phone number and updates the Owner account.
    Dispatches security alert to previous phone number.
    """
    normalized_new = normalize_phone_number(req.new_phone_number)
    verify_and_consume_phone_otp(
        db=db,
        phone_number=normalized_new,
        otp=req.otp,
        purpose="phone_change"
    )

    old_phone = current_user.phone_number
    current_user.phone_number = normalized_new
    current_user.phone_country_code = get_phone_country_code(normalized_new)
    current_user.phone_verified = True
    current_user.phone_verified_at = datetime.datetime.utcnow()
    db.commit()

    if old_phone and old_phone != normalized_new:
        alert = render_security_alert_sms("Your account phone number was successfully changed.")
        dispatch_sms(to_phone=old_phone, message=alert)

    append_audit_log(
        db,
        actor="owner",
        event="PHONE_CHANGE_COMPLETED",
        payload={
            "user_id": current_user.id,
            "old_phone": mask_phone_number(old_phone) if old_phone else None,
            "new_phone": mask_phone_number(normalized_new)
        }
    )

    return PhoneAuthResponse(
        status="success",
        message="Your phone number has been updated and verified.",
        phone_number=normalized_new
    )
