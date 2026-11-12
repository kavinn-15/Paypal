import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from './AuthContext';
import { api } from '../api/client';
import {
  formatCurrency as utilFormatCurrency,
  formatNumber as utilFormatNumber,
  formatDate as utilFormatDate,
  convertAmount as utilConvertAmount,
  getCurrencySymbol,
  DEFAULT_EXCHANGE_RATES,
  StoredRegionalPreference,
  getStoredManualPreference,
  getStoredDetectedRegion,
  setStoredManualPreference,
} from '../utils/currency';
import type { CountryItem, CurrencyItem } from '../types';

export interface RegionalPreferencesContextType {
  country: string;
  countryCode: string;
  countryName: string;
  currency: string;
  currencySymbol: string;
  currencyName: string;
  flag: string;
  locale: string;
  baseCurrency: string;
  exchangeRates: Record<string, number>;
  isLoaded: boolean;
  isLoading: boolean;
  formatCurrency: (
    amount: number | string | null | undefined,
    options?: {
      currency?: string;
      fromCurrency?: string;
      locale?: string;
      showCode?: boolean;
      minimumFractionDigits?: number;
      maximumFractionDigits?: number;
      convertFromBase?: boolean;
      noConvert?: boolean;
    }
  ) => string;
  formatNumber: (value: number | string | null | undefined, options?: Intl.NumberFormatOptions) => string;
  formatDate: (date: Date | string | number | null | undefined, options?: Intl.DateTimeFormatOptions) => string;
  convertAmount: (amount: number | string | null | undefined, fromCurrency?: string, toCurrency?: string) => number;
  updatePreferences: (
    countryCode: string,
    currencyCode: string,
    options?: { locale?: string; region_detection_enabled?: boolean }
  ) => Promise<void>;
  refreshPreferences: () => Promise<void>;
}

const RegionalPreferencesContext = createContext<RegionalPreferencesContextType | undefined>(undefined);

// Fallback country and currency dictionary for instant offline resolution
const FALLBACK_COUNTRY_MAP: Record<string, { name: string; flag: string; currency: string; locale: string }> = {
  US: { name: 'United States', flag: '🇺🇸', currency: 'USD', locale: 'en-US' },
  IN: { name: 'India', flag: '🇮🇳', currency: 'INR', locale: 'en-IN' },
  GB: { name: 'United Kingdom', flag: '🇬🇧', currency: 'GBP', locale: 'en-GB' },
  DE: { name: 'Germany', flag: '🇩🇪', currency: 'EUR', locale: 'de-DE' },
  FR: { name: 'France', flag: '🇫🇷', currency: 'EUR', locale: 'fr-FR' },
  CA: { name: 'Canada', flag: '🇨🇦', currency: 'CAD', locale: 'en-CA' },
  AU: { name: 'Australia', flag: '🇦🇺', currency: 'AUD', locale: 'en-AU' },
  JP: { name: 'Japan', flag: '🇯🇵', currency: 'JPY', locale: 'ja-JP' },
  SG: { name: 'Singapore', flag: '🇸🇬', currency: 'SGD', locale: 'en-SG' },
  AE: { name: 'United Arab Emirates', flag: '🇦🇪', currency: 'AED', locale: 'ar-AE' },
  CH: { name: 'Switzerland', flag: '🇨🇭', currency: 'CHF', locale: 'de-CH' },
  BR: { name: 'Brazil', flag: '🇧🇷', currency: 'BRL', locale: 'pt-BR' },
  MX: { name: 'Mexico', flag: '🇲🇽', currency: 'MXN', locale: 'es-MX' },
  NZ: { name: 'New Zealand', flag: '🇳🇿', currency: 'NZD', locale: 'en-NZ' },
  SE: { name: 'Sweden', flag: '🇸🇪', currency: 'SEK', locale: 'sv-SE' },
};

const FALLBACK_CURRENCY_MAP: Record<string, { name: string; symbol: string }> = {
  USD: { name: 'US Dollar', symbol: '$' },
  EUR: { name: 'Euro', symbol: '€' },
  GBP: { name: 'British Pound', symbol: '£' },
  INR: { name: 'Indian Rupee', symbol: '₹' },
  CAD: { name: 'Canadian Dollar', symbol: 'CA$' },
  AUD: { name: 'Australian Dollar', symbol: 'AU$' },
  JPY: { name: 'Japanese Yen', symbol: '¥' },
  SGD: { name: 'Singapore Dollar', symbol: 'S$' },
  AED: { name: 'UAE Dirham', symbol: 'AED' },
  CHF: { name: 'Swiss Franc', symbol: 'CHF' },
  BRL: { name: 'Brazilian Real', symbol: 'R$' },
  MXN: { name: 'Mexican Peso', symbol: 'MX$' },
  NZD: { name: 'New Zealand Dollar', symbol: 'NZ$' },
  SEK: { name: 'Swedish Krona', symbol: 'kr' },
};

