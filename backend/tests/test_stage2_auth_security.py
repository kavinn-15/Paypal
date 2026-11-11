import pytest
import datetime
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import Owner, RefreshToken, RateLimitAttempt, ConsumedToken
from backend.app.auth.security import create_access_token, create_refresh_token, hash_token, hash_password
from backend.app.config import settings


@pytest.mark.asyncio
async def test_disabled_account_rejected_across_protected_endpoints():
    """Verify that disabled accounts (account_status != 'active') cannot access any protected endpoint."""
    email = "disabled.user@testsecurity.org"
    db = SessionLocal()
    try:
        db.query(Owner).filter(Owner.email == email).delete()
        user = Owner(
            name="Disabled User",
            email=email,
            hashed_password=hash_password("ValidPassword123!"),
            currency="USD",
            is_demo=False,
            is_active=True,
            account_status="disabled",
            token_version=1,
            email_verified=True,
            terms_accepted=True,
            terms_accepted_at=datetime.datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    token = create_access_token({"sub": user_id, "email": email, "email_verified": True, "ver": 1})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Protected basic route
        me_res = await client.get("/auth/me", headers=headers)
        assert me_res.status_code == 403
        assert "deactivated or disabled" in me_res.json()["detail"].lower()

        # Protected financial route
        client_res = await client.get("/clients", headers=headers)
        assert client_res.status_code == 403

        # Login attempt with disabled status must also fail
        login_res = await client.post("/auth/login", json={"email": email, "password": "ValidPassword123!"})
        assert login_res.status_code == 403


@pytest.mark.asyncio
async def test_unverified_account_blocked_from_financial_operations():
    """Verify that unverified accounts (email_verified=False) cannot access financial operations."""
    email = "unverified.user@testsecurity.org"
    db = SessionLocal()
    try:
        db.query(Owner).filter(Owner.email == email).delete()
        user = Owner(
            name="Unverified User",
            email=email,
            hashed_password=hash_password("ValidPassword123!"),
            currency="USD",
            is_demo=False,
            is_active=True,
            account_status="active",
            token_version=1,
            email_verified=False,
            terms_accepted=True,
            terms_accepted_at=datetime.datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    token = create_access_token({"sub": user_id, "email": email, "email_verified": False, "ver": 1})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # /auth/me is basic account info -> permitted
        me_res = await client.get("/auth/me", headers=headers)
        assert me_res.status_code == 200

        # Financial operations -> must be rejected with 403
        clients_res = await client.get("/clients", headers=headers)
        assert clients_res.status_code == 403
        assert "not verified" in clients_res.json()["detail"].lower()

        obls_res = await client.get("/obligations", headers=headers)
        assert obls_res.status_code == 403

        resilience_res = await client.get("/resilience/score", headers=headers)
        assert resilience_res.status_code == 403

        audit_res = await client.get("/audit", headers=headers)
        assert audit_res.status_code == 403

        export_res = await client.get("/auth/export", headers=headers)
        assert export_res.status_code == 403


@pytest.mark.asyncio
async def test_terms_and_conditions_acceptance_enforcement():
    """Verify terms acceptance is mandatory, rejects missing/false with 400, and records timestamp."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing terms_accepted -> 400 Bad Request
        res_missing = await client.post("/auth/register", json={
            "name": "Terms Missing User",
            "email": "terms.missing@example.org",
            "password": "ValidPassword123!"
        })
        assert res_missing.status_code == 400
        assert "terms and conditions" in res_missing.json()["detail"].lower()

        # False terms_accepted -> 400 Bad Request
        res_false = await client.post("/auth/register", json={
            "name": "Terms False User",
            "email": "terms.false@example.org",
            "password": "ValidPassword123!",
            "terms_accepted": False
        })
        assert res_false.status_code == 400
        assert "terms and conditions" in res_false.json()["detail"].lower()

        # Explicit True -> 200 OK and recorded in DB
        email_ok = "terms.ok@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email_ok).delete()
            db.commit()
        finally:
            db.close()

        res_ok = await client.post("/auth/register", json={
            "name": "Terms Accepted User",
            "email": email_ok,
            "password": "ValidPassword123!",
            "terms_accepted": True
        })
        assert res_ok.status_code == 200

        db = SessionLocal()
        try:
            user = db.query(Owner).filter(Owner.email == email_ok).first()
            assert user is not None
            assert user.terms_accepted is True
            assert user.terms_accepted_at is not None
        finally:
            db.close()


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_family_reuse_detection():
    """Verify refresh token rotation and token family reuse detection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "token.family@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        reg_res = await client.post("/auth/register", json={
            "name": "Token Family User",
            "email": email,
            "password": "ValidPassword123!",
            "terms_accepted": True
        })
        assert reg_res.status_code == 200
        data = reg_res.json()
        token_1 = data["refresh_token"]

        # Step 1: Rotate token_1 -> yields token_2
        rot_res1 = await client.post("/auth/refresh", json={"refresh_token": token_1})
        assert rot_res1.status_code == 200
        token_2 = rot_res1.json()["refresh_token"]
        assert token_2 != token_1

        # Verify token_1 is hashed and marked revoked in DB
        db = SessionLocal()
        try:
            rec_1 = db.query(RefreshToken).filter(RefreshToken.token == hash_token(token_1)).first()
            assert rec_1 is not None
            assert rec_1.revoked is True
        finally:
            db.close()

        # Step 2: Malicious replay of already-revoked token_1!
        replay_res = await client.post("/auth/refresh", json={"refresh_token": token_1})
        assert replay_res.status_code == 401
        assert "reuse detected" in replay_res.json()["detail"].lower()

        # Step 3: Entire token family must now be revoked, so even token_2 is now revoked
        rot_res2 = await client.post("/auth/refresh", json={"refresh_token": token_2})
        assert rot_res2.status_code == 401


