import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.auth.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hashing():
    pwd = "SecureFintechPass2026!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_lifecycle():
    data = {"sub": 42, "email": "test@fintech.example.com"}
    token = create_access_token(data)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == 42
    assert decoded["email"] == "test@fintech.example.com"


@pytest.mark.asyncio
async def test_auth_registration_and_login_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register new user
        reg_payload = {
            "name": "Sarah Connor",
            "email": "sarah.connor@example.com",
            "password": "Password123!",
            "currency": "USD",
            "timezone": "America/New_York"
        }
        res_reg = await client.post("/auth/register", json=reg_payload)
        assert res_reg.status_code == 200
        token_data = res_reg.json()
        assert "access_token" in token_data
        assert token_data["email"] == "sarah.connor@example.com"

        # Verify duplicate registration rejected
        res_dup = await client.post("/auth/register", json=reg_payload)
        assert res_dup.status_code == 400

        # Login with correct credentials
        res_login = await client.post("/auth/login", json={
            "email": "sarah.connor@example.com",
            "password": "Password123!"
        })
        assert res_login.status_code == 200
        assert "access_token" in res_login.json()

        # Login with wrong password
        res_bad = await client.post("/auth/login", json={
            "email": "sarah.connor@example.com",
            "password": "WrongPassword!"
        })
        assert res_bad.status_code == 401

        # Check /auth/me with bearer token
        token = res_login.json()["access_token"]
        res_me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res_me.status_code == 200
        assert res_me.json()["name"] == "Sarah Connor"

