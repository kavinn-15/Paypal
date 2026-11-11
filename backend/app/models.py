import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Numeric, Float, Boolean, DateTime, Date, ForeignKey, JSON, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from backend.app.db import Base


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    currency = Column(String(10), default="USD", nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    country = Column(String(50), nullable=True, default="US")
    business_type = Column(String(50), nullable=True, default="Freelancer")
    preferred_currency = Column(String(10), nullable=True, default="USD")
    locale = Column(String(10), default="en-US", nullable=False)
    region_detection_enabled = Column(Boolean, default=True, nullable=False)
    region_preference_source = Column(String(30), default="detected", nullable=False)  # "detected" | "manual"
    region_preferences_updated_at = Column(DateTime, nullable=True)
    email_verified = Column(Boolean, default=True, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    phone_number = Column(String(32), unique=True, index=True, nullable=True)
    phone_country_code = Column(String(8), nullable=True, default="+91")
    phone_verified = Column(Boolean, default=False, nullable=False)
    phone_verified_at = Column(DateTime, nullable=True)
    account_status = Column(String(20), default="active", nullable=False)
    password_reset_token = Column(String(255), nullable=True, index=True)
    reset_token_expires_at = Column(DateTime, nullable=True)
    email_verification_token = Column(String(255), nullable=True, index=True)
    is_demo = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    terms_accepted = Column(Boolean, default=False, nullable=False)
    terms_accepted_at = Column(DateTime, nullable=True)
    token_version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    clients = relationship("Client", back_populates="owner", cascade="all, delete-orphan")
    obligations = relationship("Obligation", back_populates="owner", cascade="all, delete-orphan")
    paypal_connection = relationship("PayPalConnection", back_populates="owner", uselist=False, cascade="all, delete-orphan")
    financial_entries = relationship("FinancialEntry", back_populates="owner", cascade="all, delete-orphan")
    simulations = relationship("SimulationRun", back_populates="owner", cascade="all, delete-orphan")
    negotiation_drafts = relationship("NegotiationDraft", back_populates="owner", cascade="all, delete-orphan")
    forecasts = relationship("Forecast", back_populates="owner", cascade="all, delete-orphan")
    rescue_plans = relationship("RescuePlan", back_populates="owner", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="owner", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="owner", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="owner", cascade="all, delete-orphan")
    otps = relationship("EmailOTP", back_populates="owner", cascade="all, delete-orphan")
    phone_otps = relationship("PhoneOTP", back_populates="owner", cascade="all, delete-orphan")
    oauth_identities = relationship("OAuthIdentity", back_populates="owner", cascade="all, delete-orphan")


class PayPalConnection(Base):
    __tablename__ = "paypal_connections"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, unique=True)
    environment = Column(String(50), default="sandbox", nullable=False)  # sandbox only
    status = Column(String(50), default="connected", nullable=False)  # connected | disconnected | error
    last_checked_at = Column(DateTime, nullable=True)
    client_id_preview = Column(String(50), nullable=True)
    connection_type = Column(String(50), default="shared_sandbox", nullable=False)  # shared_sandbox | merchant_oauth
    is_shared_sandbox = Column(Boolean, default=True, nullable=False)
    merchant_id = Column(String(100), nullable=True)
    merchant_email = Column(String(255), nullable=True)
    webhook_id = Column(String(100), nullable=True)

    owner = relationship("Owner", back_populates="paypal_connection")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    country = Column(String(10), nullable=False, default="US")
    typical_invoice_amount = Column(Numeric(12, 2), nullable=False, default=Decimal("1000.00"))
    relationship_weight = Column(Float, nullable=False, default=1.0)
    is_seeded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="clients")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    payment_history = relationship("PaymentHistory", back_populates="client", cascade="all, delete-orphan")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    paypal_invoice_id = Column(String(255), unique=True, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    issue_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=False, index=True)
    paid_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="SENT")  # DRAFT | SENT | PAID | CANCELLED
    discount_applied = Column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)  # e.g. 3.00 for 3%
    pay_link = Column(String(1024), nullable=True)
    is_simulated_paid = Column(Boolean, default=False, nullable=False)
    is_seeded = Column(Boolean, default=False, nullable=False)
    invoice_number = Column(String(100), nullable=True)
    provider_status = Column(String(50), nullable=True)  # DRAFT | SENT | PAID | CANCELLED | REFUNDED

    client = relationship("Client", back_populates="invoices")
    history_records = relationship("PaymentHistory", back_populates="invoice")


