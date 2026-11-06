import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database(clean=True, demo_mode=True)


@pytest.mark.asyncio
async def test_supervisor_workflow_orchestration():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Run supervisor workflow
        res_sup = await client.post("/supervisor/run?starting_balance=1800.0")
        assert res_sup.status_code == 200
        sup_data = res_sup.json()
        assert sup_data["status"] == "completed"
        assert sup_data["shortfall_detected"] is True
        assert sup_data["recommended_plan"] in ["A", "B", "C"]
        assert len(sup_data["steps_trace"]) >= 5

        # Verify all agent contributions recorded
        agents_traced = [s["agent_name"] for s in sup_data["steps_trace"]]
        assert "ForecasterAgent" in agents_traced
        assert "CollectorAgent" in agents_traced
        assert "TreasurerAgent" in agents_traced
        assert "PlannerAgent" in agents_traced
        assert "NegotiationAgent" in agents_traced

        # Check list of past supervisor runs
        res_runs = await client.get("/supervisor/runs")
        assert res_runs.status_code == 200
        assert len(res_runs.json()) >= 1


@pytest.mark.asyncio
async def test_negotiation_agent_multi_tone_drafts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Generate client discount negotiation options
        res_neg_client = await client.post("/negotiate/generate", json={
            "target_type": "client_discount",
            "discount_pct": 3.0
        })
        assert res_neg_client.status_code == 200
        client_data = res_neg_client.json()
        assert len(client_data["options"]) == 3
        tones = [opt["tone"] for opt in client_data["options"]]
        assert "professional" in tones
        assert "friendly" in tones
        assert "urgent_respectful" in tones

        # 2. Generate contractor split negotiation options
        res_neg_contractor = await client.post("/negotiate/generate", json={
            "target_type": "contractor_split",
            "split_pct": 50.0
        })
        assert res_neg_contractor.status_code == 200
        contractor_data = res_neg_contractor.json()
        assert len(contractor_data["options"]) == 3

        # 3. Approve a negotiation draft
        draft_id = client_data["options"][0]["id"]
        res_approve = await client.post(f"/negotiate/drafts/{draft_id}/approve")
        assert res_approve.status_code == 200
        assert res_approve.json()["status"] == "approved"
