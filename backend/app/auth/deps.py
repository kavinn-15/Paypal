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
    If no token is provided or account is disabled/revoked, returns None.
    """
    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and "sub" in payload:
            user_id = payload.get("sub")
            user = db.query(Owner).filter(Owner.id == user_id).first()
            if user and user.is_active and user.account_status == "active":
                token_ver = payload.get("ver")
                if token_ver is not None and getattr(user, "token_version", 1) is not None:
                    if token_ver < getattr(user, "token_version", 1):
                        return None
                return user
    return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Owner:
    """
    Enforces authentication across all protected financial endpoints.
    Strictly verifies JWT Bearer token and rejects unauthenticated, deactivated, or expired requests.
    Zero implicit first-user fallback.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

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

    if not user.is_active or user.account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or disabled."
        )

    token_ver = payload.get("ver")
    if token_ver is not None and getattr(user, "token_version", 1) is not None:
        if token_ver < getattr(user, "token_version", 1):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been terminated or password changed. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return user


def get_verified_current_user(
    current_user: Owner = Depends(get_current_user)
) -> Owner:
    """
    Enforces that the user has verified their email before accessing protected financial endpoints.
    Demo accounts (is_demo=True) are pre-verified.
    """
    if not current_user.is_demo and not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified. Please verify your email via 6-digit OTP to access financial records."
        )
    return current_user

