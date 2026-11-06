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

export function getStoredToken(): string | null {
  return localStorage.getItem('cashflow_access_token');
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem('cashflow_refresh_token');
}

export function setStoredTokens(accessToken: string, refreshToken?: string): void {
  localStorage.setItem('cashflow_access_token', accessToken);
  if (refreshToken) {
    localStorage.setItem('cashflow_refresh_token', refreshToken);
  }
}

export function clearStoredTokens(): void {
  localStorage.removeItem('cashflow_access_token');
  localStorage.removeItem('cashflow_refresh_token');
  localStorage.removeItem('cashflow_user_email');
}

let isBootstrappingAuth = false;

async function bootstrapAuth(): Promise<string | null> {
  if (isBootstrappingAuth) return null;
  isBootstrappingAuth = true;
  try {
    const res = await fetch(`${API_BASE}/auth/demo-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    });
    if (res.ok) {
      const data = await res.json();
      setStoredTokens(data.access_token, data.refresh_token);
      if (data.email) localStorage.setItem('cashflow_user_email', data.email);
      return data.access_token;
    }
  } catch {
    // ignore
  } finally {
    isBootstrappingAuth = false;
  }
  return null;
}

async function request<T>(endpoint: string, options?: RequestInit, isRetry = false): Promise<T> {
  let token = getStoredToken();

  // If unauthenticated and calling a non-auth endpoint, bootstrap with demo-login in sandbox/dev mode
  if (!token && !endpoint.startsWith('/auth/') && !endpoint.startsWith('/health')) {
    token = await bootstrapAuth();
  }

  const url = `${API_BASE}${endpoint}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(options?.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized: attempt refresh or re-login once
  if (res.status === 401 && !isRetry && !endpoint.startsWith('/auth/')) {
    const refreshToken = getStoredRefreshToken();
    let refreshed = false;
    if (refreshToken) {
      try {
        const refRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refRes.ok) {
          const refData = await refRes.json();
          setStoredTokens(refData.access_token, refData.refresh_token);
          refreshed = true;
        }
      } catch {
        // ignore
      }
    }
    if (!refreshed) {
      const newToken = await bootstrapAuth();
      if (newToken) refreshed = true;
    }
    if (refreshed) {
      return request<T>(endpoint, options, true);
    }
  }

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

  // Authentication & Ledger Integrity
  demoLogin: async () => {
    const res = await request<any>('/auth/demo-login', { method: 'POST' });
    setStoredTokens(res.access_token, res.refresh_token);
    if (res.email) localStorage.setItem('cashflow_user_email', res.email);
    return res;
  },

  login: async (email: string, password: string) => {
    const res = await request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setStoredTokens(res.access_token, res.refresh_token);
    if (res.email) localStorage.setItem('cashflow_user_email', res.email);
    return res;
  },

  register: async (data: { name: string; email: string; password: string; currency?: string }) => {
    const res = await request<any>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    setStoredTokens(res.access_token, res.refresh_token);
    if (res.email) localStorage.setItem('cashflow_user_email', res.email);
    return res;
  },

  logout: async () => {
    try {
      const refreshToken = getStoredRefreshToken();
      await request<{ status: string; message: string }>('/auth/logout', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // ignore
    } finally {
      clearStoredTokens();
    }
  },

  getCurrentUser: () => request<any>('/auth/me'),

  getIntegrityCheck: () => request<any>('/finance/integrity-check'),
};
