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
  TimelineEntry,
  TokenResponse,
  PhoneAuthResponse,
  GoogleAuthUrlResponse,
  RegionDetectionResponse,
  CountryItem,
  CurrencyItem,
  RegionalPreferencesResponse,
  RegionalPreferencesUpdate
} from '../types';

const rawBase = (import.meta.env.VITE_API_URL as string) || '/api';
const API_BASE = rawBase.replace(/\/+$/, '');

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
  try {
    localStorage.removeItem('cashflow_access_token');
    localStorage.removeItem('cashflow_refresh_token');
    localStorage.removeItem('cashflow_user_email');
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.clear();
    }
  } catch {
    // ignore
  }
}

async function request<T>(endpoint: string, options?: RequestInit, isRetry = false): Promise<T> {
  const token = getStoredToken();
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

  // Handle 401 Unauthorized: attempt refresh token exchange if available
  if (res.status === 401 && !isRetry && !endpoint.startsWith('/auth/')) {
    const refreshToken = getStoredRefreshToken();
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
          return request<T>(endpoint, options, true);
        } else {
          clearStoredTokens();
        }
      } catch {
        clearStoredTokens();
      }
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

  getActions: () => request<Action[]>('/actions'),

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

  register: async (data: {
    name: string;
    email: string;
    password: string;
    terms_accepted: boolean;
    phone_number?: string;
    phone_country_code?: string;
    currency?: string;
    preferred_currency?: string;
    country?: string;
    business_type?: string;
  }) => {
    const res = await request<any>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    setStoredTokens(res.access_token, res.refresh_token);
    if (res.email) localStorage.setItem('cashflow_user_email', res.email);
    return res;
  },

  // Phone Authentication & SMS OTP Endpoints
  requestPhoneVerification: async (phoneNumber: string, countryCode: string = '+91') => {
    return request<PhoneAuthResponse>('/auth/phone/verification/request', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber, phone_country_code: countryCode }),
    });
  },

  verifyPhoneOtp: async (phoneNumber: string, otp: string) => {
    return request<PhoneAuthResponse>('/auth/phone/verification/verify', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber, otp }),
    });
  },

  resendPhoneOtp: async (phoneNumber: string) => {
    return request<PhoneAuthResponse>('/auth/phone/verification/resend', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber }),
    });
  },

  requestPhoneLoginOtp: async (phoneNumber: string) => {
    return request<PhoneAuthResponse>('/auth/phone/login/request-otp', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber }),
    });
  },

  verifyPhoneLoginOtp: async (phoneNumber: string, otp: string) => {
    const res = await request<TokenResponse>('/auth/phone/login/verify-otp', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber, otp }),
    });
    setStoredTokens(res.access_token, res.refresh_token);
    if (res.email) localStorage.setItem('cashflow_user_email', res.email);
    return res;
  },

  loginWithPhonePassword: async (phoneNumber: string, password: string) => {
    const res = await request<TokenResponse>('/auth/phone/login/password', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber, password }),
    });
    setStoredTokens(res.access_token, res.refresh_token);
    if (res.email) localStorage.setItem('cashflow_user_email', res.email);
    return res;
  },

  requestPhonePasswordReset: async (phoneNumber: string) => {
    return request<PhoneAuthResponse>('/auth/phone/password-reset/request', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber }),
    });
  },

  verifyPhonePasswordResetOtp: async (phoneNumber: string, otp: string) => {
    return request<{ status: string; reset_token: string; message: string }>('/auth/phone/password-reset/verify-otp', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber, otp }),
    });
  },

  confirmPhonePasswordReset: async (resetToken: string, newPassword: string) => {
    return request<{ status: string; message: string }>('/auth/phone/password-reset/confirm', {
      method: 'POST',
      body: JSON.stringify({ reset_token: resetToken, new_password: newPassword }),
    });
  },

  requestPhoneChange: async (currentPassword: string, newPhoneNumber: string, countryCode: string = '+91') => {
    return request<PhoneAuthResponse>('/auth/phone/change/request', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_phone_number: newPhoneNumber,
        phone_country_code: countryCode,
      }),
    });
  },

  verifyPhoneChange: async (newPhoneNumber: string, otp: string) => {
    return request<PhoneAuthResponse>('/auth/phone/change/verify', {
      method: 'POST',
      body: JSON.stringify({ new_phone_number: newPhoneNumber, otp }),
    });
  },

  forgotPassword: async (email: string) => {
    return request<{ status: string; message: string; dev_reset_link?: string }>('/auth/password-reset/request', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  verifyPasswordResetOtp: async (email: string, otp: string) => {
    return request<{ status: string; reset_token: string; message: string }>('/auth/password-reset/verify-otp', {
      method: 'POST',
      body: JSON.stringify({ email, otp }),
    });
  },

  confirmPasswordResetWithOtp: async (resetToken: string, newPassword: string) => {
    return request<{ status: string; message: string }>('/auth/password-reset/confirm', {
      method: 'POST',
      body: JSON.stringify({ reset_token: resetToken, new_password: newPassword }),
    });
  },

  resetPassword: async (token: string, newPassword: string) => {
    return request<{ status: string; message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    });
  },

  verifyEmailOtp: async (email: string, otp: string) => {
    return request<{ status: string; message: string; email_verified: boolean }>('/auth/email/verify', {
      method: 'POST',
      body: JSON.stringify({ email, otp }),
    });
  },

  resendVerificationOtp: async (email: string) => {
    return request<{ status: string; message: string; cooldown_seconds: number }>('/auth/email/verification/resend', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  verifyEmail: async (token: string) => {
    return request<{ status: string; message: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  },

  getGoogleAuthUrl: async (redirectUri?: string) => {
    const query = redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : '';
    return request<GoogleAuthUrlResponse>(`/auth/google/start${query}`);
  },

  submitGoogleToken: async (credential: string) => {
    const res = await request<TokenResponse>('/auth/google/token', {
      method: 'POST',
      body: JSON.stringify({ credential }),
    });
    setStoredTokens(res.access_token, res.refresh_token);
    if (res.email) localStorage.setItem('cashflow_user_email', res.email);
    return res;
  },

  completeGoogleCallback: async (code: string, state?: string, redirectUri?: string) => {
    const params = new URLSearchParams({ code });
    if (state) params.set('state', state);
    if (redirectUri) params.set('redirect_uri', redirectUri);
    const res = await request<TokenResponse>(`/auth/google/callback?${params.toString()}`);
    setStoredTokens(res.access_token, res.refresh_token);
    if (res.email) localStorage.setItem('cashflow_user_email', res.email);
    return res;
  },

  logout: async () => {
    try {
      const refreshToken = getStoredRefreshToken();
      if (refreshToken) {
        await request<{ status: string; message: string }>('/auth/logout', {
          method: 'POST',
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    } catch {
      // ignore
    } finally {
      clearStoredTokens();
    }
  },

  getCurrentUser: () => request<any>('/auth/me'),

  getIntegrityCheck: () => request<any>('/finance/integrity-check'),

  detectRegion: (options?: { timezone?: string; clientHint?: string } | string) => {
    const params = new URLSearchParams();
    let tz: string | undefined;
    let hint: string | undefined;

    if (typeof options === 'string') {
      hint = options;
    } else if (options) {
      tz = options.timezone;
      hint = options.clientHint;
    }

    if (!tz && typeof Intl !== 'undefined') {
      try {
        tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      } catch {
        // ignore
      }
    }

    if (tz) params.append('timezone', tz);
    if (hint) params.append('client_hint', hint);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request<RegionDetectionResponse>(`/region/detect${query}`);
  },

  getCountries: () => request<CountryItem[]>('/region/countries'),

  getCurrencies: () => request<CurrencyItem[]>('/region/currencies'),

  getRegionalPreferences: () => request<RegionalPreferencesResponse>('/profile/regional-preferences'),

  updateRegionalPreferences: (data: RegionalPreferencesUpdate) =>
    request<RegionalPreferencesResponse>('/profile/regional-preferences', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getExchangeRates: () =>
    request<{ base_currency: string; rates: Record<string, number>; timestamp: string }>('/region/rates'),
};