export const RegionalPreferencesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { currentUser, refreshUser } = useAuth();

  const [country, setCountry] = useState<string>('US');
  const [countryName, setCountryName] = useState<string>('United States');
  const [currency, setCurrency] = useState<string>('USD');
  const [currencySymbol, setCurrencySymbol] = useState<string>('$');
  const [currencyName, setCurrencyName] = useState<string>('US Dollar');
  const [flag, setFlag] = useState<string>('🇺🇸');
  const [locale, setLocale] = useState<string>('en-US');
  const [baseCurrency, setBaseCurrency] = useState<string>('USD');
  const [exchangeRates, setExchangeRates] = useState<Record<string, number>>(DEFAULT_EXCHANGE_RATES);
  const [isLoaded, setIsLoaded] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Fetch exchange rates once on mount
  useEffect(() => {
    let isMounted = true;
    api.getExchangeRates()
      .then((res) => {
        if (isMounted && res && res.rates) {
          setExchangeRates((prev) => ({ ...prev, ...res.rates }));
        }
      })
      .catch(() => {
        // Fallback to DEFAULT_EXCHANGE_RATES
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Helper to apply preference values to state
  const applyPreferences = useCallback(
    (targetCountry: string, targetCurrency: string, targetLocale?: string, targetFlag?: string) => {
      const cCode = (targetCountry || 'US').toUpperCase();
      const currCode = (targetCurrency || 'USD').toUpperCase();
      const countryMeta = FALLBACK_COUNTRY_MAP[cCode];
      const currencyMeta = FALLBACK_CURRENCY_MAP[currCode];

      const resolvedName = countryMeta ? countryMeta.name : cCode;
      const resolvedFlag = targetFlag || (countryMeta ? countryMeta.flag : '🌐');
      const resolvedLocale = targetLocale || (countryMeta ? countryMeta.locale : 'en-US');
      const resolvedSym = currencyMeta ? currencyMeta.symbol : getCurrencySymbol(currCode, resolvedLocale);
      const resolvedCurrName = currencyMeta ? currencyMeta.name : currCode;

      setCountry(cCode);
      setCountryName(resolvedName);
      setCurrency(currCode);
      setCurrencySymbol(resolvedSym);
      setCurrencyName(resolvedCurrName);
      setFlag(resolvedFlag);
      setLocale(resolvedLocale);
    },
    []
  );

  // Synchronize when currentUser changes (User login / account switch / logout)
  useEffect(() => {
    if (currentUser) {
      // User is logged in: strict isolation to their saved preference
      const userPreferredCurr = currentUser.preferred_currency || currentUser.currency || 'USD';
      const userCountry = currentUser.country || 'US';
      const userBase = currentUser.currency || 'USD';
      const userLocale = currentUser.locale || 'en-US';

      setBaseCurrency(userBase);
      applyPreferences(userCountry, userPreferredCurr, userLocale);
      setIsLoaded(true);
    } else {
      // Anonymous visitor: manual stored preference > detected cached preference > default US
      setBaseCurrency('USD');
      const manual = getStoredManualPreference();
      if (manual && manual.country && manual.currency) {
        applyPreferences(manual.country, manual.currency, manual.locale, manual.flag);
      } else {
        const detected = getStoredDetectedRegion();
        if (detected && detected.country && detected.currency) {
          applyPreferences(detected.country, detected.currency, detected.locale, detected.flag);
        } else {
          applyPreferences('US', 'USD', 'en-US', '🇺🇸');
        }
      }
      setIsLoaded(true);
    }
  }, [currentUser, applyPreferences]);

  // Listen to cross-component preference change events (e.g. from footer selector or external tabs)
  useEffect(() => {
    const handleRegionalChange = (e: Event) => {
      const customEvent = e as CustomEvent<StoredRegionalPreference>;
      const detail = customEvent.detail;
      if (detail && detail.currency && detail.country) {
        applyPreferences(detail.country, detail.currency, detail.locale, detail.flag);
      }
    };

    window.addEventListener('regional-preference-changed', handleRegionalChange);
    return () => {
      window.removeEventListener('regional-preference-changed', handleRegionalChange);
    };
  }, [applyPreferences]);

  // Update preferences globally across the application
  const updatePreferences = useCallback(
    async (
      newCountryCode: string,
      newCurrencyCode: string,
      options?: { locale?: string; region_detection_enabled?: boolean }
    ) => {
      setIsLoading(true);
      const cCode = (newCountryCode || country).toUpperCase();
      const currCode = (newCurrencyCode || currency).toUpperCase();
      const cMeta = FALLBACK_COUNTRY_MAP[cCode];
      const newLocale = options?.locale || (cMeta ? cMeta.locale : locale);
      const newFlag = cMeta ? cMeta.flag : '🌐';

      // 1. Immediately update internal state so UI components re-render without reload
      applyPreferences(cCode, currCode, newLocale, newFlag);

      // 2. Persist to localStorage and broadcast event
      const stored: StoredRegionalPreference = {
        country: cCode,
        countryName: cMeta ? cMeta.name : cCode,
        currency: currCode,
        flag: newFlag,
        symbol: getCurrencySymbol(currCode, newLocale),
        locale: newLocale,
        source: 'manual',
        updatedAt: new Date().toISOString(),
      };
      setStoredManualPreference(stored);

      // 3. If authenticated, persist to user's backend profile
      if (currentUser) {
        try {
          await api.updateRegionalPreferences({
            country: cCode,
            preferred_currency: currCode,
            locale: newLocale,
            region_detection_enabled: options?.region_detection_enabled,
          });
          await refreshUser();
        } catch (err) {
          console.error('Failed to update regional preferences on server:', err);
          throw err;
        }
      }

      setIsLoading(false);
    },
    [country, currency, locale, currentUser, refreshUser, applyPreferences]
  );

  const refreshPreferences = useCallback(async () => {
    if (currentUser) {
      await refreshUser();
    }
  }, [currentUser, refreshUser]);

  // Context-aware formatCurrency implementation with automatic rate conversion
  const formatCurrencyFn = useCallback(
    (
      amount: number | string | null | undefined,
      options?: {
        currency?: string;
        fromCurrency?: string;
        locale?: string;
        showCode?: boolean;
        minimumFractionDigits?: number;
        maximumFractionDigits?: number;
        convertFromBase?: boolean;
        noConvert?: boolean;
      }
    ) => {
      if (amount === null || amount === undefined || isNaN(Number(amount))) {
        return '—';
      }

      const numeric = Number(amount);

      // If explicit noConvert is requested, format as-is without rate conversion
      if (options?.noConvert) {
        const directCurrency = options?.currency || currency;
        const directLocale = options?.locale || locale;
        return utilFormatCurrency(numeric, directCurrency, directLocale, options);
      }

      // Determine target display currency:
      // The default target display currency is the user's active selected `currency` (e.g. 'INR').
      // If the caller passes options.currency that matches baseCurrency (e.g. { currency: obligation.currency } where obligation is USD),
      // that is the source currency of the data, so the target remains the user's active display currency.
      let targetCurrency = currency;
      let sourceCurrency = options?.fromCurrency || baseCurrency;

      if (options?.currency) {
        if (options.currency === baseCurrency) {
          sourceCurrency = baseCurrency;
          targetCurrency = currency;
        } else if (options.currency === currency) {
          sourceCurrency = baseCurrency;
          targetCurrency = currency;
        } else {
          // Explicit target requested by caller
          targetCurrency = options.currency;
        }
      }

      const targetLocale = options?.locale || locale;
      let numericAmount = numeric;
      let effectiveCurrency = targetCurrency;

      // Automatically convert when source and target currencies differ
      if (sourceCurrency !== targetCurrency) {
        const converted = utilConvertAmount(numeric, sourceCurrency, targetCurrency, exchangeRates);
        if (converted !== null && !isNaN(converted)) {
          numericAmount = converted;
        } else {
          effectiveCurrency = sourceCurrency;
        }
      }

      return utilFormatCurrency(numericAmount, effectiveCurrency, targetLocale, options);
    },
    [currency, locale, baseCurrency, exchangeRates]
  );

  const formatNumberFn = useCallback(
    (value: number | string | null | undefined, options?: Intl.NumberFormatOptions) => {
      return utilFormatNumber(value, locale, options);
    },
    [locale]
  );

  const formatDateFn = useCallback(
    (date: Date | string | number | null | undefined, options?: Intl.DateTimeFormatOptions) => {
      return utilFormatDate(date, locale, options);
    },
    [locale]
  );

  const convertAmountFn = useCallback(
    (amount: number | string | null | undefined, fromCurrency?: string, toCurrency?: string) => {
      const from = fromCurrency || baseCurrency;
      const to = toCurrency || currency;
      return utilConvertAmount(amount, from, to, exchangeRates);
    },
    [baseCurrency, currency, exchangeRates]
  );

  const value = useMemo(
    () => ({
      country,
      countryCode: country,
      countryName,
      currency,
      currencySymbol,
      currencyName,
      flag,
      locale,
      baseCurrency,
      exchangeRates,
      isLoaded,
      isLoading,
      formatCurrency: formatCurrencyFn,
      formatNumber: formatNumberFn,
      formatDate: formatDateFn,
      convertAmount: convertAmountFn,
      updatePreferences,
      refreshPreferences,
    }),
    [
      country,
      countryName,
      currency,
      currencySymbol,
      currencyName,
      flag,
      locale,
      baseCurrency,
      exchangeRates,
      isLoaded,
      isLoading,
      formatCurrencyFn,
      formatNumberFn,
      formatDateFn,
      convertAmountFn,
      updatePreferences,
      refreshPreferences,
    ]
  );

  return <RegionalPreferencesContext.Provider value={value}>{children}</RegionalPreferencesContext.Provider>;
};

export const useRegionalPreferences = (): RegionalPreferencesContextType => {
  const context = useContext(RegionalPreferencesContext);
  if (!context) {
    throw new Error('useRegionalPreferences must be used within a RegionalPreferencesProvider');
  }
  return context;
};

