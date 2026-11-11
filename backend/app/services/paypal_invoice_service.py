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
                "email_address": owner.email,
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

        # 2. Send invoice via PayPal Invoicing v2 to generate payer-view link
        await paypal_client.send_invoice(paypal_id, note="Invoice ready for settlement.")

        # 3. Retrieve invoice details to extract genuine payer-view link
        inv_details = await paypal_client.get_invoice(paypal_id)
        links = inv_details.get("links", [])
        payer_link = next((l["href"] for l in links if l.get("rel") == "payer-view"), None)
        if not payer_link:
            payer_link = f"https://www.sandbox.paypal.com/invoice/p/#{paypal_id}"

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

