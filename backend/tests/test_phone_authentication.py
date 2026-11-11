import pytest
import datetime
import secrets
import re
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db import SessionLocal, init_db
from backend.app.models import Owner, PhoneOTP, Obligation, RefreshToken
from backend.app.services.sms_service import get_last_dev_sms, clear_dev_sms_inbox, ConsoleSMSProvider
from backend.app.services.phone_otp_service import _PHONE_RATE_LIMITS, hash_phone_otp
from backend.app.auth.phone import normalize_phone_number, mask_phone_number


def extract_otp_from_sms(message: str) -> str:
    match = re.search(r'\b\d{6}\b', message)
    if not match:
        raise ValueError(f"No 6-digit OTP found in SMS message: {message}")
    return match.group(0)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture(autouse=True)
def clean_state():
    _PHONE_RATE_LIMITS.clear()
    clear_dev_sms_inbox()
    db = SessionLocal()
    try:
        db.query(PhoneOTP).delete()
        db.commit()
    finally:
        db.close()
    yield
    _PHONE_RATE_LIMITS.clear()
    clear_dev_sms_inbox()
    db = SessionLocal()
    try:
        db.query(PhoneOTP).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_phone_registration_and_e164_normalization():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "phone.reg@example.org"
        raw_phone = "9876543210"  # Indian 10-digit number without country code
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.query(Owner).filter(Owner.phone_number == "+919876543210").delete()
            db.commit()
        finally:
            db.close()

        res = await client.post("/auth/register", json={
            "name": "Phone User",
            "email": email,
            "password": "Password123!",
            "phone_number": raw_phone,
            "phone_country_code": "+91",
            "country": "IN",
            "terms_accepted": True
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["phone_number"] == "+919876543210"
        assert data["phone_verified"] is False

        # Verify SMS was dispatched to in-memory test inbox
        sms = get_last_dev_sms("+919876543210")
        assert sms is not None
        assert "Cashflow Lifeline: Your verification code is" in sms["message"]


@pytest.mark.asyncio
async def test_invalid_phone_number_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/auth/register", json={
            "name": "Invalid Phone User",
            "email": "invalid.phone@example.org",
            "password": "Password123!",
            "phone_number": "12345",  # Too short to be valid
            "country": "IN",
            "terms_accepted": True
        })
        assert res.status_code == 400
        assert "Invalid phone number" in res.json()["detail"] or "Unable to parse" in res.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_phone_number_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919811122233"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.phone_number == phone).delete()
            db.query(Owner).filter(Owner.email.in_(["user1.dup@test.org", "user2.dup@test.org"])).delete()
            db.commit()
        finally:
            db.close()

        # First registration succeeds
        res1 = await client.post("/auth/register", json={
            "name": "User One",
            "email": "user1.dup@test.org",
            "password": "Password123!",
            "phone_number": phone,
            "country": "IN",
            "terms_accepted": True
        })
        assert res1.status_code == 200

        # Second registration with same phone must be rejected
        res2 = await client.post("/auth/register", json={
            "name": "User Two",
            "email": "user2.dup@test.org",
            "password": "Password123!",
            "phone_number": phone,
            "country": "IN",
            "terms_accepted": True
        })
        assert res2.status_code == 400
        assert "already exists" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_international_phone_number_normalization():
    # Test UK (+44), US (+1), and India (+91)
    uk_num = normalize_phone_number("+447911123456")
    assert uk_num == "+447911123456"

    us_num = normalize_phone_number("2025550143", default_region="US")
    assert us_num == "+12025550143"

    in_num = normalize_phone_number("9876543210", default_region="IN")
    assert in_num == "+919876543210"

    masked = mask_phone_number("+919876543210")
    assert masked.startswith("+91 98")
    assert masked.endswith("210")
    assert "*" in masked


@pytest.mark.asyncio
async def test_phone_otp_verification_success_and_single_use():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919844455566"
        email = "verify.phone@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.phone_number == phone).delete()
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        # Register
        await client.post("/auth/register", json={
            "name": "Verify Tester",
            "email": email,
            "password": "Password123!",
            "phone_number": phone,
            "country": "IN",
            "terms_accepted": True
        })

        # Fetch plain code from dev inbox
        sms = get_last_dev_sms(phone)
        assert sms is not None
        code = extract_otp_from_sms(sms["message"])

        # Verify with correct code
        v_res = await client.post("/auth/phone/verification/verify", json={
            "phone_number": phone,
            "otp": code
        })
        assert v_res.status_code == 200
        assert v_res.json()["status"] == "success"

        # Verify DB reflects phone_verified=True
        db = SessionLocal()
        try:
            user = db.query(Owner).filter(Owner.phone_number == phone).first()
            assert user.phone_verified is True
            assert user.phone_verified_at is not None
        finally:
            db.close()

        # Reusing the exact same OTP code must fail (single-use)
        reuse_res = await client.post("/auth/phone/verification/verify", json={
            "phone_number": phone,
            "otp": code
        })
        assert reuse_res.status_code == 400


