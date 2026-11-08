import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.app.models import Owner, Invoice, Obligation
from backend.app.ml.simulation import project_cashflow_timeline
from backend.app.schemas import SimulationScenarioRequest, WhatIfComparisonResponse, DailyProjection


class SimulationService:

    @staticmethod
    def run_scenario(
        db: Session,
        owner: Owner,
        req: SimulationScenarioRequest,
        starting_balance: float = 1800.0
    ) -> WhatIfComparisonResponse:
        """
        Runs a What-If simulation comparing baseline cash flow against a modified scenario.
        Strictly in-memory: NEVER modifies persistent database tables or executes transactions.
        """
        now = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now + datetime.timedelta(days=14)

        # 1. Fetch real baseline records
        invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id),
            Invoice.status.in_(["SENT", "DRAFT"])
        ).all()

        obligation = db.query(Obligation).filter(
            Obligation.owner_id == owner.id,
            Obligation.status != "paid"
        ).order_by(Obligation.due_date.asc()).first()

        obl_amt = float(obligation.amount) if obligation else 3200.0
        obl_due = obligation.due_date if obligation else (now + datetime.timedelta(days=5))

        # Baseline inflows: Apex delays 14d, Nordic delays 6d, Vertex delays 8d
        baseline_inflows = []
        for inv in invoices:
            delay = 14 if "Apex" in inv.client.name else (6 if "Nordic" in inv.client.name else 8)
            baseline_inflows.append({
                "client_id": inv.client_id,
                "client_name": inv.client.name,
                "amount": float(inv.amount),
                "expected_pay_date": inv.due_date + datetime.timedelta(days=delay)
            })

        baseline_obligations = [{
            "amount": obl_amt,
            "due_date": obl_due,
            "payee_name": obligation.payee_name if obligation else "Contractor"
        }]

        proj_base, sf_date_base, sf_amt_base = project_cashflow_timeline(
            starting_balance=starting_balance,
            predicted_inflows=baseline_inflows,
            obligations=baseline_obligations,
            start_date=now,
            end_date=end_date
        )

        min_bal_base = min(p["ending_balance"] for p in proj_base) if proj_base else starting_balance
        p_shortfall_base = 0.88 if sf_amt_base > 0 else 0.05

        # 2. Apply What-If Modifications
        sim_inflows = [dict(inf) for inf in baseline_inflows]
        sim_obligations = [dict(obl) for obl in baseline_obligations]
        explanation = ""

        if req.scenario_type in ["client_delay_5d", "client_delay_10d"]:
            days = 5 if req.scenario_type == "client_delay_5d" else 10
            # Target Nordic or first client
            target = next((x for x in sim_inflows if "Nordic" in x["client_name"]), sim_inflows[0] if sim_inflows else None)
            if target:
                target["expected_pay_date"] = target["expected_pay_date"] + datetime.timedelta(days=days)
                explanation = f"Simulating {target['client_name']} delaying payment by an additional {days} days past expected date."

        elif req.scenario_type == "partial_pay_50":
            target = next((x for x in sim_inflows if "Nordic" in x["client_name"]), sim_inflows[0] if sim_inflows else None)
            if target:
                original_amt = target["amount"]
                target["amount"] = original_amt * 0.50
                explanation = f"Simulating {target['client_name']} paying only 50% (${target['amount']:,.2f}) of invoice before the deadline."

        elif req.scenario_type == "dual_delay":
            for target in sim_inflows[:2]:
                target["expected_pay_date"] = target["expected_pay_date"] + datetime.timedelta(days=7)
            explanation = "Simulating two key clients (Apex & Nordic) delaying simultaneously by 7 days."

        elif req.scenario_type == "emergency_expense":
            em_amt = req.emergency_amount or 500.0
            sim_obligations.append({
                "amount": em_amt,
                "due_date": now + datetime.timedelta(days=3),
                "payee_name": "Emergency Hardware/Tool Expense"
            })
            explanation = f"Simulating an unexpected emergency equipment expense of ${em_amt:,.2f} occurring on day 3."

        elif req.scenario_type == "expense_increase":
            sim_obligations[0]["amount"] = sim_obligations[0]["amount"] * 1.20
            explanation = f"Simulating contractor payout increasing by 20% to ${sim_obligations[0]['amount']:,.2f}."

        elif req.scenario_type == "contractor_split":
            orig = sim_obligations[0]["amount"]
            sim_obligations[0]["amount"] = orig * 0.50
            sim_obligations.append({
                "amount": orig * 0.50,
                "due_date": obl_due + datetime.timedelta(days=14),
                "payee_name": f"{obligation.payee_name if obligation else 'Contractor'} (Part 2)"
            })
            explanation = f"Simulating contractor accepting 50% (${orig*0.50:,.2f}) on Friday and remaining 50% in 14 days."

        # 3. Project Simulated Timeline
        proj_sim, sf_date_sim, sf_amt_sim = project_cashflow_timeline(
            starting_balance=starting_balance,
            predicted_inflows=sim_inflows,
            obligations=sim_obligations,
            start_date=now,
            end_date=end_date
        )

        min_bal_sim = min(p["ending_balance"] for p in proj_sim) if proj_sim else starting_balance
        p_shortfall_sim = 0.95 if sf_amt_sim > sf_amt_base else (0.15 if sf_amt_sim == 0 else 0.75)

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
