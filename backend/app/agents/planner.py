import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import RescuePlan, Action, Message, Obligation, Invoice, Client
from backend.app.schemas import (
    ForecastRunResponse, RescuePlanOut, ActionOut, PlansComparisonResponse, DailyProjection, ObligationOut
)
from backend.app.agents.collector import CollectorAgent
from backend.app.agents.treasurer import TreasurerAgent
from backend.app.guardrail.approval import (
    generate_approval_hash, compute_action_payload, generate_payload_hash, generate_canonical_approval_signature
)
from backend.app.llm.client import llm_service
from backend.app.ml.simulation import project_cashflow_timeline


def to_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class RescuePlanEngine:
    """
    Heart of the product: Generates and compares up to three Rescue Plans:
    - Plan A: "Collect without concessions" (Reminders with live pay links)
    - Plan B: "Limited early-pay discount" (3% incentive concession on selected invoice)
    - Plan C: "Collect plus agreed contractor split" (Reminder + 2-installment payout schedule)
    """

    def __init__(self, db: Session):
        self.db = db
        self.collector = CollectorAgent()
        self.treasurer = TreasurerAgent()

    def generate_plans_for_forecast(
        self,
        forecast_response: ForecastRunResponse,
        discount_pct: float = 3.0
    ) -> PlansComparisonResponse:
        run_id = forecast_response.run_id
        shortfall = forecast_response.shortfall_amount
        first_shortfall_date = forecast_response.first_shortfall_date
        starting_balance = forecast_response.starting_balance
        obligation_obj = self.db.query(Obligation).filter(Obligation.id == forecast_response.obligation.id).first()
        from backend.app.models import Owner
        from backend.app.services.region_service import CURRENCIES_DB
        owner = self.db.query(Owner).filter(Owner.id == obligation_obj.owner_id).first() if obligation_obj else None
        owner_curr = (owner.preferred_currency or owner.currency or "USD") if owner else "USD"
        owner_sym = CURRENCIES_DB.get(owner_curr, {}).get("symbol", "$")

        start_time = to_naive(forecast_response.created_at)
        obl_due = to_naive(obligation_obj.due_date)

        open_invoices_models = self.db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=obligation_obj.owner_id),
            Invoice.status.in_(["SENT", "DRAFT"])
        ).all()
        open_invoices = []
        for inv in open_invoices_models:
            # find matching prediction from forecast
            pred = next((p for p in forecast_response.client_predictions if p.client_id == inv.client_id), None)
            p_late = pred.p_late if pred else 0.5
            expected_days = pred.expected_days_late if pred else 5.0
            inv_due = to_naive(inv.due_date)
            exp_pay = to_naive(datetime.strptime(pred.expected_pay_date, "%Y-%m-%d")) if pred else inv_due
            open_invoices.append({
                "invoice_id": inv.id,
                "paypal_invoice_id": inv.paypal_invoice_id,
                "client_id": inv.client_id,
                "client_name": inv.client.name,
                "client_email": inv.client.email,
                "amount": float(inv.amount),
                "currency": inv.currency,
                "due_date": inv_due,
                "expected_pay_date": exp_pay,
                "p_late": p_late,
                "expected_days_late": expected_days,
                "relationship_weight": inv.client.relationship_weight,
                "pay_link": inv.pay_link,
            })

        # Cap discount percent by policy
        discount_pct = min(discount_pct, settings.MAX_DISCOUNT_PCT)

        plans_out: List[RescuePlanOut] = []

        # -------------------------------------------------------------
        # PLAN A: Collect without concessions
        # -------------------------------------------------------------
        scored_targets = self.collector.select_targets_for_reminder(open_invoices, shortfall)
        top_target = scored_targets[0] if scored_targets else None

        plan_a_risk = "Clients may still pay late despite reminders; settlement timing is not guaranteed."
        plan_a_rationale = (
            f"Sends an official PayPal payment reminder with a direct pay link to {top_target['client_name'] if top_target else 'open clients'} "
            f"to prompt settlement before Friday's deadline without forfeiting revenue."
        )

        # Forecast with Plan A: Target client pays on or before obligation date
        with_plan_a_inflows = []
        for inv in open_invoices:
            if top_target and inv["client_id"] == top_target["client_id"]:
                # Accelerated to invoice due date
                with_plan_a_inflows.append({"amount": inv["amount"], "expected_pay_date": inv["due_date"]})
            else:
                with_plan_a_inflows.append({"amount": inv["amount"], "expected_pay_date": inv["expected_pay_date"]})

        plan_a_with_proj, _, _ = project_cashflow_timeline(
            starting_balance=starting_balance,
            predicted_inflows=with_plan_a_inflows,
            obligations=[{"amount": float(obligation_obj.amount), "due_date": obl_due, "payee_name": obligation_obj.payee_name}],
            start_date=start_time,
            end_date=obl_due + timedelta(days=5)
        )

        plan_a_idempotency = f"act_remind_{top_target['invoice_id'] if top_target else '0'}_{uuid.uuid4().hex[:8]}"
        plan_a_amount = top_target["amount"] if top_target else 0.0
        plan_a_recipient = top_target["client_name"] if top_target else "Client"
        plan_a_hash = generate_approval_hash(
            recipient=plan_a_recipient,
            amount=plan_a_amount,
            currency="USD",
            action_type="SEND_REMINDER",
            idempotency_key=plan_a_idempotency
        )

        plan_a_msg_draft = llm_service.draft_reminder_message(
            client_name=plan_a_recipient,
            invoice_id=top_target["paypal_invoice_id"] if top_target else "INV-001",
            amount=plan_a_amount,
            due_date_str=obligation_obj.due_date.strftime("%b %d"),
            pay_link=top_target.get("pay_link") if top_target else None
        )

        plan_a_db = RescuePlan(
            owner_id=obligation_obj.owner_id,
            run_id=run_id,
            plan_type="A",
            details={"invoice_id": top_target["invoice_id"] if top_target else None, "type": "reminder"},
            cost=0.0,
            incoming_needed=shortfall,
            selected_clients=scored_targets[:2],
            rationale=plan_a_rationale,
            forecast_with_plan=plan_a_with_proj,
            forecast_without_plan=[p.model_dump() for p in forecast_response.projections],
            late_scenario={
                "outcome": "If client still pays late, balance remains at projected shortfall on due date.",
                "shortfall": shortfall
            },
            remaining_risk=f"Plausibly protects contractor payout if client acts on reminder. {plan_a_risk}"
        )
        self.db.add(plan_a_db)
        self.db.flush()

        action_a_db = Action(
            owner_id=obligation_obj.owner_id,
            plan_id=plan_a_db.id,
            action_type="SEND_REMINDER",
            recipient=plan_a_recipient,
            amount=plan_a_amount,
            currency="USD",
            state="proposed",
            idempotency_key=plan_a_idempotency,
            approval_hash=plan_a_hash,
            approval_version=2,
            paypal_ref=top_target["paypal_invoice_id"] if top_target else None
        )
        self.db.add(action_a_db)
        self.db.flush()

        msg_a = Message(
            action_id=action_a_db.id,
            client_id=top_target["client_id"] if top_target else 1,
            body=plan_a_msg_draft,
            approval_status="draft"
        )
        self.db.add(msg_a)
        self.db.flush()

        # Compute complete canonical payload signature
        canonical_a = compute_action_payload(action_a_db)
        p_hash_a = generate_payload_hash(canonical_a)
        sig_a = generate_canonical_approval_signature(p_hash_a)
        action_a_db.approval_hash = sig_a
        action_a_db.approved_payload_hash = p_hash_a
        self.db.flush()

        plans_out.append(RescuePlanOut(
            id=plan_a_db.id,
            run_id=run_id,
            plan_type="A",
            name="Plan A: Collect Without Concessions",
            description="Send official PayPal payment reminder with live pay link to top reliable client.",
            cost=0.0,
            cost_description="$0.00 concession cost. Zero revenue lost.",
            incoming_needed=shortfall,
            selected_clients=scored_targets[:2],
            rationale=plan_a_rationale,
            forecast_with_plan=[DailyProjection(**p) for p in plan_a_with_proj],
            forecast_without_plan=forecast_response.projections,
            late_scenario={
                "outcome": "If client ignores reminder, shortfall remains.",
                "shortfall": shortfall
            },
            remaining_risk="Plausibly protects contractor payment if client settles promptly. Timing is not guaranteed.",
            primary_action=ActionOut.model_validate(action_a_db)
        ))

        # -------------------------------------------------------------
        # PLAN B: Limited early-pay discount
        # -------------------------------------------------------------
        discount_cand = self.collector.select_best_discount_candidate(open_invoices, shortfall, discount_pct)
        disc_cost = discount_cand["discount_cost"] if discount_cand else round(shortfall * 0.03, 2)
        disc_client_name = discount_cand["client_name"] if discount_cand else "Client"

        plan_b_risk = "Early payment is not guaranteed; offer expires if client does not take advantage of terms."
        plan_b_rationale = (
            f"Updates PayPal invoice terms to grant {disc_client_name} a {discount_pct:.1f}% early-pay discount "
            f"(${disc_cost:,.2f}), providing strong financial incentive to pay before Friday."
        )

        with_plan_b_inflows = []
        for inv in open_invoices:
            if discount_cand and inv["client_id"] == discount_cand["client_id"]:
                # Accelerated net proceeds arrive early
                with_plan_b_inflows.append({"amount": discount_cand["net_proceeds"], "expected_pay_date": inv["due_date"]})
            else:
                with_plan_b_inflows.append({"amount": inv["amount"], "expected_pay_date": inv["expected_pay_date"]})

        plan_b_with_proj, _, _ = project_cashflow_timeline(
            starting_balance=starting_balance,
            predicted_inflows=with_plan_b_inflows,
            obligations=[{"amount": float(obligation_obj.amount), "due_date": obl_due, "payee_name": obligation_obj.payee_name}],
            start_date=start_time,
            end_date=obl_due + timedelta(days=5)
        )

        plan_b_idempotency = f"act_disc_{discount_cand['invoice_id'] if discount_cand else '0'}_{uuid.uuid4().hex[:8]}"
        plan_b_hash = generate_approval_hash(
            recipient=disc_client_name,
            amount=disc_cost,
            currency="USD",
            action_type="APPLY_DISCOUNT",
            idempotency_key=plan_b_idempotency
        )

        plan_b_msg_draft = llm_service.draft_discount_message(
            client_name=disc_client_name,
            invoice_id=discount_cand["paypal_invoice_id"] if discount_cand else "INV-002",
            original_amount=discount_cand["original_amount"] if discount_cand else 2000.0,
            discount_pct=discount_pct,
            discounted_amount=discount_cand["net_proceeds"] if discount_cand else 1940.0,
            deadline_str=obligation_obj.due_date.strftime("%b %d"),
            pay_link=discount_cand.get("pay_link") if discount_cand else None
        )

        plan_b_db = RescuePlan(
            owner_id=obligation_obj.owner_id,
            run_id=run_id,
            plan_type="B",
            details={
                "invoice_id": discount_cand["invoice_id"] if discount_cand else None,
                "discount_pct": discount_pct,
                "discount_cost": disc_cost
            },
            cost=disc_cost,
            incoming_needed=shortfall,
            selected_clients=[discount_cand] if discount_cand else [],
            rationale=plan_b_rationale,
            forecast_with_plan=plan_b_with_proj,
            forecast_without_plan=[p.model_dump() for p in forecast_response.projections],
            late_scenario={
                "outcome": "If client declines early pay offer, discount expires and shortfall of ${shortfall:,.2f} persists.",
                "shortfall": shortfall
            },
            remaining_risk=f"Plausibly protects payment date through monetary incentive. {plan_b_risk}"
        )
        self.db.add(plan_b_db)
        self.db.flush()

        action_b_db = Action(
            owner_id=obligation_obj.owner_id,
            plan_id=plan_b_db.id,
            action_type="APPLY_DISCOUNT",
            recipient=disc_client_name,
            amount=disc_cost,
            currency="USD",
            state="proposed",
            idempotency_key=plan_b_idempotency,
            approval_hash=plan_b_hash,
            approval_version=2,
            paypal_ref=discount_cand["paypal_invoice_id"] if discount_cand else None
        )
        self.db.add(action_b_db)
        self.db.flush()

        msg_b = Message(
            action_id=action_b_db.id,
            client_id=discount_cand["client_id"] if discount_cand else 1,
            body=plan_b_msg_draft,
            approval_status="draft"
        )
        self.db.add(msg_b)
        self.db.flush()

        # Compute complete canonical payload signature
        canonical_b = compute_action_payload(action_b_db)
        p_hash_b = generate_payload_hash(canonical_b)
        sig_b = generate_canonical_approval_signature(p_hash_b)
        action_b_db.approval_hash = sig_b
        action_b_db.approved_payload_hash = p_hash_b
        self.db.flush()

        plans_out.append(RescuePlanOut(
            id=plan_b_db.id,
            run_id=run_id,
            plan_type="B",
            name="Plan B: Limited Early-Pay Discount",
            description=f"Apply {discount_pct:.1f}% discount to {disc_client_name}'s invoice in exchange for settlement by Friday.",
            cost=disc_cost,
            cost_description=f"{owner_sym}{disc_cost:,.2f} discount cost ({discount_pct:.1f}% concession).",
            incoming_needed=shortfall,
            selected_clients=[discount_cand] if discount_cand else [],
            rationale=plan_b_rationale,
            forecast_with_plan=[DailyProjection(**p) for p in plan_b_with_proj],
            forecast_without_plan=forecast_response.projections,
            late_scenario={
                "outcome": "If client fails to pay by deadline, discount expires and shortfall remains.",
                "shortfall": shortfall
            },
            remaining_risk="Plausibly protects Friday invoice by providing monetary incentive. Concession expires if unaccepted.",
            primary_action=ActionOut.model_validate(action_b_db)
        ))

        # -------------------------------------------------------------
        # PLAN C: Collect plus agreed contractor split
        # Only generated when split permission is explicitly True.
        # Safe failure: No unsafe automatic 50/50 fallback if permission is False or None.
        # -------------------------------------------------------------
        split_proposal = None
        plan_c_risk = "Contractor split option unavailable or split permission not granted."
        if obligation_obj.split_allowed is True and getattr(obligation_obj, "split_consent_recorded", False) is True:
            split_proposal = self.treasurer.propose_split_option(
                obligation=obligation_obj,
                starting_balance=starting_balance,
                expected_next_inflow_date=obligation_obj.due_date + timedelta(days=5)
            )

        if split_proposal is not None:
            plan_c_inst1 = split_proposal["installment_1"]["amount"]
            plan_c_inst2 = split_proposal["installment_2"]["amount"]
            inst2_date_str = split_proposal["installment_2"]["date_str"]

            consent_is_sim = bool(getattr(obligation_obj, "split_consent_is_simulated", False))
            plan_c_risk = (
                "Requires explicit contractor consent in writing; second installment is proposed (not automated scheduled) "
                "and must be manually disbursed once subsequent client payments settle."
            )
            if consent_is_sim:
                plan_c_risk += " [SIMULATED CONSENT — DEMO ONLY: Genuine payout execution disabled]"
            plan_c_rationale = (
                f"Pays contractor {obligation_obj.payee_name} {owner_sym}{plan_c_inst1:,.2f} on Friday (fully covered by current "
                f"balance) and proposes deferring {owner_sym}{plan_c_inst2:,.2f} to {inst2_date_str} when client funds arrive."
            )
            if consent_is_sim:
                plan_c_rationale += " (SIMULATED CONSENT — DEMO ONLY)"

            # Forecast with Plan C: Friday outflow is reduced to installment 1
            plan_c_with_proj, _, _ = project_cashflow_timeline(
                starting_balance=starting_balance,
                predicted_inflows=[{"amount": inv["amount"], "expected_pay_date": inv["expected_pay_date"]} for inv in open_invoices],
                obligations=[
                    {"amount": plan_c_inst1, "due_date": obl_due, "payee_name": obligation_obj.payee_name},
                    {"amount": plan_c_inst2, "due_date": obl_due + timedelta(days=5), "payee_name": obligation_obj.payee_name}
                ],
                start_date=start_time,
                end_date=obl_due + timedelta(days=7)
            )

            plan_c_idempotency = f"act_split_{obligation_obj.id}_{uuid.uuid4().hex[:8]}"
            plan_c_currency = obligation_obj.currency or owner_curr
            plan_c_hash = generate_approval_hash(
                recipient=obligation_obj.payee_name,
                amount=plan_c_inst1,
                currency=plan_c_currency,
                action_type="SCHEDULE_PAYOUT_SPLIT",
                idempotency_key=plan_c_idempotency,
                obligation_id=obligation_obj.id,
                contractor_name=obligation_obj.payee_name,
                payout_recipient_email=obligation_obj.payee_email.strip().lower()
            )

            plan_c_msg_draft = llm_service.draft_contractor_split_message(
                contractor_name=obligation_obj.payee_name,
                total_amount=float(obligation_obj.amount),
                first_installment=plan_c_inst1,
                first_date_str=obligation_obj.due_date.strftime("%b %d"),
                second_installment=plan_c_inst2,
                second_date_str=inst2_date_str,
                currency=plan_c_currency,
                currency_symbol=owner_sym
            )

            plan_c_db = RescuePlan(
                owner_id=obligation_obj.owner_id,
                run_id=run_id,
                plan_type="C",
                details={
                    "installment_1": plan_c_inst1,
                    "installment_2": plan_c_inst2,
                    "installment_2_date": inst2_date_str,
                    "installment_2_status": "proposed_manual_disbursement",
                    "scheduling_available": False,
                    "split_allowed": obligation_obj.split_allowed,
                    "split_consent_recorded": getattr(obligation_obj, "split_consent_recorded", False),
                    "split_consent_source": getattr(obligation_obj, "split_consent_source", None),
                    "split_consent_is_simulated": consent_is_sim,
                    "obligation_id": obligation_obj.id,
                    "payout_recipient_email": obligation_obj.payee_email.strip().lower()
                },
                cost=0.0,
                incoming_needed=0.0,
                selected_clients=scored_targets[:1],
                rationale=plan_c_rationale,
                forecast_with_plan=plan_c_with_proj,
                forecast_without_plan=[p.model_dump() for p in forecast_response.projections],
                late_scenario={
                    "outcome": "If second-stage client payment delays past installment 2 date, another shortfall occurs on installment 2.",
                    "shortfall": plan_c_inst2
                },
                remaining_risk=f"Plausibly protects Friday's contractor payout. {plan_c_risk}"
            )
            self.db.add(plan_c_db)
            self.db.flush()

            action_c_db = Action(
                owner_id=obligation_obj.owner_id,
                plan_id=plan_c_db.id,
                action_type="SCHEDULE_PAYOUT_SPLIT",
                recipient=obligation_obj.payee_name,
                amount=plan_c_inst1,
                currency=plan_c_currency,
                state="proposed",
                idempotency_key=plan_c_idempotency,
                approval_hash=plan_c_hash,
                approval_version=2,
                obligation_id=obligation_obj.id,
                payout_recipient_email=obligation_obj.payee_email.strip().lower(),
                paypal_ref=f"SPLIT-OBL-{obligation_obj.id}",
                is_simulated=consent_is_sim
            )
            self.db.add(action_c_db)
            self.db.flush()

            msg_c = Message(
                action_id=action_c_db.id,
                client_id=top_target["client_id"] if top_target else 1,
                body=plan_c_msg_draft,
                approval_status="draft"
            )
            self.db.add(msg_c)
            self.db.flush()

            # Compute complete canonical payload signature
            canonical_c = compute_action_payload(action_c_db)
            p_hash_c = generate_payload_hash(canonical_c)
            sig_c = generate_canonical_approval_signature(p_hash_c)
            action_c_db.approval_hash = sig_c
            action_c_db.approved_payload_hash = p_hash_c
            self.db.flush()

            plans_out.append(RescuePlanOut(
                id=plan_c_db.id,
                run_id=run_id,
                plan_type="C",
                name="Plan C: Collect Plus Agreed Contractor Split",
                description=f"Send reminder to client and split {obligation_obj.payee_name}'s payout into two installments (inst 2 proposed for manual disbursement).",
                cost=0.0,
                cost_description=f"{owner_sym}0.00 cash cost (possible contractor goodwill impact).",
                incoming_needed=0.0,
                selected_clients=scored_targets[:1],
                rationale=plan_c_rationale,
                forecast_with_plan=[DailyProjection(**p) for p in plan_c_with_proj],
                forecast_without_plan=forecast_response.projections,
                late_scenario={
                    "outcome": "If subsequent invoices lag, second installment will be exposed to cashflow pressure.",
                    "shortfall": plan_c_inst2
                },
                remaining_risk="Plausibly protects Friday payout; requires mutual contractor agreement in writing.",
                primary_action=ActionOut.model_validate(action_c_db)
            ))

        self.db.commit()

        # Generate validated LLM trade-off summary
        tradeoff_summary = llm_service.generate_tradeoff_summary(
            shortfall_amount=shortfall,
            plan_b_discount_cost=disc_cost,
            contractor_name=obligation_obj.payee_name,
            plan_a_risk=plan_a_risk,
            plan_b_risk=plan_b_risk,
            plan_c_risk=plan_c_risk,
            currency=owner_curr,
            currency_symbol=owner_sym
        )

        return PlansComparisonResponse(
            run_id=run_id,
            obligation=ObligationOut.model_validate(obligation_obj),
            shortfall_amount=shortfall,
            first_shortfall_date=first_shortfall_date,
            tradeoff_summary=tradeoff_summary,
            plans=plans_out,
            starting_balance=starting_balance,
            driver_rankings=forecast_response.driver_ranking,
            p_shortfall=forecast_response.p_shortfall
        )