@pytest.mark.asyncio
async def test_phone_otp_incorrect_code_and_attempt_limits():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919855566677"
        req_res = await client.post("/auth/phone/verification/request", json={
            "phone_number": phone,
            "country_code": "+91"
        })
        assert req_res.status_code == 200

        # Attempt 1 wrong code
        bad1 = await client.post("/auth/phone/verification/verify", json={
            "phone_number": phone,
            "otp": "000000"
        })
        assert bad1.status_code == 400
        assert "Incorrect verification code" in bad1.json()["detail"]


@pytest.mark.asyncio
async def test_phone_otp_expired_code_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919866677788"
        db = SessionLocal()
        try:
            db.query(PhoneOTP).filter(PhoneOTP.phone_number == phone).delete()
            db.commit()
        finally:
            db.close()

        await client.post("/auth/phone/verification/request", json={"phone_number": phone})

        # Manually expire the OTP in the database
        db = SessionLocal()
        try:
            record = (
                db.query(PhoneOTP)
                .filter(PhoneOTP.phone_number == phone, PhoneOTP.purpose == "phone_verification")
                .order_by(PhoneOTP.created_at.desc())
                .first()
            )
            record.expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
            db.commit()
        finally:
            db.close()

        sms = get_last_dev_sms(phone)
        code = extract_otp_from_sms(sms["message"])

        res = await client.post("/auth/phone/verification/verify", json={
            "phone_number": phone,
            "otp": code
        })
        assert res.status_code == 400
        assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_phone_otp_purpose_separation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919877788899"
        # Request verification OTP
        await client.post("/auth/phone/verification/request", json={"phone_number": phone})
        sms = get_last_dev_sms(phone)
        verification_code = extract_otp_from_sms(sms["message"])

        # Attempt to use verification code for phone_login
        login_res = await client.post("/auth/phone/login/verify-otp", json={
            "phone_number": phone,
            "otp": verification_code
        })
        assert login_res.status_code == 400

        # Attempt to use verification code for password reset
        reset_res = await client.post("/auth/phone/password-reset/verify-otp", json={
            "phone_number": phone,
            "otp": verification_code
        })
        assert reset_res.status_code == 400


@pytest.mark.asyncio
async def test_phone_login_with_password():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919888899900"
        email = "phone.pwd@example.org"
        password = "SecurePassword123!"

        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.phone_number == phone).delete()
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        # Register
        await client.post("/auth/register", json={
            "name": "Phone Pwd User",
            "email": email,
            "password": password,
            "phone_number": phone,
            "country": "IN",
            "terms_accepted": True
        })

        # Login with correct phone & password
        login_res = await client.post("/auth/phone/login/password", json={
            "phone_number": phone,
            "password": password
        })
        assert login_res.status_code == 200
        data = login_res.json()
        assert data["access_token"] is not None
        assert data["phone_number"] == phone

        # Login with wrong password fails
        bad_res = await client.post("/auth/phone/login/password", json={
            "phone_number": phone,
            "password": "WrongPassword!"
        })
        assert bad_res.status_code == 401


@pytest.mark.asyncio
async def test_phone_login_with_otp_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919899900011"
        email = "phone.otp.login@example.org"
        password = "Password123!"

        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.phone_number == phone).delete()
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        # Register user
        await client.post("/auth/register", json={
            "name": "OTP Login User",
            "email": email,
            "password": password,
            "phone_number": phone,
            "country": "IN",
            "terms_accepted": True
        })

        # 1. Unverified phone cannot use OTP login
        unverified_req = await client.post("/auth/phone/login/request-otp", json={"phone_number": phone})
        assert unverified_req.status_code == 400
        assert "not been verified" in unverified_req.json()["detail"].lower()

        # 2. Mark phone verified
        db = SessionLocal()
        try:
            u = db.query(Owner).filter(Owner.phone_number == phone).first()
            u.phone_verified = True
            db.commit()
        finally:
            db.close()

        # 3. Request OTP for login succeeds
        req_res = await client.post("/auth/phone/login/request-otp", json={"phone_number": phone})
        assert req_res.status_code == 200

        sms = get_last_dev_sms(phone)
        code = extract_otp_from_sms(sms["message"])

        # 4. Verify login OTP
        auth_res = await client.post("/auth/phone/login/verify-otp", json={
            "phone_number": phone,
            "otp": code
        })
        assert auth_res.status_code == 200
        data = auth_res.json()
        assert data["access_token"] is not None
        assert data["phone_number"] == phone


