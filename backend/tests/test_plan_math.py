import pytest
from datetime import datetime, timedelta, timezone
from backend.app.db import SessionLocal, init_db
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.agents.planner import RescuePlanEngine
from backend.app.guardrail.approval import verify_approval_hash
from backend.scripts.seed import seed_database


@pytest.fixture(scope="module")
def setup_seed():
    seed_database(clean=True, demo_mode=True)


def test_plans_generation_and_formulas(setup_seed):
    db = SessionLocal()
    try:
        forecaster = ForecasterAgent(db)
        forecast = forecaster.run_forecast(starting_balance=1800.0)

        # Baseline check
        assert forecast.shortfall_amount == 1400.0
        assert forecast.first_shortfall_date is not None

        engine = RescuePlanEngine(db)
        comparison = engine.generate_plans_for_forecast(forecast, discount_pct=3.0)

        assert len(comparison.plans) == 3

        # Plan A checks
        plan_a = next(p for p in comparison.plans if p.plan_type == "A")
        assert plan_a.cost == 0.0
        assert plan_a.incoming_needed == 1400.0
        assert "plausibly protects" in plan_a.remaining_risk.lower()
        assert "guarantees" not in plan_a.remaining_risk.lower()
        # Verify Plan A approval hash
        action_a = plan_a.primary_action
        assert verify_approval_hash(
            provided_hash=action_a.approval_hash,
            recipient=action_a.recipient,
            amount=action_a.amount,
            currency=action_a.currency,
            action_type=action_a.action_type,
            idempotency_key=action_a.idempotency_key
        ) is True

        # Plan B checks
        plan_b = next(p for p in comparison.plans if p.plan_type == "B")
        # 3% of Apex $2000 invoice = $60.00
        assert plan_b.cost == 60.0
        assert plan_b.incoming_needed == 1400.0
        assert "plausibly protects" in plan_b.remaining_risk.lower()
        assert "guarantees" not in plan_b.remaining_risk.lower()
        action_b = plan_b.primary_action
        assert action_b.amount == 60.0
        assert verify_approval_hash(
            provided_hash=action_b.approval_hash,
            recipient=action_b.recipient,
            amount=action_b.amount,
            currency=action_b.currency,
            action_type=action_b.action_type,
            idempotency_key=action_b.idempotency_key
        ) is True

        # Plan C checks
        plan_c = next(p for p in comparison.plans if p.plan_type == "C")
        assert plan_c.cost == 0.0
        assert plan_c.incoming_needed == 0.0
        assert "plausibly protects" in plan_c.remaining_risk.lower()
        assert "guarantees" not in plan_c.remaining_risk.lower()
        action_c = plan_c.primary_action
        # First installment is $1600 (50% of $3200)
        assert action_c.amount == 1600.0
        assert verify_approval_hash(
            provided_hash=action_c.approval_hash,
            recipient=action_c.recipient,
            amount=action_c.amount,
            currency=action_c.currency,
            action_type=action_c.action_type,
            idempotency_key=action_c.idempotency_key
        ) is True

    finally:
        db.close()

