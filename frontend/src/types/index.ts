export interface Owner {
  id: number;
  name: string;
  email: string;
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
