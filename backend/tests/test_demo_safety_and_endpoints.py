import pytest
import datetime
from sqlalchemy import inspect
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db import engine, SessionLocal, init_db, Base
from backend.app.config import settings
from backend.app.models import (
    Owner, Client, Invoice, Obligation, PaymentHistory,
    FinancialEntry, RefreshToken, Forecast, RescuePlan, Action
)
from backend.app.auth.security import hash_password, create_access_token, hash_token
from backend.scripts.seed import seed_database, seed_demo_scenario, reset_database_schema


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    init_db()


# --------------------------------------------------------------------------
# 1. Calling /demo/load cannot delete database tables
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_demo_load_cannot_delete_database_tables():
    """
    Verify that calling /demo/load uses the non-destructive seeding pathway
    and never drops database tables or alters alembic schema metadata.
    """
    inspector_before = inspect(engine)
    tables_before = set(inspector_before.get_table_names())
    assert len(tables_before) > 0
    assert "owners" in tables_before
    assert "clients" in tables_before
    assert "invoices" in tables_before

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as demo user
        res_login = await client.post("/auth/demo-login")
        assert res_login.status_code == 200
        token = res_login.json()["access_token"]

        # Call /demo/load
        res_load = await client.post("/demo/load", headers={"Authorization": f"Bearer {token}"})
        assert res_load.status_code == 200
        assert res_load.json()["status"] == "success"

        # Verify all database tables still exist
        inspector_after = inspect(engine)
        tables_after = set(inspector_after.get_table_names())
        assert tables_before.issubset(tables_after)
        for tbl in ["owners", "clients", "invoices", "obligations", "financial_entries", "audit_log", "refresh_tokens"]:
            assert tbl in tables_after


# --------------------------------------------------------------------------
# 2. Demo loading does not delete existing users
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_demo_loading_does_not_delete_existing_users():
    """
    Verify that loading demo data preserves all existing registered users.
    """
    db = SessionLocal()
    try:
        user_alpha = db.query(Owner).filter(Owner.email == "alpha.founder@startup.com").first()
        if not user_alpha:
            user_alpha = Owner(
                name="Alpha Founder",
                email="alpha.founder@startup.com",
                hashed_password=hash_password("SecurePass123!"),
                is_demo=False,
                is_active=True
            )
            db.add(user_alpha)

        user_beta = db.query(Owner).filter(Owner.email == "beta.freelance@design.co").first()
        if not user_beta:
            user_beta = Owner(
                name="Beta Freelance",
                email="beta.freelance@design.co",
                hashed_password=hash_password("SecurePass123!"),
                is_demo=False,
                is_active=True
            )
            db.add(user_beta)

        db.commit()
        db.refresh(user_alpha)
        db.refresh(user_beta)
        alpha_id = user_alpha.id
        beta_id = user_beta.id
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        token = res_login.json()["access_token"]

        res_load = await client.post("/demo/load", headers={"Authorization": f"Bearer {token}"})
        assert res_load.status_code == 200

    db = SessionLocal()
    try:
        check_alpha = db.query(Owner).filter(Owner.id == alpha_id).first()
        check_beta = db.query(Owner).filter(Owner.id == beta_id).first()
        assert check_alpha is not None
        assert check_alpha.email == "alpha.founder@startup.com"
        assert check_beta is not None
        assert check_beta.email == "beta.freelance@design.co"
    finally:
        db.close()


