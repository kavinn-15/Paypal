import datetime
import hashlib
import base64
import secrets
import logging
import urllib.parse
from typing import Dict, Any, Optional, Tuple
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import Owner, OAuthIdentity

logger = logging.getLogger("oauth_service")


def generate_pkce_pair() -> Tuple[str, str]:
    """Generates PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").replace("=", "")
    return verifier, challenge


def get_google_auth_url(
    state: str,
    code_challenge: Optional[str] = None,
    redirect_uri: Optional[str] = None
) -> str:
    """Builds the Google OAuth 2.0 OpenID Connect authorization URL."""
    client_id = settings.GOOGLE_CLIENT_ID or "placeholder_google_client_id.apps.googleusercontent.com"
    target_redirect_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI

    # Safety guard: In production mode, never allow redirect_uri to point to localhost
    if not settings.DEV_MODE and ("localhost" in target_redirect_uri or "127.0.0.1" in target_redirect_uri):
        logger.warning(
            f"Prevented localhost redirect URI in production OAuth initiation: {target_redirect_uri}. "
            f"Falling back to {settings.GOOGLE_REDIRECT_URI}"
        )
        target_redirect_uri = settings.GOOGLE_REDIRECT_URI

    base = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": target_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    return f"{base}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"


async def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """
    Validates a Google ID token with Google's tokeninfo endpoint.
    Verifies audience, issuer, expiration, and extracts stable 'sub' identifier.
    """
    if not id_token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token is required."
        )

    # In local testing/mock mode if token is prefixed with "mock_google_token"
    if id_token_str.startswith("mock_google_token") or id_token_str.startswith("mock_google:"):
        if not settings.DEV_MODE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Mock Google tokens are strictly prohibited in production mode."
            )
        if ":" in id_token_str:
            parts = id_token_str.split(":")
            sub = parts[1] if len(parts) > 1 else "google_sub_123"
            email = parts[2] if len(parts) > 2 else f"google.{sub}@example.org"
        else:
            sub = id_token_str.split("_")[-1]
            email = f"google.{sub}@example.org"
        return {
            "sub": sub,
            "email": email,
            "name": f"Google User {sub}",
            "email_verified": True,
            "iss": "https://accounts.google.com",
            "aud": settings.GOOGLE_CLIENT_ID or "placeholder_google_client_id"
        }

    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token_str}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url)
            if res.status_code != 200:
                logger.error(f"Google tokeninfo rejection: {res.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired Google identity token."
                )
            payload = res.json()

            # Verify issuer
            iss = payload.get("iss")
            if iss not in ["accounts.google.com", "https://accounts.google.com"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Untrusted Google token issuer."
                )

            # Verify audience if client_id is set and not a placeholder
            if settings.GOOGLE_CLIENT_ID and "placeholder" not in settings.GOOGLE_CLIENT_ID:
                if payload.get("aud") != settings.GOOGLE_CLIENT_ID:
                    logger.error(f"Google aud mismatch: expected {settings.GOOGLE_CLIENT_ID}, got {payload.get('aud')}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid Google identity token: audience does not match configured Client ID."
                    )

            # Verify email verification status
            if str(payload.get("email_verified", "")).lower() != "true":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google account email is not verified by Google."
                )

            return payload
    except httpx.RequestError as e:
        logger.error(f"Google tokeninfo network error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to contact Google OAuth servers. Please verify network connectivity."
        )


async def exchange_google_code(
    code: str,
    code_verifier: Optional[str] = None,
    redirect_uri: Optional[str] = None
) -> Dict[str, Any]:
    """Exchanges an authorization code for Google tokens."""
    target_redirect_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI

    # Safety guard: In production mode, never allow redirect_uri to point to localhost
    if not settings.DEV_MODE and ("localhost" in target_redirect_uri or "127.0.0.1" in target_redirect_uri):
        logger.warning(
            f"Prevented localhost redirect URI in production OAuth token exchange: {target_redirect_uri}. "
            f"Falling back to {settings.GOOGLE_REDIRECT_URI}"
        )
        target_redirect_uri = settings.GOOGLE_REDIRECT_URI
    if code.startswith("mock_google_"):
        if not settings.DEV_MODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mock Google authorization codes are strictly prohibited in production mode."
            )
        sub = "dev_google_user_101"
        email = "google.dev.user@example.com"
        return {
            "access_token": "mock_google_access_token",
            "id_token": f"mock_google:{sub}:{email}",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

    if settings.DEV_MODE and (not settings.GOOGLE_CLIENT_ID or "placeholder" in (settings.GOOGLE_CLIENT_ID or "")):
        sub = "dev_google_user_101"
        email = "google.dev.user@example.com"
        return {
            "access_token": "mock_google_access_token",
            "id_token": f"mock_google:{sub}:{email}",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

    if not settings.DEV_MODE:
        if not settings.GOOGLE_CLIENT_ID or "placeholder" in settings.GOOGLE_CLIENT_ID.lower() or not settings.GOOGLE_CLIENT_SECRET or "placeholder" in settings.GOOGLE_CLIENT_SECRET.lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google OAuth is not configured for production. Valid GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required."
            )

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID or "placeholder_google_client_id",
        "client_secret": settings.GOOGLE_CLIENT_SECRET or "placeholder_google_client_secret",
        "redirect_uri": target_redirect_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        data["code_verifier"] = code_verifier

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(token_url, data=data)
            if res.status_code != 200:
                logger.error(f"Google token exchange failed: {res.text}")
                detail_msg = "Google authorization code exchange failed."
                try:
                    err_payload = res.json()
                    err_desc = err_payload.get("error_description") or err_payload.get("error")
                    if err_desc:
                        detail_msg = f"Google token exchange failed: {err_desc}."
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{detail_msg} Please verify GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI in .env."
                )
            return res.json()
    except httpx.RequestError as e:
        logger.error(f"Google exchange network error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Network error communicating with Google OAuth servers."
        )


def link_or_create_oauth_user(
    db: Session,
    provider: str,
    provider_user_id: str,
    email: str,
    name: str
) -> Owner:
    """
    Safely resolves, links, or creates an Owner account for a verified OAuth identity.
    Preserves strict multi-tenant data isolation.
    """
    email_clean = email.lower().strip()
    now = datetime.datetime.utcnow()

    # 1. Check existing OAuth link
    existing_link = db.query(OAuthIdentity).filter(
        OAuthIdentity.provider == provider,
        OAuthIdentity.provider_user_id == provider_user_id
    ).first()

    if existing_link:
        owner = db.query(Owner).filter(Owner.id == existing_link.owner_id).first()
        if owner and owner.is_active:
            if not owner.email_verified:
                owner.email_verified = True
                owner.email_verified_at = now
                db.commit()
            return owner

    # 2. Check if an Owner with this email already exists
    owner = db.query(Owner).filter(Owner.email == email_clean).first()
    if owner:
        # Check if owner is active
        if not owner.is_active or owner.account_status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated or disabled."
            )
        # Link OAuth identity to existing owner
        new_link = OAuthIdentity(
            owner_id=owner.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email_clean,
            created_at=now
        )
        db.add(new_link)
        owner.email_verified = True
        if not owner.email_verified_at:
            owner.email_verified_at = now
        db.commit()
        db.refresh(owner)
        return owner

    # 3. Create brand new Owner account
    owner = Owner(
        name=name.strip() or email_clean.split("@")[0].title(),
        email=email_clean,
        hashed_password=None,  # OAuth only user
        currency="USD",
        preferred_currency="USD",
        country="US",
        business_type="Freelancer",
        terms_accepted=True,
        terms_accepted_at=now,
        token_version=1,
        email_verified=True,  # Verified by Google/OAuth provider
        email_verified_at=now,
        account_status="active",
        is_demo=False,
        is_active=True,
        created_at=now,
        updated_at=now
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)

    new_link = OAuthIdentity(
        owner_id=owner.id,
        provider=provider,
        provider_user_id=provider_user_id,
        email=email_clean,
        created_at=now
    )
    db.add(new_link)
    db.commit()

    return owner
