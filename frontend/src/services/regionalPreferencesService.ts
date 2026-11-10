/**
 * Regional Preferences Service for Cashflow Lifeline.
 * Provides unified API access to regional preferences, country/currency catalogs,
 * geolocation detection, exchange rates, and preference synchronization.
 */

import { api } from '../api/client';
import type {
  CountryItem,
  CurrencyItem,
  RegionalPreferencesResponse,
  RegionalPreferencesUpdate,
  RegionDetectionResponse,
} from '../types';
import {
  DEFAULT_EXCHANGE_RATES,
  StoredRegionalPreference,
  getStoredManualPreference,
  getStoredDetectedRegion,
  getStoredRegionalPreference,
  setStoredManualPreference,
  setStoredDetectedRegion,
  setStoredRegionalPreference,
  formatCurrency,
  formatNumber,
  formatDate,
  convertAmount,
} from '../utils/currency';

let cachedCountries: CountryItem[] | null = null;
let cachedCurrencies: CurrencyItem[] | null = null;
let cachedRates: Record<string, number> = { ...DEFAULT_EXCHANGE_RATES };

export const regionalPreferencesService = {
  /**
   * Fetch current user's regional preferences from backend.
   */
  async getPreferences(): Promise<RegionalPreferencesResponse> {
    return await api.getRegionalPreferences();
  },

  /**
   * Update regional preferences on the backend and persist to local storage.
   */
  async updatePreferences(data: RegionalPreferencesUpdate): Promise<RegionalPreferencesResponse> {
    const res = await api.updateRegionalPreferences(data);

    // Save to local storage and dispatch event
    const stored: StoredRegionalPreference = {
      country: res.country,
      countryName: res.country_name || res.country,
      currency: res.preferred_currency,
      flag: res.flag || '🌐',
      symbol: res.currency_symbol || '$',
      locale: res.locale || 'en-US',
      source: 'manual',
      updatedAt: new Date().toISOString(),
    };
    setStoredManualPreference(stored);

    return res;
  },

  /**
   * Get supported countries list (cached).
   */
  async getCountries(): Promise<CountryItem[]> {
    if (cachedCountries && cachedCountries.length > 0) {
      return cachedCountries;
    }
    const countries = await api.getCountries();
    cachedCountries = countries;
    return countries;
  },

  /**
   * Get supported currencies list (cached).
   */
  async getCurrencies(): Promise<CurrencyItem[]> {
    if (cachedCurrencies && cachedCurrencies.length > 0) {
      return cachedCurrencies;
    }
    const currencies = await api.getCurrencies();
    cachedCurrencies = currencies;
    return currencies;
  },

  /**
   * Auto-detect user's region via backend geolocation.
   */
  async detectRegion(options?: { timezone?: string; clientHint?: string } | string): Promise<RegionDetectionResponse> {
    const res = await api.detectRegion(options);
    if (res && res.country) {
      const stored: StoredRegionalPreference = {
        country: res.country,
        countryName: res.country_name || res.country,
        currency: res.suggested_currency || 'USD',
        flag: res.flag || '🌐',
        symbol: res.currency_symbol || '$',
        locale: res.locale || 'en-US',
        source: 'detected',
        updatedAt: new Date().toISOString(),
      };
      setStoredDetectedRegion(stored);
    }
    return res;
  },

  /**
   * Fetch latest exchange rates.
   */
  async getExchangeRates(): Promise<Record<string, number>> {
    try {
      const res = await api.getExchangeRates();
      if (res && res.rates) {
        cachedRates = { ...DEFAULT_EXCHANGE_RATES, ...res.rates };
      }
    } catch {
      // Fallback to cached or default rates
    }
    return cachedRates;
  },

  /**
   * Retrieve cached exchange rates.
   */
  getCachedRates(): Record<string, number> {
    return cachedRates;
  },

  // Expose storage helpers
  getStoredPreference: getStoredRegionalPreference,
  getStoredManualPreference,
  getStoredDetectedRegion,
  setStoredManualPreference,
  setStoredDetectedRegion,
  setStoredPreference: setStoredRegionalPreference,

  // Expose formatting helpers
  formatCurrency,
  formatNumber,
  formatDate,
  convertAmount,
};

