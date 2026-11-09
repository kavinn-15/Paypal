from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ==========================================
# Authentication & User Isolation Schemas
# ==========================================

class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    phone_number: Optional[str] = None
    phone_country_code: Optional[str] = Field(default="+91", max_length=8)
    currency: Optional[str] = Field(default="USD", max_length=10)
    preferred_currency: Optional[str] = Field(default="USD", max_length=10)
    country: Optional[str] = Field(default="US", max_length=50)
    business_type: Optional[str] = Field(default="Freelancer", max_length=50)
    timezone: str = Field(default="UTC", max_length=50)
    terms_accepted: Optional[bool] = Field(default=True)
    locale: Optional[str] = Field(default="en-US", max_length=10)
    region_preference_source: Optional[str] = Field(default="detected", max_length=30)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user_id: int
    email: str
    name: str
    currency: str
    preferred_currency: Optional[str] = "USD"
    locale: Optional[str] = "en-US"
    region_detection_enabled: Optional[bool] = True
    is_demo: bool
    country: Optional[str] = "US"
    business_type: Optional[str] = "Freelancer"
    email_verified: Optional[bool] = True
    phone_number: Optional[str] = None
    phone_country_code: Optional[str] = None
    phone_verified: Optional[bool] = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class EmailVerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    status: str = "success"
    message: str
    dev_reset_link: Optional[str] = None


class PasswordResetVerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class PasswordResetVerifyOTPResponse(BaseModel):
    status: str = "success"
    reset_token: str
    message: str


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=100)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=100)


class VerifyEmailRequest(BaseModel):
    token: str


class GoogleAuthUrlResponse(BaseModel):
    auth_url: str
    state: str
    client_id: Optional[str] = None


class GoogleTokenRequest(BaseModel):
    credential: str


class UserProfile(BaseModel):
    id: int
    name: str
    email: EmailStr
    currency: str
    timezone: str
    country: Optional[str] = "US"
    business_type: Optional[str] = "Freelancer"
    preferred_currency: Optional[str] = "USD"
    locale: Optional[str] = "en-US"
    region_detection_enabled: bool = True
    region_preference_source: str = "detected"
    region_preferences_updated_at: Optional[datetime] = None
    email_verified: bool = True
    email_verified_at: Optional[datetime] = None
    phone_number: Optional[str] = None
    phone_country_code: Optional[str] = None
    phone_verified: bool = False
    phone_verified_at: Optional[datetime] = None
    account_status: str = "active"
    is_demo: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Regional Preferences & Localization Schemas
# ==========================================

class RegionalPreferencesResponse(BaseModel):
    country: str
    country_name: str
    flag: str
    currency: str              # Base ledger currency
    preferred_currency: str    # Preferred display currency
    currency_symbol: str
    locale: str
    region_detection_enabled: bool
    region_preference_source: str  # "detected" | "manual"
    updated_at: Optional[datetime] = None


class RegionalPreferencesUpdate(BaseModel):
    country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    preferred_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    locale: Optional[str] = Field(default=None, max_length=10)
    region_detection_enabled: Optional[bool] = None


class RegionDetectionResponse(BaseModel):
    country: str
    country_name: str
    flag: str
    suggested_currency: str
    currency_name: str
    currency_symbol: str
    decimals: int
    dial_code: str
    locale: str
    detection_method: str
    confidence: float


class CountryItem(BaseModel):
    code: str
    name: str
    flag: str
    currency: str
    dial_code: str
    locale: str
    popular: bool = False


class CurrencyItem(BaseModel):
    code: str
    name: str
    symbol: str
    decimals: int


# ==========================================
# Phone & SMS Authentication Schemas
# ==========================================

class PhoneVerificationRequest(BaseModel):
    phone_number: str
    country_code: Optional[str] = "+91"


class PhoneVerifyOtpRequest(BaseModel):
    phone_number: str
    otp: str = Field(min_length=6, max_length=6)


class PhoneResendOtpRequest(BaseModel):
    phone_number: str


class PhoneLoginOtpRequest(BaseModel):
    phone_number: str


class PhoneLoginVerifyOtpRequest(BaseModel):
    phone_number: str
    otp: str = Field(min_length=6, max_length=6)


class PhoneLoginPasswordRequest(BaseModel):
    phone_number: str
    password: str


class PhonePasswordResetRequest(BaseModel):
    phone_number: str


class PhonePasswordResetVerifyRequest(BaseModel):
    phone_number: str
    otp: str = Field(min_length=6, max_length=6)


class PhoneChangeRequest(BaseModel):
    current_password: str
    new_phone_number: str
    country_code: Optional[str] = "+91"


class PhoneChangeVerifyRequest(BaseModel):
    new_phone_number: str
    otp: str = Field(min_length=6, max_length=6)


class PhoneAuthResponse(BaseModel):
    status: str = "success"
    message: str
    phone_number: Optional[str] = None
    cooldown_seconds: Optional[int] = None


# ==========================================
# PayPal Connection Schemas
# ==========================================

class PayPalConnectionStatus(BaseModel):
    connected: bool
    environment: str
    status: str
    client_id_preview: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    message: Optional[str] = None


