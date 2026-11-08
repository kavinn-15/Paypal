import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models import (
    Owner, Client, Invoice, PaymentHistory, Obligation, Forecast, ClientPrediction
)
from backend.app.ml.model import PaymentDelayModel
from backend.app.ml.simulation import (
    project_cashflow_timeline, run_monte_carlo_simulation, compute_driver_ranking
)
from backend.app.llm.client import llm_service
from backend.app.schemas import (
    ForecastRunResponse, DailyProjection, ClientPredictionOut, DriverContribution, ObligationOut
)


def to_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class ForecasterAgent:
    """
    Forecaster Agent:
    - Trains late-payment model per client from history with population shrinkage.
    - Predicts open invoices' expected pay date with confidence intervals.
    - Projects day-by-day cash balance through obligation due date.
    - Computes first shortfall date and shortfall amount.
    - Executes Monte Carlo simulations for probability of shortfall.
    - Ranks driver clients and generates plain-language validated explanation.
    """

    def __init__(self, db: Session):
        self.db = db
        self.model = PaymentDelayModel()

    def run_forecast(
        self,
        obligation_id: Optional[int] = None,
        starting_balance: Optional[float] = None,
        now: Optional[datetime] = None,
        owner_id: Optional[int] = None
    ) -> ForecastRunResponse:
        current_time = to_naive(now or datetime.now(timezone.utc))

        # 1. Fetch obligation scoped to owner
        obl_query = self.db.query(Obligation)
        if owner_id:
            obl_query = obl_query.filter(Obligation.owner_id == owner_id)

        if obligation_id:
            obligation = obl_query.filter(Obligation.id == obligation_id).first()
        else:
            obligation = obl_query.filter(Obligation.status != "paid").order_by(Obligation.due_date.asc()).first()

        if not obligation:
            raise ValueError("No active contractor obligation found to protect.")

        actual_owner_id = owner_id or obligation.owner_id
        owner = self.db.query(Owner).filter(Owner.id == actual_owner_id).first()

        # If starting_balance is not explicitly provided, calculate authoritative balance from ledger
        if starting_balance is None:
            if owner:
                from backend.app.services.financial_service import FinancialService
                starting_balance = float(FinancialService.get_confirmed_balance(self.db, owner))
            else:
                starting_balance = 1800.0

        obl_due = to_naive(obligation.due_date)

        # 2. Train model on user-specific payment history
        hist_query = self.db.query(PaymentHistory).join(PaymentHistory.client)
        if actual_owner_id:
            hist_query = hist_query.filter(Client.owner_id == actual_owner_id)
        history = hist_query.all()
        self.model.fit(history)

        # 3. Predict open invoices scoped strictly to this owner
        inv_query = self.db.query(Invoice).join(Invoice.client)
        if actual_owner_id:
            inv_query = inv_query.filter(Client.owner_id == actual_owner_id)
        open_invoices = inv_query.filter(Invoice.status.in_(["SENT", "DRAFT"])).all()
        run_id = f"fc_{uuid.uuid4().hex[:12]}"

        open_invoices_with_preds = []
        client_preds_out = []

        for inv in open_invoices:
            due_d = to_naive(inv.due_date)
            pred = self.model.predict_client_delay(
                client_id=inv.client_id,
                invoice_amount=inv.amount,
                due_date=due_d
            )
            # Store in client_predictions table
            cp_record = ClientPrediction(
                run_id=run_id,
                client_id=inv.client_id,
                expected_pay_date=to_naive(pred["expected_pay_date"]),
                p_late=pred["p_late"],
                expected_days_late=pred["expected_days_late"],
                ci_low=pred["ci_low"],
                ci_high=pred["ci_high"],
                is_cold_start=pred.get("is_cold_start", False)
            )
            self.db.add(cp_record)

            item = {
                "invoice_id": inv.id,
                "paypal_invoice_id": inv.paypal_invoice_id,
                "client_id": inv.client_id,
                "client_name": inv.client.name,
                "amount": float(inv.amount),
                "due_date": due_d,
                "expected_pay_date": to_naive(pred["expected_pay_date"]),
                "p_late": pred["p_late"],
                "expected_days_late": pred["expected_days_late"],
                "ci_low": pred["ci_low"],
                "ci_high": pred["ci_high"],
                "pay_link": inv.pay_link,
                "is_cold_start": pred.get("is_cold_start", False)
            }
            open_invoices_with_preds.append(item)

            client_preds_out.append(ClientPredictionOut(
                client_id=inv.client_id,
                client_name=inv.client.name,
                invoice_amount=float(inv.amount),
                due_date=due_d.strftime("%Y-%m-%d"),
                expected_pay_date=pred["expected_pay_date"].strftime("%Y-%m-%d"),
                p_late=pred["p_late"],
                expected_days_late=pred["expected_days_late"],
                ci_low_days=pred["ci_low"],
                ci_high_days=pred["ci_high"],
                is_cold_start=pred.get("is_cold_start", False)
            ))

        # 4. Project timeline through obligation due date + 7 days
        horizon_end = max(obl_due + timedelta(days=7), current_time + timedelta(days=14))
        raw_projections, first_shortfall_date, shortfall_amount = project_cashflow_timeline(
            starting_balance=starting_balance,
            predicted_inflows=open_invoices_with_preds,
            obligations=[{
                "amount": float(obligation.amount),
                "due_date": obl_due,
                "payee_name": obligation.payee_name
            }],
            start_date=current_time,
            end_date=horizon_end
        )

        # 5. Monte Carlo simulation
        p_shortfall, ci_low_band, ci_high_band = run_monte_carlo_simulation(
            starting_balance=starting_balance,
            open_invoices_with_preds=open_invoices_with_preds,
            obligation_amount=float(obligation.amount),
            obligation_due_date=obl_due,
            start_date=current_time,
            num_simulations=1000
        )

        # Attach confidence intervals to daily projections
        projections_out = []
        for i, p in enumerate(raw_projections):
            low = ci_low_band[i] if i < len(ci_low_band) else p["ending_balance"]
            high = ci_high_band[i] if i < len(ci_high_band) else p["ending_balance"]
            projections_out.append(DailyProjection(
                date=p["date"],
                starting_balance=p["starting_balance"],
                inflows=p["inflows"],
                outflows=p["outflows"],
                ending_balance=p["ending_balance"],
                is_shortfall=p["is_shortfall"],
                shortfall_amount=p["shortfall_amount"],
                ci_low=low,
                ci_high=high
            ))

        # 6. Rank driver clients
        driver_items = compute_driver_ranking(
            starting_balance=starting_balance,
            open_invoices_with_preds=open_invoices_with_preds,
            obligation_amount=float(obligation.amount),
            obligation_due_date=obl_due,
            start_date=current_time
        )
        driver_rankings = [DriverContribution(**d) for d in driver_items]

        # 7. Plain-language explanation via LLM with strict number validation
        top_driver_name = driver_rankings[0].client_name if driver_rankings else "open invoices"
        top_driver_delay = int(round(driver_rankings[0].expected_days_late)) if driver_rankings else 5
        target_day = obligation.due_date.strftime("%A, %b %d")

        driver_explanation = llm_service.generate_driver_explanation(
            starting_balance=starting_balance,
            shortfall_amount=shortfall_amount,
            target_date_str=target_day,
            contractor_name=obligation.payee_name,
            top_client_name=top_driver_name,
            top_client_delay=top_driver_delay,
            p_shortfall=p_shortfall
        )

        # 8. Persist Forecast Run
        forecast_record = Forecast(
            owner_id=obligation.owner_id,
            run_id=run_id,
            obligation_id=obligation.id,
            created_at=current_time,
            starting_balance=starting_balance,
            assumptions={
                "starting_balance": starting_balance,
                "obligation_amount": float(obligation.amount),
                "obligation_due_date": obligation.due_date.strftime("%Y-%m-%d"),
                "num_open_invoices": len(open_invoices),
                "model_type": "LogisticRegression+EmpiricalBayesShrinkage"
            },
            projections=[p.model_dump() for p in projections_out],
            first_shortfall_date=datetime.strptime(first_shortfall_date, "%Y-%m-%d") if first_shortfall_date else None,
            shortfall_amount=shortfall_amount,
            p_shortfall=p_shortfall,
            driver_explanation=driver_explanation
        )
        self.db.add(forecast_record)
        self.db.commit()

        # Check if history is seeded
        has_seeded = any(h.source == "seeded" for h in history)

        return ForecastRunResponse(
            run_id=run_id,
            created_at=current_time,
            obligation=ObligationOut.model_validate(obligation),
            starting_balance=starting_balance,
            first_shortfall_date=first_shortfall_date,
            shortfall_amount=shortfall_amount,
            p_shortfall=p_shortfall,
            projections=projections_out,
            client_predictions=client_preds_out,
            driver_ranking=driver_rankings,
            driver_explanation=driver_explanation,
            is_source_seeded=has_seeded
        )

    def run_multi_horizon(
        self,
        starting_balance: Optional[float] = None,
        now: Optional[datetime] = None,
        owner_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes multi-horizon forecasting (7d, 30d, 60d, 90d) scoped strictly to authenticated owner.
        """
        from backend.app.ml.simulation import run_multi_horizon_simulation

        current_time = to_naive(now or datetime.now(timezone.utc))

        if starting_balance is None:
            if owner_id:
                owner = self.db.query(Owner).filter(Owner.id == owner_id).first()
                if owner:
                    from backend.app.services.financial_service import FinancialService
                    starting_balance = float(FinancialService.get_confirmed_balance(self.db, owner))
            if starting_balance is None:
                starting_balance = 1800.0

        hist_query = self.db.query(PaymentHistory).join(PaymentHistory.client)
        if owner_id:
            hist_query = hist_query.filter(Client.owner_id == owner_id)
        history = hist_query.all()
        self.model.fit(history)

        inv_query = self.db.query(Invoice).join(Invoice.client)
        if owner_id:
            inv_query = inv_query.filter(Client.owner_id == owner_id)
        open_invoices = inv_query.filter(Invoice.status.in_(["SENT", "DRAFT"])).all()

        predicted_inflows = []
        for inv in open_invoices:
            due_d = to_naive(inv.due_date)
            pred = self.model.predict_client_delay(inv.client_id, float(inv.amount), due_d)
            predicted_inflows.append({
                "amount": float(inv.amount),
                "expected_pay_date": to_naive(pred["expected_pay_date"]),
                "due_date": due_d,
                "client_name": inv.client.name
            })

        obl_query = self.db.query(Obligation).filter(Obligation.status != "paid")
        if owner_id:
            obl_query = obl_query.filter(Obligation.owner_id == owner_id)
        obligations_records = obl_query.all()

        obligations = [{
            "amount": float(o.amount),
            "due_date": to_naive(o.due_date),
            "payee_name": o.payee_name
        } for o in obligations_records]

        results = run_multi_horizon_simulation(
            starting_balance=starting_balance,
            predicted_inflows=predicted_inflows,
            obligations=obligations,
            start_date=current_time
        )
        return results


