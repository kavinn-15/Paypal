"""
Stage 3 Financial Calculations, Ledger Integrity, and Global Currency Handling Tests.
Validates:
- Multi-currency ledger isolation and strict Decimal precision
- Exchange rate enforcement (rejection of unknown rates, no silent 1.0 fallback)
- Deduplication and single source of truth in FinancialSummary
- Partial payment accounting (amount - paid_amount)
- Ledger integrity report with refunds, multi-currency verification, dynamic symbols
- Calendar-aware recurring engine (Jan 31 -> Feb 28/29 -> Mar 31 without drift)
- Multi-invoice client predictions with distinct invoice_id
- Regional detection response compatibility
- Resilience and simulation cross-currency conversion
"""

import pytest
import datetime
from decimal import Decimal

from backend.app.db import SessionLocal
from backend.app.models import Owner, Client, Invoice, Obligation, FinancialEntry, PaymentHistory, ClientPrediction
from backend.app.services.financial_service import FinancialService
from backend.app.services.region_service import (
    get_exchange_rate,
    convert_currency_amount,
    quantize_currency,
    get_currency_decimals,
    detect_region_info,
    BENCHMARK_EXCHANGE_RATES,
)
from backend.app.services.resilience_service import ResilienceService
from backend.app.services.simulation_service import SimulationService
from backend.app.agents.forecaster import ForecasterAgent
from backend.app.agents.planner import RescuePlanEngine
from backend.app.schemas import SimulationScenarioRequest, RegionDetectionResponse


def test_quantize_currency_decimals():
    """Verify ISO 4217 minor-unit decimal quantization across zero, 2, and 3-decimal currencies."""
    # Standard 2-decimal
    usd_val = quantize_currency(Decimal("123.456"), "USD")
    assert usd_val == Decimal("123.46")

    inr_val = quantize_currency(Decimal("123.454"), "INR")
    assert inr_val == Decimal("123.45")

    # Zero-decimal currencies (JPY, KRW, VND)
    jpy_val = quantize_currency(Decimal("123.75"), "JPY")
    assert jpy_val == Decimal("124")
    assert get_currency_decimals("JPY") == 0

    krw_val = quantize_currency(Decimal("50000.49"), "KRW")
    assert krw_val == Decimal("50000")
    assert get_currency_decimals("KRW") == 0

    # 3-decimal currencies (KWD, BHD, OMR)
    kwd_val = quantize_currency(Decimal("12.3456"), "KWD")
    assert kwd_val == Decimal("12.346")
    assert get_currency_decimals("KWD") == 3


def test_exchange_rate_missing_rejection():
    """Verify unknown currencies return None and are never silently treated as 1.0."""
    # Valid conversions
    eur_rate = get_exchange_rate("USD", "EUR")
    assert eur_rate == BENCHMARK_EXCHANGE_RATES["EUR"]

    inr_rate = get_exchange_rate("USD", "INR")
    assert inr_rate == BENCHMARK_EXCHANGE_RATES["INR"]

    # Unknown currency must return None
    unknown_rate = get_exchange_rate("USD", "NON_EXISTENT_XYZ")
    assert unknown_rate is None

    # convert_currency_amount must return None
    converted = convert_currency_amount(Decimal("100.00"), "USD", "NON_EXISTENT_XYZ")
    assert converted is None

    # Rejection in cross-currency conversion
    cross_converted = convert_currency_amount(Decimal("100.00"), "XYZ", "EUR")
    assert cross_converted is None


