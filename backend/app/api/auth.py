import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.config import settings
from backend.app.models import Owner, RefreshToken, Client, Invoice, Obligation, FinancialEntry, Forecast, Action
from backend.app.schemas import UserRegister, UserLogin, TokenResponse, UserProfile, RefreshTokenRequest
from backend.app.auth.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_refresh_token
from backend.app.auth.deps import get_current_user
from backend.app.guardrail.audit import append_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication & User Management"])


@router.post("/register", response_model=TokenResponse)
def register(req: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account with isolated financial ledger and credentials.
    """
    existing = db.query(Owner).filter(Owner.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )

    user = Owner(
        name=req.name,
        email=req.email.lower(),
        hashed_password=hash_password(req.password),
        currency=req.currency.upper(),
        timezone=req.timezone,
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
        payload={"user_id": user.id, "email": user.email, "currency": user.currency}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        is_demo=user.is_demo
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and issue JWT access token and refresh token.
    """
    user = db.query(Owner).filter(Owner.email == req.email.lower()).first()
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated."
        )

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
        is_demo=user.is_demo
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

    owner = db.query(Owner).filter(Owner.is_demo == True).first()
    if not owner:
        owner = db.query(Owner).first()
    if not owner:
        owner = Owner(
            name="Alex Morgan",
            email="alex.morgan.freelance@gmail.com",
            currency="USD",
            timezone="UTC",
            is_demo=True,
            is_active=True
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

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