# --------------------------------------------------------------------------
# 3. Demo loading does not modify real user accounts
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_demo_loading_does_not_modify_real_user_accounts():
    """
    Verify that existing real user accounts retain their is_demo=False status,
    personal details, and private records without any demo contamination.
    """
    db = SessionLocal()
    try:
        real_user = db.query(Owner).filter(Owner.email == "charlie.real@enterprise.org").first()
        if not real_user:
            real_user = Owner(
                name="Charlie Real",
                email="charlie.real@enterprise.org",
                hashed_password=hash_password("EnterprisePass99!"),
                currency="EUR",
                preferred_currency="EUR",
                country="DE",
                is_demo=False,
                is_active=True
            )
            db.add(real_user)
            db.commit()
            db.refresh(real_user)

        # Give real user a private client and obligation
        client_count_before = db.query(Client).filter(Client.owner_id == real_user.id).count()
        if client_count_before == 0:
            private_client = Client(
                owner_id=real_user.id,
                name="Private Corporate Client",
                email="corp@private.de",
                country="DE",
                typical_invoice_amount=5000.0,
                is_seeded=False
            )
            db.add(private_client)
            db.commit()

        real_user_id = real_user.id
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        token = res_login.json()["access_token"]
        res_load = await client.post("/demo/load", headers={"Authorization": f"Bearer {token}"})
        assert res_load.status_code == 200

    db = SessionLocal()
    try:
        refreshed_user = db.query(Owner).filter(Owner.id == real_user_id).first()
        assert refreshed_user is not None
        assert refreshed_user.is_demo is False
        assert refreshed_user.name == "Charlie Real"
        assert refreshed_user.currency == "EUR"
        assert refreshed_user.preferred_currency == "EUR"
        assert refreshed_user.country == "DE"

        # Verify real user's private clients have not been altered or marked seeded
        real_clients = db.query(Client).filter(Client.owner_id == real_user_id).all()
        assert any(c.name == "Private Corporate Client" for c in real_clients)
        assert all(c.is_seeded is False for c in real_clients)
    finally:
        db.close()


# --------------------------------------------------------------------------
# 4. An unauthorized user cannot load demo data
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_user_cannot_load_demo_data():
    """
    Verify that unauthenticated callers (401) and ordinary non-demo users (403)
    are strictly rejected from invoking /demo/load.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated request
        res_no_auth = await client.post("/demo/load")
        assert res_no_auth.status_code == 401

        # 2. Authenticated as an ordinary real user (is_demo=False)
        db = SessionLocal()
        try:
            ordinary_user = db.query(Owner).filter(Owner.email == "ordinary.user@finance.com").first()
            if not ordinary_user:
                ordinary_user = Owner(
                    name="Ordinary User",
                    email="ordinary.user@finance.com",
                    hashed_password=hash_password("ValidPassword2026!"),
                    is_demo=False,
                    is_active=True,
                    email_verified=True
                )
                db.add(ordinary_user)
                db.commit()
                db.refresh(ordinary_user)
            token_ordinary = create_access_token({"sub": ordinary_user.id, "email": ordinary_user.email})
        finally:
            db.close()

        res_forbidden = await client.post(
            "/demo/load",
            headers={"Authorization": f"Bearer {token_ordinary}"}
        )
        assert res_forbidden.status_code == 403
        assert "Ordinary authenticated user accounts cannot trigger demo data operations" in res_forbidden.json()["detail"]


# --------------------------------------------------------------------------
# 5. An unauthorized user cannot clear demo data
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_user_cannot_clear_demo_data():
    """
    Verify that unauthenticated callers (401) and ordinary non-demo users (403)
    are strictly prohibited from invoking /demo/clear.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated
        res_no_auth = await client.post("/demo/clear")
        assert res_no_auth.status_code == 401

        # 2. Authenticated as ordinary user (is_demo=False)
        db = SessionLocal()
        try:
            ordinary_user = db.query(Owner).filter(Owner.email == "ordinary.user@finance.com").first()
            token_ordinary = create_access_token({"sub": ordinary_user.id, "email": ordinary_user.email})
        finally:
            db.close()

        res_forbidden = await client.post(
            "/demo/clear",
            headers={"Authorization": f"Bearer {token_ordinary}"}
        )
        assert res_forbidden.status_code == 403


