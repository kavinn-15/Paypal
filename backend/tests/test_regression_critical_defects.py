import pytest
import datetime
import threading
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import Owner, Client, Invoice, Obligation, PaymentHistory, FinancialEntry, Action
from backend.scripts.seed import seed_database
from backend.app.guardrail.audit import append_audit_log, verify_audit_chain, compute_hash
from backend.app.guardrail.state_machine import GuardrailStateMachine, ActionState, InvalidStateTransitionError
from backend.app.guardrail.approval import generate_approval_hash


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database(clean=True, demo_mode=True)


@pytest.mark.asyncio
async def test_demo_login_cannot_issue_token_for_real_user():
    """Verify that /auth/demo-login NEVER falls back to or issues credentials for a real user account."""
    db = SessionLocal()
    try:
        # Create a real, non-demo user
        real_user = Owner(
            name="Real Independent Freelancer",
            email="real.architect@fintechcorp.example.com",
            is_demo=False,
            is_active=True
        )
        db.add(real_user)
        db.commit()
        db.refresh(real_user)
        real_id = real_user.id
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/auth/demo-login")
        assert res.status_code == 200
        data = res.json()
        # Must issue for demo user, NEVER for real user
        assert data["user_id"] != real_id
        assert data["is_demo"] is True
        assert data["email"] == "alex.morgan.freelance@example.com"


@pytest.mark.asyncio
async def test_demo_clear_does_not_delete_real_user_records():
    """Verify that calling /demo/clear only purges demo data and preserves real users' records."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a real user
        res_reg = await client.post("/auth/register", json={
            "name": "David Real Client",
            "email": "david.real@enterprise.example.com",
            "password": "SecurePassword2026!",
            "currency": "USD"
        })
        assert res_reg.status_code == 200
        token_real = res_reg.json()["access_token"]
        headers_real = {"Authorization": f"Bearer {token_real}"}

        # 2. Real user creates an obligation
        res_obl = await client.post("/obligations", json={
            "payee_name": "Critical Supplier Inc",
            "payee_email": "billing@criticalsupplier.com",
            "amount": 4500.0,
            "currency": "USD",
            "due_date": "2026-12-01T00:00:00",
            "split_allowed": True
        }, headers=headers_real)
        assert res_obl.status_code == 201
        real_obl_id = res_obl.json()["id"]

        # 3. Call /demo/clear
        res_clear = await client.post("/demo/clear", headers=headers_real)
        assert res_clear.status_code == 200

        # 4. Verify real user's obligation is 100% preserved
        res_check = await client.get(f"/obligations/{real_obl_id}", headers=headers_real)
        assert res_check.status_code == 200
        assert res_check.json()["payee_name"] == "Critical Supplier Inc"
        assert res_check.json()["amount"] == 4500.0


def test_seed_database_does_not_modify_first_registered_user():
    """Verify that seed_database selects or creates dedicated demo owner, never overwriting a real user."""
    db = SessionLocal()
    try:
        # Create an early registered non-demo user
        existing_real = db.query(Owner).filter(Owner.email == "early.founder@tech.example.com").first()
        if not existing_real:
            existing_real = Owner(
                name="Early Founder",
                email="early.founder@tech.example.com",
                is_demo=False,
                is_active=True
            )
            db.add(existing_real)
            db.commit()
            db.refresh(existing_real)

        # Call seed_database without clean
        seed_database(clean=False, demo_mode=True)

        # Verify real user was untouched
        db.refresh(existing_real)
        assert existing_real.name == "Early Founder"
        assert existing_real.is_demo is False
        assert existing_real.email == "early.founder@tech.example.com"

        # Verify dedicated demo owner exists separately
        demo_owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        assert demo_owner is not None
        assert demo_owner.id != existing_real.id
        assert demo_owner.is_demo is True
    finally:
        db.close()


@pytest.mark.asyncio
async def test_negotiator_cross_tenant_rejection():
    """Verify that NegotiationAgent rejects foreign client_id and obligation_id with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as User A (Demo user)
        res_a = await client.post("/auth/demo-login")
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        res_clients = await client.get("/clients", headers=headers_a)
        user_a_client_id = res_clients.json()[0]["id"]

        # Register User B
        res_reg_b = await client.post("/auth/register", json={
            "name": "Tenant B",
            "email": "tenant.b@crosscheck.example.com",
            "password": "StrongPassword2026!",
            "currency": "USD"
        })
        token_b = res_reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B attempts to generate negotiation targeting User A's client_id -> 400 Bad Request
        res_neg = await client.post("/negotiate/generate", json={
            "target_type": "client_discount",
            "client_id": user_a_client_id,
            "discount_pct": 3.0
        }, headers=headers_b)
        assert res_neg.status_code == 400
        assert "not found or does not belong to owner" in res_neg.json()["detail"]


@pytest.mark.asyncio
async def test_partial_payment_ledger_accounting():
    """Verify that partially paid invoices report only outstanding balance, never full amount."""
    db = SessionLocal()
    try:
        demo_owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        test_client = db.query(Client).filter(Client.owner_id == demo_owner.id).first()

        # Create test invoice for $3,000
        inv = Invoice(
            paypal_invoice_id="INV-PARTIAL-TEST-3000",
            client_id=test_client.id,
            amount=Decimal("3000.00"),
            currency="USD",
            issue_date=datetime.datetime.now(datetime.timezone.utc),
            due_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10),
            status="PARTIALLY_PAID"
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)

        # Record partial payment of $1,000 in payment_history
        hist = PaymentHistory(
            client_id=test_client.id,
            invoice_id=inv.id,
            amount=Decimal("1000.00"),
            due_date=inv.due_date,
            paid_date=datetime.datetime.now(datetime.timezone.utc),
            days_late=0.0,
            source="paypal"
        )
        db.add(hist)
        db.commit()
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post("/auth/demo-login")
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check timeline: outstanding amount must be $2,000.00, not $3,000.00
        res_timeline = await client.get("/finance/timeline", headers=headers)
        assert res_timeline.status_code == 200
        timeline_items = res_timeline.json()

        part_item = next((item for item in timeline_items if "INV-PARTIAL-TEST-3000" in item.get("reference_id", "") and item["status"] == "expected"), None)
        assert part_item is not None
        assert part_item["amount"] == 2000.0  # Exactly $3000 - $1000 partial payment!


def test_concurrent_audit_chain_thread_safety():
    """Verify that multiple threads appending to audit chain concurrently maintain unbroken cryptographic integrity."""
    db = SessionLocal()
    try:
        demo_owner = db.query(Owner).filter(Owner.email == "alex.morgan.freelance@example.com").first()
        threads = []
        errors = []

        def worker(thread_idx: int):
            worker_db = SessionLocal()
            try:
                for i in range(5):
                    append_audit_log(
                        worker_db,
                        actor=f"worker_thread_{thread_idx}",
                        event="CONCURRENT_AUDIT_TEST",
                        payload={"idx": i, "thread": thread_idx},
                        owner_id=demo_owner.id
                    )
            except Exception as e:
                errors.append(e)
            finally:
                worker_db.close()

        for t_id in range(4):
            t = threading.Thread(target=worker, args=(t_id,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0

        # Verify hash chain integrity
        is_valid, total, msg, bad_id = verify_audit_chain(db)
        assert is_valid is True
        assert bad_id is None
        assert total >= 20
    finally:
        db.close()
