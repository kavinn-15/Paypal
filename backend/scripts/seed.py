import sys
import argparse
import random
from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db import engine, SessionLocal, init_db, Base
from backend.app.models import (
    Owner, PayPalConnection, Client, Invoice, PaymentHistory, Obligation,
    AuditLog, Forecast, RescuePlan, Action, ClientPrediction, WebhookEvent, Message, FinancialEntry
)
from backend.app.guardrail.audit import compute_hash, GENESIS_HASH
from backend.app.auth.security import hash_password

CANONICAL_DEMO_EMAIL = settings.CANONICAL_DEMO_EMAIL


CLIENT_PROFILES = [
    {
        "name": "Apex Design Studio",
        "email": "billing@apexdesign.example.com",
        "country": "DE",
        "typical_invoice_amount": 2000.0,
        "relationship_weight": 0.85,
        "behavior": "chronically_late",  # 10 to 18 days late
        "mean_delay": 14,
        "std_delay": 3.0,
    },
    {
        "name": "Vertex Software Inc",
        "email": "ap@vertexsoft.example.com",
        "country": "US",
        "typical_invoice_amount": 1200.0,
        "relationship_weight": 1.0,
        "behavior": "on_time",  # 0 to 1 days late
        "mean_delay": 0.5,
        "std_delay": 0.8,
    },
    {
        "name": "Nordic Data Labs",
        "email": "finance@nordicdata.example.se",
        "country": "SE",
        "typical_invoice_amount": 1500.0,
        "relationship_weight": 0.9,
        "behavior": "overseas_variable",  # 3 to 8 days late
        "mean_delay": 6.0,
        "std_delay": 2.2,
    },
    {
        "name": "Bluefin Media",
        "email": "accounts@bluefinmedia.example.co.uk",
        "country": "GB",
        "typical_invoice_amount": 800.0,
        "relationship_weight": 0.75,
        "behavior": "occasional_late",  # 2 to 5 days late
        "mean_delay": 3.5,
        "std_delay": 1.5,
    },
    {
        "name": "Catalyst Agency",
        "email": "payables@catalystagency.example.ca",
        "country": "CA",
        "typical_invoice_amount": 600.0,
        "relationship_weight": 0.95,
        "behavior": "fast_early",  # pays early (-3 to 0 days)
        "mean_delay": -2.0,
        "std_delay": 1.0,
    },
    {
        "name": "Zenith Global Consulting",
        "email": "invoices@zenithglobal.example.com.au",
        "country": "AU",
        "typical_invoice_amount": 2500.0,
        "relationship_weight": 0.8,
        "behavior": "steady_slight_delay",  # 1 to 3 days late
        "mean_delay": 2.0,
        "std_delay": 1.2,
    },
]


def get_upcoming_friday(base_date: datetime) -> datetime:
    """Calculates the upcoming Friday at 17:00 UTC."""
    days_ahead = 4 - base_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (base_date + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)


def reset_database_schema(confirm: bool = False):
    """
    Destructive operation: drops all tables and re-initializes schema via Alembic.
    Strictly forbidden in production (when DEV_MODE is False).
    Requires explicit confirmation flag.
    """
    if not settings.DEV_MODE:
        raise RuntimeError(
            "CRITICAL SAFETY VIOLATION: Database reset is strictly forbidden when DEV_MODE is False."
        )
    if not confirm:
        raise RuntimeError(
            "CRITICAL SAFETY VIOLATION: Database reset requires explicit confirmation (confirm=True)."
        )

    db_url = str(settings.DATABASE_URL).lower()
    if any(prod_indicator in db_url for prod_indicator in ["prod", "production", "live", "rds.amazonaws.com"]):
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Database URL appears to be a production database ({settings.DATABASE_URL}). Reset aborted."
        )

    print("Cleaning existing database data and refreshing tables...")
    with engine.connect() as conn:
        from sqlalchemy import text
        try:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version;"))
            conn.commit()
        except Exception:
            pass
    Base.metadata.drop_all(bind=engine)
    print("Initializing database tables...")
    init_db()


