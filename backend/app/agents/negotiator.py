import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models import Owner, Client, Obligation, Invoice, NegotiationDraft
from backend.app.schemas import NegotiationGenerateRequest, NegotiationDraftOut, NegotiationTonesResponse
from backend.app.llm.client import llm_service
from backend.app.services.region_service import CURRENCIES_DB


class NegotiationAgent:
    """
    Dedicated Financial Negotiation Agent:
    - Analyzes payment timing conflicts between clients and payees.
    - Calculates economically bounded parameters (e.g. 3% early-pay discount or 50% contractor split).
    - Drafts personalized messages across 3 distinct tone styles:
        1. Professional (standard business etiquette)
        2. Friendly (relationship-first collaborative)
        3. Urgent but Respectful (critical deadline focus)
    - Enforces human-in-the-loop review before any communication is sent.
    """

    def __init__(self, db: Session):
        self.db = db

    def generate_options(
        self,
        owner: Owner,
        req: NegotiationGenerateRequest
    ) -> NegotiationTonesResponse:
        now = datetime.datetime.utcnow()

        if req.target_type == "client_discount":
            client = None
            if req.client_id:
                client = self.db.query(Client).filter(
                    Client.id == req.client_id,
                    Client.owner_id == owner.id
                ).first()
                if not client:
                    raise ValueError(f"Client with id {req.client_id} not found or does not belong to owner.")
            if not client:
                client = self.db.query(Client).filter(Client.owner_id == owner.id).first()

            if not client:
                raise ValueError("No eligible client found for early-payment negotiation.")

            # Find client's open invoice
            open_inv = self.db.query(Invoice).filter(
                Invoice.client_id == client.id,
                Invoice.status.in_(["SENT", "DRAFT"])
            ).first()

            inv_amt = float(open_inv.amount) if open_inv else float(client.typical_invoice_amount)
            inv_ref = open_inv.paypal_invoice_id if open_inv else "INV-CURRENT"
            inv_due = open_inv.due_date.strftime("%B %d, %Y") if open_inv else "upcoming"
            inv_curr = open_inv.currency if open_inv and open_inv.currency else (owner.preferred_currency or owner.currency or "USD")
            curr_sym = CURRENCIES_DB.get(inv_curr, {}).get("symbol", "$")
            discount_pct = req.discount_pct or 3.0
            discount_val = inv_amt * (discount_pct / 100.0)
            net_amt = inv_amt - discount_val

            # Draft 3 Tone Styles
            tones = [
                {
                    "tone": "professional",
                    "subject": f"Early Settlement Courtesy: {discount_pct:.0f}% Discount on Invoice #{inv_ref}",
                    "body": (
                        f"Hi {client.name.split()[0]},\n\n"
                        f"I hope you are having a productive week. Regarding Invoice #{inv_ref} ({curr_sym}{inv_amt:,.2f}), "
                        f"we are offering our select partners an expedited settlement courtesy of {discount_pct:.1f}% "
                        f"({curr_sym}{discount_val:,.2f} credit), bringing your balance to {curr_sym}{net_amt:,.2f} if settled within 48 hours.\n\n"
                        f"Your updated PayPal payment link is active on your portal: {open_inv.pay_link if open_inv and open_inv.pay_link else 'https://www.sandbox.paypal.com/invoice/p/#demo'}.\n\n"
                        f"Thank you for your ongoing partnership.\n\n"
                        f"Best regards,\n{owner.name}"
                    )
                },
                {
                    "tone": "friendly",
                    "subject": f"Quick note + {discount_pct:.0f}% early payment credit for {client.name.split()[0]}!",
                    "body": (
                        f"Hey {client.name.split()[0]}!\n\n"
                        f"Hope all is well with you. As we wrap up the current project milestones, I wanted to pass along "
                        f"a quick appreciation perk: we're applying a {discount_pct:.1f}% early-settlement incentive "
                        f"to Invoice #{inv_ref}. If you're able to process it this week via PayPal, you save {curr_sym}{discount_val:,.2f}!\n\n"
                        f"No pressure at all if normal terms work better for your billing cycle, but wanted to extend the option.\n\n"
                        f"Warmly,\n{owner.name}"
                    )
                },
                {
                    "tone": "urgent_respectful",
                    "subject": f"Time-Sensitive: Expedited Payment Incentive for Invoice #{inv_ref}",
                    "body": (
                        f"Dear {client.name},\n\n"
                        f"We are conducting our mid-month financial reconciliation and would greatly appreciate "
                        f"accelerating Invoice #{inv_ref} ({curr_sym}{inv_amt:,.2f}). To facilitate prompt processing before Friday, "
                        f"we have authorized a direct {discount_pct:.1f}% discount ({curr_sym}{discount_val:,.2f}), making the immediate "
                        f"settlement total {curr_sym}{net_amt:,.2f}.\n\n"
                        f"If your accounting team can remit payment within 48 hours via our PayPal link, this discount will be permanently applied.\n\n"
                        f"Thank you for your prompt assistance.\n\n"
                        f"Sincerely,\n{owner.name}"
                    )
                }
            ]

            saved_drafts = []
            for t in tones:
                draft = NegotiationDraft(
                    owner_id=owner.id,
                    client_id=client.id,
                    target_type="client_discount",
                    recipient_name=client.name,
                    recipient_email=client.email,
                    tone=t["tone"],
                    subject=t["subject"],
                    body=t["body"],
                    offered_incentive=f"{discount_pct:.1f}% discount ({curr_sym}{discount_val:,.2f})",
                    estimated_benefit=f"Accelerates {curr_sym}{net_amt:,.2f} cash inflow before Friday",
                    status="draft"
                )
                self.db.add(draft)
                self.db.commit()
                self.db.refresh(draft)
                saved_drafts.append(NegotiationDraftOut.model_validate(draft))

            return NegotiationTonesResponse(
                recipient_name=client.name,
                recipient_email=client.email,
                target_type="client_discount",
                context_summary=f"Offering {discount_pct:.1f}% concession ({curr_sym}{discount_val:,.2f}) to accelerate {curr_sym}{net_amt:,.2f} cash inflow",
                options=saved_drafts
            )

        else:
            # contractor_split
            obligation = None
            if req.obligation_id:
                obligation = self.db.query(Obligation).filter(
                    Obligation.id == req.obligation_id,
                    Obligation.owner_id == owner.id
                ).first()
                if not obligation:
                    raise ValueError(f"Obligation with id {req.obligation_id} not found or does not belong to owner.")
            if not obligation:
                obligation = self.db.query(Obligation).filter(Obligation.owner_id == owner.id).first()

            if not obligation:
                raise ValueError("No active contractor obligation found for split negotiation.")

            split_pct = req.split_pct or 50.0
            p1_amt = float(obligation.amount) * (split_pct / 100.0)
            p2_amt = float(obligation.amount) - p1_amt
            payee_first = obligation.payee_name.split()[0]
            ob_curr = obligation.currency if obligation and obligation.currency else (owner.preferred_currency or owner.currency or "USD")
            curr_sym = CURRENCIES_DB.get(ob_curr, {}).get("symbol", "$")

            tones = [
                {
                    "tone": "professional",
                    "subject": f"Payment Schedule Proposal: {obligation.payee_name} Milestone Payout",
                    "body": (
                        f"Hi {payee_first},\n\n"
                        f"Regarding your upcoming invoice of {curr_sym}{obligation.amount:,.2f} due on {obligation.due_date.strftime('%B %d')}, "
                        f"we would like to propose releasing this payment in two equal installments: {curr_sym}{p1_amt:,.2f} on Friday, "
                        f"followed by the remaining {curr_sym}{p2_amt:,.2f} in 14 days.\n\n"
                        f"This allows us to maintain alignment with our client clearance cycles while guaranteeing your scheduled transfer. "
                        f"Please let me know if this schedule works for you.\n\n"
                        f"Best regards,\n{owner.name}"
                    )
                },
                {
                    "tone": "friendly",
                    "subject": f"Quick check on Friday payout schedule ({payee_first})",
                    "body": (
                        f"Hey {payee_first},\n\n"
                        f"Incredible work on the recent deliverables! Quick heads-up regarding Friday's payout ({curr_sym}{obligation.amount:,.2f}): "
                        f"due to a slight overseas client clearance delay, would you be open to a 2-part schedule? We'll send {curr_sym}{p1_amt:,.2f} "
                        f"promptly on Friday, and the remaining {curr_sym}{p2_amt:,.2f} exactly two weeks later.\n\n"
                        f"Let me know if that's workable for you. Really appreciate your flexibility!\n\n"
                        f"Cheers,\n{owner.name}"
                    )
                },
                {
                    "tone": "urgent_respectful",
                    "subject": f"Notice: Proposed Two-Part Installment for Upcoming Payout",
                    "body": (
                        f"Dear {obligation.payee_name},\n\n"
                        f"To ensure uninterrupted payouts while navigating an offshore invoice delay, we are scheduling your {curr_sym}{obligation.amount:,.2f} "
                        f"payout in two structured installments: {curr_sym}{p1_amt:,.2f} will be remitted this Friday via PayPal Payouts, "
                        f"with the remaining {curr_sym}{p2_amt:,.2f} scheduled for release on {(obligation.due_date + datetime.timedelta(days=14)).strftime('%B %d')}.\n\n"
                        f"Please confirm your agreement so we can lock in the automated PayPal batch execution.\n\n"
                        f"Sincerely,\n{owner.name}"
                    )
                }
            ]

            saved_drafts = []
            for t in tones:
                draft = NegotiationDraft(
                    owner_id=owner.id,
                    obligation_id=obligation.id,
                    target_type="contractor_split",
                    recipient_name=obligation.payee_name,
                    recipient_email=obligation.payee_email,
                    tone=t["tone"],
                    subject=t["subject"],
                    body=t["body"],
                    offered_incentive=f"{split_pct:.0f}% upfront ({curr_sym}{p1_amt:,.2f}) + remaining in 14 days",
                    estimated_benefit=f"Prevents {curr_sym}{p2_amt:,.2f} cash crunch on Friday",
                    status="draft"
                )
                self.db.add(draft)
                self.db.commit()
                self.db.refresh(draft)
                saved_drafts.append(NegotiationDraftOut.model_validate(draft))

            return NegotiationTonesResponse(
                recipient_name=obligation.payee_name,
                recipient_email=obligation.payee_email,
                target_type="contractor_split",
                context_summary=f"Splitting {curr_sym}{obligation.amount:,.2f} obligation into {curr_sym}{p1_amt:,.2f} upfront and {curr_sym}{p2_amt:,.2f} in 14d",
                options=saved_drafts
            )