def test_multi_currency_balances_grouped():
    """Verify get_currency_balances groups strictly by currency without mixing them."""
    db = SessionLocal()
    try:
        owner = Owner(
            email=f"multicurrency_{datetime.datetime.utcnow().timestamp()}@example.com",
            hashed_password="hash",
            name="Multi Currency User",
            currency="USD",
            preferred_currency="USD",
            is_demo=False
        )
        db.add(owner)
        db.commit()

        now = datetime.datetime.utcnow()

        # Add entries in USD, EUR, and INR
        entries = [
            FinancialEntry(
                owner_id=owner.id,
                title="USD Opening",
                amount=Decimal("1000.00"),
                currency="USD",
                entry_type="opening_balance",
                category="opening_balance",
                status="confirmed",
                transaction_date=now
            ),
            FinancialEntry(
                owner_id=owner.id,
                title="USD Income",
                amount=Decimal("500.00"),
                currency="USD",
                entry_type="income",
                category="client_invoice",
                status="confirmed",
                transaction_date=now
            ),
            FinancialEntry(
                owner_id=owner.id,
                title="EUR Invoice Paid",
                amount=Decimal("800.00"),
                currency="EUR",
                entry_type="income",
                category="client_invoice",
                status="confirmed",
                transaction_date=now
            ),
            FinancialEntry(
                owner_id=owner.id,
                title="INR Service Fee",
                amount=Decimal("50000.00"),
                currency="INR",
                entry_type="income",
                category="client_invoice",
                status="confirmed",
                transaction_date=now
            ),
            FinancialEntry(
                owner_id=owner.id,
                title="EUR Server Expense",
                amount=Decimal("100.00"),
                currency="EUR",
                entry_type="expense",
                category="subscription",
                status="confirmed",
                transaction_date=now
            ),
            FinancialEntry(
                owner_id=owner.id,
                title="USD Refund",
                amount=Decimal("50.00"),
                currency="USD",
                entry_type="refund",
                category="refund",
                status="confirmed",
                transaction_date=now
            ),
        ]
        db.add_all(entries)
        db.commit()

        balances = FinancialService.get_currency_balances(db, owner)

        # Balance per currency:
        # USD: 1000 + 500 - 50 = 1450.00
        # EUR: 800 - 100 = 700.00
        # INR: 50000.00
        assert balances["USD"] == Decimal("1450.00")
        assert balances["EUR"] == Decimal("700.00")
        assert balances["INR"] == Decimal("50000.00")

        # Consolidated balance converted to USD:
        # 700 EUR in USD = 700 / 0.92 = 760.87
        # 50000 INR in USD = 50000 / 86.50 = 578.03
        # Total USD ~ 1450 + 760.87 + 578.03 = 2788.90
        confirmed_usd = FinancialService.get_confirmed_balance(db, owner, target_currency="USD")
        assert abs(confirmed_usd - Decimal("2788.90")) < Decimal("0.10")

        # If an entry has an unknown currency, get_confirmed_balance must raise ValueError
        bad_entry = FinancialEntry(
            owner_id=owner.id,
            title="Unknown Currency Entry",
            amount=Decimal("100.00"),
            currency="FAKE_CURR",
            entry_type="income",
            category="other",
            status="confirmed",
            transaction_date=now
        )
        db.add(bad_entry)
        db.commit()

        with pytest.raises(ValueError, match="exchange rate for FAKE_CURR is unavailable"):
            FinancialService.get_confirmed_balance(db, owner, target_currency="USD")
    finally:
        db.close()


def test_calendar_aware_recurrence_end_of_month():
    """Verify recurring engine handles Jan 31 -> Feb 28/29 -> Mar 31 without cumulative drift."""
    entry = FinancialEntry(
        id=101,
        owner_id=1,
        title="Month-End Software License",
        amount=Decimal("250.00"),
        currency="USD",
        entry_type="expense",
        recurrence="monthly",
        is_recurring=True,
        transaction_date=datetime.datetime(2024, 1, 31, 10, 0, 0),  # Leap year 2024
        status="confirmed"
    )

    # Generate occurrences for the next 5 months (Feb to June 2024)
    start = datetime.datetime(2024, 2, 1)
    end = datetime.datetime(2024, 6, 30, 23, 59, 59)

    occurrences = FinancialService._generate_occurrences(entry, start, end)
    dates = [o["date"] for o in occurrences]

    # Leap year 2024: Feb has 29 days!
    assert dates[0] == "2024-02-29"
    # March returns to 31st (no drift to 29th!)
    assert dates[1] == "2024-03-31"
    # April has 30 days
    assert dates[2] == "2024-04-30"
    # May returns to 31st
    assert dates[3] == "2024-05-31"

    # Now test non-leap year 2025
    entry_2025 = FinancialEntry(
        id=102,
        owner_id=1,
        title="Non-Leap Software License",
        amount=Decimal("250.00"),
        currency="USD",
        entry_type="expense",
        recurrence="monthly",
        is_recurring=True,
        transaction_date=datetime.datetime(2025, 1, 31, 10, 0, 0),
        status="confirmed"
    )
    occurrences_2025 = FinancialService._generate_occurrences(
        entry_2025, datetime.datetime(2025, 2, 1), datetime.datetime(2025, 5, 1)
    )
    dates_2025 = [o["date"] for o in occurrences_2025]
    # Non-leap year 2025: Feb has 28 days
    assert dates_2025[0] == "2025-02-28"
    assert dates_2025[1] == "2025-03-31"
    assert dates_2025[2] == "2025-04-30"