class SandboxTestResponse(BaseModel):
    success: bool
    status_code: int
    environment: str
    message: str
    token_preview: Optional[str] = None


# ==========================================
# Client & Invoice Schemas
# ==========================================

class ClientBase(BaseModel):
    name: str
    email: str
    country: str = "US"
    typical_invoice_amount: float
    relationship_weight: float = 1.0


class ClientOut(ClientBase):
    id: int
    owner_id: int
    is_seeded: bool = False
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InvoiceBase(BaseModel):
    client_id: int
    amount: float
    currency: str = "USD"
    issue_date: datetime
    due_date: datetime
    status: str = "SENT"
    discount_applied: float = 0.0
    pay_link: Optional[str] = None


class InvoiceOut(InvoiceBase):
    id: int
    paypal_invoice_id: str
    paid_date: Optional[datetime] = None
    client_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class PaymentHistoryOut(BaseModel):
    id: int
    client_id: int
    amount: float
    due_date: datetime
    paid_date: datetime
    days_late: int
    source: str  # "paypal" | "seeded"
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Obligation & Financial Entry Schemas
# ==========================================

class ObligationCreate(BaseModel):
    payee_name: str
    payee_email: str
    amount: float = Field(gt=0)
    currency: str = "USD"
    due_date: datetime
    split_allowed: bool = False


class ObligationOut(ObligationCreate):
    id: int
    owner_id: int
    status: str
    model_config = ConfigDict(from_attributes=True)


class FinancialEntryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=10)
    entry_type: str = Field(pattern="^(income|expense|opening_balance|reserve|goal)$")
    category: str = Field(default="general")
    recurrence: str = Field(default="one_time")
    transaction_date: datetime
    status: str = Field(default="expected", pattern="^(confirmed|expected|estimated|simulated)$")
    notes: Optional[str] = None


class FinancialEntryOut(FinancialEntryCreate):
    id: int
    owner_id: int
    data_source: str
    reference_id: Optional[str] = None
    is_demo: bool = False
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FinancialSummaryResponse(BaseModel):
    currency: str
    current_confirmed_balance: float
    expected_inflows_30d: float
    expected_outflows_30d: float
    net_projected_30d: float
    confirmed_inflows_count: int
    expected_inflows_count: int
    pending_obligations_count: int
    emergency_reserve_target: float
    emergency_reserve_actual: float
    reserve_coverage_ratio: float
    currency_breakdown: Optional[Dict[str, float]] = None


class LedgerIntegrityReport(BaseModel):
    is_balanced: bool
    currency: str
    reconciled_balance: float
    opening_balance: float
    total_confirmed_inflows: float
    total_confirmed_outflows: float
    total_reserves: float
    total_adjustments: float
    discrepancy: float
    verified_entries_count: int
    unreconciled_items_count: int
    notes: List[str]


# ==========================================
# Forecasting & ML Prediction Schemas
# ==========================================

class DailyProjection(BaseModel):
    date: str
    starting_balance: float
    inflows: float
    outflows: float
    ending_balance: float
    is_shortfall: bool
    shortfall_amount: float
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None


class ClientPredictionOut(BaseModel):
    client_id: int
    client_name: str
    invoice_amount: float
    due_date: str
    expected_pay_date: str
    p_late: float
    expected_days_late: float
    ci_low_days: float
    ci_high_days: float
    is_cold_start: bool = False


class DriverContribution(BaseModel):
    client_id: int
    client_name: str
    invoice_amount: float
    expected_days_late: float
    marginal_shortfall_delta: float
    explanation: str


class ForecastRunResponse(BaseModel):
    run_id: str
    created_at: datetime
    obligation: Optional[ObligationOut] = None
    starting_balance: float
    horizon_days: int = 14
    first_shortfall_date: Optional[str] = None
    shortfall_amount: float
    p_shortfall: float
    min_projected_balance: float = 0.0
    expected_income_total: float = 0.0
    expected_expense_total: float = 0.0
    projections: List[DailyProjection]
    client_predictions: List[ClientPredictionOut]
    driver_ranking: List[DriverContribution]
    driver_explanation: str
    is_source_seeded: bool = True


class MultiHorizonForecastResponse(BaseModel):
    run_id: str
    starting_balance: float
    currency: str
    horizons: Dict[str, Dict[str, Any]]  # "7d", "30d", "60d", "90d"
    generated_at: datetime


# ==========================================
# What-If Simulation Schemas
# ==========================================

class SimulationScenarioRequest(BaseModel):
    run_name: str = "Custom Scenario"
    scenario_type: str = Field(
        pattern="^(client_delay_5d|client_delay_10d|partial_pay_50|dual_delay|emergency_expense|expense_increase|contractor_split)$"
    )
    delay_client_id: Optional[int] = None
    delay_days: Optional[int] = 5
    partial_pct: Optional[float] = 50.0
    emergency_amount: Optional[float] = 500.0
    contractor_split_pct: Optional[float] = 50.0


