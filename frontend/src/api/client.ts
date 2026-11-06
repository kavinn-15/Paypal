import {
  PlansComparisonResponse,
  Obligation,
  Action,
  ClientData,
  AuditLogEntry,
  AuditVerifyResponse,
  PayPalConnectionStatus
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
};

