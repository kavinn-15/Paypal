import pytest
import datetime
import hmac
import hashlib
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db import SessionLocal, init_db
from backend.app.config import settings
from backend.app.models import Owner, EmailOTP, OAuthIdentity, Obligation, RefreshToken
from backend.app.api.auth import _FAILED_LOGINS
from backend.app.services.otp_service import compute_otp_hash


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture(autouse=True)
def clean_auth_state():
    _FAILED_LOGINS.clear()
    yield
    _FAILED_LOGINS.clear()


@pytest.mark.asyncio
async def test_registration_success_issues_otp_and_unverified_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "clara.oswald@tardis.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(EmailOTP).filter(EmailOTP.email == email).delete()
            db.commit()
        finally:
            db.close()

        res = await client.post("/auth/register", json={
            "name": "Clara Oswald",
            "email": email,
            "password": "SecurePassword2026!",
            "country": "GB",
            "business_type": "Agency",
            "preferred_currency": "GBP"
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["email"] == email
        assert data["email_verified"] is False
        assert data["access_token"] is not None

        # Verify OTP record was created in database
        db = SessionLocal()
        try:
            otp_record = db.query(EmailOTP).filter(
                EmailOTP.email == email,
                EmailOTP.purpose == "email_verification"
            ).first()
            assert otp_record is not None
            assert otp_record.attempts_count == 0
            assert otp_record.consumed_at is None
            assert otp_record.expires_at > datetime.datetime.utcnow()
            # Plain OTP must NOT be stored
            assert len(otp_record.otp_hash) == 64  # SHA256 hex length
        finally:
            db.close()


@pytest.mark.asyncio
async def test_duplicate_email_registration_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "duplicate.test@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        payload = {
            "name": "Original User",
            "email": email,
            "password": "ValidPassword123!"
        }
        res1 = await client.post("/auth/register", json=payload)
        assert res1.status_code == 200

        res2 = await client.post("/auth/register", json=payload)
        assert res2.status_code == 400
        assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_email_otp_verification_success_and_single_use():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "otp.verify@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(EmailOTP).filter(EmailOTP.email == email).delete()
            db.commit()
        finally:
            db.close()

        # Register user
        await client.post("/auth/register", json={
            "name": "OTP User",
            "email": email,
            "password": "ValidPassword123!"
        })

        # Inject a known code hash for deterministic verification testing
        test_code = "789123"
        otp_hash = compute_otp_hash(email, test_code, "email_verification")
        db = SessionLocal()
        try:
            otp_record = db.query(EmailOTP).filter(
                EmailOTP.email == email,
                EmailOTP.purpose == "email_verification"
            ).order_by(EmailOTP.id.desc()).first()
            otp_record.otp_hash = otp_hash
            otp_id = otp_record.id
            db.commit()
        finally:
            db.close()

        # Verify OTP
        verify_res = await client.post("/auth/email/verify", json={
            "email": email,
            "otp": test_code
        })
        assert verify_res.status_code == 200, verify_res.text
        data = verify_res.json()
        assert data["status"] == "success"
        assert "access_token" in data

        # Check DB owner is marked verified
        db = SessionLocal()
        try:
            owner = db.query(Owner).filter(Owner.email == email).first()
            assert owner.email_verified is True
            assert owner.email_verified_at is not None
            # OTP must be marked consumed
            otp_check = db.query(EmailOTP).filter(EmailOTP.id == otp_id).first()
            assert otp_check.consumed_at is not None
        finally:
            db.close()

        # Re-using the same OTP must fail (Single-use behavior)
        reuse_res = await client.post("/auth/email/verify", json={
            "email": email,
            "otp": test_code
        })
        assert reuse_res.status_code == 400


@pytest.mark.asyncio
async def test_email_otp_wrong_code_and_attempt_limits():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "attempts.test@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(EmailOTP).filter(EmailOTP.email == email).delete()
            db.commit()
        finally:
            db.close()

        await client.post("/auth/register", json={
            "name": "Attempts User",
            "email": email,
            "password": "ValidPassword123!"
        })

        # Inject known OTP
        correct_code = "445566"
        otp_hash = compute_otp_hash(email, correct_code, "email_verification")
        db = SessionLocal()
        try:
            record = db.query(EmailOTP).filter(EmailOTP.email == email).first()
            record.otp_hash = otp_hash
            db.commit()
        finally:
            db.close()

        # Enter wrong code
        bad_res = await client.post("/auth/email/verify", json={
            "email": email,
            "otp": "000000"
        })
        assert bad_res.status_code == 400
        assert "attempt(s) remaining" in bad_res.json()["detail"]

        # Enter 4 more bad codes to exceed max attempts (5)
        for _ in range(4):
            last_res = await client.post("/auth/email/verify", json={
                "email": email,
                "otp": "000000"
            })
        assert last_res.status_code in [400, 429]

        # Even with the correct code now, it must be locked / invalidated
        locked_res = await client.post("/auth/email/verify", json={
            "email": email,
            "otp": correct_code
        })
        assert locked_res.status_code in [400, 429]


@pytest.mark.asyncio
async def test_email_otp_expired_code_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "expired.otp@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(EmailOTP).filter(EmailOTP.email == email).delete()
            db.commit()
        finally:
            db.close()

        await client.post("/auth/register", json={
            "name": "Expired OTP User",
            "email": email,
            "password": "ValidPassword123!"
        })

        # Expire the OTP record in the DB
        code = "123456"
        db = SessionLocal()
        try:
            record = db.query(EmailOTP).filter(EmailOTP.email == email).first()
            record.otp_hash = compute_otp_hash(email, code, "email_verification")
            record.expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
            db.commit()
        finally:
            db.close()

        res = await client.post("/auth/email/verify", json={
            "email": email,
            "otp": code
        })
        assert res.status_code == 400
        assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_otp_purpose_separation():
    """Verify an email verification OTP cannot be used for password reset and vice versa."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "purpose.test@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(EmailOTP).filter(EmailOTP.email == email).delete()
            db.commit()
        finally:
            db.close()

        await client.post("/auth/register", json={
            "name": "Purpose User",
            "email": email,
            "password": "ValidPassword123!"
        })

        code = "555555"
        # Create an OTP strictly for email_verification
        db = SessionLocal()
        try:
            record = db.query(EmailOTP).filter(EmailOTP.email == email).first()
            record.otp_hash = compute_otp_hash(email, code, "email_verification")
            record.purpose = "email_verification"
            db.commit()
        finally:
            db.close()

        # Try to use it for password reset OTP verification -> MUST FAIL
        cross_res = await client.post("/auth/password-reset/verify-otp", json={
            "email": email,
            "otp": code
        })
        assert cross_res.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_flow_with_otp_and_session_revocation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "reset.flow@example.org"
        old_password = "OldPassword123!"
        new_password = "NewArgon2Password999!"

        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(EmailOTP).filter(EmailOTP.email == email).delete()
            db.commit()
        finally:
            db.close()

        # 1. Register & login
        reg_res = await client.post("/auth/register", json={
            "name": "Reset User",
            "email": email,
            "password": old_password
        })
        old_refresh_token = reg_res.json()["refresh_token"]

        # 2. Request password reset (Generic 200 response)
        req_res = await client.post("/auth/password-reset/request", json={"email": email})
        assert req_res.status_code == 200
        assert req_res.json()["status"] == "success"

        # Inject known code into the created password_reset OTP
        reset_code = "889900"
        db = SessionLocal()
        try:
            otp_record = db.query(EmailOTP).filter(
                EmailOTP.email == email,
                EmailOTP.purpose == "password_reset"
            ).order_by(EmailOTP.id.desc()).first()
            otp_record.otp_hash = compute_otp_hash(email, reset_code, "password_reset")
            db.commit()
        finally:
            db.close()

        # 3. Verify OTP -> receives reset_token
        verify_otp_res = await client.post("/auth/password-reset/verify-otp", json={
            "email": email,
            "otp": reset_code
        })
        assert verify_otp_res.status_code == 200, verify_otp_res.text
        reset_token = verify_otp_res.json()["reset_token"]
        assert reset_token is not None

        # 4. Confirm password reset with new password
        confirm_res = await client.post("/auth/password-reset/confirm", json={
            "reset_token": reset_token,
            "new_password": new_password
        })
        assert confirm_res.status_code == 200
        assert "successfully updated" in confirm_res.json()["message"]

        # 5. Verify old refresh token was revoked
        refresh_res = await client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
        assert refresh_res.status_code == 401

        # 6. Login with old password fails
        old_login = await client.post("/auth/login", json={"email": email, "password": old_password})
        assert old_login.status_code == 401

        # 7. Login with new password succeeds
        new_login = await client.post("/auth/login", json={"email": email, "password": new_password})
        assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_generic_forgot_password_no_enumeration():
    """Verify that a non-existent email returns the identical 200 generic success message."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/auth/password-reset/request", json={
            "email": "completely.nonexistent.user.999@test.org"
        })
        assert res.status_code == 200
        assert "password reset instructions have been generated" in res.json()["message"]