class WhatIfComparisonResponse(BaseModel):
    scenario_name: str
    scenario_type: str
    baseline: Dict[str, Any]
    simulated: Dict[str, Any]
    delta: Dict[str, Any]
    projections_baseline: List[DailyProjection]
    projections_simulated: List[DailyProjection]
    explanation: str


# ==========================================
# Rescue Plans & Action Schemas
# ==========================================

class ActionOut(BaseModel):
    id: int
    plan_id: Optional[int] = None
    action_type: str
    recipient: str
    amount: float
    currency: str
    state: str  # proposed | approved | executed | confirmed | failed
    idempotency_key: str
    approval_hash: str
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    paypal_ref: Optional[str] = None
    error_message: Optional[str] = None
    is_simulated: bool = False
    approval_version: int = 2
    obligation_id: Optional[int] = None
    payout_recipient_email: Optional[str] = None
    message_draft: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class RescuePlanOut(BaseModel):
    id: int
    run_id: str
    plan_type: str  # "A" | "B" | "C"
    name: str
    description: str
    cost: float
    cost_description: str
    incoming_needed: float
    shortfall_probability_after: float = 0.0
    selected_clients: List[Dict[str, Any]]
    rationale: str
    forecast_with_plan: List[DailyProjection]
    forecast_without_plan: List[DailyProjection]
    late_scenario: Dict[str, Any]
    remaining_risk: str
    primary_action: ActionOut


class PlansComparisonResponse(BaseModel):
    run_id: str
    obligation: ObligationOut
    shortfall_amount: float
    first_shortfall_date: Optional[str] = None
    tradeoff_summary: str
    plans: List[RescuePlanOut]
    starting_balance: float = 1800.0
    driver_rankings: List[DriverContribution] = Field(default_factory=list)
    p_shortfall: float = 0.0


class ApprovalRequest(BaseModel):
    approval_hash: str


class ExecuteRequest(BaseModel):
    idempotency_key: str


# ==========================================
# Negotiation Agent Schemas
# ==========================================

class NegotiationGenerateRequest(BaseModel):
    target_type: str = Field(pattern="^(client_discount|contractor_split)$")
    client_id: Optional[int] = None
    obligation_id: Optional[int] = None
    discount_pct: Optional[float] = 3.0
    split_pct: Optional[float] = 50.0


class NegotiationDraftOut(BaseModel):
    id: int
    target_type: str
    recipient_name: str
    recipient_email: str
    tone: str  # professional | friendly | urgent_respectful
    subject: str
    body: str
    offered_incentive: Optional[str] = None
    estimated_benefit: Optional[str] = None
    status: str  # draft | approved | sent | accepted | declined
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NegotiationDraftUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    offered_incentive: Optional[str] = None


class NegotiationTonesResponse(BaseModel):
    recipient_name: str
    recipient_email: str
    target_type: str
    context_summary: str
    options: List[NegotiationDraftOut]


# ==========================================
# Agent Orchestrator / Supervisor Schemas
# ==========================================

class AgentTraceStep(BaseModel):
    agent_name: str
    status: str  # completed | skipped | failed
    timestamp: str
    summary: str
    key_finding: str


class SupervisorRunResponse(BaseModel):
    run_id: str
    status: str
    obligation_evaluated: str
    shortfall_detected: bool
    shortfall_amount: float
    primary_risk_driver: str
    recommended_plan: str
    confidence_score: float
    steps_trace: List[AgentTraceStep]
    final_recommendation: str


# ==========================================
# Financial Resilience Score Schemas
# ==========================================

class ResilienceFactor(BaseModel):
    name: str
    score: float  # 0 to 100
    weight: float
    status: str  # strong | neutral | at_risk
    detail: str
    impact: str  # positive | negative | neutral


class ResilienceScoreResponse(BaseModel):
    overall_score: int  # 0 to 100
    category: str  # Excellent | Good | Moderate | Fragile | Critical
    reserve_runway_days: float
    debtor_reliability_pct: float
    obligation_load_ratio: float
    concentration_risk_hhi: float
    receivables_exposure_pct: float
    emergency_tolerance_usd: float
    improving_factors: List[str]
    reducing_factors: List[str]
    recommended_actions: List[str]
    factors: List[ResilienceFactor]


# ==========================================
# Audit & Webhook Schemas
# ==========================================

class AuditLogOut(BaseModel):
    id: int
    ts: datetime
    actor: str
    event: str
    payload: Dict[str, Any]
    prev_hash: str
    hash: str
    model_config = ConfigDict(from_attributes=True)


class AuditVerifyResponse(BaseModel):
    chain_valid: bool
    total_blocks: int
    genesis_valid: bool
    message: str
    corrupted_block_id: Optional[int] = None


class SimulateWebhookRequest(BaseModel):
    invoice_id: Optional[int] = None
    paypal_invoice_id: Optional[str] = None
    amount: Optional[float] = None


class WebhookEventOut(BaseModel):
    id: int
    paypal_event_id: str
    event_type: str
    verified: bool
    processed: bool
    received_at: datetime
    is_simulated: bool
    model_config = ConfigDict(from_attributes=True)
