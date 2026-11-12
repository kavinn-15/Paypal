import pytest
from httpx import AsyncClient, ASGITransport
from urllib.parse import parse_qs, urlparse

from backend.app.main import app
from backend.app.config import Settings, settings
from backend.app.services.oauth_service import get_google_auth_url
from backend.app.api.auth import validate_oauth_redirect_uri


def test_settings_default_dev_redirect_uri():
    """In development mode, GOOGLE_REDIRECT_URI defaults to local frontend callback."""
    s = Settings(
        DEV_MODE=True,
        APP_BASE_URL="http://localhost:5173",
        GOOGLE_REDIRECT_URI=None
    )
    assert s.GOOGLE_REDIRECT_URI == "http://localhost:5173/auth/callback/google"


def test_settings_derives_redirect_uri_from_app_base_url():
    """When APP_BASE_URL is set to production, GOOGLE_REDIRECT_URI dynamically derives from it."""
    s = Settings(
        DEV_MODE=True,
        APP_BASE_URL="https://cashflow-lifeline.vercel.app",
        GOOGLE_REDIRECT_URI=None
    )
    assert s.GOOGLE_REDIRECT_URI == "https://cashflow-lifeline.vercel.app/auth/callback/google"


def test_settings_overrides_stale_localhost_redirect_when_app_base_is_production():
    """If APP_BASE_URL is a production domain, stale localhost GOOGLE_REDIRECT_URI is auto-corrected."""
    s = Settings(
        DEV_MODE=True,
        APP_BASE_URL="https://cashflow-lifeline.vercel.app",
        GOOGLE_REDIRECT_URI="http://localhost:5173/auth/callback/google"
    )
    assert s.GOOGLE_REDIRECT_URI == "https://cashflow-lifeline.vercel.app/auth/callback/google"


def test_settings_preserves_explicit_custom_non_localhost_redirect():
    """Explicit custom non-localhost redirect URIs are preserved."""
    s = Settings(
        DEV_MODE=True,
        APP_BASE_URL="https://cashflow-lifeline.vercel.app",
        GOOGLE_REDIRECT_URI="https://cashflow-lifeline.vercel.app/custom/callback"
    )
    assert s.GOOGLE_REDIRECT_URI == "https://cashflow-lifeline.vercel.app/custom/callback"


def test_settings_production_strictly_forbids_localhost_redirect():
    """In production mode (DEV_MODE=False), GOOGLE_REDIRECT_URI is never allowed to be localhost."""
    s = Settings(
        DEV_MODE=False,
        APP_BASE_URL="http://localhost:5173",
        GOOGLE_REDIRECT_URI="http://localhost:5173/auth/callback/google",
        APPROVAL_SECRET="super-strong-test-approval-secret-32-chars-long",
        JWT_SECRET="super-strong-test-jwt-secret-32-chars-long-here",
        OTP_PEPPER="super-strong-test-otp-pepper-32-chars-long-here",
        PAYPAL_WEBHOOK_ID="WH-VALID-1234567890",
        PAYPAL_CLIENT_ID="VALID_SANDBOX_CLIENT_ID_XYZ",
        PAYPAL_CLIENT_SECRET="VALID_SANDBOX_SECRET_XYZ"
    )
    assert "localhost" not in s.GOOGLE_REDIRECT_URI
    assert "127.0.0.1" not in s.GOOGLE_REDIRECT_URI
    assert s.GOOGLE_REDIRECT_URI == "https://cashflow-lifeline.vercel.app/auth/callback/google"


def test_validate_oauth_redirect_uri_allowlist():
    """validate_oauth_redirect_uri permits configured domains and rejects open redirects."""
    # Production callback allowed
    prod_uri = "https://cashflow-lifeline.vercel.app/auth/callback/google"
    assert validate_oauth_redirect_uri(prod_uri) == prod_uri

    # Subdomain on vercel.app allowed
    preview_uri = "https://cashflow-lifeline-git-preview-test.vercel.app/auth/callback/google"
    assert validate_oauth_redirect_uri(preview_uri) == preview_uri

    # Open redirect / malicious domain rejected and replaced with safe default
    malicious = "https://evil-attacker-site.com/auth/callback/google"
    assert validate_oauth_redirect_uri(malicious) == settings.GOOGLE_REDIRECT_URI


def test_get_google_auth_url_construction():
    """get_google_auth_url constructs valid Google OAuth URL with proper redirect_uri."""
    auth_url = get_google_auth_url(
        state="test_state_123",
        redirect_uri="https://cashflow-lifeline.vercel.app/auth/callback/google"
    )
    parsed = urlparse(auth_url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    qs = parse_qs(parsed.query)
    assert qs["redirect_uri"] == ["https://cashflow-lifeline.vercel.app/auth/callback/google"]
    assert qs["state"] == ["test_state_123"]
    assert qs["response_type"] == ["code"]


@pytest.mark.asyncio
async def test_auth_google_start_with_production_redirect(monkeypatch):
    """GET /auth/google/start respects production redirect_uri when configured."""
    monkeypatch.setattr(settings, "APP_BASE_URL", "https://cashflow-lifeline.vercel.app")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "https://cashflow-lifeline.vercel.app/auth/callback/google")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/auth/google/start")
        assert res.status_code == 200
        data = res.json()
        assert "cashflow-lifeline.vercel.app" in data["auth_url"]
        assert "localhost" not in data["auth_url"]


@pytest.mark.asyncio
async def test_auth_google_start_with_explicit_client_redirect_param(monkeypatch):
    """GET /auth/google/start accepts a valid client-supplied redirect_uri."""
    monkeypatch.setattr(settings, "DEV_MODE", True)
    prod_cb = "https://cashflow-lifeline.vercel.app/auth/callback/google"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/auth/google/start?redirect_uri={prod_cb}")
        assert res.status_code == 200
        data = res.json()
        assert "cashflow-lifeline.vercel.app" in data["auth_url"]


@pytest.mark.asyncio
async def test_auth_google_start_rejects_malicious_client_redirect_param(monkeypatch):
    """GET /auth/google/start ignores unapproved client-supplied redirect_uri and uses safe default."""
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "https://cashflow-lifeline.vercel.app/auth/callback/google")
    malicious = "https://phishing-scam.com/steal"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/auth/google/start?redirect_uri={malicious}")
        assert res.status_code == 200
        data = res.json()
        assert "phishing-scam.com" not in data["auth_url"]
        assert "cashflow-lifeline.vercel.app" in data["auth_url"]

