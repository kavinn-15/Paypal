export interface Owner {
  id: number;
  name: string;
  email: string;
  currency?: string;
  preferred_currency?: string;
  country?: string;
  business_type?: string;
  email_verified?: boolean;
  account_status?: string;
  is_demo?: boolean;
}

export interface UserProfile {
  id: number;
  name: string;
  email: string;
  currency: string;
  preferred_currency?: string;
  country?: string;
  business_type?: string;
  email_verified?: boolean;
  account_status?: string;
  timezone: string;
  is_demo: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  user_id: number;
  email: string;
  name: string;
  currency: string;
  country?: string;
  business_type?: string;
  email_verified?: boolean;
  is_demo: boolean;
}

export interface ForgotPasswordResponse {
  status: string;
  message: string;
  dev_reset_link?: string;
}

export interface Obligation {
  id: number;
  owner_id: number;
  payee_name: string;
  payee_email: string;
  amount: number;
  currency: string;
  due_date: string;
  split_allowed: boolean;
  status: string;
}

export interface DailyProjection {
  date: string;
  starting_balance: number;
  inflows: number;
  outflows: number;
  ending_balance: number;
  is_shortfall: boolean;
  shortfall_amount: number;
  ci_low?: number;
  ci_high?: number;
}

export interface ClientPrediction {
  client_id: number;
  client_name: string;
  invoice_amount: number;
  due_date: string;
  expected_pay_date: string;
  p_late: number;
  expected_days_late: number;
  ci_low_days: number;
  ci_high_days: number;
  is_cold_start?: boolean;
}

export interface DriverContribution {
  client_id: number;
  client_name: string;
  invoice_amount: number;
  expected_days_late: number;
  marginal_shortfall_delta: number;
  explanation: string;
}

export interface Action {
  id: number;
  plan_id?: number;
  action_type: string;
  recipient: string;
  amount: number;
  currency: string;
  state: "proposed" | "approved" | "executed" | "confirmed" | "failed";
  idempotency_key: string;
  approval_hash: string;
  approved_at?: string;
  executed_at?: string;
  confirmed_at?: string;
  paypal_ref?: string;
  error_message?: string;
  is_simulated: boolean;
  message_draft?: string;
}

export interface RescuePlan {
  id: number;
  run_id: string;
  plan_type: "A" | "B" | "C";
  name: string;
  description: string;
  cost: number;
  cost_description: string;
  incoming_needed: number;
  selected_clients: any[];
  rationale: string;
  forecast_with_plan: DailyProjection[];
  forecast_without_plan: DailyProjection[];
  late_scenario: {
    outcome: string;
    shortfall: number;
  };
  remaining_risk: string;
  primary_action: Action;
}

export interface PlansComparisonResponse {
  run_id: string;
  obligation: Obligation;
  shortfall_amount: number;
  first_shortfall_date?: string;
  tradeoff_summary: string;
  plans: RescuePlan[];
}

export interface ClientData {
  id: number;
  name: string;
  email: string;
  country: string;
  typical_invoice_amount: number;
  relationship_weight: number;
  avg_delay_days: number;
  p_late: number;
  history_count: number;
  is_seeded: boolean;
  open_invoices: Array<{
    id: number;
    paypal_invoice_id: string;
    amount: number;
    currency: string;
    due_date: string;
    status: string;
    discount_applied: number;
    pay_link?: string;
  }>;
}

export interface AuditLogEntry {
  id: number;
  ts: string;
  actor: string;
  event: string;
  payload: Record<string, any>;
  prev_hash: string;
  hash: string;
}

export interface AuditVerifyResponse {
  chain_valid: boolean;
  total_blocks: number;
  genesis_valid: boolean;
  message: string;
  corrupted_block_id?: number;
}

export interface PayPalConnectionStatus {
  connected: boolean;
  environment: string;
  status: string;
  client_id_preview?: string;
  last_checked_at?: string;
  message?: string;
}

export interface WhatIfComparisonResponse {
  scenario_name: string;
  scenario_type: string;
  baseline: {
    shortfall_amount: number;
    first_shortfall_date?: string;
    min_projected_balance: number;
    p_shortfall: number;
  };
  simulated: {
    shortfall_amount: number;
    first_shortfall_date?: string;
    min_projected_balance: number;
    p_shortfall: number;
  };
  delta: {
    shortfall_change: number;
    min_balance_change: number;
    additional_capital_needed: number;
    p_shortfall_change: number;
  };
  projections_baseline: DailyProjection[];
  projections_simulated: DailyProjection[];
  explanation: string;
}

export interface SimulationPreset {
  id: string;
  name: string;
  scenario_type: string;
  description: string;
  impact_hint: string;
}

export interface AgentTraceStep {
  agent_name: string;
  status: string;
  timestamp: string;
  summary: string;
  key_finding: string;
}

export interface SupervisorRunResponse {
  run_id: string;
  status: string;
  obligation_evaluated: string;
  shortfall_detected: boolean;
  shortfall_amount: number;
  primary_risk_driver: string;
  recommended_plan: string;
  confidence_score: number;
  steps_trace: AgentTraceStep[];
  final_recommendation: string;
}

export interface NegotiationDraft {
  id: number;
  target_type: string;
  recipient_name: string;
  recipient_email: string;
  tone: string;
  subject: string;
  body: string;
  offered_incentive?: string;
  estimated_benefit?: string;
  status: string;
  created_at: string;
}

export interface NegotiationTonesResponse {
  recipient_name: string;
  recipient_email: string;
  target_type: string;
  context_summary: string;
  options: NegotiationDraft[];
}

export interface ResilienceFactor {
  name: string;
  score: number;
  weight: number;
  status: "strong" | "neutral" | "at_risk";
  detail: string;
  impact: "positive" | "negative" | "neutral";
}

export interface ResilienceScoreResponse {
  overall_score: number;
  category: "Excellent" | "Good" | "Moderate" | "Fragile" | "Critical";
  reserve_runway_days: number;
  debtor_reliability_pct: number;
  obligation_load_ratio: number;
  concentration_risk_hhi: number;
  receivables_exposure_pct: number;
  emergency_tolerance_usd: number;
  improving_factors: string[];
  reducing_factors: string[];
  recommended_actions: string[];
  factors: ResilienceFactor[];
}

export interface TimelineEntry {
  id: string;
  title: string;
  amount: number;
  currency: string;
  direction: "inflow" | "outflow";
  category: string;
  date: string;
  status: "confirmed" | "expected" | "estimated" | "simulated";
  data_source: string;
  reference_id?: string;
}

export interface FinancialSummaryResponse {
  currency: string;
  current_confirmed_balance: number;
  expected_inflows_30d: number;
  expected_outflows_30d: number;
  net_projected_30d: number;
  confirmed_inflows_count: number;
  expected_inflows_count: number;
  pending_obligations_count: number;
  emergency_reserve_target: number;
  emergency_reserve_actual: number;
  reserve_coverage_ratio: number;
}
