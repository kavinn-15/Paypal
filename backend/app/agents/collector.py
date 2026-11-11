from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.app.models import Client, Invoice


def _to_naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


class CollectorAgent:
    """
    Collector Agent:
    - Selects which clients to target using a computed score:
      Score = TimingPenalty * (Amount / Shortfall) * (1 - p_late) * RelationshipWeight
    - Filters or penalizes invoices due AFTER the obligation due date so that
      the chosen action actually protects the target deadline (e.g. Friday).
    - Generates stored 'why selected' rationales.
    - Selects optimal candidates for standard reminders vs early-pay discount concessions.
    """

    def select_targets_for_reminder(
        self,
        open_invoices: List[Dict[str, Any]],
        shortfall_amount: float,
        obligation_due_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Ranks and selects clients whose payment plausibly covers the shortfall before the obligation deadline.
        Invoices due AFTER the obligation due date cannot protect the deadline and are excluded/deprioritized.
        """
        from backend.app.services.region_service import CURRENCIES_DB

        obl_dt = _to_naive(obligation_due_date)

        scored = []
        for inv in open_invoices:
            amount = inv["amount"]
            p_late = inv.get("p_late", 0.5)
            rel_weight = inv.get("relationship_weight", 1.0)
            p_on_time = max(1.0 - p_late, 0.05)
            inv_curr = inv.get("currency", "USD")
            curr_sym = CURRENCIES_DB.get(inv_curr, {}).get("symbol", "$")

            inv_due = _to_naive(inv.get("due_date"))

            # Timing check: if invoice is due after the contractor's deadline,
            # payment will not arrive in time to protect Friday's payout
            timing_valid = True
            if obl_dt and inv_due:
                if inv_due.date() > obl_dt.date():
                    timing_valid = False

            expected_days_late = float(inv.get("expected_days_late", 5.0))
            # Reminder responsiveness: clients with smaller typical delays respond much better to simple reminders
            delay_responsiveness = 1.0 / (1.0 + max(0.0, expected_days_late / 4.0))

            # Score prioritizes invoices that cover a large fraction of the gap, have smaller delays, and high reliability
            coverage_ratio = min(amount / max(shortfall_amount, 1.0), 1.5)
            timing_factor = 1.0 if timing_valid else 0.01
            score = coverage_ratio * p_on_time * rel_weight * delay_responsiveness * timing_factor

            coverage_pct = min(amount / max(shortfall_amount, 1.0) * 100, 100) if shortfall_amount > 0 else 100
            timing_note = "" if timing_valid else " (Note: Due after contractor deadline)"
            why_selected = (
                f"Invoice of {curr_sym}{amount:,.2f} covers {coverage_pct:.0f}% of the shortfall. "
                f"Client has an estimated {p_on_time*100:.0f}% probability of timely settlement with relationship weight {rel_weight:.2f}.{timing_note}"
            )

            scored.append({
                "invoice_id": inv["invoice_id"],
                "paypal_invoice_id": inv["paypal_invoice_id"],
                "client_id": inv["client_id"],
                "client_name": inv["client_name"],
                "amount": amount,
                "score": round(score, 3),
                "timing_valid": timing_valid,
                "why_selected": why_selected,
                "pay_link": inv.get("pay_link")
            })

        # Prefer timing_valid candidates first, then sort by score descending
        scored.sort(key=lambda x: (x["timing_valid"], x["score"]), reverse=True)
        return scored

    def select_best_discount_candidate(
        self,
        open_invoices: List[Dict[str, Any]],
        shortfall_amount: float,
        discount_pct: float = 3.0,
        obligation_due_date: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Selects the single best invoice for an early payment concession.
        Prioritizes larger invoices that are historically delayed (high elasticity to financial incentives)
        and whose net proceeds arrive in time to cover the shortfall.
        """
        candidates = []
        from backend.app.services.region_service import CURRENCIES_DB
        obl_dt = _to_naive(obligation_due_date)

        for inv in open_invoices:
            amount = inv["amount"]
            p_late = inv.get("p_late", 0.5)
            discount_amount = round(amount * (discount_pct / 100.0), 2)
            net_proceeds = amount - discount_amount
            inv_curr = inv.get("currency", "USD")
            curr_sym = CURRENCIES_DB.get(inv_curr, {}).get("symbol", "$")

            inv_due = _to_naive(inv.get("due_date"))
            timing_valid = True
            if obl_dt and inv_due:
                if inv_due.date() > obl_dt.date():
                    timing_valid = False

            # Best discount candidate has high amount, high delay, and net proceeds cover the shortfall
            timing_factor = 1.0 if timing_valid else 0.01
            incentive_fit = (amount / max(shortfall_amount, 1.0)) * (0.5 + p_late) * timing_factor

            disc_coverage_pct = min(net_proceeds / max(shortfall_amount, 1.0) * 100, 100) if shortfall_amount > 0 else 100
            candidates.append({
                "invoice_id": inv["invoice_id"],
                "paypal_invoice_id": inv["paypal_invoice_id"],
                "client_id": inv["client_id"],
                "client_name": inv["client_name"],
                "original_amount": amount,
                "discount_pct": discount_pct,
                "discount_cost": discount_amount,
                "net_proceeds": net_proceeds,
                "score": incentive_fit,
                "timing_valid": timing_valid,
                "why_selected": (
                    f"Selected {inv['client_name']}'s {curr_sym}{amount:,.2f} invoice because early cash acceleration "
                    f"yields {curr_sym}{net_proceeds:,.2f} net (covering {disc_coverage_pct:.0f}% "
                    f"of shortfall) at an affordable {discount_pct:.1f}% discount cost of {curr_sym}{discount_amount:,.2f}."
                ),
                "pay_link": inv.get("pay_link")
            })

        candidates.sort(key=lambda x: (x["timing_valid"], x["score"]), reverse=True)
        return candidates[0] if candidates else None
