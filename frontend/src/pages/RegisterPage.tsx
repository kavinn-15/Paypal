import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { PhoneInput } from '../components/PhoneInput';
import { RegionalFooterSelector } from '../components/RegionalFooterSelector';
import { CountryItem, CurrencyItem } from '../types';
import {
  getStoredManualPreference,
  setStoredDetectedRegion
} from '../utils/currency';
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  User,
  Globe,
  Briefcase,
  DollarSign,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Loader2,
  ShieldCheck,
  Sparkles,
  MapPin,
  Flame
} from 'lucide-react';

const GoogleIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} viewBox="0 0 24 24">
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
    />
  </svg>
);

export const RegisterPage: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [phoneCountryCode, setPhoneCountryCode] = useState('+91');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [country, setCountry] = useState('US');
  const [businessType, setBusinessType] = useState('Freelancer');
  const [preferredCurrency, setPreferredCurrency] = useState('USD');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [countriesList, setCountriesList] = useState<CountryItem[]>([]);
  const [currenciesList, setCurrenciesList] = useState<CurrencyItem[]>([]);
  const [detectedBadge, setDetectedBadge] = useState<{ countryName: string; flag: string; currency: string } | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const { register } = useAuth();
  const navigate = useNavigate();

  // Load catalogs and detect regional preferences on mount
  useEffect(() => {
    let isMounted = true;
    const initializeRegion = async () => {
      try {
        const [cList, currList] = await Promise.all([
          api.getCountries().catch(() => []),
          api.getCurrencies().catch(() => []),
        ]);
        if (isMounted) {
          if (cList.length > 0) setCountriesList(cList);
          if (currList.length > 0) setCurrenciesList(currList);
        }

        // Check stored manual preference first
        const manualStored = getStoredManualPreference();
        if (manualStored && isMounted) {
          setCountry(manualStored.country);
          setPreferredCurrency(manualStored.currency);
          return;
        }

        // Fresh visitor: auto-detect region
        const detected = await api.detectRegion().catch(() => null);
        if (detected && isMounted && detected.country) {
          setCountry(detected.country);
          if (detected.currency) setPreferredCurrency(detected.currency);
          if (detected.dial_code) setPhoneCountryCode(detected.dial_code);
          setStoredDetectedRegion({
            country: detected.country,
            countryName: detected.country_name,
            currency: detected.currency,
            flag: detected.flag,
            symbol: detected.symbol,
            locale: detected.locale,
            source: 'detected',
            updatedAt: new Date().toISOString(),
          });

          setDetectedBadge({
            countryName: detected.country_name,
            flag: detected.flag,
            currency: detected.currency,
          });
        }
      } catch {
        // Fallback silently
      }
    };

    initializeRegion();
    return () => {
      isMounted = false;
    };
  }, []);

  const passwordStrength = useMemo(() => {
    let score = 0;
    if (password.length >= 8) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    return score;
  }, [password]);

  const strengthLabel = useMemo(() => {
    if (!password) return '';
    if (passwordStrength <= 1) return 'Weak (Requires 8+ chars & numbers)';
    if (passwordStrength === 2) return 'Fair';
    if (passwordStrength === 3) return 'Good';
    return 'Strong';
  }, [password, passwordStrength]);

  const strengthColor = useMemo(() => {
    if (passwordStrength <= 1) return 'bg-[var(--r)]';
    if (passwordStrength === 2) return 'bg-[var(--y)]';
    if (passwordStrength === 3) return 'bg-blue-500';
    return 'bg-[var(--g)]';
  }, [passwordStrength]);

  const handleGoogleSignUp = async () => {
    setError(null);
    setGoogleLoading(true);
    try {
      const redirectUri = `${window.location.origin}/auth/callback/google`;
      const res = await api.getGoogleAuthUrl(redirectUri);
      if (res.auth_url) {
        const clientId = res.client_id || import.meta.env.VITE_GOOGLE_CLIENT_ID;
        const isPlaceholder = !clientId || clientId.includes('placeholder_google_client_id') || res.auth_url.includes('placeholder_google_client_id');
        if (isPlaceholder) {
          navigate(`/auth/callback/google?code=mock_google_dev_user&state=${encodeURIComponent(res.state || 'dev_state')}`);
          return;
        }
        window.location.href = res.auth_url;
      }
    } catch (err: any) {
      setError(err.message || 'Unable to connect to Google authentication.');
      setGoogleLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Please provide your full name or legal business name.');
      return;
    }

    if (!email.trim() || !email.includes('@')) {
      setError('Please provide a valid business email address.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (passwordStrength < 2) {
      setError('Password must contain both letters and at least one number.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    if (!termsAccepted) {
      setError('Please accept the Terms of Service and Privacy Policy to proceed.');
      return;
    }

    setLoading(true);
    try {
      await register({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
        phone_number: phoneNumber.trim() || undefined,
        phone_country_code: phoneCountryCode,
        country,
        business_type: businessType,
        preferred_currency: preferredCurrency,
        currency: preferredCurrency,
        terms_accepted: termsAccepted,
      });

      // Mark newly registered user for guided onboarding wizard
      sessionStorage.setItem('cashflow_show_onboarding', 'true');

      if (phoneNumber.trim()) {
        navigate(`/verify-phone?phone=${encodeURIComponent(phoneNumber.trim())}&email=${encodeURIComponent(email.trim().toLowerCase())}`, {
          replace: true,
          state: { phone: phoneNumber.trim(), email: email.trim().toLowerCase() },
        });
      } else {
        navigate(`/verify-email?email=${encodeURIComponent(email.trim().toLowerCase())}`, {
          replace: true,
          state: { email: email.trim().toLowerCase() },
        });
      }
    } catch (err: any) {
      setError(err.message || 'Registration failed. An account with this email or phone may already exist.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--tx)] flex flex-col justify-between ignara-page-enter">
      {/* Top Simple Header */}
      <div className="max-w-[1080px] mx-auto w-full px-4 sm:px-6 py-4 sm:py-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div
            className="w-10 h-10 rounded-[12px] flex items-center justify-center text-white shrink-0 shadow-md"
            style={{ background: 'var(--grad-ember)' }}
          >
            <Flame className="w-5 h-5 text-white fill-white/20" strokeWidth={2.2} />
          </div>
          <span className="font-semibold text-base sm:text-lg tracking-tight text-[var(--tx)] flex items-center gap-1.5">
            Cashflow Lifeline
          </span>
        </Link>
        <Link to="/login" className="text-xs text-[var(--mu)] hover:text-[var(--tx)] transition-colors py-1.5">
          Already have an account? <span className="text-[var(--o1)] font-semibold">Sign In</span>
        </Link>
      </div>

      {/* Main Register Card */}
      <div className="max-w-xl w-full mx-auto px-4 py-4 sm:py-6">
        <div className="ignara-card p-6 sm:p-8 space-y-5">
          <div className="space-y-1 text-center">
            <h1 className="ignara-h1 text-2xl sm:text-3xl font-semibold">
              Create Your Account
            </h1>
            <p className="text-xs text-[var(--mu)]">
              Autonomous cashflow forecasting and protection for independent businesses
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="leading-relaxed break-words flex-1">{error}</div>
            </div>
          )}

          {/* Sign Up with Google */}
          <button
            type="button"
            onClick={handleGoogleSignUp}
            disabled={googleLoading || loading}
            className="ignara-btn-secondary w-full py-2.5 text-xs font-semibold"
          >
            {googleLoading ? (
              <Loader2 className="w-4 h-4 animate-spin text-[var(--o1)] shrink-0" />
            ) : (
              <GoogleIcon className="w-4 h-4 shrink-0" />
            )}
            <span>Sign up with Google</span>
          </button>

          <div className="relative flex items-center justify-center my-1">
            <div className="border-t border-[var(--line)] w-full" />
            <span className="bg-[var(--card)] px-3 text-[10.5px] font-mono uppercase tracking-wider text-[var(--dim)] absolute">
              or register with email
            </span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name & Email Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">
                  Full Name / Business Name
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Sarah Connor"
                    required
                    className="ignara-input w-full pl-9"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">
                  Business Email
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="sarah@agency.com"
                    required
                    className="ignara-input w-full pl-9"
                  />
                </div>
              </div>
            </div>

            {/* Mobile Phone Number with Country Selection */}
            <div className="space-y-1 bg-[var(--side)] p-3 rounded-[14px] border border-[var(--line)]">
              <PhoneInput
                value={phoneNumber}
                onChange={(full, code) => {
                  setPhoneNumber(full);
                  setPhoneCountryCode(code);
                }}
                defaultCountryCode="+91"
                label="Mobile Phone Number (for SMS Alerts & Login)"
                placeholder="98765 43210"
              />
              <p className="text-[10.5px] text-[var(--dim)]">
                You will receive a 6-digit SMS verification code to verify your mobile number.
              </p>
            </div>

            {/* Detected Location Badge */}
            {detectedBadge && (
              <div className="p-2.5 rounded-[12px] bg-[var(--o1)]/10 border border-[var(--o1)]/30 text-[var(--o1)] text-xs flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-[var(--o1)] shrink-0" />
                  <span>
                    Location detected: <strong>{detectedBadge.flag} {detectedBadge.countryName}</strong> (Suggested: <strong>{detectedBadge.currency}</strong>)
                  </span>
                </div>
                <span className="text-[10px] bg-[var(--card)] px-2 py-0.5 rounded-full font-mono border border-[var(--o1)]/20">
                  Auto-localized
                </span>
              </div>
            )}

            {/* Country, Business Type, Currency */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">Country / Region</label>
                <div className="relative">
                  <Globe className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <select
                    value={country}
                    onChange={(e) => {
                      const newCountry = e.target.value;
                      setCountry(newCountry);
                      setDetectedBadge(null);
                      const matched = countriesList.find((c) => c.code === newCountry);
                      if (matched && matched.currency) {
                        setPreferredCurrency(matched.currency);
                      }
                    }}
                    className="ignara-input w-full pl-9 cursor-pointer"
                  >
                    {countriesList.length > 0 ? (
                      countriesList.map((c) => (
                        <option key={c.code} value={c.code} className="bg-[var(--card)] text-[var(--tx)]">
                          {c.flag} {c.name} ({c.code})
                        </option>
                      ))
                    ) : (
                      <>
                        <option value="US" className="bg-[var(--card)] text-[var(--tx)]">🇺🇸 United States (US)</option>
                        <option value="IN" className="bg-[var(--card)] text-[var(--tx)]">🇮🇳 India (IN)</option>
                        <option value="GB" className="bg-[var(--card)] text-[var(--tx)]">🇬🇧 United Kingdom (GB)</option>
                        <option value="DE" className="bg-[var(--card)] text-[var(--tx)]">🇩🇪 Germany (DE)</option>
                        <option value="CA" className="bg-[var(--card)] text-[var(--tx)]">🇨🇦 Canada (CA)</option>
                        <option value="AU" className="bg-[var(--card)] text-[var(--tx)]">🇦🇺 Australia (AU)</option>
                        <option value="SG" className="bg-[var(--card)] text-[var(--tx)]">🇸🇬 Singapore (SG)</option>
                      </>
                    )}
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">Business Type</label>
                <div className="relative">
                  <Briefcase className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <select
                    value={businessType}
                    onChange={(e) => setBusinessType(e.target.value)}
                    className="ignara-input w-full pl-9 cursor-pointer"
                  >
                    <option value="Freelancer" className="bg-[var(--card)] text-[var(--tx)]">Freelancer</option>
                    <option value="Agency" className="bg-[var(--card)] text-[var(--tx)]">Agency</option>
                    <option value="Small business" className="bg-[var(--card)] text-[var(--tx)]">Small Business</option>
                    <option value="Startup" className="bg-[var(--card)] text-[var(--tx)]">Startup</option>
                    <option value="Other" className="bg-[var(--card)] text-[var(--tx)]">Other</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">Preferred Currency</label>
                <div className="relative">
                  <DollarSign className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <select
                    value={preferredCurrency}
                    onChange={(e) => {
                      setPreferredCurrency(e.target.value);
                      setDetectedBadge(null);
                    }}
                    className="ignara-input w-full pl-9 cursor-pointer"
                  >
                    {currenciesList.length > 0 ? (
                      currenciesList.map((curr) => (
                        <option key={curr.code} value={curr.code} className="bg-[var(--card)] text-[var(--tx)]">
                          {curr.code} ({curr.symbol}) — {curr.name}
                        </option>
                      ))
                    ) : (
                      <>
                        <option value="USD" className="bg-[var(--card)] text-[var(--tx)]">USD ($) — US Dollar</option>
                        <option value="INR" className="bg-[var(--card)] text-[var(--tx)]">INR (₹) — Indian Rupee</option>
                        <option value="EUR" className="bg-[var(--card)] text-[var(--tx)]">EUR (€) — Euro</option>
                        <option value="GBP" className="bg-[var(--card)] text-[var(--tx)]">GBP (£) — British Pound</option>
                        <option value="CAD" className="bg-[var(--card)] text-[var(--tx)]">CAD (CA$) — Canadian Dollar</option>
                        <option value="AUD" className="bg-[var(--card)] text-[var(--tx)]">AUD (A$) — Australian Dollar</option>
                      </>
                    )}
                  </select>
                </div>
              </div>
            </div>

            {/* Password & Confirm Password */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min. 8 chars"
                    required
                    className="ignara-input w-full pl-9 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2 top-2 p-1.5 text-[var(--dim)] hover:text-[var(--tx)] rounded-md min-w-[36px] min-h-[36px] flex items-center justify-center cursor-pointer"
                    aria-label="Toggle password visibility"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">Confirm Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter password"
                    required
                    className="ignara-input w-full pl-9 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-2 top-2 p-1.5 text-[var(--dim)] hover:text-[var(--tx)] rounded-md min-w-[36px] min-h-[36px] flex items-center justify-center cursor-pointer"
                    aria-label="Toggle confirm password visibility"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Password strength meter */}
            {password && (
              <div className="space-y-1.5 pt-0.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-[var(--dim)]">Password Strength:</span>
                  <span className={`font-semibold ${strengthColor.replace('bg-', 'text-')}`}>
                    {strengthLabel}
                  </span>
                </div>
                <div className="h-1.5 w-full bg-[var(--side)] rounded-full overflow-hidden flex">
                  <div
                    className={`h-full transition-all duration-300 ${strengthColor}`}
                    style={{ width: `${Math.min(100, Math.max(15, passwordStrength * 25))}%` }}
                  />
                </div>
              </div>
            )}

            {/* Consent Checkboxes */}
            <div className="space-y-2 pt-2 text-xs">
              <label className="flex items-start space-x-2.5 text-[var(--mu)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={termsAccepted}
                  onChange={(e) => setTermsAccepted(e.target.checked)}
                  required
                  className="mt-0.5 w-4 h-4 rounded border-[var(--line)] bg-[var(--bg)] text-[var(--o1)] focus:ring-0 shrink-0 cursor-pointer"
                />
                <span className="text-[11.5px] leading-relaxed text-[var(--mu)]">
                  I agree to the <span className="text-[var(--o1)] font-semibold">Terms of Service</span>,{' '}
                  <span className="text-[var(--o1)] font-semibold">Privacy Policy</span>, and consent to process financial records required for cashflow intelligence.
                </span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="ignara-btn-primary w-full py-3 text-xs sm:text-sm font-semibold"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                  <span>Creating Isolated Account...</span>
                </>
              ) : (
                <>
                  <span>Create Account &amp; Start Onboarding</span>
                  <ArrowRight className="w-4 h-4 shrink-0" />
                </>
              )}
            </button>
          </form>

          <div className="border-t border-[var(--line)] pt-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[var(--mu)]">
            <div className="flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-[var(--g)] shrink-0" />
              <span>Zero plain text passwords &bull; Encrypted ledger</span>
            </div>
            <Link to="/login" className="text-[var(--o1)] font-semibold hover:underline py-1">
              Sign In Instead &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Footer info & Regional Selector */}
      <div className="py-6 flex flex-col items-center justify-center gap-3 text-center text-xs text-[var(--dim)]">
        <div className="flex items-center gap-2">
          <span>Region &amp; Currency:</span>
          <RegionalFooterSelector />
        </div>
        <div>
          PayPal AI Hackathon 2026 &bull; Strict multi-tenant isolation &bull; Dedicated owner tenancy
        </div>
      </div>
    </div>
  );
};
