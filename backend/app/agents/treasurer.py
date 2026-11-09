from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from backend.app.models import Obligation


class TreasurerAgent:
    """
    Treasurer Agent:
    - Ranks upcoming obligations by urgency and amount.
    - Proposes optimal cash timing and installment split options around expected cash inflows.
    """

    def rank_obligations(self, obligations: List[Obligation], current_date: datetime) -> List[Dict[str, Any]]:
        """Ranks list of obligations by urgency (days remaining) and amount."""
        ranked = []
        for obl in obligations:
            days_left = (obl.due_date.date() - current_date.date()).days
            urgency_score = 1.0 / max(days_left, 1) * (obl.amount / 1000.0)
            ranked.append({
                "obligation_id": obl.id,
                "payee_name": obl.payee_name,
                "amount": obl.amount,
                "currency": obl.currency,
                "due_date": obl.due_date,
                "days_left": days_left,
                "split_allowed": obl.split_allowed,
                "urgency_score": round(urgency_score, 3)
            })
        ranked.sort(key=lambda x: (x["days_left"], -x["amount"]))
        return ranked

    def propose_split_option(
        self,
        obligation: Obligation,
        starting_balance: float,
        expected_next_inflow_date: datetime,
        min_reserve: float = 200.0
    ) -> Optional[Dict[str, Any]]:
        """
        Proposes a 2-stage installment schedule for the obligation:
        Installment 1: Paid on original due date within available balance (e.g. 50%).
        Installment 2: Scheduled when next expected invoice arrives.
        """
        if not obligation.split_allowed:
            return None

        total = float(obligation.amount)
        # Default 50/50 split or affordable portion
        inst1 = round(total * 0.5, 2)
        inst2 = round(total - inst1, 2)

        # Ensure inst1 is covered by starting balance
        if starting_balance < inst1:
            inst1 = max(round(starting_balance - min_reserve, 2), round(total * 0.25, 2))
            inst2 = round(total - inst1, 2)

        # Normalize to naive UTC datetimes to prevent offset-naive vs offset-aware comparison errors
        obl_due = obligation.due_date.replace(tzinfo=None) if obligation.due_date.tzinfo else obligation.due_date
        inflow_dt = expected_next_inflow_date.replace(tzinfo=None) if expected_next_inflow_date.tzinfo else expected_next_inflow_date
        inst2_date = max(inflow_dt, obl_due + timedelta(days=5))

        return {
            "total_amount": total,
            "currency": obligation.currency,
            "payee_name": obligation.payee_name,
            "payee_email": obligation.payee_email,
            "installment_1": {
                "amount": inst1,
                "date": obligation.due_date,
                "date_str": obligation.due_date.strftime("%Y-%m-%d")
            },
            "installment_2": {
                "amount": inst2,
                "date": inst2_date,
                "date_str": inst2_date.strftime("%Y-%m-%d"),
                "status": "proposed",  # Explicitly labeled as proposed rather than scheduled (no automated persistent scheduler)
                "scheduling_available": False
            },
            "goodwill_cost_proxy": 0.0,  # Cash outlay cost is $0.00
            "qualitative_risk": (
                "Possible strain on contractor relationship; requires contractor agreement in writing. "
                "Second installment is proposed (not automated scheduled) and must be manually funded by subsequent payments."
            )
        }

