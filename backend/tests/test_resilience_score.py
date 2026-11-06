import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database(clean=True, demo_mode=True)


@pytest.mark.asyncio
async def test_financial_resilience_score_calculation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        assert res_login.status_code == 200
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.get("/resilience/score?starting_balance=1800.0", headers=headers)
        assert res.status_code == 200
        data = res.json()

        # Score must be between 0 and 100
        assert 0 <= data["overall_score"] <= 100
        assert data["category"] in ["Excellent", "Good", "Moderate", "Fragile", "Critical"]

        # Verify all 6 explainable factors present
        assert len(data["factors"]) == 6
        factor_names = [f["name"] for f in data["factors"]]
        assert "Cash Reserve Coverage" in factor_names
        assert "Expected Income Reliability" in factor_names
        assert "Upcoming Obligations Load" in factor_names
        assert "Payment Concentration Risk" in factor_names
        assert "Receivables Exposure" in factor_names
        assert "Expense Shock Tolerance" in factor_names

        # Verify recommendations and factors
        assert len(data["improving_factors"]) > 0
        assert len(data["reducing_factors"]) > 0
        assert len(data["recommended_actions"]) > 0

