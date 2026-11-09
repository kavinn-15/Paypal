import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.scripts.seed import seed_database
from backend.app.db import SessionLocal
from backend.app.models import Owner, Action, Invoice, Obligation


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database(clean=True, demo_mode=True)


@pytest.mark.asyncio
async def test_user_isolation_and_id_manipulation():
    """Verify that User B cannot view, modify, approve, or execute User A's financial objects."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as User A (Alex Morgan)
        res_a = await client.post("/auth/demo-login")
        assert res_a.status_code == 200
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # User A runs forecast to get an action
        res_fc = await client.post("/forecast/run?starting_balance=1800.0", headers=headers_a)
        assert res_fc.status_code == 200
        action_a_id = res_fc.json()["plans"][0]["primary_action"]["id"]

        # Get User A's obligation
        res_obls_a = await client.get("/obligations", headers=headers_a)
        assert res_obls_a.status_code == 200
        obl_a_id = res_obls_a.json()[0]["id"]

        # 2. Register User B
        res_reg_b = await client.post("/auth/register", json={
            "name": "Attacker User",
            "email": "attacker@evilcorp.example.com",
            "password": "EvilPassword123!",
            "currency": "USD"
        })
        assert res_reg_b.status_code == 200
        token_b = res_reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 3. User B tries to access User A's action -> 404 (or 403)
        res_b_get_act = await client.get(f"/actions/{action_a_id}", headers=headers_b)
        assert res_b_get_act.status_code in (403, 404)

        # User B tries to approve User A's action -> 404 (or 403)
        res_b_app = await client.post(
            f"/actions/{action_a_id}/approve",
            json={"approval_hash": "fake_hash_attempt"},
            headers=headers_b
        )
        assert res_b_app.status_code in (403, 404)

        # User B tries to execute User A's action -> 404 (or 403)
        res_b_exec = await client.post(
            f"/actions/{action_a_id}/execute",
            json={"idempotency_key": "fake_idemp"},
            headers=headers_b
        )
        assert res_b_exec.status_code in (403, 404)

        # User B tries to get User A's obligation -> 404 (or 403)
        res_b_get_obl = await client.get(f"/obligations/{obl_a_id}", headers=headers_b)
        assert res_b_get_obl.status_code in (403, 404)

        # User B tries to delete User A's obligation -> 404 (or 403)
        res_b_del_obl = await client.delete(f"/obligations/{obl_a_id}", headers=headers_b)
        assert res_b_del_obl.status_code in (403, 404)

        # User B's obligation list is empty (isolated)
        res_b_obls = await client.get("/obligations", headers=headers_b)
        assert res_b_obls.status_code == 200
        assert len(res_b_obls.json()) == 0


@pytest.mark.asyncio
async def test_ledger_reconciliation_integrity_check():
    """Verify that /finance/integrity-check correctly reconciles authoritative ledger."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        assert res_login.status_code == 200
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res_check = await client.get("/finance/integrity-check", headers=headers)
        assert res_check.status_code == 200
        data = res_check.json()
        assert data["currency"] == "USD"
        assert data["is_balanced"] is True
        assert data["discrepancy"] == 0.0
        assert data["opening_balance"] == 1800.0
        assert data["reconciled_balance"] >= 0.0


@pytest.mark.asyncio
async def test_token_refresh_and_logout_revocation():
    """Verify refresh token rotation and revocation on logout."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register test user
        res_reg = await client.post("/auth/register", json={
            "name": "Refresh Tester",
            "email": "refresh.tester@example.com",
            "password": "StrongPassword2026!",
            "currency": "USD"
        })
        assert res_reg.status_code == 200
        auth_data = res_reg.json()
        refresh_tok = auth_data["refresh_token"]
        access_tok = auth_data["access_token"]

        # Exchange refresh token for new access token
        res_refresh = await client.post("/auth/refresh", json={"refresh_token": refresh_tok})
        assert res_refresh.status_code == 200
        refreshed_data = res_refresh.json()
        assert "access_token" in refreshed_data
        assert refreshed_data["token_type"] == "bearer"

        # Logout to revoke the refresh token (authenticated call)
        res_logout = await client.post(
            "/auth/logout",
            json={"refresh_token": refresh_tok},
            headers={"Authorization": f"Bearer {access_tok}"}
        )
        assert res_logout.status_code == 200
        assert res_logout.json()["status"] == "success"

        # Using revoked refresh token must now be rejected
        res_revoked = await client.post("/auth/refresh", json={"refresh_token": refresh_tok})
        assert res_revoked.status_code == 401


@pytest.mark.asyncio
async def test_webhook_replay_safety():
    """Verify that replaying a paid invoice webhook does not alter cash balance or duplicate payments."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check balance before
        res_bal_before = await client.get("/finance/summary", headers=headers)
        assert res_bal_before.status_code == 200
        bal_before = res_bal_before.json()["current_confirmed_balance"]

        # First simulated webhook delivery for invoice INV2-DEMO-APEX-001
        res1 = await client.post("/dev/simulate-webhook", json={"paypal_invoice_id": "INV2-DEMO-APEX-001"}, headers=headers)
        assert res1.status_code == 200
        assert res1.json()["simulated"] is True

        # Check balance after simulation: simulated payments NEVER mutate confirmed balance!
        res_bal_after1 = await client.get("/finance/summary", headers=headers)
        bal_after1 = res_bal_after1.json()["current_confirmed_balance"]
        assert bal_after1 == bal_before

        # Replay the simulated webhook
        res2 = await client.post("/dev/simulate-webhook", json={"paypal_invoice_id": "INV2-DEMO-APEX-001"}, headers=headers)
        assert res2.status_code == 200

        # Balance MUST NOT be credited by simulation
        res_bal_after2 = await client.get("/finance/summary", headers=headers)
        bal_after2 = res_bal_after2.json()["current_confirmed_balance"]
        assert bal_after2 == bal_before
