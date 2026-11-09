from typing import List, Dict, Any
from backend.app.models import Client, Invoice


class CollectorAgent:
    """
    Collector Agent:
    - Selects which clients to target using a computed score:
      Score = (Amount / Shortfall) * (1 - p_late) * RelationshipWeight
    - Generates stored 'why selected' rationales.
    - Selects optimal candidates for standard reminders vs early-pay discount concessions.
    """

    def select_targets_for_reminder(
        self,
        open_invoices: List[Dict[str, Any]],
        shortfall_amount: float
    ) -> List[Dict[str, Any]]:
        """
        Ranks and selects clients whose payment plausibly covers the shortfall.
        """
        scored = []
        for inv in open_invoices:
            amount = inv["amount"]
            p_late = inv.get("p_late", 0.5)
            rel_weight = inv.get("relationship_weight", 1.0)
            p_on_time = max(1.0 - p_late, 0.05)

            # Score prioritizes invoices that cover a large fraction of the gap and have high reliability
            coverage_ratio = min(amount / max(shortfall_amount, 1.0), 1.5)
            score = coverage_ratio * p_on_time * rel_weight

            coverage_pct = min(amount / max(shortfall_amount, 1.0) * 100, 100) if shortfall_amount > 0 else 100
            why_selected = (
                f"Invoice of ${amount:,.2f} covers {coverage_pct:.0f}% of the shortfall. "
                f"Client has an estimated {p_on_time*100:.0f}% probability of timely settlement with relationship weight {rel_weight:.2f}."
            )

            scored.append({
                "invoice_id": inv["invoice_id"],
                "paypal_invoice_id": inv["paypal_invoice_id"],
                "client_id": inv["client_id"],
                "client_name": inv["client_name"],
                "amount": amount,
                "score": round(score, 3),
                "why_selected": why_selected,
                "pay_link": inv.get("pay_link")
            })

        # Sort descending by computed score
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def select_best_discount_candidate(
        self,
        open_invoices: List[Dict[str, Any]],
        shortfall_amount: float,
        discount_pct: float = 3.0
    ) -> Dict[str, Any]:
        """
        Selects the single best invoice for an early payment concession.
        Prioritizes larger invoices that are historically delayed (high elasticity to financial incentives).
        """
        candidates = []
        for inv in open_invoices:
            amount = inv["amount"]
            p_late = inv.get("p_late", 0.5)
            discount_amount = round(amount * (discount_pct / 100.0), 2)
            net_proceeds = amount - discount_amount

            # Best discount candidate has high amount, high delay, and net proceeds cover the shortfall
            incentive_fit = (amount / max(shortfall_amount, 1.0)) * (0.5 + p_late)

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
                "why_selected": (
                    f"Selected {inv['client_name']}'s ${amount:,.2f} invoice because early cash acceleration "
                    f"yields ${net_proceeds:,.2f} net (covering {disc_coverage_pct:.0f}% "
                    f"of shortfall) at an affordable {discount_pct:.1f}% discount cost of ${discount_amount:,.2f}."
                ),
                "pay_link": inv.get("pay_link")
            })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0] if candidates else None

