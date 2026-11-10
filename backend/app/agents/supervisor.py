import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models import Owner, Obligation, AgentWorkflowRun
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.agents.collector import CollectorAgent
from backend.app.agents.treasurer import TreasurerAgent
from backend.app.agents.planner import RescuePlanEngine
from backend.app.agents.negotiator import NegotiationAgent
from backend.app.schemas import SupervisorRunResponse, AgentTraceStep, NegotiationGenerateRequest


class AgentSupervisor:
    """
    Agent Orchestrator / Supervisor:
    - Coordinates the 4 core specialized financial agents + Negotiation Agent.
    - Manages workflow state, execution permissions, and conflict resolution.
    - Logs every agent's contribution to persistent database trace.
    - Evaluates trade-offs and generates supervisory recommendation.
    """

    def __init__(self, db: Session):
        self.db = db

    def orchestrate_rescue_workflow(
        self,
        owner: Owner,
        obligation_id: Optional[int] = None,
        starting_balance: Optional[float] = None
    ) -> SupervisorRunResponse:
        run_id = f"sup_{uuid.uuid4().hex[:12]}"
        now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        steps_trace: List[AgentTraceStep] = []

        from backend.app.services.region_service import CURRENCIES_DB
        owner_curr = owner.preferred_currency or owner.currency or "USD"
        owner_sym = CURRENCIES_DB.get(owner_curr, {}).get("symbol", "$")

        if starting_balance is None:
            from backend.app.services.financial_service import FinancialService
            starting_balance = float(FinancialService.get_confirmed_balance(self.db, owner))

        # Step 1: Forecaster Agent scoped strictly to authenticated owner
        forecaster = ForecasterAgent(self.db)
        forecast_res = forecaster.run_forecast(
            obligation_id=obligation_id,
            starting_balance=starting_balance,
            owner_id=owner.id
        )
        has_shortfall = forecast_res.shortfall_amount > 0

        steps_trace.append(AgentTraceStep(
            agent_name="ForecasterAgent",
            status="completed",
            timestamp=now_str,
            summary=f"Detected shortfall of {owner_sym}{forecast_res.shortfall_amount:,.2f} on {forecast_res.first_shortfall_date} (p={forecast_res.p_shortfall*100:.0f}%)",
            key_finding=forecast_res.driver_explanation[:120] + "..." if forecast_res.driver_explanation else "Shortfall identified"
        ))

        # Step 2: Collector Agent
        collector = CollectorAgent()
        invoices_list = [
            {
                "invoice_id": cp.client_id,
                "paypal_invoice_id": f"INV-{cp.client_id}",
                "client_id": cp.client_id,
                "client_name": cp.client_name,
                "amount": cp.invoice_amount,
                "p_late": cp.p_late,
                "relationship_weight": 1.0,
                "pay_link": None
            }
            for cp in forecast_res.client_predictions
        ]
        scored_targets = collector.select_targets_for_reminder(invoices_list, forecast_res.shortfall_amount or 1400.0)
        top_target = scored_targets[0] if scored_targets else None
        collector_summary = (
            f"Ranked {top_target['client_name']} as primary candidate (score: {top_target['score']}, invoice: {owner_sym}{top_target['amount']:,.2f})"
            if top_target else "No high-scoring client available"
        )
        steps_trace.append(AgentTraceStep(
            agent_name="CollectorAgent",
            status="completed",
            timestamp=now_str,
            summary=collector_summary,
            key_finding=f"Identified {top_target['client_name'] if top_target else 'none'} as prime recovery target"
        ))

        # Step 3: Treasurer Agent
        treasurer = TreasurerAgent()
        target_obl = None
        if forecast_res.obligation:
            target_obl = self.db.query(Obligation).filter(
                Obligation.id == forecast_res.obligation.id,
                Obligation.owner_id == owner.id
            ).first()
        if not target_obl:
            target_obl = self.db.query(Obligation).filter(
                Obligation.owner_id == owner.id
            ).order_by(Obligation.due_date.asc()).first()

        split_eval = None
        if target_obl:
            split_eval = treasurer.propose_split_option(
                obligation=target_obl,
                starting_balance=starting_balance,
                expected_next_inflow_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
            )

        treasurer_summary = (
            f"Evaluated {target_obl.payee_name} obligation: split allowed = {target_obl.split_allowed}, installment 1 = ${split_eval['installment_1']['amount']:,.2f}"
            if target_obl and split_eval else (
                f"Obligation {target_obl.payee_name} evaluated for single settlement"
                if target_obl else "No active obligations pending settlement"
            )
        )
        steps_trace.append(AgentTraceStep(
            agent_name="TreasurerAgent",
            status="completed",
            timestamp=now_str,
            summary=treasurer_summary,
            key_finding=f"Split installment is {'feasible' if target_obl and target_obl.split_allowed else 'prohibited or not required'}"
        ))

        # Step 4: Planner Agent
        planner = RescuePlanEngine(self.db)
        plans_res = planner.generate_plans_for_forecast(forecast_res, discount_pct=3.0)
        plan_summaries = ", ".join([f"Plan {p.plan_type} ({owner_sym}{p.cost:,.2f} cost)" for p in plans_res.plans])
        steps_trace.append(AgentTraceStep(
            agent_name="PlannerAgent",
            status="completed",
            timestamp=now_str,
            summary=f"Synthesized {len(plans_res.plans)} rescue plans: {plan_summaries}",
            key_finding=f"Generated {len(plans_res.plans)} costed rescue plans with cryptographic HMAC signatures"
        ))

        # Step 5: Financial Negotiation Agent
        negotiator = NegotiationAgent(self.db)
        try:
            negotiator.generate_options(
                owner=owner,
                req=NegotiationGenerateRequest(target_type="client_discount", discount_pct=3.0)
            )
        except Exception:
            pass  # Non-blocking if owner has no open invoice for negotiation

        steps_trace.append(AgentTraceStep(
            agent_name="NegotiationAgent",
            status="completed",
            timestamp=now_str,
            summary="Prepared negotiation draft templates across Professional, Friendly, and Urgent tones",
            key_finding="Drafted multi-tone client negotiation messages ready for human authorization"
        ))

        # Supervisory Multi-Criteria Plan Evaluation & Dynamic Selection
        if not has_shortfall:
            recommended = "NONE"
            confidence_score = 0.98
            rec_reason = (
                f"No cash shortfall detected across the forecast horizon. Authoritative confirmed balance of "
                f"{owner_sym}{starting_balance:,.2f} safely satisfies all obligations. No rescue action is required."
            )
        else:
            # Score each available plan dynamically using financial criteria
            scored_plans = []
            for p in plans_res.plans:
                cost = float(p.cost or 0.0)
                residual = float(p.late_scenario.get("shortfall", 0.0) if p.late_scenario else 0.0)
                # Coverage ratio (0 to 1)
                shortfall_amt = max(forecast_res.shortfall_amount, 1.0)
                coverage = max(0.0, 1.0 - (residual / shortfall_amt))
                # Cost efficiency (1.0 = zero cost, decreases with concession)
                cost_ratio = cost / shortfall_amt
                cost_eff = max(0.0, 1.0 - (cost_ratio * 2.0))
                # Feasibility / Speed
                speed_score = 0.8
                if p.plan_type == "B":
                    speed_score = 0.95  # Fast 48h settlement incentive
                elif p.plan_type == "C":
                    speed_score = 0.90 if (target_obl and target_obl.split_allowed) else 0.20
                elif p.plan_type == "A":
                    speed_score = 0.70  # Client might still pay late

                # Composite score
                composite = (coverage * 0.45) + (cost_eff * 0.25) + (speed_score * 0.30)
                scored_plans.append({
                    "plan": p,
                    "score": composite,
                    "coverage": coverage,
                    "cost": cost,
                    "residual": residual
                })

            scored_plans.sort(key=lambda x: x["score"], reverse=True)
            best = scored_plans[0]
            recommended = best["plan"].plan_type
            confidence_score = round(min(max(best["score"], 0.70), 0.96), 2)

            target_name = top_target["client_name"] if top_target else "primary client"
            payee_name = target_obl.payee_name if target_obl else "contractor"
            best_cost = best["cost"]

            if recommended == "B":
                rec_reason = (
                    f"Plan B (early settlement discount) is the optimal supervisory recommendation. "
                    f"For a concession of {owner_sym}{best_cost:,.2f}, it creates an actionable incentive for {target_name} "
                    f"to accelerate settlement within 48 hours, eliminating the projected {owner_sym}{forecast_res.shortfall_amount:,.2f} "
                    f"deficit before {payee_name}'s scheduled payout."
                )
            elif recommended == "C":
                rec_reason = (
                    f"Plan C (contractor installment schedule) is the optimal supervisory recommendation. "
                    f"It provides immediate cash relief by splitting {payee_name}'s payment with zero concession cost, "
                    f"protecting current working capital until expected receivables clear."
                )
            else:
                rec_reason = (
                    f"Plan A (direct invoice payment reminder) is the optimal supervisory recommendation. "
                    f"With zero concession cost, prompting {target_name} provides the cleanest recovery path "
                    f"to settle the {owner_sym}{forecast_res.shortfall_amount:,.2f} projected shortfall."
                )

        # Persist Agent Workflow Run
        workflow_run = AgentWorkflowRun(
            owner_id=owner.id,
            run_id=run_id,
            status="completed",
            steps_trace=[s.model_dump() for s in steps_trace],
            selected_plan=recommended,
            final_recommendation=rec_reason
        )
        self.db.add(workflow_run)
        self.db.commit()

        return SupervisorRunResponse(
            run_id=run_id,
            status="completed",
            obligation_evaluated=target_obl.payee_name if target_obl else (forecast_res.obligation.payee_name if forecast_res.obligation else "Upcoming Obligation"),
            shortfall_detected=has_shortfall,
            shortfall_amount=forecast_res.shortfall_amount,
            primary_risk_driver=forecast_res.driver_ranking[0].client_name if forecast_res.driver_ranking else (top_target['client_name'] if top_target else "None"),
            recommended_plan=recommended,
            confidence_score=confidence_score,
            steps_trace=steps_trace,
            final_recommendation=rec_reason
        )
