import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db import SessionLocal, init_db
from backend.app.models import Owner, Obligation, Invoice, Client


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.mark.asyncio
async def test_new_user_empty_state_returns_404_with_cors_headers():
    email = "empty.user@cashflowlifeline.com"
    db = SessionLocal()
    try:
        existing = db.query(Owner).filter(Owner.email == email).first()
        if existing:
            db.delete(existing)
            db.commit()

        user = Owner(
            email=email,
            name="Empty User",
            hashed_password="$2b$12$eXampleHashedPasswordForTestOnly99999999999999999999999",
            email_verified=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    from backend.app.api.auth import create_access_token
    token = create_access_token(data={"sub": str(user_id), "email": email})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": "https://cashflow-lifeline.vercel.app",
        }

        # 1. Test /forecast/latest
        res_latest = await client.get("/forecast/latest", headers=headers)
        assert res_latest.status_code == 404, res_latest.text
        assert "obligation" in res_latest.json()["detail"].lower()
        assert res_latest.headers.get("access-control-allow-origin") == "https://cashflow-lifeline.vercel.app"

        # 2. Test /forecast/run
        res_run = await client.post("/forecast/run", headers=headers)
        assert res_run.status_code == 404, res_run.text
        assert "obligation" in res_run.json()["detail"].lower()
        assert res_run.headers.get("access-control-allow-origin") == "https://cashflow-lifeline.vercel.app"

        # 3. Test /supervisor/run
        res_sup = await client.post("/supervisor/run", headers=headers)
        assert res_sup.status_code == 404, res_sup.text
        assert "obligation" in res_sup.json()["detail"].lower()
        assert res_sup.headers.get("access-control-allow-origin") == "https://cashflow-lifeline.vercel.app"

        # 4. Now create an obligation (as the onboarding modal would do)
        res_create_obl = await client.post(
            "/obligations",
            json={
                "payee_name": "Sarah Jenkins (Senior UX Contractor)",
                "payee_email": "sarah.jenkins@contractor.org",
                "amount": 3000.0,
                "currency": "USD",
                "due_date": "2026-11-20T17:00:00Z",
                "split_allowed": True,
            },
            headers=headers,
        )
        assert res_create_obl.status_code == 201, res_create_obl.text

        # 5. Now forecast and supervisor should run successfully without crashing
        res_post_forecast = await client.post("/forecast/run", headers=headers)
        assert res_post_forecast.status_code == 200, res_post_forecast.text
        forecast_data = res_post_forecast.json()
        assert "run_id" in forecast_data
        assert "plans" in forecast_data or "obligation" in forecast_data

        res_post_sup = await client.post("/supervisor/run", headers=headers)
        assert res_post_sup.status_code == 200, res_post_sup.text
        sup_data = res_post_sup.json()
        assert "recommended_plan" in sup_data
        assert len(sup_data.get("steps_trace", [])) > 0

        # 6. Clean up test user and created records
        db = SessionLocal()
        try:
            u = db.query(Owner).filter(Owner.id == user_id).first()
            if u:
                db.delete(u)
                db.commit()
        finally:
            db.close()