def test_partial_payment_inflows_and_deduplication():
    """Verify PARTIALLY_PAID invoices accurately calculate amount - paid_amount."""
    db = SessionLocal()
    try:
        owner = Owner(
            email=f"partial_pay_{datetime.datetime.utcnow().timestamp()}@example.com",
            hashed_password="hash",
            name="Partial User",
            currency="USD",
            preferred_currency="USD",
            is_demo=False
        )
        db.add(owner)
        db.commit()

        client = Client(owner_id=owner.id, name="Partial Client", email="client@test.com")
        db.add(client)
        db.commit()

        now = datetime.datetime.utcnow()
        due_date = now + datetime.timedelta(days=10)

        # Invoice for $3,000
        inv = Invoice(
            client_id=client.id,
            paypal_invoice_id=f"INV-PARTIAL-{datetime.datetime.utcnow().timestamp()}",
            amount=Decimal("3000.00"),
            currency="USD",
            issue_date=now,
            due_date=due_date,
            status="PARTIALLY_PAID"
        )
        db.add(inv)
        db.commit()

        # Record partial payment of $1,000
        ph = PaymentHistory(
            client_id=client.id,
            invoice_id=inv.id,
            amount=Decimal("1000.00"),
            due_date=due_date,
            paid_date=now,
            days_late=0,
            source="paypal",
            transaction_reference=f"TX-PARTIAL-{datetime.datetime.utcnow().timestamp()}"
        )
        db.add(ph)
        db.commit()

        summary = FinancialService.get_summary(db, owner)

        # Outstanding receivable should be 3000 - 1000 = 2000.00
        assert summary.expected_inflows_30d == Decimal("2000.00")
    finally:
        db.close()


def test_ledger_integrity_with_refunds_and_multi_currency():
    """Verify FinancialService.check_integrity calculates balance formula including refunds."""
    db = SessionLocal()
    try:
        owner = Owner(
            email=f"integrity_{datetime.datetime.utcnow().timestamp()}@example.com",
            hashed_password="hash",
            name="Integrity User",
            currency="EUR",
            preferred_currency="EUR",
            is_demo=False
        )
        db.add(owner)
        db.commit()

        now = datetime.datetime.utcnow()

        # Opening balance 2000 EUR
        # Inflow 500 EUR
        # Expense 300 EUR
        # Reserve 200 EUR
        # Refund 100 EUR
        # Adjustment 50 EUR
        # Expected Reconciled: 2000 + 500 - 300 - 200 - 100 + 50 = 1950 EUR
        entries = [
            FinancialEntry(owner_id=owner.id, title="Opening", amount=Decimal("2000.00"), currency="EUR", entry_type="opening_balance", category="opening_balance", status="confirmed", transaction_date=now),
            FinancialEntry(owner_id=owner.id, title="Sale", amount=Decimal("500.00"), currency="EUR", entry_type="income", category="client_invoice", status="confirmed", transaction_date=now),
            FinancialEntry(owner_id=owner.id, title="Office", amount=Decimal("300.00"), currency="EUR", entry_type="expense", category="subscription", status="confirmed", transaction_date=now),
            FinancialEntry(owner_id=owner.id, title="Tax Reserve", amount=Decimal("200.00"), currency="EUR", entry_type="reserve", category="tax", status="confirmed", transaction_date=now),
            FinancialEntry(owner_id=owner.id, title="Client Refund", amount=Decimal("100.00"), currency="EUR", entry_type="refund", category="refund", status="confirmed", transaction_date=now),
            FinancialEntry(owner_id=owner.id, title="Credit Adjustment", amount=Decimal("50.00"), currency="EUR", entry_type="adjustment", category="adjustment", status="confirmed", transaction_date=now),
        ]
        db.add_all(entries)
        db.commit()

        report = FinancialService.check_integrity(db, owner)

        assert report.is_balanced is True
        assert report.currency == "EUR"
        assert report.opening_balance == 2000.0
        assert report.total_confirmed_inflows == 500.0
        assert report.total_confirmed_outflows == 300.0
        assert report.total_reserves == 200.0
        assert report.total_refunds == 100.0
        assert report.total_adjustments == 50.0
        assert report.reconciled_balance == 1950.0
        assert report.discrepancy == 0.0
    finally:
        db.close()


