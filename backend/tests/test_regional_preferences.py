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
