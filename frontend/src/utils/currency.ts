/**
 * Currency and Regional Formatting Utilities for Cashflow Lifeline.
 * Provides locale-aware currency formatting, zero-decimal currency handling,
 * and persistent storage helpers for regional preferences.
 */

export const ZERO_DECIMAL_CURRENCIES = new Set([
  'BIF', 'CLP', 'DJF', 'GNF', 'JPY', 'KMF', 'KRW', 'MGA',
  'PYG', 'RWF', 'UGX', 'VND', 'VUV', 'XAF', 'XOF', 'XPF'
]);

export const THREE_DECIMAL_CURRENCIES = new Set([
  'BHD', 'IQD', 'JOD', 'KWD', 'OMR', 'TND'
]);

export const REGIONAL_PREFERENCE_STORAGE_KEY = 'cashflow_regional_preference';
export const DETECTED_REGION_STORAGE_KEY = 'cashflow_detected_region';

export interface StoredRegionalPreference {
  country: string;
  countryName: string;
  currency: string;
  flag: string;
  symbol: string;
  locale?: string;
  source: 'detected' | 'manual';
  updatedAt: string;
}

/**
 * Get fraction digits for a given ISO 4217 currency code.
 */
export function getCurrencyFractionDigits(currencyCode: string): number {
  const code = (currencyCode || 'USD').toUpperCase();
  if (ZERO_DECIMAL_CURRENCIES.has(code)) return 0;
  if (THREE_DECIMAL_CURRENCIES.has(code)) return 3;
  return 2;
}

/**
 * Formats a numeric amount using locale and currency.
 * Fully supports zero-decimal currencies like JPY, KRW and standard currencies like USD, EUR, INR.
 */
export function formatCurrency(
  amount: number | string | null | undefined,
  currencyCode: string = 'USD',
  locale: string = 'en-US',
  options?: {
    showCode?: boolean;
    maximumFractionDigits?: number;
    minimumFractionDigits?: number;
  }
): string {
  if (amount === null || amount === undefined || isNaN(Number(amount))) {
    return '—';
  }

  const num = typeof amount === 'number' ? amount : parseFloat(amount);
  const code = (currencyCode || 'USD').toUpperCase();
  const defaultDecimals = getCurrencyFractionDigits(code);

  const minDecimals = options?.minimumFractionDigits ?? defaultDecimals;
  const maxDecimals = options?.maximumFractionDigits ?? defaultDecimals;

  try {
    const formatter = new Intl.NumberFormat(locale || 'en-US', {
      style: 'currency',
      currency: code,
      minimumFractionDigits: minDecimals,
      maximumFractionDigits: maxDecimals,
    });
    const formatted = formatter.format(num);

    if (options?.showCode) {
      return `${formatted} ${code}`;
    }
    return formatted;
  } catch {
    // Graceful fallback for non-standard environments
    const fixed = num.toFixed(defaultDecimals);
    return `${code} ${fixed}`;
  }
}

/**
 * Returns currency symbol for a given currency code.
 */
export function getCurrencySymbol(currencyCode: string = 'USD', locale: string = 'en-US'): string {
  const code = (currencyCode || 'USD').toUpperCase();
  try {
    const formatter = new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: code,
    });
    const parts = formatter.formatToParts(0);
    const symbolPart = parts.find((p) => p.type === 'currency');
    return symbolPart ? symbolPart.value : code;
  } catch {
    return code;
  }
}

/**
 * Read explicit manual regional preference from localStorage.
 * Stale or detected entries residing under the manual key are evicted.
 */
export function getStoredManualPreference(): StoredRegionalPreference | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    const item = localStorage.getItem(REGIONAL_PREFERENCE_STORAGE_KEY);
    if (!item) return null;
    const parsed = JSON.parse(item) as StoredRegionalPreference;
    if (parsed && parsed.source === 'manual') {
      return parsed;
    }
    // Clean up disposable or legacy detected entries in the manual key
    localStorage.removeItem(REGIONAL_PREFERENCE_STORAGE_KEY);
    return null;
  } catch {
    return null;
  }
}

/**
 * Save explicit user manual preference to localStorage and notify listeners.
 */
export function setStoredManualPreference(pref: StoredRegionalPreference): void {
  try {
    const manualPref: StoredRegionalPreference = {
      ...pref,
      source: 'manual',
      updatedAt: new Date().toISOString()
    };
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(REGIONAL_PREFERENCE_STORAGE_KEY, JSON.stringify(manualPref));
    }
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function' && typeof CustomEvent !== 'undefined') {
      window.dispatchEvent(new CustomEvent('regional-preference-changed', { detail: manualPref }));
    }
  } catch (e) {
    console.error('Failed to save manual regional preference:', e);
  }
}

/**
 * Read cached auto-detected region from localStorage/sessionStorage.
 */
export function getStoredDetectedRegion(): StoredRegionalPreference | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    const item = localStorage.getItem(DETECTED_REGION_STORAGE_KEY);
    if (!item) return null;
    return JSON.parse(item) as StoredRegionalPreference;
  } catch {
    return null;
  }
}

/**
 * Cache auto-detected region without contaminating manual preference.
 */
export function setStoredDetectedRegion(pref: StoredRegionalPreference): void {
  try {
    const detectedPref: StoredRegionalPreference = {
      ...pref,
      source: 'detected',
      updatedAt: new Date().toISOString()
    };
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(DETECTED_REGION_STORAGE_KEY, JSON.stringify(detectedPref));
    }
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function' && typeof CustomEvent !== 'undefined') {
      window.dispatchEvent(new CustomEvent('regional-preference-changed', { detail: detectedPref }));
    }
  } catch (e) {
    console.error('Failed to cache detected region:', e);
  }
}

/**
 * Read active regional preference with proper priority:
 * 1. Explicit user manual preference
 * 2. Cached auto-detected region
 */
export function getStoredRegionalPreference(): StoredRegionalPreference | null {
  const manual = getStoredManualPreference();
  if (manual) return manual;
  return getStoredDetectedRegion();
}

/**
 * Store regional preference, routing by source (manual vs detected).
 */
export function setStoredRegionalPreference(pref: StoredRegionalPreference): void {
  if (pref.source === 'manual') {
    setStoredManualPreference(pref);
  } else {
    setStoredDetectedRegion(pref);
  }
}
