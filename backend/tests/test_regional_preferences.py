import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import Owner, AuditLog
from backend.app.auth.security import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_user():
    db: Session = SessionLocal()
    user = db.query(Owner).filter(Owner.email == "test.regional@example.com").first()
    if not user:
        user = Owner(
            name="Regional Test User",
            email="test.regional@example.com",
            currency="USD",
            preferred_currency="USD",
            country="US",
            locale="en-US",
            region_detection_enabled=True,
            region_preference_source="detected",
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email, "email_verified": True})
    db.close()
    return {"user_id": user.id, "token": token}


def test_detect_region_with_client_hint(client):
    """Explicit client hint takes priority and maps to correct country and currency."""
    res = client.get("/api/region/detect?client_hint=IN")
    assert res.status_code == 200
    data = res.json()
    assert data["country"] == "IN"
    assert data["country_name"] == "India"
    assert data["suggested_currency"] == "INR"
    assert data["currency_symbol"] == "₹"
    assert data["flag"] == "🇮🇳"
    assert data["detection_method"] == "client_hint"
    assert data["confidence"] == 1.0


def test_detect_region_with_cf_header(client):
    """Cloudflare CF-IPCountry header is respected."""
    headers = {"CF-IPCountry": "GB"}
    res = client.get("/api/region/detect", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["country"] == "GB"
    assert data["country_name"] == "United Kingdom"
    assert data["suggested_currency"] == "GBP"
    assert data["currency_symbol"] == "£"
    assert data["detection_method"] == "header"


def test_detect_region_with_accept_language(client):
    """Accept-Language header is used when proxy headers and public IP are not present."""
    headers = {"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}
    res = client.get("/api/region/detect", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["country"] == "DE"
    assert data["suggested_currency"] == "EUR"
    assert data["currency_symbol"] == "€"
    assert data["detection_method"] == "browser_locale"


def test_detect_region_default_fallback(client):
    """Local loopback without headers falls back cleanly to US / USD."""
    res = client.get("/api/region/detect")
    assert res.status_code == 200
    data = res.json()
    assert "country" in data
    assert "suggested_currency" in data
    assert "currency_symbol" in data


def test_get_countries_catalog(client):
    """Returns sorted country catalog including popular items at top."""
    res = client.get("/api/region/countries")
    assert res.status_code == 200
    countries = res.json()
    assert len(countries) > 50
    # First country should be marked popular
    assert countries[0]["popular"] is True
    # Find India and US
    codes = [c["code"] for c in countries]
    assert "US" in codes
    assert "IN" in codes
    assert "GB" in codes


def test_get_currencies_catalog(client):
    """Returns supported currencies list with decimals and symbols."""
    res = client.get("/api/region/currencies")
    assert res.status_code == 200
    currencies = res.json()
    codes = {c["code"]: c for c in currencies}
    assert "USD" in codes
    assert "INR" in codes
    assert "JPY" in codes
    assert codes["JPY"]["decimals"] == 0  # Zero-decimal currency
    assert codes["USD"]["decimals"] == 2
    assert codes["INR"]["symbol"] == "₹"


def test_get_and_update_user_regional_preferences(client, auth_user):
    """Authenticated user can fetch and update their regional preferences safely."""
    headers = {"Authorization": f"Bearer {auth_user['token']}"}

    # 1. Fetch current preferences
    res = client.get("/api/profile/regional-preferences", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["country"] in ["US", "IN"]
    assert data["currency"] == "USD"

    # 2. Update to India / INR
    update_payload = {
        "country": "IN",
        "preferred_currency": "INR",
        "locale": "en-IN",
        "region_detection_enabled": False
    }
    put_res = client.put("/api/profile/regional-preferences", json=update_payload, headers=headers)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["country"] == "IN"
    assert updated["country_name"] == "India"
    assert updated["preferred_currency"] == "INR"
    assert updated["currency_symbol"] == "₹"
    assert updated["currency"] == "USD"  # Base ledger currency preserved!
    assert updated["region_preference_source"] == "manual"
    assert updated["region_detection_enabled"] is False

    # 3. Verify in database
    db: Session = SessionLocal()
    user = db.query(Owner).filter(Owner.id == auth_user["user_id"]).first()
    assert user.country == "IN"
    assert user.preferred_currency == "INR"
    assert user.currency == "USD"
    assert user.region_preference_source == "manual"
    assert user.region_preferences_updated_at is not None

    # Verify audit log was recorded
    audit = db.query(AuditLog).filter(
        AuditLog.event == "REGIONAL_PREFERENCES_UPDATED"
    ).order_by(AuditLog.id.desc()).first()
    assert audit is not None
    assert audit.payload["user_id"] == auth_user["user_id"]
    db.close()


def test_update_regional_preferences_invalid_country_rejected(client, auth_user):
    """Validation rejects invalid country or currency."""
    headers = {"Authorization": f"Bearer {auth_user['token']}"}
    res = client.put("/api/profile/regional-preferences", json={"country": "ZZ"}, headers=headers)
    assert res.status_code == 400
    assert "Unsupported country code" in res.json()["detail"]

    res2 = client.put("/api/profile/regional-preferences", json={"preferred_currency": "XYZ"}, headers=headers)
    assert res2.status_code == 400
    assert "Unsupported currency code" in res2.json()["detail"]


def test_detect_region_public_ip_india_mocked(client, monkeypatch):
    """Public IP from India resolves to IN and INR with status 'success'."""
    from backend.app.services import region_service

    async def mock_lookup(ip: str):
        return {"country": "IN", "currency": "INR", "city": "Bengaluru", "region": "Karnataka"}

    monkeypatch.setattr(region_service, "lookup_ip_geolocation", mock_lookup)
    headers = {"X-Forwarded-For": "103.21.244.2"}
    res = client.get("/api/region/detect", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is True
    assert data["status"] == "success"
    assert data["country"] == "IN"
    assert data["suggested_currency"] == "INR"
    assert data["detection_method"] == "ip_geolocation"


def test_detect_region_public_ip_us_mocked(client, monkeypatch):
    """Public IP from US resolves to US and USD with status 'success'."""
    from backend.app.services import region_service

    async def mock_lookup(ip: str):
        return {"country": "US", "currency": "USD", "city": "Ashburn", "region": "Virginia"}

    monkeypatch.setattr(region_service, "lookup_ip_geolocation", mock_lookup)
    headers = {"X-Forwarded-For": "8.8.8.8"}
    res = client.get("/api/region/detect", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is True
    assert data["status"] == "success"
    assert data["country"] == "US"
    assert data["suggested_currency"] == "USD"
    assert data["detection_method"] == "ip_geolocation"


def test_detect_region_public_ip_uk_mocked(client, monkeypatch):
    """Public IP from UK resolves to GB and GBP with status 'success'."""
    from backend.app.services import region_service

    async def mock_lookup(ip: str):
        return {"country": "GB", "currency": "GBP", "city": "London", "region": "England"}

    monkeypatch.setattr(region_service, "lookup_ip_geolocation", mock_lookup)
    headers = {"X-Forwarded-For": "212.58.244.20"}
    res = client.get("/api/region/detect", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is True
    assert data["status"] == "success"
    assert data["country"] == "GB"
    assert data["suggested_currency"] == "GBP"
    assert data["detection_method"] == "ip_geolocation"


def test_client_hint_cannot_override_reliable_detection(client):
    """A stale or malicious client_hint cannot override a reliable proxy header."""
    headers = {"CF-IPCountry": "IN"}
    res = client.get("/api/region/detect?client_hint=US", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # IN must win over the client_hint US
    assert data["country"] == "IN"
    assert data["suggested_currency"] == "INR"
    assert data["detection_method"] == "header"


def test_untrusted_proxy_host_header_ignored():
    """Proxy headers from untrusted hosts are ignored for geolocation."""
    from backend.app.services.region_service import get_country_from_headers

    # Untrusted client host outside trusted list
    headers = {"cf-ipcountry": "DE"}
    country = get_country_from_headers(headers, client_host="203.0.113.195", trusted_proxies=["127.0.0.1"])
    assert country is None


def test_dev_country_override(client, monkeypatch):
    """DEV_COUNTRY_OVERRIDE takes precedence when DEV_MODE is enabled."""
    from backend.app.config import settings

    monkeypatch.setattr(settings, "DEV_MODE", True)
    monkeypatch.setattr(settings, "DEV_COUNTRY_OVERRIDE", "IN")

    res = client.get("/api/region/detect")
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is True
    assert data["country"] == "IN"
    assert data["suggested_currency"] == "INR"
    assert data["detection_method"] == "dev_override"


def test_localhost_without_headers_returns_unavailable(client):
    """Pure localhost request without hints/headers returns explicit unavailable response."""
    res = client.get("/api/region/detect")
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is False
    assert data["status"] == "unavailable"
    assert data["detection_method"] == "unavailable"
    assert data["country"] is None
    assert data["suggested_currency"] is None


def test_provider_failure_returns_graceful_unavailable(client, monkeypatch):
    """When external geolocation provider fails, service fails closed without 500 error."""
    from backend.app.services import region_service

    async def failing_lookup(ip: str):
        return None

    monkeypatch.setattr(region_service, "lookup_ip_geolocation", failing_lookup)
    headers = {"X-Forwarded-For": "198.51.100.1"}
    res = client.get("/api/region/detect", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is False
    assert data["status"] == "unavailable"


def test_get_exchange_rates_endpoint(client):
    """GET /api/region/rates returns benchmark exchange rates and cross conversions."""
    res = client.get("/api/region/rates")
    assert res.status_code == 200
    data = res.json()
    assert data["base_currency"] == "USD"
    rates = data["rates"]
    assert "INR" in rates
    assert "EUR" in rates
    assert "GBP" in rates
    assert "JPY" in rates
    assert rates["USD"] == 1.0
    assert rates["INR"] == 86.50

    # Cross currency rate query
    res_cross = client.get("/api/region/rates?from_currency=USD&to_currency=INR")
    assert res_cross.status_code == 200
    data_cross = res_cross.json()
    assert data_cross["from_currency"] == "USD"
    assert data_cross["to_currency"] == "INR"
    assert data_cross["rate"] == 86.50


def test_multi_user_regional_preference_isolation(client):
    """User preferences are strictly isolated per account and never leak across users."""
    db: Session = SessionLocal()
    # Create or reset User Alpha (INR preference)
    user_alpha = db.query(Owner).filter(Owner.email == "alpha.user@fintech.test").first()
    if not user_alpha:
        user_alpha = Owner(
            name="User Alpha",
            email="alpha.user@fintech.test",
            currency="USD",
            preferred_currency="INR",
            country="IN",
            locale="en-IN",
            is_active=True,
            email_verified=True,
        )
        db.add(user_alpha)
    else:
        user_alpha.preferred_currency = "INR"
        user_alpha.country = "IN"
        user_alpha.locale = "en-IN"
    db.commit()
    db.refresh(user_alpha)

    # Create or reset User Beta (EUR preference)
    user_beta = db.query(Owner).filter(Owner.email == "beta.user@fintech.test").first()
    if not user_beta:
        user_beta = Owner(
            name="User Beta",
            email="beta.user@fintech.test",
            currency="USD",
            preferred_currency="EUR",
            country="DE",
            locale="de-DE",
            is_active=True,
            email_verified=True,
        )
        db.add(user_beta)
    else:
        user_beta.preferred_currency = "EUR"
        user_beta.country = "DE"
        user_beta.locale = "de-DE"
    db.commit()
    db.refresh(user_beta)

    token_alpha = create_access_token({"sub": user_alpha.id, "email": user_alpha.email, "email_verified": True})
    token_beta = create_access_token({"sub": user_beta.id, "email": user_beta.email, "email_verified": True})

    # Fetch preferences for Alpha
    res_a = client.get("/api/profile/regional-preferences", headers={"Authorization": f"Bearer {token_alpha}"})
    assert res_a.status_code == 200
    assert res_a.json()["preferred_currency"] == "INR"
    assert res_a.json()["country"] == "IN"
    assert res_a.json()["currency_symbol"] == "₹"

    # Fetch preferences for Beta
    res_b = client.get("/api/profile/regional-preferences", headers={"Authorization": f"Bearer {token_beta}"})
    assert res_b.status_code == 200
    assert res_b.json()["preferred_currency"] == "EUR"
    assert res_b.json()["country"] == "DE"
    assert res_b.json()["currency_symbol"] == "€"

    # Changing Alpha to JPY must not alter Beta
    res_update = client.put(
        "/api/profile/regional-preferences",
        headers={"Authorization": f"Bearer {token_alpha}"},
        json={"country": "JP", "preferred_currency": "JPY"}
    )
    assert res_update.status_code == 200
    assert res_update.json()["preferred_currency"] == "JPY"

    # Verify Beta is still EUR
    res_b_after = client.get("/api/profile/regional-preferences", headers={"Authorization": f"Bearer {token_beta}"})
    assert res_b_after.status_code == 200
    assert res_b_after.json()["preferred_currency"] == "EUR"
    assert res_b_after.json()["country"] == "DE"

    db.close()

