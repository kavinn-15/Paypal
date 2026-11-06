import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database(clean=True, demo_mode=True)


@pytest.mark.asyncio
async def test_what_if_simulation_presets_and_scenarios():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Check presets
        res_presets = await client.get("/simulation/presets")
        assert res_presets.status_code == 200
        presets = res_presets.json()
        assert len(presets) >= 5
        preset_types = [p["scenario_type"] for p in presets]
        assert "client_delay_5d" in preset_types
        assert "emergency_expense" in preset_types
        assert "contractor_split" in preset_types

        # 2. Run client_delay_5d simulation
        res_delay = await client.post("/simulation/run", json={
            "run_name": "Test 5-Day Delay",
            "scenario_type": "client_delay_5d",
            "delay_days": 5
        })
        assert res_delay.status_code == 200
        data_delay = res_delay.json()
        assert "baseline" in data_delay
        assert "simulated" in data_delay
        assert "delta" in data_delay
        assert len(data_delay["projections_simulated"]) > 0

        # 3. Run emergency expense shock simulation ($500)
        res_em = await client.post("/simulation/run", json={
            "run_name": "Emergency Hardware Shock",
            "scenario_type": "emergency_expense",
            "emergency_amount": 500.0
        })
        assert res_em.status_code == 200
        data_em = res_em.json()
        assert data_em["simulated"]["shortfall_amount"] >= data_em["baseline"]["shortfall_amount"]

        # 4. Run contractor split simulation (50/50 split)
        res_split = await client.post("/simulation/run", json={
            "run_name": "Contractor 50/50 Split",
            "scenario_type": "contractor_split",
            "contractor_split_pct": 50.0
        })
        assert res_split.status_code == 200
        data_split = res_split.json()
        # Splitting contractor reduces shortfall on Friday
        assert data_split["simulated"]["shortfall_amount"] < data_split["baseline"]["shortfall_amount"]