class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    due_date = Column(DateTime, nullable=False)
    paid_date = Column(DateTime, nullable=False)
    days_late = Column(Integer, nullable=False)
    source = Column(String(50), nullable=False, default="paypal")  # "paypal" | "seeded"
    transaction_reference = Column(String(255), unique=True, nullable=True, index=True)

    client = relationship("Client", back_populates="payment_history")
    invoice = relationship("Invoice", back_populates="history_records")


class Obligation(Base):
    __tablename__ = "obligations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    payee_name = Column(String(255), nullable=False)
    payee_email = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    due_date = Column(DateTime, nullable=False, index=True)
    split_allowed = Column(Boolean, default=False, nullable=False)
    split_consent_recorded = Column(Boolean, default=False, nullable=False)
    split_consent_source = Column(String(100), nullable=True)  # written_agreement | contractor_email | demo_consent
    split_consent_timestamp = Column(DateTime, nullable=True)
    split_consent_is_simulated = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending | split_agreed | paid
    is_demo = Column(Boolean, default=False, nullable=False)

    owner = relationship("Owner", back_populates="obligations")


class FinancialEntry(Base):
    """
    Unified financial timeline entry for all confirmed, expected, estimated, and simulated cash flows.
    Supports rent, salary, contractor, subscription, tax, loan, goals, reserves, opening balance.
    """
    __tablename__ = "financial_entries"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_id = Column(String(255), unique=True, nullable=True, index=True)
    title = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    entry_type = Column(String(50), nullable=False)  # opening_balance | confirmed_income | confirmed_expense | expected_income | expected_expense | estimated_income | simulated_income | reserve | refund | adjustment
    category = Column(String(100), nullable=False)  # client_invoice, rent, salary, contractor, subscription, loan, tax, emergency, reserve_fund, financial_goal
    recurrence = Column(String(50), default="one_time", nullable=False)  # one_time | daily | weekly | monthly | quarterly | annual
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurrence_end_date = Column(DateTime, nullable=True)
    is_cancelled = Column(Boolean, default=False, nullable=False)
    parent_entry_id = Column(Integer, ForeignKey("financial_entries.id", ondelete="SET NULL"), nullable=True)
    reconciled = Column(Boolean, default=False, nullable=False)
    transaction_date = Column(DateTime, nullable=False, index=True)
    status = Column(String(50), default="expected", nullable=False)  # confirmed | expected | estimated | simulated
    data_source = Column(String(50), default="manual", nullable=False)  # paypal | manual | bank_sync | simulation
    reference_id = Column(String(255), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    is_demo = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="financial_entries")


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    obligation_id = Column(Integer, ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    starting_balance = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    horizon_days = Column(Integer, default=14, nullable=False)
    assumptions = Column(JSON, nullable=False, default=dict)
    projections = Column(JSON, nullable=False, default=list)
    first_shortfall_date = Column(DateTime, nullable=True)
    shortfall_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    p_shortfall = Column(Float, default=0.0, nullable=False)
    min_projected_balance = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    expected_income_total = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    expected_expense_total = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    driver_explanation = Column(Text, nullable=True)
    is_demo = Column(Boolean, default=False, nullable=False)

    owner = relationship("Owner", back_populates="forecasts")


class ClientPrediction(Base):
    __tablename__ = "client_predictions"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True, index=True)
    expected_pay_date = Column(DateTime, nullable=False)
    p_late = Column(Float, nullable=False)
    expected_days_late = Column(Float, nullable=False)
    ci_low = Column(Float, nullable=False)
    ci_high = Column(Float, nullable=False)
    is_cold_start = Column(Boolean, default=False, nullable=False)

    client = relationship("Client")
    invoice = relationship("Invoice")