def seed_demo_scenario(db: Session, target_owner: Optional[Owner] = None) -> Owner:
    """
    Dedicated non-destructive demo scenario seeding function.
    Safely seeds the Alex Morgan hackathon demo scenario (clients, historical invoices, open invoices,
    contractor obligation, opening balance, and audit genesis block) into an existing database session.

    NEVER drops tables, NEVER deletes existing user accounts, and NEVER touches non-demo users.
    Scoped strictly to the identified demo owner. Idempotent across multiple runs.
    """
    if target_owner is not None:
        if not target_owner.is_demo:
            raise ValueError("Safety violation: Refusing to seed demo data into a real (non-demo) user account.")
        owner = target_owner
    else:
        owner = db.query(Owner).filter(Owner.email == CANONICAL_DEMO_EMAIL).first()
        if owner:
            if not owner.is_demo:
                raise ValueError(
                    f"Safety violation: Account with email '{CANONICAL_DEMO_EMAIL}' exists but is not a demo account. "
                    "Refusing to overwrite or convert real user account."
                )
        else:
            print(f"Creating dedicated demo owner: {CANONICAL_DEMO_EMAIL}...")
            owner = Owner(
                name="Alex Morgan",
                email=CANONICAL_DEMO_EMAIL,
                hashed_password=hash_password("DemoAlex2026!"),
                currency="USD",
                timezone="UTC",
                is_demo=True,
                is_active=True,
                email_verified=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=365)
            )
            db.add(owner)
            db.flush()

    # PayPal Sandbox Connection record
    conn = db.query(PayPalConnection).filter(PayPalConnection.owner_id == owner.id).first()
    if not conn:
        conn = PayPalConnection(
            owner_id=owner.id,
            environment="sandbox",
            status="connected",
            client_id_preview="sb-client-id-demo-8428",
            last_checked_at=datetime.now(timezone.utc)
        )
        db.add(conn)

    # Create or update clients & 12 months historical payments
    random.seed(42)  # Deterministic seed for reproducible hackathon demo
    now = datetime.now(timezone.utc)
    created_clients = []

    for p in CLIENT_PROFILES:
        client = db.query(Client).filter(
            Client.owner_id == owner.id,
            Client.email == p["email"]
        ).first()
        if not client:
            client = Client(
                owner_id=owner.id,
                name=p["name"],
                email=p["email"],
                country=p["country"],
                typical_invoice_amount=p["typical_invoice_amount"],
                relationship_weight=p["relationship_weight"],
                is_seeded=True,
                created_at=now - timedelta(days=365)
            )
            db.add(client)
            db.flush()
        created_clients.append((client, p))

        # Ensure no leftover test transactions pollute demo history
        db.query(PaymentHistory).filter(
            PaymentHistory.client_id == client.id,
            PaymentHistory.source != "seeded"
        ).delete()

        # Check if client has history
        existing_hist = db.query(PaymentHistory).filter(PaymentHistory.client_id == client.id).count()
        if existing_hist == 0:
            for m in range(12, 0, -1):
                due_date = now - timedelta(days=m * 30)
                delay = int(round(random.gauss(p["mean_delay"], p["std_delay"])))
                if p["behavior"] == "chronically_late":
                    delay = max(delay, 9)
                elif p["behavior"] == "on_time":
                    delay = max(min(delay, 1), 0)

                paid_date = due_date + timedelta(days=delay)
                amount_variation = round(p["typical_invoice_amount"] * random.uniform(0.9, 1.1), 2)

                inv_id = f"INV2-HIST-{owner.id}-{client.id}-{m:02d}"
                hist_inv = db.query(Invoice).filter(
                    Invoice.client_id == client.id,
                    Invoice.paypal_invoice_id == inv_id
                ).first()
                if not hist_inv:
                    hist_inv = Invoice(
                        paypal_invoice_id=inv_id,
                        client_id=client.id,
                        amount=amount_variation,
                        currency="USD",
                        issue_date=due_date - timedelta(days=20),
                        due_date=due_date,
                        paid_date=paid_date,
                        status="PAID",
                        discount_applied=0.0,
                        pay_link=f"https://www.sandbox.paypal.com/invoice/p/#{inv_id}"
                    )
                    db.add(hist_inv)
                    db.flush()

                history_record = db.query(PaymentHistory).filter(
                    PaymentHistory.client_id == client.id,
                    PaymentHistory.invoice_id == hist_inv.id
                ).first()
                if not history_record:
                    history_record = PaymentHistory(
                        client_id=client.id,
                        invoice_id=hist_inv.id,
                        amount=amount_variation,
                        due_date=due_date,
                        paid_date=paid_date,
                        days_late=delay,
                        source="seeded"
                    )
                    db.add(history_record)

    due_friday = get_upcoming_friday(now)

    open_invoices_data = [
        {
            "client_index": 0,  # Apex Design Studio
            "amount": 2000.0,
            "due_date": due_friday - timedelta(days=2),
            "issue_days_ago": 18,
            "paypal_id": "INV2-DEMO-APEX-001"
        },
        {
            "client_index": 2,  # Nordic Data Labs
            "amount": 1500.0,
            "due_date": due_friday - timedelta(days=1),
            "issue_days_ago": 14,
            "paypal_id": "INV2-DEMO-NORDIC-002"
        },
        {
            "client_index": 1,  # Vertex Software
            "amount": 1000.0,
            "due_date": due_friday + timedelta(days=4),
            "issue_days_ago": 10,
            "paypal_id": "INV2-DEMO-VERTEX-003"
        }
    ]

    for inv_info in open_invoices_data:
        c = created_clients[inv_info["client_index"]][0]
        paypal_id = inv_info["paypal_id"] if owner.email == CANONICAL_DEMO_EMAIL else f"{inv_info['paypal_id']}-{owner.id}"
        
        existing_by_paypal = db.query(Invoice).filter(Invoice.paypal_invoice_id == paypal_id).first()
        if existing_by_paypal:
            existing_open = existing_by_paypal
            existing_open.client_id = c.id
        else:
            existing_open = db.query(Invoice).filter(
                Invoice.client_id == c.id,
                Invoice.status.in_(["SENT", "DRAFT"])
            ).first()

        if existing_open:
            existing_open.paypal_invoice_id = paypal_id
            existing_open.invoice_number = f"INV-DEMO-{inv_info['client_index']+1:03d}"
            existing_open.amount = inv_info["amount"]
            existing_open.due_date = inv_info["due_date"]
            existing_open.status = "SENT"
            existing_open.paid_date = None
            existing_open.is_seeded = True
            existing_open.is_simulated_paid = False
            existing_open.provider_status = "SENT"
            existing_open.discount_applied = 0.0
            existing_open.pay_link = f"https://www.sandbox.paypal.com/invoice/p/#{paypal_id}"
            db.query(PaymentHistory).filter(PaymentHistory.invoice_id == existing_open.id).delete()
            target_id = existing_open.id
        else:
            open_inv = Invoice(
                paypal_invoice_id=paypal_id,
                invoice_number=f"INV-DEMO-{inv_info['client_index']+1:03d}",
                client_id=c.id,
                amount=inv_info["amount"],
                currency="USD",
                issue_date=now - timedelta(days=inv_info["issue_days_ago"]),
                due_date=inv_info["due_date"],
                paid_date=None,
                status="SENT",
                discount_applied=0.0,
                pay_link=f"https://www.sandbox.paypal.com/invoice/p/#{paypal_id}",
                is_seeded=True,
                provider_status="SENT"
            )
            db.add(open_inv)
            db.flush()
            target_id = open_inv.id

        # Clean up any extraneous open invoice for this client or matching paypal_id to prevent duplicates / UNIQUE constraint errors
        duplicates = db.query(Invoice).filter(
            Invoice.id != target_id,
            Invoice.status.in_(["SENT", "DRAFT"]),
            (Invoice.client_id == c.id) | (Invoice.paypal_invoice_id == paypal_id)
        ).all()
        for dup in duplicates:
            db.query(PaymentHistory).filter(PaymentHistory.invoice_id == dup.id).delete()
            db.delete(dup)
        db.flush()

    contractor_obligation = db.query(Obligation).filter(
        Obligation.owner_id == owner.id,
        Obligation.payee_email == "marcus.contractor@example.com"
    ).first()
    if not contractor_obligation:
        contractor_obligation = Obligation(
            owner_id=owner.id,
            payee_name="Marcus Sterling",
            payee_email="marcus.contractor@example.com",
            amount=3200.0,
            currency="USD",
            due_date=due_friday,
            split_allowed=True,
            split_consent_recorded=True,
            split_consent_source="written_email_agreement",
            split_consent_timestamp=now,
            split_consent_is_simulated=True,
            status="pending",
            is_demo=True
        )
        db.add(contractor_obligation)
    else:
        contractor_obligation.amount = 3200.0
        contractor_obligation.due_date = due_friday
        contractor_obligation.split_allowed = True
        contractor_obligation.split_consent_recorded = True
        contractor_obligation.split_consent_source = "written_email_agreement"
        contractor_obligation.split_consent_timestamp = now
        contractor_obligation.split_consent_is_simulated = True
        contractor_obligation.status = "pending"
        contractor_obligation.is_demo = True

    # Clean up any extraneous obligations for this demo persona so Marcus Sterling is the single obligation
    extra_obls = db.query(Obligation).filter(
        Obligation.owner_id == owner.id,
        Obligation.payee_email != "marcus.contractor@example.com"
    ).all()
    for extra in extra_obls:
        db.delete(extra)

    opening_ref = "OPENING-BAL-001" if owner.email == CANONICAL_DEMO_EMAIL else f"OPENING-BAL-{owner.id}"
    opening_entry = db.query(FinancialEntry).filter(
        FinancialEntry.owner_id == owner.id,
        FinancialEntry.entry_type == "opening_balance",
        FinancialEntry.is_demo == True
    ).first()
    if not opening_entry:
        opening_entry = FinancialEntry(
            owner_id=owner.id,
            title="PayPal Working Balance",
            amount=1800.0,
            currency="USD",
            entry_type="opening_balance",
            category="opening_balance",
            recurrence="one_time",
            transaction_date=now - timedelta(days=1),
            status="confirmed",
            data_source="paypal",
            reference_id=opening_ref,
            notes="Starting verified sandbox PayPal account balance",
            is_demo=True
        )
        db.add(opening_entry)
    else:
        opening_entry.amount = 1800.0
        opening_entry.status = "confirmed"

    # Reset any leftover ledger transactions for demo owner so baseline cash balance is strictly $1,800
    db.query(FinancialEntry).filter(
        FinancialEntry.owner_id == owner.id,
        FinancialEntry.entry_type != "opening_balance"
    ).delete()
    db.flush()

    existing_audit = db.query(AuditLog).filter(
        AuditLog.owner_id == owner.id,
        AuditLog.event == "GENESIS_INITIALIZED"
    ).first()
    if not existing_audit:
        genesis_payload = {
            "message": "Genesis Block - Cashflow Lifeline Audit Chain Initialized",
            "environment": "sandbox",
            "owner": owner.email
        }
        genesis_hash = compute_hash(GENESIS_HASH, now, "system", "GENESIS_INITIALIZED", genesis_payload)
        audit_genesis = AuditLog(
            owner_id=owner.id,
            ts=now,
            actor="system",
            event="GENESIS_INITIALIZED",
            payload=genesis_payload,
            prev_hash=GENESIS_HASH,
            hash=genesis_hash
        )
        db.add(audit_genesis)

    db.commit()

    # Automatically provision fresh live PayPal Sandbox invoices so they are immediately payable
    if settings.PAYPAL_CLIENT_ID and "placeholder" not in settings.PAYPAL_CLIENT_ID.lower() and "your_paypal" not in settings.PAYPAL_CLIENT_ID.lower():
        try:
            import asyncio
            from backend.app.services.paypal_invoice_service import provision_sandbox_invoices
            asyncio.run(provision_sandbox_invoices(db=db, owner_id=owner.id))
            print("Successfully provisioned fresh live PayPal Sandbox invoices with payer links!")
        except Exception as e:
            print(f"Note: Live sandbox invoice provisioning skipped: {e}")

    print("Successfully seeded Cashflow Lifeline demo scenario!")
    print(f"- Owner: {owner.name} ({owner.email}) [ID={owner.id}]")
    print(f"- Clients verified/created: {len(created_clients)} with payment history")
    print("- Contractor Obligation: Marcus Sterling ($3200 due on Friday)")
    print("- Initial PayPal Balance: $1,800")
    return owner


