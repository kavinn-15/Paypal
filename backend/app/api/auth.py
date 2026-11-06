from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner
from backend.app.schemas import UserRegister, UserLogin, TokenResponse, UserProfile
from backend.app.auth.security import hash_password, verify_password, create_access_token
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

    append_audit_log(
        db,
        actor="system",
        event="USER_REGISTERED",
        payload={"user_id": user.id, "email": user.email, "currency": user.currency}
    )

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        is_demo=user.is_demo
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and issue JWT access token.
    """
    user = db.query(Owner).filter(Owner.email == req.email.lower()).first()
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        currency=user.currency,
        is_demo=user.is_demo
    )


@router.post("/demo-login", response_model=TokenResponse)
def demo_login(db: Session = Depends(get_db)):
    """
    One-click instant login as Alex Morgan (PayPal AI Hackathon demo scenario).
    """
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
    return TokenResponse(
        access_token=token,
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