# --------------------------------------------------------------------------
# 6. One demo user cannot delete another demo user's data
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_one_demo_user_cannot_delete_another_demo_user_data():
    """
    Verify that /demo/clear is strictly scoped to the caller's owner ID.
    Demo User A clearing their data must leave Demo User B's records untouched.
    """
    db = SessionLocal()
    try:
        # Create Demo User A
        demo_a = db.query(Owner).filter(Owner.email == "demo.user.a@test.org").first()
        if not demo_a:
            demo_a = Owner(
                name="Demo User A",
                email="demo.user.a@test.org",
                hashed_password=hash_password("DemoPasswordA1!"),
                is_demo=True,
                is_active=True,
                email_verified=True
            )
            db.add(demo_a)

        # Create Demo User B
        demo_b = db.query(Owner).filter(Owner.email == "demo.user.b@test.org").first()
        if not demo_b:
            demo_b = Owner(
                name="Demo User B",
                email="demo.user.b@test.org",
                hashed_password=hash_password("DemoPasswordB2!"),
                is_demo=True,
                is_active=True,
                email_verified=True
            )
            db.add(demo_b)

        db.commit()
        db.refresh(demo_a)
        db.refresh(demo_b)

        # Seed specific data for Demo User B
        client_b = Client(
            owner_id=demo_b.id,
            name="Demo B Unique Client",
            email="unique.client@demob.org",
            is_seeded=True
        )
        db.add(client_b)

        obl_b = Obligation(
            owner_id=demo_b.id,
            payee_name="Demo B Exclusive Contractor",
            payee_email="exclusive@contractorb.org",
            amount=7777.0,
            currency="USD",
            due_date=datetime.datetime.utcnow() + datetime.timedelta(days=7),
            status="pending"
        )
        db.add(obl_b)

        entry_b = FinancialEntry(
            owner_id=demo_b.id,
            title="Demo B Reserve",
            amount=9999.0,
            currency="USD",
            entry_type="opening_balance",
            category="opening_balance",
            transaction_date=datetime.datetime.utcnow(),
            status="confirmed",
            is_demo=True
        )
        db.add(entry_b)
        db.commit()

        token_a = create_access_token({"sub": demo_a.id, "email": demo_a.email, "email_verified": True})
        b_id = demo_b.id
    finally:
        db.close()

    # User A invokes /demo/clear
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_clear_a = await client.post("/demo/clear", headers={"Authorization": f"Bearer {token_a}"})
        assert res_clear_a.status_code == 200

    # Verify User B's records are 100% intact
    db = SessionLocal()
    try:
        check_client_b = db.query(Client).filter(Client.owner_id == b_id, Client.name == "Demo B Unique Client").first()
        check_obl_b = db.query(Obligation).filter(Obligation.owner_id == b_id, Obligation.payee_name == "Demo B Exclusive Contractor").first()
        check_entry_b = db.query(FinancialEntry).filter(FinancialEntry.owner_id == b_id, FinancialEntry.title == "Demo B Reserve").first()

        assert check_client_b is not None
        assert check_obl_b is not None
        assert float(check_obl_b.amount) == 7777.0
        assert check_entry_b is not None
        assert float(check_entry_b.amount) == 9999.0
    finally:
        db.close()


# --------------------------------------------------------------------------
# 7. Demo seeding can run multiple times without creating duplicate records
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_demo_seeding_idempotent_no_duplicate_records():
    """
    Verify that invoking /demo/load multiple times is strictly idempotent:
    produces the exact same number of clients, invoices, obligations, and balances.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        token = res_login.json()["access_token"]
        user_id = res_login.json()["user_id"]

        # Clean demo state for this user first
        await client.post("/demo/clear", headers={"Authorization": f"Bearer {token}"})

        # Run 1
        res1 = await client.post("/demo/load", headers={"Authorization": f"Bearer {token}"})
        assert res1.status_code == 200

        db = SessionLocal()
        try:
            clients_count_1 = db.query(Client).filter(Client.owner_id == user_id).count()
            obls_count_1 = db.query(Obligation).filter(Obligation.owner_id == user_id).count()
            invoices_count_1 = db.query(Invoice).join(Client).filter(Client.owner_id == user_id).count()
            entries_count_1 = db.query(FinancialEntry).filter(FinancialEntry.owner_id == user_id).count()

            assert clients_count_1 == 6
            assert obls_count_1 == 1
        finally:
            db.close()

        # Run 2
        res2 = await client.post("/demo/load", headers={"Authorization": f"Bearer {token}"})
        assert res2.status_code == 200

        # Run 3
        res3 = await client.post("/demo/load", headers={"Authorization": f"Bearer {token}"})
        assert res3.status_code == 200

        db = SessionLocal()
        try:
            clients_count_3 = db.query(Client).filter(Client.owner_id == user_id).count()
            obls_count_3 = db.query(Obligation).filter(Obligation.owner_id == user_id).count()
            invoices_count_3 = db.query(Invoice).join(Client).filter(Client.owner_id == user_id).count()
            entries_count_3 = db.query(FinancialEntry).filter(FinancialEntry.owner_id == user_id).count()

            # Zero duplicate records created
            assert clients_count_3 == clients_count_1
            assert obls_count_3 == obls_count_1
            assert invoices_count_3 == invoices_count_1
            assert entries_count_3 == entries_count_1
        finally:
            db.close()


# --------------------------------------------------------------------------
# 8. Demo login creates a valid refresh-token record
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_demo_login_creates_valid_refresh_token_record():
    """
    Verify that /auth/demo-login issues a valid refresh token and persists it
    in the refresh_tokens table.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/auth/demo-login")
        assert res.status_code == 200
        data = res.json()
        assert "refresh_token" in data
        assert "access_token" in data
        refresh_token = data["refresh_token"]
        user_id = data["user_id"]

        db = SessionLocal()
        try:
            token_rec = db.query(RefreshToken).filter(
                RefreshToken.token.in_([refresh_token, hash_token(refresh_token)]),
                RefreshToken.owner_id == user_id
            ).first()
            assert token_rec is not None
            assert token_rec.revoked is False
            assert token_rec.expires_at > datetime.datetime.utcnow()
        finally:
            db.close()


