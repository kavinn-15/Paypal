import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.scripts.seed import seed_database
from backend.app.guardrail.approval import generate_approval_hash


@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    seed_database(clean=True, demo_mode=True)


@pytest.mark.asyncio
async def test_end_to_end_api_lifecycle(monkeypatch):
    from backend.app.services.execution import paypal_client

    async def mock_send_reminder(*args, **kwargs):
        return True

    monkeypatch.setattr(paypal_client, "send_invoice_reminder", mock_send_reminder)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 0. Authenticate via demo login
        res_login = await client.post("/auth/demo-login")
        assert res_login.status_code == 200
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Health check
        res_health = await client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json()["environment"] == "sandbox"

        # 2. Check clients
        res_clients = await client.get("/clients", headers=headers)
        assert res_clients.status_code == 200
        clients = res_clients.json()
        assert len(clients) == 6
        assert any(c["name"] == "Apex Design Studio" for c in clients)

        # 3. Check obligations
        res_obls = await client.get("/obligations", headers=headers)
        assert res_obls.status_code == 200
        obls = res_obls.json()
        assert len(obls) >= 1
        marcus = next(o for o in obls if "Marcus" in o["payee_name"])
        assert marcus["amount"] == 3200.0

        # 4. Run forecast & plan comparison
        res_forecast = await client.post("/forecast/run?starting_balance=1800.0", headers=headers)
        assert res_forecast.status_code == 200
        fc_data = res_forecast.json()
        assert fc_data["shortfall_amount"] == 1400.0
        assert len(fc_data["plans"]) == 3

        plan_a = next(p for p in fc_data["plans"] if p["plan_type"] == "A")
        action_a = plan_a["primary_action"]
        assert action_a["state"] == "proposed"

        # 5. Owner approves Plan A with HMAC signature
        res_approve = await client.post(
            f"/actions/{action_a['id']}/approve",
            json={"approval_hash": action_a["approval_hash"]},
            headers=headers
        )
        assert res_approve.status_code == 200
        approved_action = res_approve.json()
        assert approved_action["state"] == "approved"
        assert approved_action["approved_at"] is not None

        # 6. Owner executes Plan A
        res_exec = await client.post(
            f"/actions/{action_a['id']}/execute",
            json={"idempotency_key": action_a["idempotency_key"]},
            headers=headers
        )
        assert res_exec.status_code == 200
        exec_action = res_exec.json()
        assert exec_action["state"] == "executed"
        assert exec_action["executed_at"] is not None

        # 7. Simulate client payment arrival (dev webhook)
        res_webhook = await client.post(
            "/dev/simulate-webhook",
            json={"paypal_invoice_id": action_a["paypal_ref"]},
            headers=headers
        )
        assert res_webhook.status_code == 200
        wh_data = res_webhook.json()
        assert wh_data["simulated"] is True
        assert wh_data["result"]["action_confirmed"] == action_a["id"]

        # 8. Check that action is in SIMULATED status (never genuine confirmed from simulation)
        res_action_check = await client.get(f"/actions/{action_a['id']}", headers=headers)
        assert res_action_check.status_code == 200
        simulated_action = res_action_check.json()
        assert simulated_action["state"] == "simulated"
        assert simulated_action["is_simulated"] is True
        assert simulated_action["confirmed_at"] is None

        # 9. Verify Audit Hash Chain
        res_audit = await client.get("/audit/verify", headers=headers)
        assert res_audit.status_code == 200
        audit_res = res_audit.json()
        assert audit_res["chain_valid"] is True
        assert audit_res["corrupted_block_id"] is None
        assert audit_res["total_blocks"] >= 4

