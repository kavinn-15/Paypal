import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple


def generate_daily_dates(start_date: datetime, end_date: datetime) -> List[str]:
    """Generates contiguous list of dates formatted as YYYY-MM-DD."""
    days = (end_date.date() - start_date.date()).days
    return [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(max(days + 1, 1))]


def project_cashflow_timeline(
    starting_balance: float,
    predicted_inflows: List[Dict[str, Any]],  # list of {amount, expected_pay_date}
    obligations: List[Dict[str, Any]],       # list of {amount, due_date, payee_name}
    start_date: datetime,
    end_date: datetime
) -> Tuple[List[Dict[str, Any]], Optional[str], float]:
    """
    Simulates day-by-day cashflow from start_date to end_date.
    Returns:
        (projections, first_shortfall_date, shortfall_amount)
    """
    date_strs = generate_daily_dates(start_date, end_date)
    daily_inflows = {d: 0.0 for d in date_strs}
    daily_outflows = {d: 0.0 for d in date_strs}

    for inf in predicted_inflows:
        d_str = inf["expected_pay_date"].strftime("%Y-%m-%d")
        amt = float(inf["amount"])
        if d_str in daily_inflows:
            daily_inflows[d_str] += amt
        elif inf["expected_pay_date"].date() < start_date.date():
            # Arrived earlier or today
            daily_inflows[date_strs[0]] += amt

    for obl in obligations:
        d_str = obl["due_date"].strftime("%Y-%m-%d")
        amt = float(obl["amount"])
        if d_str in daily_outflows:
            daily_outflows[d_str] += amt
        elif obl["due_date"].date() < start_date.date():
            daily_outflows[date_strs[0]] += amt

    projections = []
    current_balance = starting_balance
    first_shortfall_date = None
    max_shortfall_amount = 0.0

    for d in date_strs:
        day_start = current_balance
        inflow = daily_inflows[d]
        outflow = daily_outflows[d]
        ending = day_start + inflow - outflow

        is_shortfall = ending < 0.0
        shortfall = abs(ending) if is_shortfall else 0.0

        if is_shortfall:
            if first_shortfall_date is None:
                first_shortfall_date = d
            if shortfall > max_shortfall_amount:
                max_shortfall_amount = shortfall

        projections.append({
            "date": d,
            "starting_balance": round(day_start, 2),
            "inflows": round(inflow, 2),
            "outflows": round(outflow, 2),
            "ending_balance": round(ending, 2),
            "is_shortfall": is_shortfall,
            "shortfall_amount": round(shortfall, 2)
        })
        current_balance = ending

    return projections, first_shortfall_date, round(max_shortfall_amount, 2)


def run_monte_carlo_simulation(
    starting_balance: float,
    open_invoices_with_preds: List[Dict[str, Any]],
    obligation_amount: float,
    obligation_due_date: datetime,
    start_date: datetime,
    scheduled_expenses: Optional[List[Dict[str, Any]]] = None,
    num_simulations: int = 1000
) -> Tuple[float, List[float], List[float]]:
    """
    Runs Monte Carlo simulation sampling payment arrival dates across client distributions.
    Accurately accounts for scheduled expenses deducted on their actual dates.
    Returns:
        (p_shortfall, ci_low_band, ci_high_band)
    """
    days_to_sim = max((obligation_due_date.date() - start_date.date()).days + 7, 7)
    date_strs = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_to_sim + 1)]
    target_idx = (obligation_due_date.date() - start_date.date()).days

    # Calculate deterministic daily scheduled expense outflows across timeline
    daily_scheduled_outflows = np.zeros(len(date_strs))
    if scheduled_expenses:
        for exp in scheduled_expenses:
            diff = (exp["due_date"].date() - start_date.date()).days
            amt = float(exp["amount"])
            if 0 <= diff < len(date_strs):
                daily_scheduled_outflows[diff] += amt
            elif diff < 0:
                daily_scheduled_outflows[0] += amt

    shortfall_count = 0
    trajectories = np.zeros((num_simulations, len(date_strs)))

    np.random.seed(42)  # reproducible

    for sim in range(num_simulations):
        bal = starting_balance
        sim_inflows = np.zeros(len(date_strs))

        for inv in open_invoices_with_preds:
            # Sample days late using truncated normal bounded by [ci_low, ci_high]
            mean_days = inv["expected_days_late"]
            low = inv["ci_low"]
            high = inv["ci_high"]
            std = max((high - low) / 3.29, 0.5)

            sampled_days = np.random.normal(mean_days, std)
            sampled_days = np.clip(sampled_days, low - 2, high + 5)

            pay_date = inv["due_date"] + timedelta(days=int(round(sampled_days)))
            diff = (pay_date.date() - start_date.date()).days

            if 0 <= diff < len(date_strs):
                sim_inflows[diff] += inv["amount"]
            elif diff < 0:
                sim_inflows[0] += inv["amount"]

        # Run day-by-day balance for this simulation path
        for t in range(len(date_strs)):
            bal += sim_inflows[t]
            bal -= daily_scheduled_outflows[t]
            if t == target_idx:
                bal -= obligation_amount
            trajectories[sim, t] = bal

        if trajectories[sim, target_idx] < 0:
            shortfall_count += 1

    p_shortfall = float(shortfall_count / num_simulations)
    ci_low_band = [round(float(x), 2) for x in np.percentile(trajectories, 10, axis=0)]
    ci_high_band = [round(float(x), 2) for x in np.percentile(trajectories, 90, axis=0)]

    return round(p_shortfall, 3), ci_low_band, ci_high_band


