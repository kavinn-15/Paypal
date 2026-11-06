from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class OwnerBase(BaseModel):
    name: str
    email: EmailStr


class OwnerOut(OwnerBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


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


class ClientBase(BaseModel):
    name: str
    email: str
    country: str = "US"
    typical_invoice_amount: float
    relationship_weight: float = 1.0


class ClientOut(ClientBase):
    id: int
    owner_id: int
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
    obligation: ObligationOut
    starting_balance: float
    first_shortfall_date: Optional[str] = None
    shortfall_amount: float
    p_shortfall: float
    projections: List[DailyProjection]
    client_predictions: List[ClientPredictionOut]
    driver_ranking: List[DriverContribution]
    driver_explanation: str
    is_source_seeded: bool = True


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


class ApprovalRequest(BaseModel):
    approval_hash: str


class ExecuteRequest(BaseModel):
    idempotency_key: str


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