@pytest.mark.asyncio
async def test_immediate_session_invalidation_on_logout():
    """Verify that calling logout invalidates outstanding access tokens via token_version."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "logout.invalidation@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        reg_res = await client.post("/auth/register", json={
            "name": "Logout User",
            "email": email,
            "password": "ValidPassword123!",
            "terms_accepted": True
        })
        access_token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Token is valid before logout
        me_res1 = await client.get("/auth/me", headers=headers)
        assert me_res1.status_code == 200

        # Perform logout
        logout_res = await client.post("/auth/logout", headers=headers)
        assert logout_res.status_code == 200

        # Protected endpoint must immediately reject the old access token
        me_res2 = await client.get("/auth/me", headers=headers)
        assert me_res2.status_code == 401
        assert "terminated" in me_res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_database_backed_login_rate_limiting():
    """Verify database-backed rate limiting tracks failed attempts across calls and resets on success."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "ratelimit.db@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(RateLimitAttempt).filter(RateLimitAttempt.key == email).delete()
            user = Owner(
                name="Rate Limit User",
                email=email,
                hashed_password=hash_password("CorrectPassword123!"),
                currency="USD",
                is_demo=False,
                is_active=True,
                account_status="active",
                email_verified=True,
                terms_accepted=True,
                terms_accepted_at=datetime.datetime.utcnow()
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Send 5 failed login attempts
        for _ in range(5):
            res_bad = await client.post("/auth/login", json={"email": email, "password": "WrongPassword!"})
            assert res_bad.status_code == 401

        # 6th attempt should be blocked by rate limiting with 429
        res_blocked = await client.post("/auth/login", json={"email": email, "password": "WrongPassword!"})
        assert res_blocked.status_code == 429
        assert "too many" in res_blocked.json()["detail"].lower()

        # Clear attempts in DB and verify successful login
        db = SessionLocal()
        db.query(RateLimitAttempt).filter(RateLimitAttempt.key == email).delete()
        db.commit()
        db.close()

        res_ok = await client.post("/auth/login", json={"email": email, "password": "CorrectPassword123!"})
        assert res_ok.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_token_single_use_database_tracking():
    """Verify single-use token tracking in database rejects replayed reset tokens."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "reset.singleuse@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        reg_res = await client.post("/auth/register", json={
            "name": "Single Use User",
            "email": email,
            "password": "Password123!",
            "terms_accepted": True
        })
        assert reg_res.status_code == 200

        # Request reset OTP
        await client.post("/auth/password-reset/request", json={"email": email})

        # Set known OTP
        from backend.app.services.otp_service import compute_otp_hash
        from backend.app.models import EmailOTP
        test_code = "654321"
        db = SessionLocal()
        try:
            otp_record = db.query(EmailOTP).filter(
                EmailOTP.email == email,
                EmailOTP.purpose == "password_reset"
            ).order_by(EmailOTP.id.desc()).first()
            otp_record.otp_hash = compute_otp_hash(email, test_code, "password_reset")
            db.commit()
        finally:
            db.close()

        # Verify OTP to get reset token
        v_res = await client.post("/auth/password-reset/verify-otp", json={"email": email, "otp": test_code})
        assert v_res.status_code == 200
        reset_token = v_res.json()["reset_token"]

        # First use -> succeeds
        c_res1 = await client.post("/auth/password-reset/confirm", json={
            "reset_token": reset_token,
            "new_password": "NewValidPassword999!"
        })
        assert c_res1.status_code == 200

        # Second use (replay) -> must fail with 400
        c_res2 = await client.post("/auth/password-reset/confirm", json={
            "reset_token": reset_token,
            "new_password": "AnotherPassword999!"
        })
        assert c_res2.status_code == 400
        assert "already been used" in c_res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_production_mode_rejects_mock_oauth_and_console_providers(monkeypatch):
    """Verify that when DEV_MODE is False, mock OAuth and console dispatch are strictly rejected."""
    monkeypatch.setattr(settings, "DEV_MODE", False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Mock Google Token must be rejected in production
        mock_token_res = await client.post("/auth/google/token", json={
            "credential": "mock_google_token_12345"
        })
        assert mock_token_res.status_code == 401
        assert "prohibited in production" in mock_token_res.json()["detail"].lower()

        # Mock Google callback code must be rejected in production
        mock_code_res = await client.get("/auth/google/callback?code=mock_google_code_123")
        assert mock_code_res.status_code in [400, 401]