def seed_database(
    clean: bool = False,
    demo_mode: bool = True,
    db: Optional[Session] = None,
    target_owner: Optional[Owner] = None,
    confirm_clean: bool = False
) -> Owner:
    """
    Top-level seeding entry point for CLI and tests.
    If a Session is passed as the first positional argument (e.g. seed_database(db)),
    it is detected and clean is guaranteed to be set to False to prevent table deletion.
    """
    if isinstance(clean, Session):
        db = clean
        clean = False

    if clean:
        if not settings.DEV_MODE:
            raise RuntimeError("Database reset is strictly forbidden when DEV_MODE is False.")
        reset_database_schema(confirm=True)

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        return seed_demo_scenario(db=db, target_owner=target_owner)
    except Exception as e:
        db.rollback()
        raise e
    finally:
        if close_session:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed database for Cashflow Lifeline demo.")
    parser.add_argument("--clean", action="store_true", help="Clean all data before seeding (requires --confirm-destructive-reset)")
    parser.add_argument("--confirm-destructive-reset", action="store_true", help="Explicit confirmation required to drop database tables")
    parser.add_argument("--demo-mode", action="store_true", default=True, help="Set up clean 3-minute demo scenario")
    args = parser.parse_args()

    if args.clean:
        if not args.confirm_destructive_reset:
            print("ERROR: Destructive database reset requires the explicit --confirm-destructive-reset flag.")
            sys.exit(1)
        reset_database_schema(confirm=True)

    seed_database(clean=False, demo_mode=args.demo_mode)
