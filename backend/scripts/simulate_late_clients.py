import argparse
from datetime import datetime, timedelta
from backend.app.db import SessionLocal
from backend.app.models import Client, Invoice, Obligation


def simulate_late_scenario(days_delay: int = 5, client_names: list = None):
    """
    Simulates late payment from key clients by adjusting open invoice expected dates
    or historical delay parameters.
    """
    db = SessionLocal()
    try:
        query = db.query(Invoice).filter(Invoice.status == "SENT")
        if client_names:
            query = query.join(Client).filter(Client.name.in_(client_names))

        invoices = query.all()
        print(f"Applying +{days_delay} days delay simulation to {len(invoices)} open invoice(s)...")
        for inv in invoices:
            old_due = inv.due_date
            inv.due_date = old_due + timedelta(days=days_delay)
            print(f"  Invoice {inv.paypal_invoice_id} ({inv.client.name}): ${inv.amount} shifted from {old_due.strftime('%Y-%m-%d')} to {inv.due_date.strftime('%Y-%m-%d')}")

        db.commit()
        print("Simulation applied successfully. Re-run forecast to observe shortfall impact.")
    except Exception as e:
        db.rollback()
        print(f"Simulation failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate late payment shifts for open client invoices.")
    parser.add_argument("--days", type=int, default=5, help="Number of days to shift invoices later (default 5)")
    parser.add_argument("--clients", nargs="+", default=None, help="Specific client names to delay")
    args = parser.parse_args()
    simulate_late_scenario(args.days, args.clients)

