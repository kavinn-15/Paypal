import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, JSON, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from backend.app.db import Base


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    clients = relationship("Client", back_populates="owner", cascade="all, delete-orphan")
    obligations = relationship("Obligation", back_populates="owner", cascade="all, delete-orphan")
    paypal_connection = relationship("PayPalConnection", back_populates="owner", uselist=False, cascade="all, delete-orphan")


class PayPalConnection(Base):
    __tablename__ = "paypal_connections"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, unique=True)
    environment = Column(String(50), default="sandbox", nullable=False)  # sandbox only
    status = Column(String(50), default="connected", nullable=False)  # connected | disconnected | error
    last_checked_at = Column(DateTime, nullable=True)
    client_id_preview = Column(String(50), nullable=True)

    owner = relationship("Owner", back_populates="paypal_connection")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    country = Column(String(10), nullable=False, default="US")
    typical_invoice_amount = Column(Float, nullable=False, default=1000.0)
    relationship_weight = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    owner = relationship("Owner", back_populates="clients")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")
    payment_history = relationship("PaymentHistory", back_populates="client", cascade="all, delete-orphan")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    paypal_invoice_id = Column(String(255), unique=True, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    issue_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=False, index=True)
    paid_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="SENT")  # DRAFT | SENT | PAID | CANCELLED
    discount_applied = Column(Float, default=0.0, nullable=False)  # e.g. 3.0 for 3%
    pay_link = Column(String(1024), nullable=True)

    client = relationship("Client", back_populates="invoices")
    history_records = relationship("PaymentHistory", back_populates="invoice")


class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Float, nullable=False)
    due_date = Column(DateTime, nullable=False)
    paid_date = Column(DateTime, nullable=False)
    days_late = Column(Integer, nullable=False)
    source = Column(String(50), nullable=False, default="paypal")  # "paypal" | "seeded"

    client = relationship("Client", back_populates="payment_history")
    invoice = relationship("Invoice", back_populates="history_records")


class Obligation(Base):
    __tablename__ = "obligations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    payee_name = Column(String(255), nullable=False)
    payee_email = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    due_date = Column(DateTime, nullable=False, index=True)
    split_allowed = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending | split_agreed | paid

    owner = relationship("Owner", back_populates="obligations")


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    obligation_id = Column(Integer, ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    starting_balance = Column(Float, nullable=False, default=0.0)
    assumptions = Column(JSON, nullable=False, default=dict)
    projections = Column(JSON, nullable=False, default=list)
    first_shortfall_date = Column(DateTime, nullable=True)
    shortfall_amount = Column(Float, default=0.0, nullable=False)
    p_shortfall = Column(Float, default=0.0, nullable=False)
    driver_explanation = Column(Text, nullable=True)


class ClientPrediction(Base):
    __tablename__ = "client_predictions"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    expected_pay_date = Column(DateTime, nullable=False)
    p_late = Column(Float, nullable=False)
    expected_days_late = Column(Float, nullable=False)
    ci_low = Column(Float, nullable=False)
    ci_high = Column(Float, nullable=False)

    client = relationship("Client")


class RescuePlan(Base):
    __tablename__ = "rescue_plans"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), nullable=False, index=True)
    plan_type = Column(String(10), nullable=False)  # "A" | "B" | "C"
    details = Column(JSON, nullable=False, default=dict)
    cost = Column(Float, nullable=False, default=0.0)
    incoming_needed = Column(Float, nullable=False, default=0.0)
    selected_clients = Column(JSON, nullable=False, default=list)
    rationale = Column(Text, nullable=False)
    forecast_with_plan = Column(JSON, nullable=False, default=list)
    forecast_without_plan = Column(JSON, nullable=False, default=list)
    late_scenario = Column(JSON, nullable=False, default=dict)
    remaining_risk = Column(Text, nullable=False)

    actions = relationship("Action", back_populates="plan", cascade="all, delete-orphan")


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("rescue_plans.id", ondelete="CASCADE"), nullable=True)
    action_type = Column(String(100), nullable=False)  # SEND_REMINDER | APPLY_DISCOUNT | SCHEDULE_PAYOUT_SPLIT
    recipient = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    state = Column(String(50), nullable=False, default="proposed")  # proposed | approved | executed | confirmed | failed
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    approval_hash = Column(String(255), nullable=False)
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    paypal_ref = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    is_simulated = Column(Boolean, default=False, nullable=False)

    plan = relationship("RescuePlan", back_populates="actions")
    messages = relationship("Message", back_populates="action", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(Integer, ForeignKey("actions.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    body = Column(Text, nullable=False)
    approval_status = Column(String(50), default="draft", nullable=False)  # draft | approved | sent

    action = relationship("Action", back_populates="messages")
    client = relationship("Client")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    actor = Column(String(100), nullable=False)  # owner | system | webhook | agent
    event = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    prev_hash = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False, index=True)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    paypal_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    verified = Column(Boolean, default=False, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    processed = Column(Boolean, default=False, nullable=False, index=True)
    received_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_simulated = Column(Boolean, default=False, nullable=False)

