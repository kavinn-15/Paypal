import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.app.models import Owner, Invoice, Obligation, PaymentHistory
from backend.app.ml.simulation import project_cashflow_timeline
from backend.app.schemas import SimulationScenarioRequest, WhatIfComparisonResponse, DailyProjection


class SimulationService:

    @staticmethod
    def run_scenario(
        db: Session,
        owner: Owner,
        req: SimulationScenarioRequest,
        starting_balance: Optional[float] = None
    ) -> WhatIfComparisonResponse:
        """
        Runs a What-If simulation comparing baseline cash flow against a modified scenario.
        Strictly in-memory: NEVER modifies persistent database tables or executes transactions.
        """
        now = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now + datetime.timedelta(days=14)

        from backend.app.services.financial_service import FinancialService
        from backend.app.services.region_service import CURRENCIES_DB, convert_currency_amount

        owner_curr = (owner.preferred_currency or owner.currency or "USD").strip().upper()
        curr_sym = CURRENCIES_DB.get(owner_curr, {}).get("symbol", "$")

        if starting_balance is None:
            starting_balance = float(FinancialService.get_confirmed_balance(db, owner, target_currency=owner_curr))

        # 1. Fetch real baseline records
        invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id),
            Invoice.status.in_(["SENT", "DRAFT", "PARTIALLY_PAID"])
        ).all()

        obligations_models = db.query(Obligation).filter(
            Obligation.owner_id == owner.id,
            Obligation.status != "paid"
        ).order_by(Obligation.due_date.asc()).all()

        baseline_obligations = []
        for obl in obligations_models:
            obl_dec = Decimal(str(obl.amount))
            obl_curr = (obl.currency or owner_curr).strip().upper()
            if obl_curr != owner_curr:
                conv_obl = convert_currency_amount(obl_dec, obl_curr, owner_curr, round_minor_unit=True)
                amt_obl = float(conv_obl) if conv_obl is not None else float(obl_dec)
            else:
                amt_obl = float(obl_dec)
            baseline_obligations.append({
                "obligation_id": obl.id,
                "amount": amt_obl,
                "due_date": obl.due_date,
                "payee_name": obl.payee_name
            })

        # Calculate baseline inflows from empirical client payment history
        baseline_inflows = []
        for inv in invoices:
            hist_items = getattr(inv, "history_records", None) or getattr(inv, "payment_history", [])
            paid_amount = sum(Decimal(str(h.amount)) for h in hist_items)
            unpaid_dec = Decimal(str(inv.amount)) - paid_amount
            if unpaid_dec <= Decimal("0"):
                continue

            inv_curr = (inv.currency or owner_curr).strip().upper()
            if inv_curr != owner_curr:
                conv_inv = convert_currency_amount(unpaid_dec, inv_curr, owner_curr, round_minor_unit=True)
                amt_in_owner = float(conv_inv) if conv_inv is not None else float(unpaid_dec)
            else:
                amt_in_owner = float(unpaid_dec)

            # Determine empirical delay from actual client payment history
            c_history = db.query(PaymentHistory).filter(PaymentHistory.client_id == inv.client_id).all()
            if len(c_history) >= 2:
                avg_delay = max(0, int(round(sum(r.days_late for r in c_history) / len(c_history))))
            elif len(c_history) == 1:
                avg_delay = max(0, c_history[0].days_late)
            else:
                avg_delay = 3  # Neutral prior for clients without history

            baseline_inflows.append({
                "client_id": inv.client_id,
                "client_name": inv.client.name,
                "amount": amt_in_owner,
                "expected_pay_date": inv.due_date + datetime.timedelta(days=avg_delay)
            })

        proj_base, sf_date_base, sf_amt_base = project_cashflow_timeline(
            starting_balance=starting_balance,
            predicted_inflows=baseline_inflows,
            obligations=baseline_obligations,
            start_date=now,
            end_date=end_date
        )

        min_bal_base = min(p["ending_balance"] for p in proj_base) if proj_base else starting_balance
        if sf_amt_base > 0:
            tot_obl_amt = sum(o["amount"] for o in baseline_obligations)
            ratio = sf_amt_base / max(tot_obl_amt, 1.0)
            p_shortfall_base = min(0.95, max(0.50, round(0.50 + ratio * 0.45, 2)))
        else:
            p_shortfall_base = 0.05

        # 2. Apply What-If Modifications
        sim_inflows = [dict(inf) for inf in baseline_inflows]
        sim_obligations = [dict(obl) for obl in baseline_obligations]
        explanation = ""

        if req.scenario_type in ["client_delay_5d", "client_delay_10d"]:
            days = req.delay_days if (req.delay_days is not None and req.delay_days > 0) else (5 if req.scenario_type == "client_delay_5d" else 10)
            if req.delay_client_id:
                target = next((x for x in sim_inflows if x["client_id"] == req.delay_client_id), None)
            else:
                target = max(sim_inflows, key=lambda x: x["amount"]) if sim_inflows else None

            if target:
                target["expected_pay_date"] = target["expected_pay_date"] + datetime.timedelta(days=days)
                explanation = f"Simulating {target['client_name']} delaying payment by an additional {days} days past expected date ({target['expected_pay_date'].strftime('%b %d')})."
            else:
                explanation = f"Simulation requested client delay of {days} days, but no eligible open receivables were found to delay."

        elif req.scenario_type == "partial_pay_50":
            pct = req.partial_pct if (req.partial_pct is not None and 0 < req.partial_pct <= 100) else 50.0
            if req.delay_client_id:
                target = next((x for x in sim_inflows if x["client_id"] == req.delay_client_id), None)
            else:
                target = max(sim_inflows, key=lambda x: x["amount"]) if sim_inflows else None

            if target:
                original_amt = target["amount"]
                target["amount"] = round(original_amt * (pct / 100.0), 2)
                explanation = f"Simulating {target['client_name']} paying only {pct:.0f}% ({curr_sym}{target['amount']:,.2f}) of invoice before the deadline."
            else:
                explanation = f"Simulation requested partial payment of {pct:.0f}%, but no eligible open receivables were found."

        elif req.scenario_type == "dual_delay":
            days = req.delay_days if (req.delay_days is not None and req.delay_days > 0) else 7
            if len(sim_inflows) >= 2:
                for target in sim_inflows[:2]:
                    target["expected_pay_date"] = target["expected_pay_date"] + datetime.timedelta(days=days)
                explanation = f"Simulating two key clients ({sim_inflows[0]['client_name']} & {sim_inflows[1]['client_name']}) delaying simultaneously by {days} days."
            elif len(sim_inflows) == 1:
                sim_inflows[0]["expected_pay_date"] = sim_inflows[0]["expected_pay_date"] + datetime.timedelta(days=days)
                explanation = f"Simulating client {sim_inflows[0]['client_name']} delaying payment by {days} days (only 1 open invoice exists)."
            else:
                explanation = f"Simulation requested dual client delay, but no open receivables were found."

        elif req.scenario_type == "emergency_expense":
            em_amt = req.emergency_amount if (req.emergency_amount is not None and req.emergency_amount > 0) else 500.0
            sim_obligations.append({
                "amount": em_amt,
                "due_date": now + datetime.timedelta(days=3),
                "payee_name": "Emergency Hardware/Tool Expense"
            })
            explanation = f"Simulating an unexpected emergency equipment expense of {curr_sym}{em_amt:,.2f} occurring in 3 days."

        elif req.scenario_type == "expense_increase":
            if sim_obligations:
                sim_obligations[0]["amount"] = round(sim_obligations[0]["amount"] * 1.20, 2)
                explanation = f"Simulating contractor payout ({sim_obligations[0]['payee_name']}) increasing by 20% to {curr_sym}{sim_obligations[0]['amount']:,.2f}."
            else:
                explanation = "Simulation requested 20% expense increase, but no active obligations exist to increase."

        elif req.scenario_type == "contractor_split":
            if sim_obligations:
                split_pct = (req.contractor_split_pct if (req.contractor_split_pct is not None and 0 < req.contractor_split_pct < 100) else 50.0) / 100.0
                orig = sim_obligations[0]["amount"]
                part1 = round(orig * split_pct, 2)
                part2 = round(orig - part1, 2)
                sim_obligations[0]["amount"] = part1
                obl_due_date = sim_obligations[0]["due_date"]
                sim_obligations.append({
                    "amount": part2,
                    "due_date": obl_due_date + datetime.timedelta(days=14),
                    "payee_name": f"{sim_obligations[0]['payee_name']} (Part 2)"
                })
                explanation = (
                    f"Simulating {sim_obligations[0]['payee_name']} accepting {split_pct*100:.0f}% ({curr_sym}{part1:,.2f}) upfront "
                    f"and remaining {100-split_pct*100:.0f}% ({curr_sym}{part2:,.2f}) deferred by 14 days."
                )
            else:
                explanation = "Cannot simulate contractor split: no active contractor obligations exist in the account."

        # 3. Project Simulated Timeline
        proj_sim, sf_date_sim, sf_amt_sim = project_cashflow_timeline(
            starting_balance=starting_balance,
            predicted_inflows=sim_inflows,
            obligations=sim_obligations,
            start_date=now,
            end_date=end_date
        )

        min_bal_sim = min(p["ending_balance"] for p in proj_sim) if proj_sim else starting_balance
        if sf_amt_sim > 0:
            tot_obl_sim = sum(o["amount"] for o in sim_obligations)
            ratio_sim = sf_amt_sim / max(tot_obl_sim, 1.0)
            p_shortfall_sim = min(0.98, max(0.55, round(0.55 + ratio_sim * 0.40, 2)))
        else:
            p_shortfall_sim = 0.05

        delta_sf = sf_amt_sim - sf_amt_base
        delta_min = min_bal_sim - min_bal_base
        addl_needed = max(0.0, sf_amt_sim - sf_amt_base)

        return WhatIfComparisonResponse(
            scenario_name=req.run_name,
            scenario_type=req.scenario_type,
            baseline={
                "shortfall_amount": sf_amt_base,
                "first_shortfall_date": sf_date_base,
                "min_projected_balance": min_bal_base,
                "p_shortfall": p_shortfall_base
            },
            simulated={
                "shortfall_amount": sf_amt_sim,
                "first_shortfall_date": sf_date_sim,
                "min_projected_balance": min_bal_sim,
                "p_shortfall": p_shortfall_sim
            },
            delta={
                "shortfall_change": round(delta_sf, 2),
                "min_balance_change": round(delta_min, 2),
                "additional_capital_needed": round(addl_needed, 2),
                "p_shortfall_change": round(p_shortfall_sim - p_shortfall_base, 2)
            },
            projections_baseline=[DailyProjection(**p) for p in proj_base],
            projections_simulated=[DailyProjection(**p) for p in proj_sim],
            explanation=explanation
        )