# --------------------------------------------------------------------------
# 9. Demo refresh-token rotation works
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_demo_refresh_token_rotation_and_revocation():
    """
    Verify that demo accounts support refresh token rotation:
    - /auth/refresh revokes the old refresh token and issues a new one.
    - Replaying the revoked refresh token fails with 401.
    - /auth/logout revokes active refresh tokens.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        assert res_login.status_code == 200
        t1 = res_login.json()["refresh_token"]

        # 1. Rotate refresh token via /auth/refresh
        res_refresh = await client.post("/auth/refresh", json={"refresh_token": t1})
        assert res_refresh.status_code == 200
        data_refresh = res_refresh.json()
        t2 = data_refresh["refresh_token"]
        a2 = data_refresh["access_token"]
        assert t2 != t1

        # Check DB: t1 is revoked, t2 is active
        db = SessionLocal()
        try:
            rec1 = db.query(RefreshToken).filter(RefreshToken.token.in_([t1, hash_token(t1)])).first()
            rec2 = db.query(RefreshToken).filter(RefreshToken.token.in_([t2, hash_token(t2)])).first()
            assert rec1 is not None and rec1.revoked is True
            assert rec2 is not None and rec2.revoked is False
        finally:
            db.close()

        # 2. Logout revokes active refresh tokens
        res_logout = await client.post("/auth/logout", headers={"Authorization": f"Bearer {a2}"})
        assert res_logout.status_code == 200

        # Attempt to use t2 after logout MUST be rejected (401)
        res_after_logout = await client.post("/auth/refresh", json={"refresh_token": t2})
        assert res_after_logout.status_code == 401

        # 3. Replay of old refresh token t1 MUST be rejected (401)
        res_replay = await client.post("/auth/refresh", json={"refresh_token": t1})
        assert res_replay.status_code == 401


# --------------------------------------------------------------------------
# 10. Production configuration rejects demo endpoints
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_production_configuration_rejects_demo_endpoints(monkeypatch):
    """
    Verify that when settings.DEV_MODE is False (or ALLOW_DEMO_ENDPOINTS is False),
    all demo endpoints (/auth/demo-login, /demo/load, /demo/clear, /demo/status)
    are strictly rejected with 403 Forbidden.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Obtain demo token while in dev mode
        res_login = await client.post("/auth/demo-login")
        token = res_login.json()["access_token"]

        # Simulate production environment
        monkeypatch.setattr(settings, "DEV_MODE", False)
        monkeypatch.setattr(settings, "ALLOW_DEMO_ENDPOINTS", False)

        # 1. /auth/demo-login must be rejected
        res_prod_login = await client.post("/auth/demo-login")
        assert res_prod_login.status_code == 403

        # 2. /demo/load must be rejected
        res_prod_load = await client.post("/demo/load", headers={"Authorization": f"Bearer {token}"})
        assert res_prod_load.status_code == 403

        # 3. /demo/clear must be rejected
        res_prod_clear = await client.post("/demo/clear", headers={"Authorization": f"Bearer {token}"})
        assert res_prod_clear.status_code == 403

        # 4. /demo/status must be rejected
        res_prod_status = await client.get("/demo/status", headers={"Authorization": f"Bearer {token}"})
        assert res_prod_status.status_code == 403
