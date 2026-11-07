import React, { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
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
  ShieldCheck
} from 'lucide-react';

export const RegisterPage: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [country, setCountry] = useState('US');
  const [businessType, setBusinessType] = useState('Freelancer');
  const [preferredCurrency, setPreferredCurrency] = useState('USD');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { register } = useAuth();
  const navigate = useNavigate();

  // Dynamic password strength scoring (0 to 4)
  const passwordStrength = useMemo(() => {
    let score = 0;
    if (password.length >= 8) score += 1;
    if (/[A-Z]/.test(password)) score += 1;
    if (/[0-9]/.test(password)) score += 1;
    if (/[^A-Za-z0-9]/.test(password)) score += 1;
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
    if (passwordStrength <= 1) return 'bg-red-500';
    if (passwordStrength === 2) return 'bg-amber-500';
    if (passwordStrength === 3) return 'bg-blue-400';
    return 'bg-emerald-400';
  }, [passwordStrength]);

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
        country,
        business_type: businessType,
        preferred_currency: preferredCurrency,
        currency: preferredCurrency,
      });

      // Mark newly registered user for guided onboarding wizard
      sessionStorage.setItem('cashflow_show_onboarding', 'true');
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      setError(err.message || 'Registration failed. An account with this email may already exist.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink-950 flex flex-col justify-between text-white selection:bg-electric selection:text-white">
      {/* Top Simple Header */}
      <div className="max-w-[1440px] mx-auto w-full px-4 sm:px-6 py-6 flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-ink-900 border border-electric/40 flex items-center justify-center font-mono font-bold text-electric text-xs shadow-glow-electric">
            CL
          </div>
          <span className="font-extrabold text-base tracking-tight text-white flex items-center gap-1.5">
            Cashflow Lifeline
            <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-full bg-electric/15 text-electric-300 border border-electric/30">
              PayPal AI
            </span>
          </span>
        </Link>
        <Link to="/login" className="text-xs text-sardine-muted hover:text-white transition-colors">
          Already have an account? <span className="text-electric-300 font-bold">Sign In</span>
        </Link>
      </div>

      {/* Main Register Card */}
      <div className="max-w-xl w-full mx-auto px-4 py-6">
        <div className="rounded-2xl border border-ink-800 bg-ink-900/90 backdrop-blur-xl p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="space-y-1.5 text-center">
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Create Your Account
            </h1>
            <p className="text-xs text-sardine-muted">
              Autonomous cashflow forecasting and protection for independent businesses
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
              <div className="leading-relaxed">{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name & Email Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-300">
                  Full Name / Business Name
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Sarah Connor"
                    required
                    className="w-full pl-9 pr-3 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-electric transition-colors"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-300">
                  Business Email
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="sarah@agency.com"
                    required
                    className="w-full pl-9 pr-3 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-electric transition-colors"
                  />
                </div>
              </div>
            </div>

            {/* Country, Business Type, Currency */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-300">Country</label>
                <div className="relative">
                  <Globe className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                  <select
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white focus:outline-none focus:border-electric transition-colors appearance-none cursor-pointer"
                  >
                    <option value="US">United States (US)</option>
                    <option value="IN">India (IN)</option>
                    <option value="GB">United Kingdom (GB)</option>
                    <option value="DE">Germany (DE)</option>
                    <option value="CA">Canada (CA)</option>
                    <option value="AU">Australia (AU)</option>
                    <option value="SG">Singapore (SG)</option>
                    <option value="OTHER">Other Region</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-300">Business Type</label>
                <div className="relative">
                  <Briefcase className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                  <select
                    value={businessType}
                    onChange={(e) => setBusinessType(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white focus:outline-none focus:border-electric transition-colors appearance-none cursor-pointer"
                  >
                    <option value="Freelancer">Freelancer</option>
                    <option value="Agency">Agency</option>
                    <option value="Small business">Small Business</option>
                    <option value="Startup">Startup</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-300">Base Currency</label>
                <div className="relative">
                  <DollarSign className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                  <select
                    value={preferredCurrency}
                    onChange={(e) => setPreferredCurrency(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white focus:outline-none focus:border-electric transition-colors appearance-none cursor-pointer"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="INR">INR (₹)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="CAD">CAD (C$)</option>
                    <option value="AUD">AUD (A$)</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Password & Confirm Password */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-300">Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min. 8 chars"
                    required
                    className="w-full pl-9 pr-10 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-electric transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-3 text-sardine-muted hover:text-white"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-300">Confirm Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter password"
                    required
                    className="w-full pl-9 pr-10 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-electric transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-3 text-sardine-muted hover:text-white"
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
                  <span className="text-sardine-muted">Password Strength:</span>
                  <span className={`font-semibold ${strengthColor.replace('bg-', 'text-')}`}>
                    {strengthLabel}
                  </span>
                </div>
                <div className="h-1.5 w-full bg-ink-950 rounded-full overflow-hidden flex">
                  <div
                    className={`h-full transition-all duration-300 ${strengthColor}`}
                    style={{ width: `${Math.min(100, Math.max(15, passwordStrength * 25))}%` }}
                  />
                </div>
              </div>
            )}

            {/* Consent Checkboxes */}
            <div className="space-y-2 pt-2 text-xs">
              <label className="flex items-start space-x-2.5 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={termsAccepted}
                  onChange={(e) => setTermsAccepted(e.target.checked)}
                  required
                  className="mt-0.5 w-4 h-4 rounded border-ink-700 bg-ink-950 text-electric focus:ring-0 shrink-0"
                />
                <span className="text-[11px] leading-relaxed text-slate-300">
                  I agree to the <span className="text-electric-300 font-semibold">Terms of Service</span>,{' '}
                  <span className="text-electric-300 font-semibold">Privacy Policy</span>, and consent to process financial records required for cashflow intelligence.
                </span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 rounded-xl bg-electric hover:bg-electric-600 text-white font-bold text-xs sm:text-sm shadow-glow-electric transition-all flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer pt-3"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Creating Isolated Account...</span>
                </>
              ) : (
                <>
                  <span>Create Account &amp; Start Onboarding</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="border-t border-ink-800 pt-4 flex items-center justify-between text-xs text-sardine-muted">
            <div className="flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Zero plain text passwords &bull; Encrypted ledger</span>
            </div>
            <Link to="/login" className="text-electric-300 font-bold hover:underline">
              Sign In Instead &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Footer info */}
      <div className="py-6 text-center text-[11px] text-sardine-muted">
        PayPal AI Hackathon 2026 &bull; Strict multi-tenant isolation &bull; Dedicated owner tenancy
      </div>
    </div>
  );
};

