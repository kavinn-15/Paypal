import React, { useState, useEffect, useMemo } from 'react';
import { Globe, Search, Check, X, Sparkles, Loader2, ArrowRight } from 'lucide-react';
import { api } from '../api/client';
import { CountryItem, CurrencyItem } from '../types';
import {
  getStoredManualPreference,
  setStoredManualPreference,
  getStoredDetectedRegion,
  setStoredDetectedRegion,
  StoredRegionalPreference
} from '../utils/currency';
import { useAuth } from '../context/AuthContext';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

interface RegionalFooterSelectorProps {
  className?: string;
  variant?: 'footer' | 'inline' | 'compact';
}

export const RegionalFooterSelector: React.FC<RegionalFooterSelectorProps> = ({
  className = '',
  variant = 'footer'
}) => {
  const { currentUser, refreshUser } = useAuth();
  const regionalPrefs = useRegionalPreferences();
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'country' | 'currency'>('country');

  // Catalogs
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [currencies, setCurrencies] = useState<CurrencyItem[]>([]);
  const [isLoadingCatalogs, setIsLoadingCatalogs] = useState(false);

  // Current active selections
  const [selectedCountry, setSelectedCountry] = useState<string>(regionalPrefs.country || 'US');
  const [selectedCountryName, setSelectedCountryName] = useState<string>(regionalPrefs.countryName || 'United States');
  const [selectedFlag, setSelectedFlag] = useState<string>(regionalPrefs.flag || '🇺🇸');
  const [selectedCurrency, setSelectedCurrency] = useState<string>(regionalPrefs.currency || 'USD');
  const [selectedSymbol, setSelectedSymbol] = useState<string>(regionalPrefs.currencySymbol || '$');

  // Sync state when regionalPrefs updates
  useEffect(() => {
    setSelectedCountry(regionalPrefs.country);
    setSelectedCountryName(regionalPrefs.countryName);
    setSelectedFlag(regionalPrefs.flag);
    setSelectedCurrency(regionalPrefs.currency);
    setSelectedSymbol(regionalPrefs.currencySymbol);
  }, [regionalPrefs.country, regionalPrefs.countryName, regionalPrefs.flag, regionalPrefs.currency, regionalPrefs.currencySymbol]);

  // Search & detection states
  const [searchQuery, setSearchQuery] = useState('');
  const [isDetecting, setIsDetecting] = useState(false);
  const [detectionNotice, setDetectionNotice] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // 1. Initial Load: Auth User > Manual Storage > Cached Detected > Live Auto Detect
  useEffect(() => {
    const initPreferences = async () => {
      // 1. Authenticated User: Highest priority (never overwrite with detection)
      if (currentUser?.country && (currentUser?.preferred_currency || currentUser?.currency)) {
        setSelectedCountry(currentUser.country);
        setSelectedCurrency(currentUser.preferred_currency || currentUser.currency || 'USD');
        return;
      }

      // 2. Anonymous Returning Visitor with explicit manual preference
      const manualStored = getStoredManualPreference();
      if (manualStored) {
        setSelectedCountry(manualStored.country);
        setSelectedCountryName(manualStored.countryName || manualStored.country);
        setSelectedFlag(manualStored.flag || '🌐');
        setSelectedCurrency(manualStored.currency);
        setSelectedSymbol(manualStored.symbol || '$');
        return;
      }

      // 3. Cached Detection (session / non-manual storage - render immediately, then revalidate in background)
      const cachedDetected = getStoredDetectedRegion();
      if (cachedDetected && cachedDetected.country) {
        setSelectedCountry(cachedDetected.country);
        setSelectedCountryName(cachedDetected.countryName || cachedDetected.country);
        setSelectedFlag(cachedDetected.flag || '🌐');
        setSelectedCurrency(cachedDetected.currency);
        setSelectedSymbol(cachedDetected.symbol || '$');
      }

      // 4. Auto detect / refresh region from server
      try {
        const detected = await api.detectRegion();
        if (detected && detected.detected && detected.country) {
          setSelectedCountry(detected.country);
          setSelectedCountryName(detected.country_name || detected.country);
          setSelectedFlag(detected.flag || '🌐');
          setSelectedCurrency(detected.suggested_currency || 'USD');
          setSelectedSymbol(detected.currency_symbol || '$');

          setStoredDetectedRegion({
            country: detected.country,
            countryName: detected.country_name || detected.country,
            currency: detected.suggested_currency || 'USD',
            flag: detected.flag || '🌐',
            symbol: detected.currency_symbol || '$',
            locale: detected.locale,
            source: 'detected',
            updatedAt: new Date().toISOString()
          });
        }
      } catch (err) {
        // Silently fallback to neutral defaults
      }
    };

    initPreferences();

    // Listen for cross-component preference updates
    const handlePrefChange = (e: Event) => {
      const customEvent = e as CustomEvent<StoredRegionalPreference>;
      if (customEvent.detail) {
        setSelectedCountry(customEvent.detail.country);
        setSelectedCountryName(customEvent.detail.countryName);
        setSelectedFlag(customEvent.detail.flag);
        setSelectedCurrency(customEvent.detail.currency);
        setSelectedSymbol(customEvent.detail.symbol);
      }
    };

    window.addEventListener('regional-preference-changed', handlePrefChange);
    return () => {
      window.removeEventListener('regional-preference-changed', handlePrefChange);
    };
  }, [currentUser]);

  // 2. Fetch catalogs when modal opens
  useEffect(() => {
    if (!isOpen) return;

    const fetchCatalogs = async () => {
      if (countries.length > 0 && currencies.length > 0) return;
      setIsLoadingCatalogs(true);
      try {
        const [cList, currList] = await Promise.all([
          api.getCountries(),
          api.getCurrencies()
        ]);
        setCountries(cList);
        setCurrencies(currList);

        // Update country name & flag if available
        const currentC = cList.find((c) => c.code === selectedCountry);
        if (currentC) {
          setSelectedCountryName(currentC.name);
          setSelectedFlag(currentC.flag);
        }
        const currentCurr = currList.find((c) => c.code === selectedCurrency);
        if (currentCurr) {
          setSelectedSymbol(currentCurr.symbol);
        }
      } catch (err) {
        console.error('Failed to load countries or currencies:', err);
      } finally {
        setIsLoadingCatalogs(false);
      }
    };

    fetchCatalogs();
  }, [isOpen, selectedCountry, selectedCurrency, countries.length, currencies.length]);

  // Auto-detect action inside modal
  const handleAutoDetect = async () => {
    setIsDetecting(true);
    setDetectionNotice(null);
    try {
      const detected = await api.detectRegion();
      if (detected && detected.detected && detected.country) {
        setSelectedCountry(detected.country);
        setSelectedCountryName(detected.country_name || detected.country);
        setSelectedFlag(detected.flag || '🌐');
        setSelectedCurrency(detected.suggested_currency || 'USD');
        setSelectedSymbol(detected.currency_symbol || '$');
        setDetectionNotice(`Detected: ${detected.country_name || detected.country} (${detected.suggested_currency || 'USD'})`);
      } else {
        setDetectionNotice('Automatic location detection is unavailable in this environment. Please choose manually below.');
      }
    } catch {
      setDetectionNotice('Unable to detect location. Please select manually.');
    } finally {
      setIsDetecting(false);
    }
  };

  // Filtered lists based on search
  const filteredCountries = useMemo(() => {
    if (!searchQuery.trim()) return countries;
    const q = searchQuery.toLowerCase().trim();
    return countries.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.code.toLowerCase().includes(q) ||
        c.currency.toLowerCase().includes(q)
    );
  }, [countries, searchQuery]);

  const filteredCurrencies = useMemo(() => {
    if (!searchQuery.trim()) return currencies;
    const q = searchQuery.toLowerCase().trim();
    return currencies.filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q) ||
        c.symbol.toLowerCase().includes(q)
    );
  }, [currencies, searchQuery]);

  // When a country is selected, optionally suggest its native currency
  const handleSelectCountry = (country: CountryItem) => {
    setSelectedCountry(country.code);
    setSelectedCountryName(country.name);
    setSelectedFlag(country.flag);

    // Automatically synchronize display currency to country default
    if (country.currency) {
      setSelectedCurrency(country.currency);
      const matchCurr = currencies.find((c) => c.code === country.currency);
      if (matchCurr) {
        setSelectedSymbol(matchCurr.symbol);
      }
    }
  };

  const handleSelectCurrency = (currency: CurrencyItem) => {
    setSelectedCurrency(currency.code);
    setSelectedSymbol(currency.symbol);
  };

  // Save changes
  const handleSave = async () => {
    setIsSaving(true);
    try {
      await regionalPrefs.updatePreferences(selectedCountry, selectedCurrency);
      setIsOpen(false);
    } catch (err) {
      console.error('Failed to save preferences:', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700/60 bg-slate-900/80 hover:bg-slate-800 hover:border-cyan-500/50 text-slate-300 hover:text-white transition-all text-xs font-medium backdrop-blur-sm group ${className}`}
        title="Change Country & Currency Preferences"
      >
        <Globe className="w-3.5 h-3.5 text-cyan-400 group-hover:rotate-12 transition-transform" />
        <span className="text-base leading-none">{selectedFlag}</span>
        <span className="font-semibold text-slate-200">{selectedCountryName || selectedCountry}</span>
        <span className="text-slate-500">|</span>
        <span className="text-cyan-400 font-mono font-medium">
          {selectedCurrency} {selectedSymbol}
        </span>
      </button>

      {/* Modal Dialog */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fadeIn">
          <div className="relative w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden text-slate-100">
            {/* Header */}
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                  <Globe className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-white text-base">Regional Preferences &amp; Currency</h3>
                  <p className="text-xs text-slate-400">Personalize country localization and display currency.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Auto-Detect Banner */}
            <div className="px-5 py-3 bg-slate-950/40 border-b border-slate-800/80 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-slate-300">
                <span className="text-base">{selectedFlag}</span>
                <span>Current: <strong>{selectedCountryName}</strong> ({selectedCurrency} {selectedSymbol})</span>
              </div>
              <button
                type="button"
                onClick={handleAutoDetect}
                disabled={isDetecting}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 transition disabled:opacity-50"
              >
                {isDetecting ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>Detecting...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3 h-3" />
                    <span>Auto-detect</span>
                  </>
                )}
              </button>
            </div>

            {detectionNotice && (
              <div className="px-5 py-2 bg-cyan-950/40 text-cyan-300 border-b border-cyan-800/40 text-xs flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span>{detectionNotice}</span>
              </div>
            )}

            {/* Search and Navigation Tabs */}
            <div className="p-4 border-b border-slate-800 space-y-3 bg-slate-900/90">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder={activeTab === 'country' ? 'Search country name, code, or currency...' : 'Search currency code or name...'}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-xs text-white placeholder-slate-400 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>

              <div className="flex rounded-xl bg-slate-800/60 p-1 border border-slate-700/50">
                <button
                  type="button"
                  onClick={() => setActiveTab('country')}
                  className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition ${
                    activeTab === 'country'
                      ? 'bg-cyan-500 text-slate-950 font-semibold shadow-sm'
                      : 'text-slate-300 hover:text-white'
                  }`}
                >
                  1. Country / Region ({selectedCountry})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('currency')}
                  className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition ${
                    activeTab === 'currency'
                      ? 'bg-cyan-500 text-slate-950 font-semibold shadow-sm'
                      : 'text-slate-300 hover:text-white'
                  }`}
                >
                  2. Display Currency ({selectedCurrency})
                </button>
              </div>
            </div>

            {/* Content Lists */}
            <div className="flex-1 overflow-y-auto p-4 max-h-[320px] divide-y divide-slate-800/60">
              {isLoadingCatalogs ? (
                <div className="flex flex-col items-center justify-center py-12 text-slate-400 gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
                  <span className="text-xs">Loading regional catalog...</span>
                </div>
              ) : activeTab === 'country' ? (
                filteredCountries.length === 0 ? (
                  <div className="text-center py-8 text-xs text-slate-400">No countries match "{searchQuery}"</div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {filteredCountries.map((c) => {
                      const isSelected = selectedCountry === c.code;
                      return (
                        <button
                          key={c.code}
                          type="button"
                          onClick={() => handleSelectCountry(c)}
                          className={`flex items-center justify-between p-2.5 rounded-xl border text-left transition ${
                            isSelected
                              ? 'border-cyan-500 bg-cyan-950/30 text-white ring-1 ring-cyan-500/50'
                              : 'border-slate-800/80 bg-slate-950/40 hover:bg-slate-800/60 text-slate-300 hover:text-white hover:border-slate-700'
                          }`}
                        >
                          <div className="flex items-center gap-2.5 truncate">
                            <span className="text-lg leading-none">{c.flag}</span>
                            <div className="truncate">
                              <div className="text-xs font-medium truncate flex items-center gap-1.5">
                                <span>{c.name}</span>
                                {c.popular && (
                                  <span className="text-[10px] px-1 py-0.2 bg-slate-800 text-slate-400 rounded">Top</span>
                                )}
                              </div>
                              <div className="text-[10px] text-slate-400 font-mono">
                                {c.code} · {c.currency} · {c.dial_code}
                              </div>
                            </div>
                          </div>
                          {isSelected && <Check className="w-4 h-4 text-cyan-400 shrink-0 ml-2" />}
                        </button>
                      );
                    })}
                  </div>
                )
              ) : (
                filteredCurrencies.length === 0 ? (
                  <div className="text-center py-8 text-xs text-slate-400">No currencies match "{searchQuery}"</div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {filteredCurrencies.map((curr) => {
                      const isSelected = selectedCurrency === curr.code;
                      return (
                        <button
                          key={curr.code}
                          type="button"
                          onClick={() => handleSelectCurrency(curr)}
                          className={`flex items-center justify-between p-2.5 rounded-xl border text-left transition ${
                            isSelected
                              ? 'border-cyan-500 bg-cyan-950/30 text-white ring-1 ring-cyan-500/50'
                              : 'border-slate-800/80 bg-slate-950/40 hover:bg-slate-800/60 text-slate-300 hover:text-white hover:border-slate-700'
                          }`}
                        >
                          <div className="truncate">
                            <div className="text-xs font-semibold flex items-center gap-1.5">
                              <span className="text-cyan-400 font-mono">{curr.code}</span>
                              <span className="text-slate-200">({curr.symbol})</span>
                            </div>
                            <div className="text-[10px] text-slate-400 truncate">{curr.name}</div>
                          </div>
                          {isSelected && <Check className="w-4 h-4 text-cyan-400 shrink-0 ml-2" />}
                        </button>
                      );
                    })}
                  </div>
                )
              )}
            </div>

            {/* Footer Actions */}
            <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between gap-3">
              <div className="text-[11px] text-slate-400 flex items-center gap-1.5 truncate">
                <span>Selected:</span>
                <span className="text-white font-medium">{selectedCountryName}</span>
                <ArrowRight className="w-3 h-3 text-slate-500 inline" />
                <span className="text-cyan-400 font-mono font-semibold">{selectedCurrency} ({selectedSymbol})</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="px-3.5 py-1.5 rounded-xl border border-slate-700 text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={isSaving}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-semibold text-xs shadow-md transition disabled:opacity-50"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save &amp; Apply</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
