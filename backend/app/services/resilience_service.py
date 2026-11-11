from typing import List, Dict, Any, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.app.models import Owner, Invoice, Obligation, PaymentHistory
from backend.app.schemas import ResilienceScoreResponse, ResilienceFactor


class ResilienceService:

    @staticmethod
    def calculate_score(db: Session, owner: Owner, starting_balance: Optional[float] = None) -> ResilienceScoreResponse:
        from backend.app.services.financial_service import FinancialService
        from backend.app.services.region_service import CURRENCIES_DB, convert_currency_amount

        owner_curr = (owner.preferred_currency or owner.currency or "USD").strip().upper()
        curr_sym = CURRENCIES_DB.get(owner_curr, {}).get("symbol", "$")

        if starting_balance is None:
            starting_balance = float(FinancialService.get_confirmed_balance(db, owner, target_currency=owner_curr))

        invoices = db.query(Invoice).join(Invoice.client).filter(
            Invoice.client.has(owner_id=owner.id),
            Invoice.status.in_(["SENT", "DRAFT", "PARTIALLY_PAID"])
        ).all()

        obligations = db.query(Obligation).filter(
            Obligation.owner_id == owner.id,
            Obligation.status != "paid"
        ).all()

        # Convert open invoices to owner_curr and account for partial payments
        open_invoices_data = []
        tot_invoices = 0.0
        for i in invoices:
            hist_items = getattr(i, "history_records", None) or getattr(i, "payment_history", [])
            paid_amount = sum(Decimal(str(h.amount)) for h in hist_items)
            unpaid_dec = Decimal(str(i.amount)) - paid_amount
            if unpaid_dec <= Decimal("0"):
                continue
            inv_curr = (i.currency or owner_curr).strip().upper()
            if inv_curr != owner_curr:
                conv = convert_currency_amount(unpaid_dec, inv_curr, owner_curr, round_minor_unit=True)
                amt_in_owner = float(conv) if conv is not None else float(unpaid_dec)
            else:
                amt_in_owner = float(unpaid_dec)
            tot_invoices += amt_in_owner
            open_invoices_data.append({
                "invoice": i,
                "amount": amt_in_owner,
                "client_name": i.client.name
            })

        # Convert obligations to owner_curr
        tot_obligations = 0.0
        for o in obligations:
            obl_dec = Decimal(str(o.amount))
            obl_curr = (o.currency or owner_curr).strip().upper()
            if obl_curr != owner_curr:
                conv = convert_currency_amount(obl_dec, obl_curr, owner_curr, round_minor_unit=True)
                amt_in_owner = float(conv) if conv is not None else float(obl_dec)
            else:
                amt_in_owner = float(obl_dec)
            tot_obligations += amt_in_owner

        # 1. Cash Reserve Coverage (Weight: 20%)
        # Runway in days assuming 30-day burn rate from obligations
        daily_burn = max(tot_obligations / 30.0, 50.0)
        runway_days = round(starting_balance / daily_burn, 1)
        score_reserve = min(100.0, max(10.0, (runway_days / 30.0) * 100.0))

        # 2. Debtor Reliability (Weight: 20%)
        # Calculate statistical late probability per client from actual PaymentHistory
        insufficient_history_clients = []
        if tot_invoices > 0:
            weighted_late = 0.0
            for item in open_invoices_data:
                inv_obj = item["invoice"]
                c_history = db.query(PaymentHistory).filter(PaymentHistory.client_id == inv_obj.client_id).all()
                if len(c_history) >= 2:
                    delays = [r.days_late for r in c_history]
                    late_count = sum(1 for d in delays if d > 0)
                    # Empirical Bayes / Laplace smoothing
                    p_late = round((late_count + 1.0) / (len(delays) + 2.0), 3)
                    item["has_insufficient_history"] = False
                else:
                    # Neutral prior (0.50) when historical payment data is insufficient
                    p_late = 0.50
                    item["has_insufficient_history"] = True
                    insufficient_history_clients.append(item["client_name"])

                item["p_late"] = p_late
                weighted_late += item["amount"] * p_late

            avg_p_late = weighted_late / tot_invoices
            reliability_pct = round((1.0 - avg_p_late) * 100.0, 1)
        else:
            reliability_pct = 80.0
        score_reliability = reliability_pct

        # 3. Obligations Load (Weight: 20%)
        # Obligation-to-liquidity ratio
        liquidity = starting_balance + tot_invoices
        obligation_ratio = (tot_obligations / liquidity) if liquidity > 0 else 1.0
        score_obligations = max(10.0, min(100.0, (1.0 - obligation_ratio) * 100.0))

        # 4. Concentration Risk (Weight: 15%)
        # Herfindahl-Hirschman Index (HHI)
        if tot_invoices > 0:
            shares = [(item["amount"] / tot_invoices) ** 2 for item in open_invoices_data]
            hhi = sum(shares)
        else:
            hhi = 0.2
        score_concentration = max(15.0, min(100.0, (1.0 - hhi) * 100.0))

        # 5. Receivables Exposure (Weight: 15%)
        # Percentage of total assets locked in unpaid receivables
        exposure_pct = (tot_invoices / liquidity * 100.0) if liquidity > 0 else 50.0
        score_exposure = max(10.0, min(100.0, (100.0 - exposure_pct)))

        # 6. Unexpected Expense Shock Tolerance (Weight: 10%)
        # Max shock absorbable without going into negative balance
        unprotected_shortfall = max(0.0, tot_obligations - starting_balance)
        shock_capacity = max(0.0, starting_balance - 500.0)
        score_shock = 80.0 if unprotected_shortfall == 0 else max(15.0, 50.0 - (unprotected_shortfall / 100.0))

        # Overall weighted composite score (0-100)
        overall = int(round(
            (score_reserve * 0.20) +
            (score_reliability * 0.20) +
            (score_obligations * 0.20) +
            (score_concentration * 0.15) +
            (score_exposure * 0.15) +
            (score_shock * 0.10)
        ))

        # Categorize
        if overall >= 80:
            category = "Excellent"
        elif overall >= 65:
            category = "Good"
        elif overall >= 50:
            category = "Moderate"
        elif overall >= 35:
            category = "Fragile"
        else:
            category = "Critical"

        improving = [
            f"Active confirmed cash balance of {curr_sym}{starting_balance:,.2f} provides {runway_days:.0f} days baseline runway."
        ]
        if score_concentration > 60:
            improving.append("Invoices distributed across multiple client accounts.")
        if tot_invoices > 0 and len(insufficient_history_clients) == 0:
            improving.append("Payment reliability calculated from verified historical settlement records.")

        top_client_amounts = sorted([item["amount"] for item in open_invoices_data], reverse=True)
        top2_share = min(100, int((sum(top_client_amounts[:2]) / max(tot_invoices, 1.0)) * 100)) if top_client_amounts else 0

        # Dynamically identify debtor with highest risk exposure
        highest_risk_item = max(open_invoices_data, key=lambda x: x["amount"] * x.get("p_late", 0.5)) if open_invoices_data else None

        reducing = []
        if highest_risk_item and highest_risk_item.get("p_late", 0.0) >= 0.40:
            hr_p = int(round(highest_risk_item["p_late"] * 100))
            reducing.append(
                f"{highest_risk_item['client_name']} exhibits an estimated {hr_p}% late-payment risk, "
                f"locking up {curr_sym}{highest_risk_item['amount']:,.2f} in pending receivables."
            )
        elif open_invoices_data:
            top_rec = max(open_invoices_data, key=lambda x: x["amount"])
            reducing.append(f"Receivables exposure: {top_rec['client_name']} represents {curr_sym}{top_rec['amount']:,.2f} of total pending revenue.")
        else:
            reducing.append("No active open receivables detected to support upcoming cash inflows.")

        if tot_obligations > starting_balance:
            gap = tot_obligations - starting_balance
            reducing.append(f"Upcoming fixed obligations ({curr_sym}{tot_obligations:,.2f}) exceed current cash balance by {curr_sym}{gap:,.2f}.")
        elif tot_obligations > 0:
            reducing.append(f"Upcoming fixed commitments totaling {curr_sym}{tot_obligations:,.2f} due in current settlement cycle.")

        if len(open_invoices_data) > 1 and top2_share > 60:
            reducing.append(f"Receivables concentration: top clients represent {top2_share}% of total pending revenue.")
        elif len(open_invoices_data) == 1:
            reducing.append(f"Single-client concentration: 100% of open receivables rely on {open_invoices_data[0]['client_name']}.")

        recommendations = []
        if open_invoices_data:
            top_debtor = max(open_invoices_data, key=lambda x: x["amount"])
            discounted_amt = round(top_debtor["amount"] * 0.97, 2)
            recommendations.append(
                f"Execute Rescue Plan B: apply 3% early-pay discount to {top_debtor['client_name']} to unlock {curr_sym}{discounted_amt:,.2f} within 48h."
            )
        else:
            recommendations.append("Issue and send client invoices promptly to establish predictable receivables.")

        if obligations:
            first_obl = obligations[0]
            part1 = round(float(first_obl.amount) * 0.5, 2)
            part2 = round(float(first_obl.amount) - part1, 2)
            recommendations.append(
                f"Enable split payment arrangement on {first_obl.payee_name}'s payout ({curr_sym}{part1:,.2f} upfront, {curr_sym}{part2:,.2f} deferred upon mutual agreement)."
            )
        else:
            recommendations.append("No fixed obligations currently pending; maintain working capital for upcoming commitments.")

        emergency_buffer = max(1000.0, round(tot_obligations, -2)) if tot_obligations > 0 else 1000.0
        recommendations.append(
            f"Establish an automated emergency cash buffer of {curr_sym}{emergency_buffer:,.2f} for recurring commitments."
        )

        factors = [
            ResilienceFactor(
                name="Cash Reserve Coverage",
                score=round(score_reserve, 1),
                weight=0.20,
                status="neutral" if score_reserve >= 50 else "at_risk",
                detail=f"{runway_days:.1f} days of operating runway at current payout run rate.",
                impact="neutral" if score_reserve >= 50 else "negative"
            ),
            ResilienceFactor(
                name="Expected Income Reliability",
                score=round(score_reliability, 1),
                weight=0.20,
                status="at_risk" if score_reliability < 55 else "strong",
                detail=(
                    f"{reliability_pct:.1f}% weighted likelihood of on-time payment clearance "
                    f"({len(insufficient_history_clients)} client(s) with limited history assigned neutral prior)."
                    if insufficient_history_clients else
                    f"{reliability_pct:.1f}% weighted likelihood of on-time payment clearance based on verified settlement history."
                ),
                impact="negative" if score_reliability < 55 else "positive"
            ),
            ResilienceFactor(
                name="Upcoming Obligations Load",
                score=round(score_obligations, 1),
                weight=0.20,
                status="at_risk" if score_obligations < 50 else "neutral",
                detail=f"{curr_sym}{tot_obligations:,.2f} in fixed obligations due against {curr_sym}{starting_balance:,.2f} starting cash.",
                impact="negative"
            ),
            ResilienceFactor(
                name="Payment Concentration Risk",
                score=round(score_concentration, 1),
                weight=0.15,
                status="neutral" if score_concentration >= 55 else "at_risk",
                detail=f"HHI of {hhi:.2f} across {len(invoices)} open client invoices.",
                impact="neutral"
            ),
            ResilienceFactor(
                name="Receivables Exposure",
                score=round(score_exposure, 1),
                weight=0.15,
                status="at_risk",
                detail=f"{exposure_pct:.1f}% of total anticipated cash is currently locked in open invoices.",
                impact="negative"
            ),
            ResilienceFactor(
                name="Expense Shock Tolerance",
                score=round(score_shock, 1),
                weight=0.10,
                status="at_risk",
                detail="Low capacity for unexpected emergency outlays prior to Friday settlement.",
                impact="negative"
            )
        ]

        return ResilienceScoreResponse(
            overall_score=overall,
            category=category,
            reserve_runway_days=runway_days,
            debtor_reliability_pct=reliability_pct,
            obligation_load_ratio=round(obligation_ratio, 2),
            concentration_risk_hhi=round(hhi, 2),
            receivables_exposure_pct=round(exposure_pct, 1),
            emergency_tolerance_usd=round(shock_capacity, 2),
            improving_factors=improving,
            reducing_factors=reducing,
            recommended_actions=recommendations,
            factors=factors
        )

