import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';
import { PayPalConnectionStatus, CountryItem, CurrencyItem } from '../types';
import { PhoneInput } from '../components/PhoneInput';
import {
  Settings,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Key,
  Globe,
  Shield,
  Lock,
  Bot,
  Radio,
  Mail,
  Phone,
  Edit2,
  X,
  Check,
  RotateCcw,
  Loader2,
  Sparkles,
  LogOut,
  UserCheck
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { currentUser, refreshUser, logout } = useAuth();
  const { updatePreferences } = useRegionalPreferences();

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore
    } finally {
      window.location.href = '/login';
    }
  };
  const [status, setStatus] = useState<PayPalConnectionStatus | null>(null);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; token_preview?: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // Change / Add phone modal state
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [phoneStep, setPhoneStep] = useState<'details' | 'verify_otp'>('details');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPhoneNumber, setNewPhoneNumber] = useState('');
  const [newPhoneCountryCode, setNewPhoneCountryCode] = useState('+91');
  const [changeOtpCode, setChangeOtpCode] = useState('');
  const [changeCooldown, setChangeCooldown] = useState(0);
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSuccess, setPhoneSuccess] = useState<string | null>(null);

  // Regional preferences state
  const [countriesList, setCountriesList] = useState<CountryItem[]>([]);
  const [currenciesList, setCurrenciesList] = useState<CurrencyItem[]>([]);
  const [selectedCountry, setSelectedCountry] = useState(currentUser?.country || 'US');
  const [selectedDisplayCurrency, setSelectedDisplayCurrency] = useState(
    currentUser?.preferred_currency || currentUser?.currency || 'USD'
  );
  const [autoDetectEnabled, setAutoDetectEnabled] = useState(
    currentUser?.region_detection_enabled !== false
  );
  const [preferenceSource, setPreferenceSource] = useState(
    currentUser?.region_preference_source || 'detected'
  );
  const [preferencesUpdatedAt, setPreferencesUpdatedAt] = useState<string | null>(
    currentUser?.region_preferences_updated_at || null
  );
  const [regionalSaving, setRegionalSaving] = useState(false);
  const [regionalSuccess, setRegionalSuccess] = useState<string | null>(null);
  const [regionalError, setRegionalError] = useState<string | null>(null);
  const [isRedetecting, setIsRedetecting] = useState(false);
  const [redetectSuggestion, setRedetectSuggestion] = useState<{
    country: string;
    countryName: string;
    flag: string;
    currency: string;
    method: string;
  } | null>(null);
  const [redetectNotice, setRedetectNotice] = useState<string | null>(null);

  useEffect(() => {
    api.getPayPalConnection().then(setStatus).catch(() => {});

    // Fetch regional catalogs and current profile preferences
    Promise.all([
      api.getCountries().catch(() => []),
      api.getCurrencies().catch(() => []),
      api.getRegionalPreferences().catch(() => null)
    ]).then(([cList, currList, prefs]) => {
      if (cList.length > 0) setCountriesList(cList);
      if (currList.length > 0) setCurrenciesList(currList);
      if (prefs) {
        setSelectedCountry(prefs.country);
        setSelectedDisplayCurrency(prefs.preferred_currency);
        setAutoDetectEnabled(prefs.region_detection_enabled);
        setPreferenceSource(prefs.region_preference_source);
        if (prefs.updated_at) setPreferencesUpdatedAt(prefs.updated_at);
      }
    });
  }, []);

  const handleSaveRegionalPreferences = async () => {
    setRegionalSaving(true);
    setRegionalSuccess(null);
    setRegionalError(null);
    try {
      await updatePreferences(selectedCountry, selectedDisplayCurrency, {
        region_detection_enabled: autoDetectEnabled,
      });
      setPreferenceSource('manual');
      setPreferencesUpdatedAt(new Date().toISOString());
      setRegionalSuccess(
        'Regional preferences saved successfully! All dashboards, cards, tables, and AI agents are immediately synchronized.'
      );
    } catch (err: any) {
      setRegionalError(err.message || 'Failed to update regional preferences.');
    } finally {
      setRegionalSaving(false);
    }
  };

  const handleRedetectLocation = async () => {
    setIsRedetecting(true);
    setRedetectNotice(null);
    setRedetectSuggestion(null);
    try {
      const detected = await api.detectRegion();
      if (detected && detected.detected && detected.country) {
        setRedetectSuggestion({
          country: detected.country,
          countryName: detected.country_name || detected.country,
          flag: detected.flag || '🌐',
          currency: detected.suggested_currency || 'USD',
          method: detected.detection_method
        });
      } else {
        setRedetectNotice('Unable to detect your location reliably. You can select your country and currency manually below.');
      }
    } catch {
      setRedetectNotice('Unable to detect your location reliably. You can select your country and currency manually below.');
    } finally {
      setIsRedetecting(false);
    }
  };

  const handleApplySuggestion = () => {
    if (redetectSuggestion) {
      setSelectedCountry(redetectSuggestion.country);
      setSelectedDisplayCurrency(redetectSuggestion.currency);
      setRedetectSuggestion(null);
      setRedetectNotice(`Applied ${redetectSuggestion.countryName} (${redetectSuggestion.currency}). Click "Save Regional Preferences" to persist.`);
    }
  };

  // Cooldown timer
  useEffect(() => {
    if (changeCooldown <= 0) return;
    const timer = setInterval(() => {
      setChangeCooldown((c) => (c > 0 ? c - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [changeCooldown]);

  const handleTestConnection = async () => {
    try {
      setIsTesting(true);
      const res = await api.testPayPalConnection();
      setTestResult(res);
      const updated = await api.getPayPalConnection();
      setStatus(updated);
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || 'Connection test failed' });
    } finally {
      setIsTesting(false);
    }
  };

  const handleOpenPhoneModal = () => {
    setPhoneStep('details');
    setCurrentPassword('');
    setNewPhoneNumber('');
    setChangeOtpCode('');
    setPhoneError(null);
    setPhoneSuccess(null);
    setShowPhoneModal(true);
  };

  const handleRequestPhoneChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPhoneError(null);

    if (!newPhoneNumber.trim()) {
      setPhoneError('Please enter a valid new mobile phone number.');
      return;
    }

    if (!currentPassword) {
      setPhoneError('Please enter your current password to authorize this security change.');
      return;
    }

    setPhoneLoading(true);
    try {
      const res = await api.requestPhoneChange(currentPassword, newPhoneNumber.trim(), newPhoneCountryCode);
      setPhoneStep('verify_otp');
      setChangeCooldown(res.cooldown_seconds || 60);
      setPhoneSuccess('6-digit SMS verification code sent to the new phone number.');
    } catch (err: any) {
      setPhoneError(err.message || 'Failed to request phone number change. Check your current password.');
    } finally {
      setPhoneLoading(false);
    }
  };

  const handleVerifyPhoneChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPhoneError(null);

    const cleanOtp = changeOtpCode.replace(/\D/g, '');
    if (cleanOtp.length !== 6) {
      setPhoneError('Please enter the 6-digit SMS verification code.');
      return;
    }

    setPhoneLoading(true);
    try {
      await api.verifyPhoneChange(newPhoneNumber.trim(), cleanOtp);
      await refreshUser();
      setPhoneSuccess('Phone number successfully updated and verified! Security alert dispatched to prior number.');
      setTimeout(() => {
        setShowPhoneModal(false);
      }, 1500);
    } catch (err: any) {
      setPhoneError(err.message || 'Invalid or expired OTP code.');
    } finally {
      setPhoneLoading(false);
    }
  };

  const handleResendChangeOtp = async () => {
    if (changeCooldown > 0 || !newPhoneNumber.trim() || !currentPassword) return;
    setPhoneError(null);
    setPhoneLoading(true);
    try {
      const res = await api.requestPhoneChange(currentPassword, newPhoneNumber.trim(), newPhoneCountryCode);
      setChangeCooldown(res.cooldown_seconds || 60);
      setPhoneSuccess('A fresh SMS OTP has been sent.');
    } catch (err: any) {
      setPhoneError(err.message || 'Failed to resend SMS code.');
    } finally {
      setPhoneLoading(false);
    }
  };

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Bento Header */}
      <div className="border-b border-[var(--line)] pb-2 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">
              Settings &amp; Security
            </h1>
            <span className="text-xs bg-[var(--g)]/15 text-[var(--g)] border border-[var(--g)]/30 px-2.5 py-0.5 rounded-full font-semibold">
              Sandbox Guard Active
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Verify PayPal sandbox connection, multi-channel authentication, deterministic guardrail limits, and AI safety bounds
          </p>
        </div>
      </div>

      {/* Security & Contact Information Card */}
      <div className="ignara-card p-4 sm:p-6 space-y-4 sm:space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--o1)]/10 border border-[var(--o1)]/20 flex items-center justify-center text-[var(--o1)] shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="ignara-h3">Security &amp; Contact Credentials</h3>
              <p className="text-xs text-[var(--mu)]">Identity verification, contact channels, and multi-factor credentials</p>
            </div>
          </div>

          <button
            onClick={handleOpenPhoneModal}
            className="ignara-btn-secondary flex items-center justify-center space-x-1.5 px-3 py-2 text-xs font-semibold rounded-xl min-h-[44px] sm:min-h-0 self-stretch sm:self-auto"
          >
            <Edit2 className="w-3.5 h-3.5 text-[var(--o1)] shrink-0" />
            <span>{currentUser?.phone_number ? 'Change Phone Number' : 'Add Phone Number'}</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4 pt-1 sm:pt-2">
          {/* Email Channel */}
          <div className="p-3.5 sm:p-4 rounded-xl border border-[var(--line)] bg-[var(--card2)] flex items-center justify-between gap-2">
            <div className="flex items-center space-x-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-[var(--side)] border border-[var(--line)] flex items-center justify-center text-[var(--o1)] shrink-0">
                <Mail className="w-4 h-4 text-[var(--o1)]" />
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--dim)] block">
                  Registered Work Email
                </span>
                <span className="font-semibold text-xs sm:text-sm text-[var(--tx)] block truncate max-w-[170px] sm:max-w-[240px]">
                  {currentUser?.email || 'N/A'}
                </span>
              </div>
            </div>

            {currentUser?.email_verified || currentUser?.is_demo ? (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-[var(--g)]/15 text-[var(--g)] border border-[var(--g)]/30 rounded-full text-[11px] font-semibold shrink-0">
                <CheckCircle2 className="w-3 h-3 text-[var(--g)]" />
                <span>Verified</span>
              </span>
            ) : (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-[var(--y)]/15 text-[var(--y)] border border-[var(--y)]/30 rounded-full text-[11px] font-semibold shrink-0">
                <AlertTriangle className="w-3 h-3 text-[var(--y)]" />
                <span>Unverified</span>
              </span>
            )}
          </div>

          {/* Phone Channel */}
          <div className="p-3.5 sm:p-4 rounded-xl border border-[var(--line)] bg-[var(--card2)] flex items-center justify-between gap-2">
            <div className="flex items-center space-x-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-[var(--side)] border border-[var(--line)] flex items-center justify-center text-[var(--o1)] shrink-0">
                <Phone className="w-4 h-4 text-[var(--o1)]" />
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--dim)] block">
                  Mobile SMS Channel
                </span>
                <span className="font-mono font-semibold text-xs sm:text-sm text-[var(--tx)] block truncate">
                  {currentUser?.phone_number || 'No phone registered'}
                </span>
              </div>
            </div>

            {currentUser?.phone_number ? (
              currentUser.phone_verified || currentUser.is_demo ? (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-[var(--g)]/15 text-[var(--g)] border border-[var(--g)]/30 rounded-full text-[11px] font-semibold shrink-0">
                  <CheckCircle2 className="w-3 h-3 text-[var(--g)]" />
                  <span>Verified</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-[var(--y)]/15 text-[var(--y)] border border-[var(--y)]/30 rounded-full text-[11px] font-semibold shrink-0">
                  <AlertTriangle className="w-3 h-3 text-[var(--y)]" />
                  <span>Unverified</span>
                </span>
              )
            ) : (
              <button
                onClick={handleOpenPhoneModal}
                className="text-[11px] font-semibold text-[var(--o1)] hover:underline shrink-0 p-1 min-h-[44px] flex items-center cursor-pointer"
              >
                + Register Phone
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Regional Preferences & Currency Localization Card */}
      <div className="ignara-card p-4 sm:p-6 space-y-4 sm:space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 shrink-0">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h3 className="ignara-h3">Regional Preferences &amp; Currency Localization</h3>
              <p className="text-xs text-[var(--mu)]">
                Operating country, display currency format, and automated approximate IP geolocation
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleRedetectLocation}
              disabled={isRedetecting}
              className="ignara-btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold cursor-pointer"
              title="Re-detect country and currency using network geolocation"
            >
              {isRedetecting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--o1)]" />
                  <span>Detecting...</span>
                </>
              ) : (
                <>
                  <RefreshCw className="w-3.5 h-3.5 text-[var(--o1)]" />
                  <span>Re-detect My Location</span>
                </>
              )}
            </button>
            <span className="text-[11px] font-mono px-2.5 py-1 rounded-full border bg-[var(--card2)] text-[var(--mu)] border-[var(--line)]">
              Source: <strong className="text-[var(--o1)] uppercase">{preferenceSource}</strong>
            </span>
            {preferencesUpdatedAt && (
              <span className="text-[10px] text-[var(--dim)] hidden sm:inline">
                Updated {new Date(preferencesUpdatedAt).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>

        {redetectSuggestion && (
          <div className="p-3 bg-[var(--o1)]/10 border border-[var(--o1)]/30 rounded-xl text-xs text-[var(--tx)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[var(--o1)] shrink-0" />
              <span>
                Detected location: <strong>{redetectSuggestion.flag} {redetectSuggestion.countryName}</strong> (Suggested: <strong>{redetectSuggestion.currency}</strong>). Apply to form fields?
              </span>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-auto">
              <button
                type="button"
                onClick={handleApplySuggestion}
                className="ignara-btn-primary px-3 py-1 rounded-lg text-xs font-semibold"
              >
                Apply
              </button>
              <button
                type="button"
                onClick={() => setRedetectSuggestion(null)}
                className="ignara-btn-secondary px-2.5 py-1 rounded-lg text-xs"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {redetectNotice && (
          <div className="p-3 bg-[var(--y)]/10 border border-[var(--y)]/30 rounded-xl text-xs text-[var(--y)] flex items-center justify-between gap-2">
            <span>{redetectNotice}</span>
            <button
              type="button"
              onClick={() => setRedetectNotice(null)}
              className="text-[var(--y)] hover:opacity-80 text-xs font-semibold px-1 cursor-pointer"
            >
              &times;
            </button>
          </div>
        )}

        {regionalSuccess && (
          <div className="p-3 bg-[var(--g)]/10 border border-[var(--g)]/30 rounded-xl text-xs text-[var(--g)] flex items-start space-x-2">
            <CheckCircle2 className="w-4 h-4 text-[var(--g)] shrink-0 mt-0.5" />
            <span>{regionalSuccess}</span>
          </div>
        )}

        {regionalError && (
          <div className="p-3 bg-[var(--r)]/10 border border-[var(--r)]/30 rounded-xl text-xs text-[var(--r)] flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-[var(--r)] shrink-0 mt-0.5" />
            <span>{regionalError}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
          {/* Country Selection */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-[var(--tx)]">Country / Region</label>
            <select
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--card2)] border border-[var(--line)] rounded-xl text-xs sm:text-sm text-[var(--tx)] focus:outline-none focus:border-[var(--o1)] cursor-pointer"
              style={{ backgroundColor: 'var(--card2)', color: 'var(--tx)' }}
            >
              {countriesList.length > 0 ? (
                countriesList.map((c) => (
                  <option key={c.code} value={c.code} className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>
                    {c.flag} {c.name} ({c.code})
                  </option>
                ))
              ) : (
                <>
                  <option value="US" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>🇺🇸 United States (US)</option>
                  <option value="IN" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>🇮🇳 India (IN)</option>
                  <option value="GB" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>🇬🇧 United Kingdom (GB)</option>
                  <option value="DE" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>🇩🇪 Germany (DE)</option>
                  <option value="CA" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>🇨🇦 Canada (CA)</option>
                  <option value="AU" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>🇦🇺 Australia (AU)</option>
                </>
              )}
            </select>
            <span className="text-[10px] text-[var(--mu)] block">
              Governs regional formatting and standard payment dial codes.
            </span>
          </div>

          {/* Preferred Display Currency */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-[var(--tx)]">Preferred Display Currency</label>
            <select
              value={selectedDisplayCurrency}
              onChange={(e) => setSelectedDisplayCurrency(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--card2)] border border-[var(--line)] rounded-xl text-xs sm:text-sm text-[var(--tx)] focus:outline-none focus:border-[var(--o1)] cursor-pointer"
              style={{ backgroundColor: 'var(--card2)', color: 'var(--tx)' }}
            >
              {currenciesList.length > 0 ? (
                currenciesList.map((cur) => (
                  <option key={cur.code} value={cur.code} className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>
                    {cur.code} ({cur.symbol}) — {cur.name}
                  </option>
                ))
              ) : (
                <>
                  <option value="USD" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>USD ($) — US Dollar</option>
                  <option value="INR" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>INR (₹) — Indian Rupee</option>
                  <option value="EUR" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>EUR (€) — Euro</option>
                  <option value="GBP" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>GBP (£) — British Pound</option>
                  <option value="CAD" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>CAD (CA$) — Canadian Dollar</option>
                  <option value="AUD" className="bg-[var(--card)] text-[var(--tx)]" style={{ backgroundColor: 'var(--card)', color: 'var(--tx)' }}>AUD (A$) — Australian Dollar</option>
                </>
              )}
            </select>
            <span className="text-[10px] text-[var(--mu)] block">
              Financial dashboard, summaries, and forecasts render in this currency.
            </span>
          </div>

          {/* Base Accounting Ledger Currency (Informational / Safety) */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-[var(--tx)]">Base Accounting Ledger</label>
            <div className="p-2.5 rounded-xl bg-[var(--card2)] border border-[var(--line)] text-xs font-mono font-semibold text-[var(--tx)] flex items-center justify-between min-h-[42px]">
              <span>{currentUser?.currency || 'USD'} (Fixed)</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--g)]/15 text-[var(--g)] border border-[var(--g)]/30 font-sans font-semibold">
                Audited Ledger
              </span>
            </div>
            <span className="text-[10px] text-[var(--dim)] block">
              Underlying ledger currency. Preserved to prevent unauthorized cross-currency ledger drift.
            </span>
          </div>
        </div>

        {/* Auto detection toggle and actions */}
        <div className="pt-3 border-t border-[var(--line)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <label className="flex items-center space-x-2 text-xs text-[var(--tx)] cursor-pointer">
            <input
              type="checkbox"
              checked={autoDetectEnabled}
              onChange={(e) => setAutoDetectEnabled(e.target.checked)}
              className="w-4 h-4 rounded border-[var(--line)] bg-[var(--card2)] text-[var(--o1)] accent-[var(--o1)] focus:ring-0"
            />
            <span>Enable automatic regional detection on future visits</span>
          </label>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <button
              type="button"
              onClick={() => {
                setSelectedCountry(currentUser?.country || 'US');
                setSelectedDisplayCurrency(currentUser?.preferred_currency || currentUser?.currency || 'USD');
                setAutoDetectEnabled(currentUser?.region_detection_enabled !== false);
                setRegionalSuccess(null);
                setRegionalError(null);
              }}
              className="ignara-btn-secondary px-3 py-1.5 text-xs font-medium cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveRegionalPreferences}
              disabled={regionalSaving}
              className="ignara-btn-primary px-4 py-1.5 text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {regionalSaving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <span>Save Regional Preferences</span>
              )}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Sandbox Connection Card */}
        <div className="ignara-card p-4 sm:p-6 space-y-4 sm:space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--o1)]/10 border border-[var(--o1)]/20 flex items-center justify-center text-[var(--o1)] shrink-0">
                <Key className="w-5 h-5" />
              </div>
              <div>
                <h3 className="ignara-h3">PayPal REST API Sandbox</h3>
                <p className="text-xs text-[var(--mu)]">Target: api-m.sandbox.paypal.com</p>
              </div>
            </div>

            <button
              onClick={handleTestConnection}
              disabled={isTesting}
              className="ignara-btn-primary flex items-center justify-center space-x-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl min-h-[40px] self-stretch sm:self-auto cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />
              <span>{isTesting ? 'Testing...' : 'Test Connection'}</span>
            </button>
          </div>

          {/* Test Result Message */}
          {testResult && (
            <div
              className={`p-3.5 sm:p-4 rounded-xl border text-xs shadow-2xs ${
                testResult.success
                  ? 'bg-[var(--g)]/10 text-[var(--g)] border-[var(--g)]/30'
                  : 'bg-[var(--y)]/10 text-[var(--y)] border-[var(--y)]/30'
              }`}
            >
              <div className="font-bold flex items-center space-x-1.5">
                {testResult.success ? <CheckCircle2 className="w-4 h-4 text-[var(--g)] shrink-0" /> : <AlertTriangle className="w-4 h-4 text-[var(--y)] shrink-0" />}
                <span>{testResult.success ? 'Sandbox Authentication Verified' : 'Authentication Diagnostic'}</span>
              </div>
              <p className="mt-1 text-[var(--tx)] break-words">{testResult.message}</p>
              {testResult.token_preview && (
                <p className="font-mono text-[11px] mt-1.5 bg-[var(--card2)] p-1.5 rounded-lg border border-[var(--line)] text-[var(--g)] break-all">
                  Token: {testResult.token_preview}
                </p>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-3 text-xs border-t border-[var(--line)]">
            <div className="bg-[var(--card2)] p-3 rounded-xl border border-[var(--line)]">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Integration Type</span>
              <span className="font-semibold text-[var(--tx)] block mt-0.5 truncate">{status?.account_label || 'Shared Developer Sandbox'}</span>
              <span className="text-[10px] text-[var(--mu)] block">Test / Demo Mode</span>
            </div>
            <div className="bg-[var(--card2)] p-3 rounded-xl border border-[var(--line)]">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Environment</span>
              <span className="font-bold text-[var(--g)] block mt-0.5">SANDBOX ONLY</span>
              <span className="text-[10px] text-[var(--mu)] block">Hard Refusal Active</span>
            </div>
            <div className="bg-[var(--card2)] p-3 rounded-xl border border-[var(--line)] col-span-2 sm:col-span-1">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Webhook ID</span>
              <span className="font-mono font-semibold text-[var(--tx)] block mt-0.5 truncate">
                {status?.webhook_id ? status.webhook_id.substring(0, 14) + '...' : 'Registered via API'}
              </span>
              <span className="text-[10px] text-[var(--mu)] block">Verified Listener</span>
            </div>
          </div>
          <div className="p-3 bg-[var(--side)] border border-[var(--line)] rounded-xl text-[11px] text-[var(--mu)] leading-relaxed">
            <span className="font-semibold text-[var(--tx)]">Integration Notice: </span>
            This workspace uses the Cashflow Lifeline shared PayPal developer sandbox for simulated transactions and verification testing. Connecting an individual live merchant account requires PayPal Seller Onboarding (OAuth partner referrals).
          </div>
        </div>

        {/* Safety Policy Limits Card */}
        <div className="ignara-card p-4 sm:p-6 space-y-4 sm:space-y-5">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shrink-0">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="ignara-h3">Deterministic Policy Controls</h3>
              <p className="text-xs text-[var(--mu)]">Enforced by Guardrail Agent. Zero code paths bypass these bounds.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 bg-[var(--card2)] rounded-xl border border-[var(--line)]">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Early Discount</span>
              <span className="font-bold text-[var(--tx)] text-base">5.0% Cap</span>
              <span className="text-[10px] text-[var(--mu)] block mt-0.5">Plan B capped at 3.0%</span>
            </div>

            <div className="p-3.5 bg-[var(--card2)] rounded-xl border border-[var(--line)]">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Single Payout</span>
              <span className="font-bold text-[var(--tx)] text-base">$10,000 Cap</span>
              <span className="text-[10px] text-[var(--mu)] block mt-0.5">Hard financial ceiling</span>
            </div>

            <div className="p-3.5 bg-[var(--card2)] rounded-xl border border-[var(--line)]">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Currencies</span>
              <span className="font-bold text-[var(--tx)] text-sm">USD, EUR, GBP</span>
              <span className="text-[10px] text-[var(--mu)] block mt-0.5">Strict ISO whitelist</span>
            </div>
          </div>
        </div>

        {/* LLM Safety & Fallback Pod */}
        <div className="ignara-card p-4 sm:p-6 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--o1)]/10 border border-[var(--o1)]/20 flex items-center justify-center text-[var(--o1)] shrink-0">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="ignara-h3">LLM Safety Boundary</h3>
              <p className="text-xs text-[var(--mu)]">Google Gemini / Anthropic / Template Fallback</p>
            </div>
          </div>

          <div className="p-4 bg-[var(--card2)] rounded-xl border border-[var(--line)] text-xs space-y-2 text-[var(--tx)]">
            <div className="flex items-center space-x-2 text-[var(--g)] font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Zero-Execution Rule Enforced</span>
            </div>
            <p className="text-[var(--mu)] text-[11px] leading-relaxed">
              The AI layer is restricted to plain-language driver summaries and message drafts. It can never approve, execute, or modify any dollar amount or transaction.
            </p>
          </div>
        </div>

        {/* Webhook Ingress Architecture */}
        <div className="ignara-card p-4 sm:p-6 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--g)]/10 border border-[var(--g)]/20 flex items-center justify-center text-[var(--g)] shrink-0">
              <Radio className="w-5 h-5" />
            </div>
            <div>
              <h3 className="ignara-h3">Webhook Ingress Pipeline</h3>
              <p className="text-xs text-[var(--mu)]">Cryptographically verified via PayPal API</p>
            </div>
          </div>

          <div className="p-4 bg-[var(--card2)] rounded-xl border border-[var(--line)] text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[var(--mu)]">Verification Endpoint:</span>
              <span className="font-mono text-[var(--tx)] font-semibold">/v1/notifications/verify-webhook-signature</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[var(--mu)]">Queue Persistence:</span>
              <span className="font-mono text-[var(--g)] font-semibold">asyncio + SQLite / MySQL WAL</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[var(--mu)]">Auto-Recalculate on Pay:</span>
              <span className="font-mono text-[var(--o1)] font-semibold">Enabled</span>
            </div>
          </div>
        </div>
      </div>

      {/* Account Session & Sign Out Section */}
      <div className="ignara-card p-4 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start sm:items-center space-x-3.5">
            <div className="w-10 h-10 rounded-xl bg-[var(--side)] border border-[var(--line)] flex items-center justify-center text-[var(--o1)] shrink-0">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="ignara-h3">Active User Account Session</h3>
                {currentUser?.is_demo && (
                  <span className="text-[10px] bg-[var(--y)]/15 text-[var(--y)] border border-[var(--y)]/30 font-semibold px-2 py-0.5 rounded-full">
                    Demo Mode (Alex Morgan)
                  </span>
                )}
              </div>
              <p className="text-xs text-[var(--mu)] mt-0.5">
                Logged in as <strong className="text-[var(--tx)]">{currentUser?.name || 'User'}</strong> ({currentUser?.email}). Sign out to switch accounts.
              </p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className={`w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-semibold transition-all shadow-xs flex items-center justify-center space-x-2 min-h-[44px] cursor-pointer ${
              currentUser?.is_demo
                ? 'bg-rose-600 hover:bg-rose-700 text-white'
                : 'bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30'
            }`}
          >
            <LogOut className="w-4 h-4" />
            <span>{currentUser?.is_demo ? 'Exit Demo Account & Sign Out' : 'Sign Out of Account'}</span>
          </button>
        </div>
      </div>

      {/* Change / Register Phone Modal */}
      {showPhoneModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-3 sm:p-4 animate-fadeIn">
          <div className="bg-[var(--card)] rounded-2xl max-w-md w-full max-h-[92vh] flex flex-col p-4 sm:p-6 shadow-2xl border border-[var(--line)] space-y-4 sm:space-y-5 text-[var(--tx)]">
            <div className="flex justify-between items-center shrink-0">
              <div className="flex items-center space-x-2">
                <Phone className="w-5 h-5 text-[var(--o1)] shrink-0" />
                <h3 className="ignara-h3 truncate">
                  {currentUser?.phone_number ? 'Update Mobile Phone' : 'Register Mobile Phone'}
                </h3>
              </div>
              <button
                onClick={() => setShowPhoneModal(false)}
                aria-label="Close phone modal"
                className="w-9 h-9 sm:w-8 sm:h-8 flex items-center justify-center rounded-lg text-[var(--dim)] hover:text-[var(--tx)] hover:bg-[var(--card2)] transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto pr-1 space-y-4">
              {phoneError && (
                <div className="p-3 bg-[var(--r)]/10 border border-[var(--r)]/30 rounded-xl text-xs text-[var(--r)] flex items-start space-x-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span className="break-words">{phoneError}</span>
                </div>
              )}

              {phoneSuccess && (
                <div className="p-3 bg-[var(--g)]/10 border border-[var(--g)]/30 rounded-xl text-xs text-[var(--g)] flex items-start space-x-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                  <span className="break-words">{phoneSuccess}</span>
                </div>
              )}

              {phoneStep === 'details' ? (
                <form onSubmit={handleRequestPhoneChange} className="space-y-4">
                  <p className="text-xs text-[var(--mu)] leading-relaxed">
                    For account security, changing your mobile number requires confirming your account password. An SMS code will be sent to the new number.
                  </p>

                  <div className="space-y-1">
                    <label className="block text-xs font-semibold text-[var(--tx)]">
                      Current Account Password <span className="text-[var(--r)]">*</span>
                    </label>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3 pointer-events-none" />
                      <input
                        type="password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        placeholder="••••••••"
                        required
                        className="ignara-input w-full pl-9"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <PhoneInput
                      value={newPhoneNumber}
                      onChange={(full, code) => {
                        setNewPhoneNumber(full);
                        setNewPhoneCountryCode(code);
                      }}
                      defaultCountryCode="+91"
                      label="New Mobile Phone Number"
                      placeholder="98765 43210"
                      required
                    />
                  </div>

                  <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setShowPhoneModal(false)}
                      className="ignara-btn-secondary w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-semibold rounded-xl transition-colors min-h-[44px] sm:min-h-0 flex items-center justify-center cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={phoneLoading}
                      className="ignara-btn-primary w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-semibold rounded-xl shadow-btn transition-colors disabled:opacity-50 flex items-center justify-center space-x-1.5 min-h-[44px] sm:min-h-0 cursor-pointer"
                    >
                      {phoneLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>Send SMS Verification</span>
                    </button>
                  </div>
                </form>
              ) : (
                <form onSubmit={handleVerifyPhoneChange} className="space-y-4">
                  <p className="text-xs text-[var(--mu)] leading-relaxed">
                    Enter the 6-digit SMS code sent to <strong className="font-mono text-[var(--tx)] break-all">{newPhoneNumber}</strong>:
                  </p>

                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={changeOtpCode}
                    onChange={(e) => setChangeOtpCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="123456"
                    required
                    autoFocus
                    className="w-full text-center tracking-[0.25em] sm:tracking-[0.4em] font-mono text-lg sm:text-xl py-2.5 sm:py-3 bg-[var(--bg)] border border-[var(--line)] text-[var(--tx)] rounded-xl focus:outline-none focus:border-[var(--o1)]"
                  />

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs text-[var(--mu)]">
                    <span>
                      {changeCooldown > 0 ? (
                        <span>Resend in <strong>{changeCooldown}s</strong></span>
                      ) : (
                        <button
                          type="button"
                          onClick={handleResendChangeOtp}
                          disabled={phoneLoading}
                          className="text-[var(--o1)] font-semibold flex items-center space-x-1 min-h-[44px] sm:min-h-0 py-1 cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Resend SMS OTP</span>
                        </button>
                      )}
                    </span>
                    <span>Valid for 5 mins</span>
                  </div>

                  <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setPhoneStep('details')}
                      className="ignara-btn-secondary w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-semibold rounded-xl transition-colors min-h-[44px] sm:min-h-0 flex items-center justify-center cursor-pointer"
                    >
                      Back
                    </button>
                    <button
                      type="submit"
                      disabled={phoneLoading || changeOtpCode.length !== 6}
                      className="ignara-btn-primary w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-semibold rounded-xl shadow-btn transition-colors disabled:opacity-50 flex items-center justify-center space-x-1.5 min-h-[44px] sm:min-h-0 cursor-pointer"
                    >
                      {phoneLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>Verify &amp; Update Phone</span>
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
