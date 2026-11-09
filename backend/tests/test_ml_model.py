import pytest
from datetime import datetime, timedelta, timezone
from backend.app.models import PaymentHistory
from backend.app.ml.model import PaymentDelayModel
from backend.app.ml.simulation import (
    project_cashflow_timeline, run_monte_carlo_simulation, compute_driver_ranking
)


def test_model_shrinkage_and_intervals():
    now = datetime.now(timezone.utc)
    records = []

    # Population: Client 1 has 10 records with mean delay = 2 days
    for i in range(10):
        records.append(PaymentHistory(
            client_id=1,
            amount=1000.0,
            due_date=now - timedelta(days=i*30),
            paid_date=now - timedelta(days=i*30 - 2),
            days_late=2,
            source="seeded"
        ))

    # Client 2 has only 1 record with delay = 20 days (small sample)
    records.append(PaymentHistory(
        client_id=2,
        amount=2000.0,
        due_date=now - timedelta(days=30),
        paid_date=now - timedelta(days=10),
        days_late=20,
        source="seeded"
    ))

    model = PaymentDelayModel(shrinkage_strength=5.0)
    model.fit(records)

    pred1 = model.predict_client_delay(client_id=1, invoice_amount=1000.0, due_date=now)
    pred2 = model.predict_client_delay(client_id=2, invoice_amount=2000.0, due_date=now)

    # Client 1 with 10 records: mean delay stays very close to 2.0
    assert abs(pred1["expected_days_late"] - 2.0) < 1.0

    # Client 2 with 1 record (delay=20): Empirical Bayes pulls it substantially towards population mean (< 20)
    assert pred2["expected_days_late"] < 15.0
    # Small sample uncertainty widens the interval
    assert (pred2["ci_high"] - pred2["ci_low"]) > (pred1["ci_high"] - pred1["ci_low"])


def test_project_cashflow_timeline_shortfall_detection():
    now = datetime(2026, 11, 10, 12, 0, 0)
    starting_balance = 1800.0

    # Inflow: $2,000 arriving on Nov 16 (after Friday obligation)
    inflows = [{
        "amount": 2000.0,
        "expected_pay_date": datetime(2026, 11, 16, 12, 0, 0)
    }]

    # Contractor Obligation: $3,200 due on Nov 13
    obligations = [{
        "amount": 3200.0,
        "due_date": datetime(2026, 11, 13, 12, 0, 0),
        "payee_name": "Marcus Sterling"
    }]

    projections, first_shortfall_date, shortfall_amount = project_cashflow_timeline(
        starting_balance=starting_balance,
        predicted_inflows=inflows,
        obligations=obligations,
        start_date=now,
        end_date=datetime(2026, 11, 18, 12, 0, 0)
    )

    # Starting balance $1800 - obligation $3200 = shortfall $1400 on Nov 13
    assert first_shortfall_date == "2026-11-13"
    assert shortfall_amount == 1400.0

    # Verify daily ending balances
    nov_12 = next(p for p in projections if p["date"] == "2026-11-12")
    assert nov_12["ending_balance"] == 1800.0
    assert nov_12["is_shortfall"] is False

    nov_13 = next(p for p in projections if p["date"] == "2026-11-13")
    assert nov_13["ending_balance"] == -1400.0
    assert nov_13["is_shortfall"] is True

    nov_16 = next(p for p in projections if p["date"] == "2026-11-16")
    # Inflow $2000 arrives, balance rises from -1400 to +600
    assert nov_16["ending_balance"] == 600.0

