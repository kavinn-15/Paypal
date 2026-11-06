from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Owner
from backend.app.auth.security import decode_access_token
from backend.app.config import settings

security_bearer = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[Owner]:
    """
    Extracts the current user if a valid JWT is provided.
    If no token is provided, returns None.
    """
    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and "sub" in payload:
            user_id = payload.get("sub")
            user = db.query(Owner).filter(Owner.id == user_id).first()
            if user:
                return user
    return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Owner:
    """
    Enforces authentication.
    In DEV_MODE, if no Bearer token is provided, gracefully falls back to the primary
    seeded owner (Alex Morgan) to ensure seamless hackathon demo & automated test compatibility.
    When a token IS provided, strictly isolates the user.
    """
    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = payload.get("sub")
        user = db.query(Owner).filter(Owner.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # Development & Demo Fallback
    if settings.DEV_MODE:
        owner = db.query(Owner).first()
        if owner:
            return owner
        # If no owner exists yet, create default Alex Morgan demo persona
        demo_owner = Owner(
            name="Alex Morgan",
            email="alex.morgan.freelance@gmail.com",
            currency="USD",
            timezone="UTC",
            is_demo=True,
            is_active=True
        )
        db.add(demo_owner)
        db.commit()
        db.refresh(demo_owner)
        return demo_owner

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
