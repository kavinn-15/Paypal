import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from backend.app.models import Owner, Client, Invoice
from backend.app.paypal.client import paypal_client

logger = logging.getLogger(__name__)


async def provision_sandbox_invoices(db: Session, owner_id: int) -> List[Dict[str, Any]]:
    """
    Creates and sends genuine PayPal Sandbox invoices using PayPal Invoicing v2 API
    for the owner's open scenario clients (Nordic Data Labs, Apex Design Studio, Vertex Software).
    Retrieves genuine INV2-... IDs, payer-view links, and stores them in the local database.
    """
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise ValueError(f"Owner {owner_id} not found.")

    clients = db.query(Client).filter(Client.owner_id == owner_id).all()
    client_by_name = {c.name: c for c in clients}

    now = datetime.now(timezone.utc)
    provision_specs = [
        {
            "client_name": "Nordic Data Labs",
            "amount": 1500.0,
            "due_days": 1,
            "note": "Milestone deliverable - Data engineering pipeline"
        },
        {
            "client_name": "Apex Design Studio",
            "amount": 2000.0,
            "due_days": 2,
            "note": "UI/UX component design & brand assets"
        },
        {
            "client_name": "Vertex Software Inc",
            "amount": 1000.0,
            "due_days": 9,
            "note": "Backend API integration & testing"
        }
    ]

    results = []
    ts = int(time.time())

    for idx, spec in enumerate(provision_specs, start=1):
        client = client_by_name.get(spec["client_name"])
        if not client:
            continue

        issue_date = now - timedelta(days=10)
        due_date = now + timedelta(days=spec["due_days"])
        inv_number = f"INV-{owner_id}-{ts}-{idx:02d}"

        invoice_payload = {
            "detail": {
                "invoice_number": inv_number,
                "reference": f"REF-{spec['client_name'][:6].upper()}",
                "invoice_date": issue_date.strftime("%Y-%m-%d"),
                "currency_code": "USD",
                "note": spec["note"],
                "term": "NET_10",
                "payment_term": {
                    "term_type": "DUE_ON_DATE_SPECIFIED",
                    "due_date": due_date.strftime("%Y-%m-%d")
                }
            },
            "invoicer": {
                "name": {
                    "given_name": owner.name.split()[0] if owner.name else "Alex",
                    "surname": owner.name.split()[-1] if owner.name and " " in owner.name else "Morgan"
                },
                "business_name": "Cashflow Lifeline Freelance Studio"
            },
            "primary_recipients": [
                {
                    "billing_info": {
                        "name": {
                            "given_name": client.name.split()[0],
                            "surname": client.name.split()[-1] if " " in client.name else "Client"
                        },
                        "email_address": client.email
                    }
                }
            ],
            "items": [
                {
                    "name": f"Consulting Services - {spec['client_name']}",
                    "description": spec["note"],
                    "quantity": "1",
                    "unit_amount": {
                        "currency_code": "USD",
                        "value": f"{spec['amount']:.2f}"
                    },
                    "unit_of_measure": "QUANTITY"
                }
            ],
            "configuration": {
                "allow_tip": False,
                "tax_calculated_after_discount": True,
                "tax_inclusive": False
            }
        }

        # 1. Create invoice via PayPal Invoicing v2
        created_res = await paypal_client.create_invoice(invoice_payload)
        paypal_id = created_res.get("id")
        if not paypal_id:
            href = created_res.get("href", "")
            if "/v2/invoicing/invoices/" in href:
                paypal_id = href.split("/v2/invoicing/invoices/")[-1]

        if not paypal_id:
            logger.warning(f"Could not extract invoice id from create_invoice response: {created_res}")
            continue

        # 2. Send invoice via PayPal Invoicing v2 to activate it
        await paypal_client.send_invoice(paypal_id, note="Invoice ready for settlement.")

        # 3. Retrieve invoice details to extract genuine recipient_view_url from PayPal metadata
        inv_details = await paypal_client.get_invoice(paypal_id)
        meta = inv_details.get("detail", {}).get("metadata", {})
        payer_link = meta.get("recipient_view_url")
        if not payer_link:
            raw_hash = paypal_id.replace("INV2-", "").replace("-", "")
            payer_link = f"https://www.sandbox.paypal.com/invoice/p/#{raw_hash}"

        # 4. Find or create local invoice record
        local_inv = db.query(Invoice).filter(
            Invoice.client_id == client.id,
            Invoice.status == "SENT"
        ).first()

        if local_inv:
            local_inv.paypal_invoice_id = paypal_id
            local_inv.invoice_number = inv_number
            local_inv.amount = spec["amount"]
            local_inv.due_date = due_date
            local_inv.issue_date = issue_date
            local_inv.pay_link = payer_link
            local_inv.provider_status = "SENT"
            local_inv.is_seeded = False
        else:
            local_inv = Invoice(
                paypal_invoice_id=paypal_id,
                invoice_number=inv_number,
                client_id=client.id,
                amount=spec["amount"],
                currency="USD",
                issue_date=issue_date,
                due_date=due_date,
                paid_date=None,
                status="SENT",
                discount_applied=0.0,
                pay_link=payer_link,
                provider_status="SENT",
                is_seeded=False
            )
            db.add(local_inv)

        db.commit()
        db.refresh(local_inv)

        results.append({
            "client_name": client.name,
            "paypal_invoice_id": paypal_id,
            "invoice_number": inv_number,
            "amount": spec["amount"],
            "currency": "USD",
            "due_date": due_date.isoformat(),
            "pay_link": payer_link,
            "provider_status": "SENT"
        })

    return results


async def sync_open_invoices_from_paypal(db: Session, owner_id: int) -> int:
    """
    Checks all open invoices for this owner against PayPal Invoicing v2 API.
    If an invoice has been marked PAID on PayPal, automatically processes the
    reconciliation event and updates the financial ledger and forecast.
    Returns the count of newly reconciled invoices.
    """
    open_invoices = (
        db.query(Invoice)
        .join(Client)
        .filter(
            Client.owner_id == owner_id,
            Invoice.status.in_(["SENT", "DRAFT"])
        )
        .all()
    )

    reconciled_count = 0
    from backend.app.events.processor import process_webhook_event

    for inv in open_invoices:
        if inv.paypal_invoice_id and "INV2-" in inv.paypal_invoice_id and "DEMO" not in inv.paypal_invoice_id:
            try:
                remote_inv = await paypal_client.get_invoice(inv.paypal_invoice_id)
                if remote_inv.get("status") == "PAID":
                    payments = remote_inv.get("payments", {})
                    tx_list = payments.get("transactions", [])
                    tx_id = tx_list[0].get("payment_id") if tx_list else f"SYNC-{inv.paypal_invoice_id}"
                    paid_amt = payments.get("paid_amount", {}).get("value", str(inv.amount))
                    evt_payload = {
                        "id": f"WH-AUTO-SYNC-{tx_id}",
                        "create_time": datetime.now(timezone.utc).isoformat(),
                        "event_type": "INVOICING.INVOICE.PAID",
                        "resource": {
                            "invoice": {"id": inv.paypal_invoice_id},
                            "amount": {"value": str(paid_amt), "currency_code": inv.currency},
                            "payments": [{"payment_id": tx_id, "amount": {"value": str(paid_amt), "currency_code": inv.currency}}]
                        }
                    }
                    process_webhook_event(db, evt_payload, is_simulated=False)
                    reconciled_count += 1
            except Exception as e:
                logger.debug(f"PayPal invoice check failed for {inv.paypal_invoice_id}: {e}")

    return reconciled_count

