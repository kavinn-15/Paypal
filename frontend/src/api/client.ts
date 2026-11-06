import {
  PlansComparisonResponse,
  Obligation,
  Action,
  ClientData,
  AuditLogEntry,
  AuditVerifyResponse,
  PayPalConnectionStatus,
  WhatIfComparisonResponse,
  SimulationPreset,
  SupervisorRunResponse,
  NegotiationTonesResponse,
  NegotiationDraft,
  ResilienceScoreResponse,
  FinancialSummaryResponse,
  TimelineEntry
} from '../types';

const API_BASE = '/api';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errorJson = await res.json();
      errorDetail = errorJson.detail || JSON.stringify(errorJson);
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  getHealth: () => request<{ status: string; environment: string; dev_mode: boolean }>('/health'),

  getPayPalConnection: () => request<PayPalConnectionStatus>('/paypal/connection'),

  testPayPalConnection: () =>
    request<{ success: boolean; status_code: number; environment: string; message: string; token_preview?: string }>(
      '/paypal/test-connection',
      { method: 'POST' }
    ),

  getObligations: () => request<Obligation[]>('/obligations'),

  createObligation: (data: Partial<Obligation>) =>
    request<Obligation>('/obligations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getLatestForecast: () => request<PlansComparisonResponse>('/forecast/latest'),

  runForecast: (startingBalance = 1800.0, discountPct = 3.0) =>
    request<PlansComparisonResponse>(`/forecast/run?starting_balance=${startingBalance}&discount_pct=${discountPct}`, {
      method: 'POST',
    }),

  getMultiHorizonForecast: (startingBalance = 1800.0) =>
    request<Record<string, any>>(`/forecast/horizons?starting_balance=${startingBalance}`),

  approveAction: (actionId: number, approvalHash: string) =>
    request<Action>(`/actions/${actionId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approval_hash: approvalHash }),
    }),

  executeAction: (actionId: number, idempotencyKey: string) =>
    request<Action>(`/actions/${actionId}/execute`, {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: idempotencyKey }),
    }),

  simulateWebhook: (paypalInvoiceId?: string, amount?: number) =>
    request<{ success: boolean; simulated: boolean; message: string; result: any }>(
      '/dev/simulate-webhook',
      {
        method: 'POST',
        body: JSON.stringify({ paypal_invoice_id: paypalInvoiceId, amount }),
      }
    ),

  getClients: () => request<ClientData[]>('/clients'),

  getAuditLogs: () => request<AuditLogEntry[]>('/audit'),

  verifyAuditChain: () => request<AuditVerifyResponse>('/audit/verify'),

  // What-If Simulation
  getSimulationPresets: () => request<SimulationPreset[]>('/simulation/presets'),

  runSimulation: (data: {
    run_name?: string;
    scenario_type: string;
    delay_days?: number;
    partial_pct?: number;
    emergency_amount?: number;
    contractor_split_pct?: number;
  }, startingBalance = 1800.0) =>
    request<WhatIfComparisonResponse>(`/simulation/run?starting_balance=${startingBalance}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Agent Orchestrator / Supervisor
  runSupervisor: (startingBalance = 1800.0) =>
    request<SupervisorRunResponse>(`/supervisor/run?starting_balance=${startingBalance}`, {
      method: 'POST',
    }),

  getSupervisorRuns: () => request<any[]>('/supervisor/runs'),

  // Financial Negotiation Agent
  generateNegotiation: (data: {
    target_type: 'client_discount' | 'contractor_split';
    client_id?: number;
    obligation_id?: number;
    discount_pct?: number;
    split_pct?: number;
  }) =>
    request<NegotiationTonesResponse>('/negotiate/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getNegotiationDrafts: () => request<NegotiationDraft[]>('/negotiate/drafts'),

  approveNegotiationDraft: (draftId: number) =>
    request<NegotiationDraft>(`/negotiate/drafts/${draftId}/approve`, {
      method: 'POST',
    }),

  // Financial Resilience Score
  getResilienceScore: (startingBalance = 1800.0) =>
    request<ResilienceScoreResponse>(`/resilience/score?starting_balance=${startingBalance}`),

  // Financial Timeline & Summary
  getFinancialSummary: () => request<FinancialSummaryResponse>('/finance/summary'),

  getFinancialTimeline: () => request<TimelineEntry[]>('/finance/timeline'),

  // Demo Scenario Controls
  loadDemoScenario: () => request<{ status: string; message: string; is_demo_active: boolean }>('/demo/load', {
    method: 'POST',
  }),

  clearDemoScenario: () => request<{ status: string; message: string; is_demo_active: boolean }>('/demo/clear', {
    method: 'POST',
  }),

  getDemoStatus: () => request<{ is_demo_active: boolean; persona?: string }>('/demo/status'),
};