@pytest.mark.asyncio
async def test_google_oauth_start_and_token_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Start endpoint returns valid Google OAuth URL
        start_res = await client.get("/auth/google/start")
        assert start_res.status_code == 200
        data = start_res.json()
        assert "accounts.google.com" in data["auth_url"]
        assert "scope=openid%20email%20profile" in data["auth_url"]
        assert data["state"] is not None

        # 2. Token verification with mock token in DEV_MODE
        mock_credential = "mock_google_token_sub_google987654"
        google_res = await client.post("/auth/google/token", json={
            "credential": mock_credential
        })
        assert google_res.status_code == 200, google_res.text
        user_data = google_res.json()
        assert user_data["email_verified"] is True
        assert "google987654" in user_data["email"]

        # Verify OAuthIdentity record in DB
        db = SessionLocal()
        try:
            link = db.query(OAuthIdentity).filter(
                OAuthIdentity.provider == "google",
                OAuthIdentity.provider_user_id == "google987654"
            ).first()
            assert link is not None
            assert link.owner_id == user_data["user_id"]
        finally:
            db.close()


@pytest.mark.asyncio
async def test_google_oauth_safe_account_linking():
    """Verify linking a Google identity to an existing owner account without duplicating owner records."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "google.link.existing@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(OAuthIdentity).filter(OAuthIdentity.email == email).delete()
            db.commit()
        finally:
            db.close()

        # Create user via regular registration
        reg_res = await client.post("/auth/register", json={
            "name": "Existing User",
            "email": email,
            "password": "Password123!"
        })
        owner_id = reg_res.json()["user_id"]

        # Link Google OAuth identity
        mock_credential = f"mock_google:sub_google_linked_999:{email}"
        token_res = await client.post("/auth/google/token", json={
            "credential": mock_credential
        })
        assert token_res.status_code == 200, token_res.text
        data = token_res.json()
        assert data["user_id"] == owner_id  # Same user ID, not duplicate!

        db = SessionLocal()
        try:
            links = db.query(OAuthIdentity).filter(OAuthIdentity.owner_id == owner_id).all()
            assert len(links) >= 1
            assert links[0].provider == "google"
        finally:
            db.close()
