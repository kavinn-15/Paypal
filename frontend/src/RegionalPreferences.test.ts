import { describe, it, expect, beforeEach } from 'vitest';
import {
  formatCurrency,
  getCurrencySymbol,
  getCurrencyFractionDigits,
  getStoredRegionalPreference,
  setStoredRegionalPreference,
  ZERO_DECIMAL_CURRENCIES,
  REGIONAL_PREFERENCE_STORAGE_KEY,
  StoredRegionalPreference
} from './utils/currency';

// Simple polyfill for node test environment
const mockStorage = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(globalThis, 'localStorage', {
  value: mockStorage,
  writable: true,
});

describe('Regional Preferences & Currency Localization Tests', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('Currency Fraction Digits & Zero-Decimal Handlers', () => {
    it('identifies zero-decimal currencies accurately', () => {
      expect(ZERO_DECIMAL_CURRENCIES.has('JPY')).toBe(true);
      expect(ZERO_DECIMAL_CURRENCIES.has('KRW')).toBe(true);
      expect(ZERO_DECIMAL_CURRENCIES.has('VND')).toBe(true);
      expect(ZERO_DECIMAL_CURRENCIES.has('USD')).toBe(false);
      expect(ZERO_DECIMAL_CURRENCIES.has('INR')).toBe(false);
      expect(ZERO_DECIMAL_CURRENCIES.has('EUR')).toBe(false);

      expect(getCurrencyFractionDigits('JPY')).toBe(0);
      expect(getCurrencyFractionDigits('KRW')).toBe(0);
      expect(getCurrencyFractionDigits('USD')).toBe(2);
      expect(getCurrencyFractionDigits('INR')).toBe(2);
      expect(getCurrencyFractionDigits('EUR')).toBe(2);
      expect(getCurrencyFractionDigits('KWD')).toBe(3);
    });
  });

  describe('formatCurrency Intl Localization', () => {
    it('formats standard 2-decimal USD amounts', () => {
      const formatted = formatCurrency(2500, 'USD', 'en-US');
      expect(formatted).toContain('$2,500.00');
    });

    it('formats standard 2-decimal INR amounts', () => {
      const formatted = formatCurrency(150000, 'INR', 'en-IN');
      // Indian numbering system 1,50,000.00
      expect(formatted).toContain('1,50,000.00');
    });

    it('formats zero-decimal currencies without trailing decimal zeroes', () => {
      const formattedJPY = formatCurrency(5000, 'JPY', 'ja-JP');
      // Should not contain .00
      expect(formattedJPY).not.toContain('.00');
      expect(formattedJPY).toContain('5,000');

      const formattedKRW = formatCurrency(120000, 'KRW', 'ko-KR');
      expect(formattedKRW).not.toContain('.00');
      expect(formattedKRW).toContain('120,000');
    });

    it('handles null, undefined, and NaN gracefully', () => {
      expect(formatCurrency(null)).toBe('—');
      expect(formatCurrency(undefined)).toBe('—');
      expect(formatCurrency('invalid_num')).toBe('—');
    });

    it('supports appending currency code option', () => {
      const formatted = formatCurrency(100, 'USD', 'en-US', { showCode: true });
      expect(formatted).toContain('USD');
    });
  });

  describe('getCurrencySymbol', () => {
    it('returns appropriate symbols for major currencies', () => {
      expect(getCurrencySymbol('USD', 'en-US')).toBe('$');
      expect(getCurrencySymbol('EUR', 'en-US')).toBe('€');
      expect(getCurrencySymbol('GBP', 'en-US')).toBe('£');
      const inrSymbol = getCurrencySymbol('INR', 'en-IN');
      expect(['₹', 'INR', 'Rs.'].some((s) => inrSymbol.includes(s) || inrSymbol === s)).toBe(true);
    });
  });

  describe('LocalStorage Regional Preference Persistence', () => {
    it('stores and retrieves regional preferences correctly', () => {
      expect(getStoredRegionalPreference()).toBeNull();

      const pref: StoredRegionalPreference = {
        country: 'IN',
        countryName: 'India',
        currency: 'INR',
        flag: '🇮🇳',
        symbol: '₹',
        locale: 'en-IN',
        source: 'manual',
        updatedAt: '2026-11-10T00:00:00.000Z'
      };

      setStoredRegionalPreference(pref);
      const retrieved = getStoredRegionalPreference();
      expect(retrieved).not.toBeNull();
      expect(retrieved?.country).toBe('IN');
      expect(retrieved?.countryName).toBe('India');
      expect(retrieved?.currency).toBe('INR');
      expect(retrieved?.flag).toBe('🇮🇳');
      expect(retrieved?.symbol).toBe('₹');
    });
  });
});