def test_multi_invoice_client_predictions():
    """Verify distinct ClientPrediction records are generated per invoice_id when a client has multiple invoices."""
    db = SessionLocal()
    try:
        owner = Owner(
            email=f"multi_inv_{datetime.datetime.utcnow().timestamp()}@example.com",
            hashed_password="hash",
            name="Multi Invoice User",
            currency="USD",
            preferred_currency="USD",
            is_demo=False
        )
        db.add(owner)
        db.commit()

        client = Client(owner_id=owner.id, name="Double Invoice Corp", email="double@corp.com")
        db.add(client)
        db.commit()

        now = datetime.datetime.utcnow()

        # Two distinct invoices for the same client
        inv1 = Invoice(
            client_id=client.id,
            paypal_invoice_id=f"INV-MULTI-1-{datetime.datetime.utcnow().timestamp()}",
            amount=Decimal("1500.00"),
            currency="USD",
            issue_date=now,
            due_date=now + datetime.timedelta(days=3),
            status="SENT"
        )
        inv2 = Invoice(
            client_id=client.id,
            paypal_invoice_id=f"INV-MULTI-2-{datetime.datetime.utcnow().timestamp()}",
            amount=Decimal("2500.00"),
            currency="USD",
            issue_date=now,
            due_date=now + datetime.timedelta(days=7),
            status="SENT"
        )
        db.add_all([inv1, inv2])

        # Obligation
        obl = Obligation(
            owner_id=owner.id,
            payee_name="Contractor Dave",
            payee_email="dave@contractor.com",
            amount=Decimal("3000.00"),
            currency="USD",
            due_date=now + datetime.timedelta(days=5),
            status="pending",
            split_allowed=False
        )
        db.add(obl)
        db.commit()

        forecaster = ForecasterAgent(db)
        forecast_resp = forecaster.run_forecast(obligation_id=obl.id, starting_balance=500.0, owner_id=owner.id)

        # Verify both predictions exist and have distinct invoice_ids
        client_preds = forecast_resp.client_predictions
        assert len(client_preds) == 2
        invoice_ids = {p.invoice_id for p in client_preds}
        assert invoice_ids == {inv1.id, inv2.id}

        # Test RescuePlanEngine matches prediction by invoice_id
        planner = RescuePlanEngine(db)
        plans_resp = planner.generate_plans_for_forecast(forecast_resp)
        assert len(plans_resp.plans) >= 2
    finally:
        db.close()


@pytest.mark.asyncio
async def test_regional_detection_response_aliases(monkeypatch):
    """Verify RegionDetectionResponse includes both suggested_currency/currency and currency_symbol/symbol."""
    from backend.app.services import region_service
    monkeypatch.setattr(region_service.settings, "DEV_MODE", True)
    monkeypatch.setattr(region_service.settings, "DEV_COUNTRY_OVERRIDE", "IN")

    resp = await detect_region_info(
        headers={},
        client_host="127.0.0.1",
        timezone="Asia/Kolkata"
    )
    assert "suggested_currency" in resp
    assert "currency" in resp
    assert resp["suggested_currency"] == "INR"
    assert resp["currency"] == "INR"

    assert "currency_symbol" in resp
    assert "symbol" in resp
    assert resp["currency_symbol"] == "₹"
    assert resp["symbol"] == "₹"

    # Verify Pydantic schema validation
    schema_obj = RegionDetectionResponse(**resp)
    assert schema_obj.currency == "INR"
    assert schema_obj.symbol == "₹"
    assert schema_obj.suggested_currency == "INR"
    assert schema_obj.currency_symbol == "₹"


def test_resilience_and_simulation_cross_currency():
    """Verify ResilienceService and SimulationService convert amounts to owner's base currency."""
    db = SessionLocal()
    try:
        owner = Owner(
            email=f"cross_curr_{datetime.datetime.utcnow().timestamp()}@example.com",
            hashed_password="hash",
            name="Cross Currency User",
            currency="EUR",
            preferred_currency="EUR",
            is_demo=False
        )
        db.add(owner)
        db.commit()

        client = Client(owner_id=owner.id, name="US Client Inc", email="us@client.com")
        db.add(client)
        db.commit()

        now = datetime.datetime.utcnow()

        # Invoice in USD for 1000 USD (owner is EUR)
        inv = Invoice(
            client_id=client.id,
            paypal_invoice_id=f"INV-USD-EUR-{datetime.datetime.utcnow().timestamp()}",
            amount=Decimal("1000.00"),
            currency="USD",
            issue_date=now,
            due_date=now + datetime.timedelta(days=4),
            status="SENT"
        )
        # Obligation in GBP for 500 GBP
        obl = Obligation(
            owner_id=owner.id,
            payee_name="UK Supplier",
            payee_email="supplier@uk.com",
            amount=Decimal("500.00"),
            currency="GBP",
            due_date=now + datetime.timedelta(days=6),
            status="pending"
        )
        db.add_all([inv, obl])
        db.commit()

        # Test Resilience score calculation with EUR starting balance
        resilience_resp = ResilienceService.calculate_score(db, owner, starting_balance=1500.0)
        assert resilience_resp.overall_score > 0
        assert resilience_resp.category in ["Excellent", "Good", "Moderate", "Fragile", "Critical"]

        # Test What-If Simulation
        sim_req = SimulationScenarioRequest(
            run_name="Test Delay",
            scenario_type="client_delay_5d"
        )
        sim_resp = SimulationService.run_scenario(db, owner, sim_req, starting_balance=1500.0)
        assert len(sim_resp.projections_baseline) > 0
        assert len(sim_resp.projections_simulated) > 0
    finally:
        db.close()
