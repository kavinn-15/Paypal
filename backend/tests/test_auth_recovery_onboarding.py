import pytest
import datetime
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import Owner, Obligation
from backend.app.api.auth import _FAILED_LOGINS


@pytest.fixture(autouse=True)
def clean_state():
    _FAILED_LOGINS.clear()
    yield
    _FAILED_LOGINS.clear()


@pytest.mark.asyncio
async def test_registration_with_extended_fields():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Clean up existing test email if present
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == "sarah.connor@cyberdyne.org").delete()
            db.commit()
        finally:
            db.close()

        res = await client.post("/auth/register", json={
            "name": "Sarah Connor",
            "email": "sarah.connor@cyberdyne.org",
            "password": "SecurePassword123!",
            "country": "US",
            "business_type": "Agency",
            "preferred_currency": "USD",
            "terms_accepted": True
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["email"] == "sarah.connor@cyberdyne.org"
        assert data["name"] == "Sarah Connor"
        assert data["country"] == "US"
        assert data["business_type"] == "Agency"
        assert data["access_token"] is not None
        assert data["refresh_token"] is not None
        assert data["is_demo"] is False


@pytest.mark.asyncio
async def test_registration_duplicate_email_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": "First User",
            "email": "duplicate@test.org",
            "password": "Password1234!",
            "country": "US",
            "terms_accepted": True
        }
        # First registration or cleanup
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == "duplicate@test.org").delete()
            db.commit()
        finally:
            db.close()

        res1 = await client.post("/auth/register", json=payload)
        assert res1.status_code == 200

        res2 = await client.post("/auth/register", json=payload)
        assert res2.status_code == 400
        assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_registration_weak_password_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Short password
        res = await client.post("/auth/register", json={
            "name": "Weak Pass User",
            "email": "weak@test.org",
            "password": "short"
        })
        assert res.status_code in [400, 422]

        # No number
        res2 = await client.post("/auth/register", json={
            "name": "Weak Pass User",
            "email": "weak2@test.org",
            "password": "justletterslong"
        })
        assert res2.status_code == 400
        assert "number" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_flow_and_bad_credentials():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "logintest@test.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        # Register user
        await client.post("/auth/register", json={
            "name": "Login Test",
            "email": email,
            "password": "ValidPassword999!",
            "terms_accepted": True
        })

        # Bad password
        bad_res = await client.post("/auth/login", json={
            "email": email,
            "password": "WrongPassword123!"
        })
        assert bad_res.status_code == 401

        # Good password
        good_res = await client.post("/auth/login", json={
            "email": email,
            "password": "ValidPassword999!"
        })
        assert good_res.status_code == 200
        assert good_res.json()["access_token"] is not None


@pytest.mark.asyncio
async def test_login_rate_limiting():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "ratelimit@test.org"
        # Make 5 failed attempts
        for _ in range(5):
            await client.post("/auth/login", json={"email": email, "password": "WrongPassword123!"})

        # 6th attempt should trigger 429 Too Many Requests
        blocked_res = await client.post("/auth/login", json={"email": email, "password": "WrongPassword123!"})
        assert blocked_res.status_code == 429
        assert "Too many failed login attempts" in blocked_res.json()["detail"]


@pytest.mark.asyncio
async def test_password_recovery_and_reset_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "recovery@test.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        # Register user
        await client.post("/auth/register", json={
            "name": "Recovery User",
            "email": email,
            "password": "OriginalPassword123!",
            "terms_accepted": True
        })

        # Request forgot password
        forgot_res = await client.post("/auth/forgot-password", json={"email": email})
        assert forgot_res.status_code == 200
        data = forgot_res.json()
        assert data["status"] == "success"
        dev_link = data.get("dev_reset_link")
        assert dev_link is not None
        token = dev_link.split("token=")[-1]
        assert len(token) > 10

        # Reset with invalid token fails
        invalid_reset = await client.post("/auth/reset-password", json={
            "token": "completely-fake-token",
            "new_password": "NewStrongPassword789!"
        })
        assert invalid_reset.status_code == 400

        # Reset with valid token succeeds
        valid_reset = await client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "NewStrongPassword789!"
        })
        assert valid_reset.status_code == 200
        assert "successfully updated" in valid_reset.json()["message"]

        # Token cannot be reused (single-use)
        reuse_reset = await client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "AnotherNewPassword999!"
        })
        assert reuse_reset.status_code == 400

        # Login with old password fails
        old_login = await client.post("/auth/login", json={
            "email": email,
            "password": "OriginalPassword123!"
        })
        assert old_login.status_code == 401

        # Login with new password succeeds
        new_login = await client.post("/auth/login", json={
            "email": email,
            "password": "NewStrongPassword789!"
        })
        assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_multi_tenant_data_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email.in_(["alice@freelance.org", "bob@freelance.org"])).delete()
            db.commit()
        finally:
            db.close()

        # Register Alice
        res_a = await client.post("/auth/register", json={
            "name": "Alice User",
            "email": "alice@freelance.org",
            "password": "AliceSecret123!",
            "terms_accepted": True
        })
        token_a = res_a.json()["access_token"]

        # Register Bob
        res_b = await client.post("/auth/register", json={
            "name": "Bob User",
            "email": "bob@freelance.org",
            "password": "BobSecret123!",
            "terms_accepted": True
        })
        token_b = res_b.json()["access_token"]

        # Mark Alice and Bob verified so financial endpoints are accessible
        db_ver = SessionLocal()
        db_ver.query(Owner).filter(Owner.email.in_(["alice@freelance.org", "bob@freelance.org"])).update({"email_verified": True})
        db_ver.commit()
        db_ver.close()

        # Alice creates an obligation
        create_res = await client.post(
            "/obligations",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "payee_name": "Alice Contractor",
                "payee_email": "contractor@alice.org",
                "amount": 750.00,
                "due_date": "2026-11-20T12:00:00Z",
                "category": "contractor"
            }
        )
        assert create_res.status_code in [200, 201], create_res.text
        alice_ob_id = create_res.json()["id"]

        # Bob lists obligations: Alice's obligation must NOT appear
        bob_ob_res = await client.get("/obligations", headers={"Authorization": f"Bearer {token_b}"})
        assert bob_ob_res.status_code == 200
        bob_obligations = bob_ob_res.json()
        assert all(ob["id"] != alice_ob_id for ob in bob_obligations)