class RescuePlan(Base):
    __tablename__ = "rescue_plans"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id = Column(String(100), nullable=False, index=True)
    plan_type = Column(String(10), nullable=False)  # "A" | "B" | "C"
    details = Column(JSON, nullable=False, default=dict)
    cost = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    incoming_needed = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    shortfall_probability_after = Column(Float, default=0.0, nullable=False)
    selected_clients = Column(JSON, nullable=False, default=list)
    rationale = Column(Text, nullable=False)
    forecast_with_plan = Column(JSON, nullable=False, default=list)
    forecast_without_plan = Column(JSON, nullable=False, default=list)
    late_scenario = Column(JSON, nullable=False, default=dict)
    remaining_risk = Column(Text, nullable=False)
    is_demo = Column(Boolean, default=False, nullable=False)

    owner = relationship("Owner", back_populates="rescue_plans")
    actions = relationship("Action", back_populates="plan", cascade="all, delete-orphan")


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    plan_id = Column(Integer, ForeignKey("rescue_plans.id", ondelete="CASCADE"), nullable=True)
    action_type = Column(String(100), nullable=False)  # SEND_REMINDER | APPLY_DISCOUNT | SCHEDULE_PAYOUT_SPLIT
    recipient = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    state = Column(String(50), nullable=False, default="proposed")  # proposed | approved | executed | confirmed | failed
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    approval_hash = Column(String(255), nullable=False)
    approved_payload_hash = Column(String(64), nullable=True)  # SHA-256 of exact canonical payload
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    paypal_ref = Column(String(255), nullable=True)
    provider_request_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    execution_error = Column(Text, nullable=True)
    is_simulated = Column(Boolean, default=False, nullable=False)
    is_seeded = Column(Boolean, default=False, nullable=False)
    is_demo = Column(Boolean, default=False, nullable=False)
    approval_version = Column(Integer, default=2, nullable=False)
    obligation_id = Column(Integer, ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True)
    payout_recipient_email = Column(String(255), nullable=True)

    owner = relationship("Owner", back_populates="actions")
    plan = relationship("RescuePlan", back_populates="actions")
    messages = relationship("Message", back_populates="action", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "approval_version" not in kwargs:
            kwargs["approval_version"] = 2
        super().__init__(**kwargs)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(Integer, ForeignKey("actions.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    body = Column(Text, nullable=False)
    approval_status = Column(String(50), default="draft", nullable=False)  # draft | approved | sent

    action = relationship("Action", back_populates="messages")
    client = relationship("Client")


class NegotiationDraft(Base):
    """
    Dedicated financial negotiation drafts (early payment incentive or contractor split),
    with multiple tone styles (Professional, Friendly, Urgent-Respectful).
    """
    __tablename__ = "negotiation_drafts"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    obligation_id = Column(Integer, ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True)
    target_type = Column(String(50), nullable=False)  # client_discount | contractor_split
    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    tone = Column(String(50), default="professional", nullable=False)  # professional | friendly | urgent_respectful
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    offered_incentive = Column(String(255), nullable=True)
    estimated_benefit = Column(String(255), nullable=True)
    status = Column(String(50), default="draft", nullable=False)  # draft | approved | sent | accepted | declined
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="negotiation_drafts")


class SimulationRun(Base):
    """
    What-If simulation engine run records (never modifies real financial tables).
    """
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    run_name = Column(String(255), nullable=False)
    scenario_type = Column(String(100), nullable=False)  # client_delay_5d | client_delay_10d | partial_pay_50 | dual_delay | emergency_expense | expense_increase | contractor_split
    parameters = Column(JSON, nullable=False, default=dict)
    baseline_metrics = Column(JSON, nullable=False, default=dict)
    simulated_metrics = Column(JSON, nullable=False, default=dict)
    delta_metrics = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="simulations")


class AgentWorkflowRun(Base):
    """
    Supervisor / Orchestrator trace of all autonomous agent steps, validations, and recommendations.
    """
    __tablename__ = "agent_workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(50), default="running", nullable=False)  # running | completed | failed | awaiting_approval
    steps_trace = Column(JSON, nullable=False, default=list)
    selected_plan = Column(String(10), nullable=True)
    final_recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    ts = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    actor = Column(String(100), nullable=False)  # owner | system | webhook | agent
    event = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    prev_hash = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False, index=True)

    owner = relationship("Owner", back_populates="audit_logs")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    paypal_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    verified = Column(Boolean, default=False, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    processed = Column(Boolean, default=False, nullable=False, index=True)
    processing_state = Column(String(50), default="received", nullable=False, index=True)  # received | processing | processed | quarantined | failed | dead_letter
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    error_details = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    reconciliation_status = Column(String(50), default="pending", nullable=False)  # pending | matched | manual_review_required | reconciled | payout_failed | unverified_signature
    received_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_simulated = Column(Boolean, default=False, nullable=False)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(100), nullable=True)


