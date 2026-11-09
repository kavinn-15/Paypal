import sys
import argparse
import random
from datetime import datetime, timedelta, timezone
from backend.app.db import engine, SessionLocal, init_db, Base
from backend.app.models import (
    Owner, PayPalConnection, Client, Invoice, PaymentHistory, Obligation,
    AuditLog, Forecast, RescuePlan, Action, ClientPrediction, WebhookEvent, Message, FinancialEntry
)
from backend.app.guardrail.audit import compute_hash, GENESIS_HASH
from backend.app.auth.security import hash_password


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


def seed_database(clean: bool = False, demo_mode: bool = True):
    if clean:
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
    db = SessionLocal()

    try:
        # Select dedicated demo owner (Alex Morgan) rather than modifying the first registered user
        owner = db.query(Owner).filter(
            (Owner.email == "alex.morgan.freelance@example.com") | (Owner.is_demo == True)
        ).first()

        if not owner:
            print("Creating dedicated demo owner: Alex Morgan...")
            owner = Owner(
                name="Alex Morgan",
                email="alex.morgan.freelance@example.com",
                hashed_password=hash_password("DemoAlex2026!"),
                currency="USD",
                timezone="UTC",
                is_demo=True,
                is_active=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=365)
            )
            db.add(owner)
            db.flush()
        else:
            # Ensure dedicated demo owner is marked as demo
            owner.is_demo = True
            db.flush()

        # PayPal Sandbox Connection record
        conn = db.query(PayPalConnection).filter_by(owner_id=owner.id).first()
        if not conn:
            print("Creating PayPal Sandbox connection...")
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
            client = db.query(Client).filter_by(email=p["email"]).first()
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

            # Check if client has history
            existing_hist = db.query(PaymentHistory).filter_by(client_id=client.id).count()
            if existing_hist == 0:
                # Generate 12 historical monthly payments
                for m in range(12, 0, -1):
                    due_date = now - timedelta(days=m * 30)
                    delay = int(round(random.gauss(p["mean_delay"], p["std_delay"])))
                    if p["behavior"] == "chronically_late":
                        delay = max(delay, 9)
                    elif p["behavior"] == "on_time":
                        delay = max(min(delay, 1), 0)

                    paid_date = due_date + timedelta(days=delay)
                    amount_variation = round(p["typical_invoice_amount"] * random.uniform(0.9, 1.1), 2)

                    # Create past invoice
                    inv_id = f"INV2-HIST-{client.id}-{m:02d}-{int(now.timestamp()) % 10000}"
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

                    history_record = PaymentHistory(
                        client_id=client.id,
                        invoice_id=hist_inv.id,
                        amount=amount_variation,
                        due_date=due_date,
                        paid_date=paid_date,
                        days_late=delay,
                        source="seeded"  # Visibly marked as seeded
                    )
                    db.add(history_record)

        # Open invoices currently awaiting payment (Demo Scenario)
        # Friday obligation is in 5 days.
        # Alex has $1,800 in PayPal balance.
        # Alex owes contractor Marcus Sterling $3,200 due on Friday (5 days from now).
        # Apex Design ($2,000) has an open invoice due in 2 days, but they are chronically 14 days late!
        # Nordic Data Labs ($1,500) has an open invoice due in 1 day, with variable 6-day delay.
        # Vertex Software ($1,000) has an open invoice due in 9 days.

        open_invoices_data = [
            {
                "client_index": 0,  # Apex Design Studio
                "amount": 2000.0,
                "due_in_days": 2,
                "issue_days_ago": 18,
                "paypal_id": "INV2-DEMO-APEX-001"
            },
            {
                "client_index": 2,  # Nordic Data Labs
                "amount": 1500.0,
                "due_in_days": 1,
                "issue_days_ago": 14,
                "paypal_id": "INV2-DEMO-NORDIC-002"
            },
            {
                "client_index": 1,  # Vertex Software
                "amount": 1000.0,
                "due_in_days": 9,
                "issue_days_ago": 10,
                "paypal_id": "INV2-DEMO-VERTEX-003"
            }
        ]

        for inv_info in open_invoices_data:
            c = created_clients[inv_info["client_index"]][0]
            existing_open = db.query(Invoice).filter_by(paypal_invoice_id=inv_info["paypal_id"]).first()
            if not existing_open:
                open_inv = Invoice(
                    paypal_invoice_id=inv_info["paypal_id"],
                    client_id=c.id,
                    amount=inv_info["amount"],
                    currency="USD",
                    issue_date=now - timedelta(days=inv_info["issue_days_ago"]),
                    due_date=now + timedelta(days=inv_info["due_in_days"]),
                    paid_date=None,
                    status="SENT",
                    discount_applied=0.0,
                    pay_link=f"https://www.sandbox.paypal.com/invoice/p/#{inv_info['paypal_id']}"
                )
                db.add(open_inv)

        # Obligation: Marcus Sterling (Lead Backend Contractor)
        contractor_obligation = db.query(Obligation).filter_by(payee_email="marcus.contractor@example.com").first()
        due_friday = now + timedelta(days=5)  # Upcoming Friday
        if not contractor_obligation:
            print("Creating contractor obligation: Marcus Sterling ($3,200 due in 5 days)...")
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
                status="pending"
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

        # Opening confirmed cash balance entry ($1,800.00)
        opening_entry = db.query(FinancialEntry).filter_by(reference_id="OPENING-BAL-001").first()
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
                reference_id="OPENING-BAL-001",
                notes="Starting verified sandbox PayPal account balance",
                is_demo=True
            )
            db.add(opening_entry)

        # Initialize Audit Log Genesis Block if empty
        existing_audit = db.query(AuditLog).first()
        if not existing_audit:
            genesis_payload = {
                "message": "Genesis Block - Cashflow Lifeline Audit Chain Initialized",
                "environment": "sandbox",
                "owner": owner.email
            }
            genesis_hash = compute_hash(GENESIS_HASH, now, "system", "GENESIS_INITIALIZED", genesis_payload)
            audit_genesis = AuditLog(
                ts=now,
                actor="system",
                event="GENESIS_INITIALIZED",
                payload=genesis_payload,
                prev_hash=GENESIS_HASH,
                hash=genesis_hash
            )
            db.add(audit_genesis)

        db.commit()
        print("Successfully seeded Cashflow Lifeline database!")
        print(f"- Owner: {owner.name} ({owner.email})")
        print(f"- Clients created: {len(created_clients)} with 12-month payment history (labeled 'seeded')")
        print(f"- Open Invoices: Apex ($2000, due in 2d), Nordic ($1500, due in 1d), Vertex ($1000, due in 9d)")
        print(f"- Contractor Obligation: Marcus Sterling ($3200 due on Friday, split allowed: True)")
        print(f"- Initial PayPal Balance: $1,800 (Reveals $1,400 projected shortfall before contractor payout)")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed database for Cashflow Lifeline demo.")
    parser.add_argument("--clean", action="store_true", help="Clean all data before seeding")
    parser.add_argument("--demo-mode", action="store_true", default=True, help="Set up clean 3-minute demo scenario")
    args = parser.parse_args()
    seed_database(clean=args.clean, demo_mode=args.demo_mode)

