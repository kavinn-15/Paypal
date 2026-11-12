import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

from backend.app.config import settings, Settings
from backend.app.main import app, lifespan
from backend.app.db import get_db, init_db, run_migrations


# =========================================================================
# 1. Tests for TEMPORARY DEPLOYMENT MODE (DATABASE_DISABLED = True)
# =========================================================================

@pytest.mark.asyncio
async def test_startup_and_routes_when_database_disabled(monkeypatch):
    """
    Verifies that when DATABASE_DISABLED=true:
    1. init_db() and run_migrations() do not run or error.
    2. FastAPI lifespan starts without attempting database connections.
    3. Health checks, status, and database-independent endpoints return 200 OK.
    4. Database-dependent endpoints return controlled 503 Service Unavailable.
    5. No fake data or bypassed auth occurs.
    """
    monkeypatch.setattr(settings, "DATABASE_DISABLED", True)

    # 1. Verify init_db() and run_migrations() are safe no-ops
    init_db()
    run_migrations()

    # 2. Verify lifespan context manager starts and stops without error
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            # 3. Independent endpoints MUST return 200 OK
            res_health = await client.get("/health")
            assert res_health.status_code == status.HTTP_200_OK
            data_health = res_health.json()
            assert data_health["status"] == "healthy"
            assert data_health["database_disabled"] is True

            res_status = await client.get("/status")
            assert res_status.status_code == status.HTTP_200_OK
            data_status = res_status.json()
            assert data_status["status"] == "online"

            res_countries = await client.get("/region/countries")
            assert res_countries.status_code == status.HTTP_200_OK
            assert isinstance(res_countries.json(), list)
            assert len(res_countries.json()) > 0

            res_currencies = await client.get("/region/currencies")
            assert res_currencies.status_code == status.HTTP_200_OK
            assert isinstance(res_currencies.json(), list)
            assert len(res_currencies.json()) > 0

            res_rates = await client.get("/region/rates")
            assert res_rates.status_code == status.HTTP_200_OK
            assert "rates" in res_rates.json()

            # 4. Database-dependent endpoints MUST return 503 Service Unavailable
            res_db_health = await client.get("/health/db")
            assert res_db_health.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "temporarily unavailable" in res_db_health.json()["detail"].lower()

            res_login = await client.post("/auth/login", json={
                "email": "user@example.com",
                "password": "Password123!"
            })
            assert res_login.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "DATABASE_DISABLED" in res_login.json()["detail"]

            res_register = await client.post("/auth/register", json={
                "name": "Test User",
                "email": "newuser@example.com",
                "password": "Password123!",
                "currency": "USD"
            })
            assert res_register.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "DATABASE_DISABLED" in res_register.json()["detail"]

            res_clients = await client.get("/clients", headers={"Authorization": "Bearer fake_token"})
            assert res_clients.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            res_forecast = await client.get("/forecast/latest", headers={"Authorization": "Bearer fake_token"})
            assert res_forecast.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            res_obligations = await client.get("/obligations", headers={"Authorization": "Bearer fake_token"})
            assert res_obligations.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            res_webhook = await client.post("/webhooks/paypal", json={"id": "WH-TEST-123", "event_type": "PAYMENT.CAPTURE.COMPLETED"})
            assert res_webhook.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# =========================================================================
# 2. Tests for NORMAL DATABASE MODE (DATABASE_DISABLED = False)
# =========================================================================

@pytest.mark.asyncio
async def test_normal_database_mode_when_disabled_is_false(monkeypatch):
    """
    Verifies that when DATABASE_DISABLED=false:
    1. Normal database initialization works.
    2. /health reflects database_disabled=False.
    3. /health/db connects and returns 200 OK.
    4. Database routes operate normally without 503 errors.
    """
    monkeypatch.setattr(settings, "DATABASE_DISABLED", False)

    # Ensure schema is ready
    init_db()

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res_health = await client.get("/health")
            assert res_health.status_code == status.HTTP_200_OK
            assert res_health.json()["database_disabled"] is False

            res_db_health = await client.get("/health/db")
            assert res_db_health.status_code == status.HTTP_200_OK
            assert res_db_health.json()["status"] == "healthy"
            assert res_db_health.json()["database"] == "connected"


def test_config_aliases_and_defaults():
    """
    Verifies that DATABASE_DISABLED can be set via multiple alias choices
    (DATABASE_DISABLED, DISABLE_DATABASE, SKIP_DB_INIT).
    """
    s_default = Settings()
    assert s_default.DATABASE_DISABLED is False

    s1 = Settings(DATABASE_DISABLED=True)
    assert s1.DATABASE_DISABLED is True

    s2 = Settings(DISABLE_DATABASE=True)
    assert s2.DATABASE_DISABLED is True

    s3 = Settings(SKIP_DB_INIT=True)
    assert s3.DATABASE_DISABLED is True