def compute_driver_ranking(
    starting_balance: float,
    open_invoices_with_preds: List[Dict[str, Any]],
    obligation_amount: float,
    obligation_due_date: datetime,
    start_date: datetime,
    scheduled_expenses: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Ranks clients by their marginal contribution to the projected shortfall.
    For each client: computes shortfall difference between client paying late vs client paying on-time.
    Considers scheduled expenses.
    """
    outflows = [{"amount": obligation_amount, "due_date": obligation_due_date, "payee_name": "Contractor"}]
    if scheduled_expenses:
        for exp in scheduled_expenses:
            outflows.append({
                "amount": float(exp["amount"]),
                "due_date": exp["due_date"],
                "payee_name": exp.get("title", "Expense")
            })

    # 1. Baseline shortfall calculation
    baseline_inflows = [
        {"amount": inv["amount"], "expected_pay_date": inv["expected_pay_date"]}
        for inv in open_invoices_with_preds
    ]
    _, _, baseline_shortfall = project_cashflow_timeline(
        starting_balance,
        baseline_inflows,
        outflows,
        start_date,
        obligation_due_date + timedelta(days=3)
    )

    drivers = []
    for inv in open_invoices_with_preds:
        # Counterfactual: what if this client paid on time (on invoice due date)?
        counterfactual_inflows = []
        for other in open_invoices_with_preds:
            if other["client_id"] == inv["client_id"]:
                counterfactual_inflows.append({
                    "amount": other["amount"],
                    "expected_pay_date": other["due_date"]  # paid on time!
                })
            else:
                counterfactual_inflows.append({
                    "amount": other["amount"],
                    "expected_pay_date": other["expected_pay_date"]
                })

        _, _, cf_shortfall = project_cashflow_timeline(
            starting_balance,
            counterfactual_inflows,
            outflows,
            start_date,
            obligation_due_date + timedelta(days=3)
        )

        marginal_delta = max(baseline_shortfall - cf_shortfall, 0.0)
        drivers.append({
            "client_id": inv["client_id"],
            "client_name": inv["client_name"],
            "invoice_amount": inv["amount"],
            "expected_days_late": inv["expected_days_late"],
            "marginal_shortfall_delta": round(marginal_delta, 2),
            "explanation": (
                f"{inv['client_name']} typically pays {inv['expected_days_late']:.0f} days late on a "
                f"${inv['amount']:,.0f} invoice, delaying cash past your contractor's due date."
            )
        })

    # Sort descending by marginal shortfall delta
    drivers.sort(key=lambda d: d["marginal_shortfall_delta"], reverse=True)
    return drivers


def run_multi_horizon_simulation(
    starting_balance: float,
    predicted_inflows: List[Dict[str, Any]],
    obligations: List[Dict[str, Any]],
    start_date: datetime
) -> Dict[str, Dict[str, Any]]:
    """
    Computes deterministic forecasts across multiple planning horizons:
    7 days, 30 days, 60 days, and 90 days.
    """
    horizons = {"7d": 7, "30d": 30, "60d": 60, "90d": 90}
    results = {}

    for label, days in horizons.items():
        end_date = start_date + timedelta(days=days)
        projections, first_shortfall, max_shortfall = project_cashflow_timeline(
            starting_balance=starting_balance,
            predicted_inflows=predicted_inflows,
            obligations=obligations,
            start_date=start_date,
            end_date=end_date
        )

        min_bal = min([p["ending_balance"] for p in projections]) if projections else starting_balance
        final_bal = projections[-1]["ending_balance"] if projections else starting_balance
        tot_inflows = sum([p["inflows"] for p in projections])
        tot_outflows = sum([p["outflows"] for p in projections])

        # Shortfall risk probability approximation across horizon
        p_short = 0.85 if max_shortfall > 0 else 0.05
        if max_shortfall > 0 and final_bal > 0:
            p_short = 0.70  # temporary dip

        # Days of runway without incoming revenue
        avg_daily_burn = (tot_outflows / days) if days > 0 else 1.0
        runway_days = round(starting_balance / max(avg_daily_burn, 10.0), 1)

        results[label] = {
            "horizon_days": days,
            "starting_balance": round(starting_balance, 2),
            "ending_balance": round(final_bal, 2),
            "min_projected_balance": round(min_bal, 2),
            "first_shortfall_date": first_shortfall,
            "shortfall_amount": round(max_shortfall, 2),
            "p_shortfall": p_short,
            "total_inflows": round(tot_inflows, 2),
            "total_outflows": round(tot_outflows, 2),
            "runway_days": runway_days,
            "projections": projections
        }

    return results