class PayPalWebhookRegistration(Base):
    """
    Persisted PayPal webhook registrations for verification and lifecycle tracking.
    """
    __tablename__ = "paypal_webhook_registrations"

    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(String(100), unique=True, nullable=False, index=True)
    url = Column(String(500), nullable=False)
    environment = Column(String(50), default="sandbox", nullable=False)
    status = Column(String(50), default="active", nullable=False)  # active | disabled | deleted
    event_types = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_verified_at = Column(DateTime, nullable=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id = Column(String(100), nullable=True, index=True)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="refresh_tokens")


class ExchangeRate(Base):
    """
    Authoritative currency exchange rates. Prevents illegal direct cross-currency arithmetic.
    """
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String(10), nullable=False, index=True)
    to_currency = Column(String(10), nullable=False, index=True)
    rate = Column(Numeric(18, 6), nullable=False)
    source = Column(String(100), default="ecb_or_bank_ref", nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("from_currency", "to_currency", name="uq_from_to_currency"),)


class EmailOTP(Base):
    """
    Cryptographic single-use 6-digit email OTPs.
    Only keyed HMAC hashes are stored; plain OTPs are never stored or logged.
    """
    __tablename__ = "email_otps"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    otp_hash = Column(String(255), nullable=False)
    purpose = Column(String(50), nullable=False)  # "email_verification" or "password_reset"
    expires_at = Column(DateTime, nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="otps")


class OAuthIdentity(Base):
    """
    Federated OAuth identities (Google, Microsoft) securely linked to an Owner account.
    Stores stable provider subject identifier ('sub').
    """
    __tablename__ = "oauth_identities"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # "google", "microsoft"
    provider_user_id = Column(String(255), nullable=False)  # Google sub
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
        Index("ix_oauth_identities_provider_sub", "provider", "provider_user_id"),
    )

    owner = relationship("Owner", back_populates="oauth_identities")


class PhoneOTP(Base):
    """
    Cryptographic single-use 6-digit SMS phone OTPs.
    Only keyed HMAC hashes are stored; plain OTPs are never stored or logged.
    """
    __tablename__ = "phone_otps"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True, index=True)
    phone_number = Column(String(32), nullable=False, index=True)
    otp_hash = Column(String(255), nullable=False)
    purpose = Column(String(50), nullable=False)  # "phone_verification", "phone_login", "password_reset", "phone_change"
    expires_at = Column(DateTime, nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_phone_otps_phone_purpose", "phone_number", "purpose"),
    )

    owner = relationship("Owner", back_populates="phone_otps")


class RateLimitAttempt(Base):
    """
    Database-backed rate limit tracker across multiple workers and restarts.
    """
    __tablename__ = "rate_limit_attempts"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, index=True)
    attempt_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)


class ConsumedToken(Base):
    """
    Database-backed single-use token tracking (e.g. password reset jti) across workers.
    """
    __tablename__ = "consumed_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(255), unique=True, nullable=False, index=True)
    consumed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class OAuthState(Base):
    """
    Cryptographically secure, persisted, single-use OAuth 2.0 / PKCE state records.
    """
    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(255), unique=True, nullable=False, index=True)
    code_verifier = Column(String(255), nullable=True)
    consumed = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