@pytest.mark.asyncio
async def test_phone_password_reset_and_session_revocation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919800011122"
        email = "phone.reset@example.org"
        old_pwd = "OldPassword123!"
        new_pwd = "NewArgon2Pass999!"

        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.phone_number == phone).delete()
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        reg_res = await client.post("/auth/register", json={
            "name": "Reset User",
            "email": email,
            "password": old_pwd,
            "phone_number": phone,
            "country": "IN",
            "terms_accepted": True
        })
        old_refresh = reg_res.json()["refresh_token"]

        # Request password reset via phone
        req_res = await client.post("/auth/phone/password-reset/request", json={"phone_number": phone})
        assert req_res.status_code == 200

        sms = get_last_dev_sms(phone)
        code = extract_otp_from_sms(sms["message"])

        # Verify OTP -> yields reset token
        v_res = await client.post("/auth/phone/password-reset/verify-otp", json={
            "phone_number": phone,
            "otp": code
        })
        assert v_res.status_code == 200
        reset_token = v_res.json()["reset_token"]

        # Confirm new password
        confirm_res = await client.post("/auth/phone/password-reset/confirm", json={
            "reset_token": reset_token,
            "new_password": new_pwd
        })
        assert confirm_res.status_code == 200

        # Old refresh token is revoked
        refresh_attempt = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert refresh_attempt.status_code == 401

        # Old password login fails
        old_login = await client.post("/auth/login", json={"email": email, "password": old_pwd})
        assert old_login.status_code == 401

        # New password login succeeds
        new_login = await client.post("/auth/phone/login/password", json={"phone_number": phone, "password": new_pwd})
        assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_change_existing_phone_number_with_reauth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "change.phone@example.org"
        old_phone = "+919811100001"
        new_phone = "+919811100002"
        password = "Password123!"

        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.phone_number.in_([old_phone, new_phone])).delete()
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        reg_res = await client.post("/auth/register", json={
            "name": "Change User",
            "email": email,
            "password": password,
            "phone_number": old_phone,
            "country": "IN",
            "terms_accepted": True
        })
        token = reg_res.json()["access_token"]

        # Request change with WRONG current password fails
        bad_req = await client.post(
            "/auth/phone/change/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "WrongPassword!", "new_phone_number": new_phone}
        )
        assert bad_req.status_code == 400
        assert "Incorrect password" in bad_req.json()["detail"]

        # Request change with correct password succeeds
        good_req = await client.post(
            "/auth/phone/change/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": password, "new_phone_number": new_phone}
        )
        assert good_req.status_code == 200

        # Extract OTP sent to new_phone
        sms = get_last_dev_sms(new_phone)
        code = extract_otp_from_sms(sms["message"])

        # Verify change
        v_res = await client.post(
            "/auth/phone/change/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_phone_number": new_phone, "otp": code}
        )
        assert v_res.status_code == 200

        # Check that user profile now contains new phone
        me_res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        assert me_res.json()["phone_number"] == new_phone
        assert me_res.json()["phone_verified"] is True


@pytest.mark.asyncio
async def test_email_only_existing_user_compatibility_and_financial_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "email.only@example.org"
        pwd = "Password123!"

        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        # Register without phone number (email-only)
        reg_res = await client.post("/auth/register", json={
            "name": "Email Only User",
            "email": email,
            "password": pwd,
            "terms_accepted": True
        })
        assert reg_res.status_code == 200
        assert reg_res.json()["phone_number"] is None
        token = reg_res.json()["access_token"]

        # Mark email verified
        db = SessionLocal()
        try:
            u = db.query(Owner).filter(Owner.email == email).first()
            u.email_verified = True
            db.commit()
        finally:
            db.close()

        # User creates an isolated obligation
        ob_res = await client.post(
            "/obligations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "payee_name": "Isolated Contractor",
                "payee_email": "contractor@isolated.org",
                "amount": 950.00,
                "due_date": "2026-11-25T12:00:00Z"
            }
        )
        assert ob_res.status_code in [200, 201]
        ob_id = ob_res.json()["id"]

        # Another user cannot see this obligation
        other_login = await client.post("/auth/demo-login")
        other_token = other_login.json()["access_token"]
        list_res = await client.get("/obligations", headers={"Authorization": f"Bearer {other_token}"})
        assert all(o["id"] != ob_id for o in list_res.json())


@pytest.mark.asyncio
async def test_resend_cooldown_and_rate_limiting():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "+919822233344"
        # 1st request succeeds
        r1 = await client.post("/auth/phone/verification/request", json={"phone_number": phone})
        assert r1.status_code == 200

        # Immediate 2nd request triggers 429 resend cooldown
        r2 = await client.post("/auth/phone/verification/request", json={"phone_number": phone})
        assert r2.status_code == 429
        assert "Please wait" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_google_login_compatibility():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = "google.compat@example.org"
        db = SessionLocal()
        try:
            db.query(Owner).filter(Owner.email == email).delete()
            db.commit()
        finally:
            db.close()

        mock_token = f"mock_google:google_compat_sub_999:{email}"
        res = await client.post("/auth/google/token", json={"credential": mock_token})
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == email
        assert data["email_verified"] is True
        assert data["phone_verified"] is False

