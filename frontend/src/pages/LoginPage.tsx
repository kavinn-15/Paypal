import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { PhoneInput } from '../components/PhoneInput';
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  Phone,
  KeyRound,
  AlertCircle,
  ArrowRight,
  Play,
  Loader2,
  CheckCircle,
  RotateCcw,
  Flame,
  Sparkles
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

type LoginTab = 'email' | 'phone_password' | 'phone_otp';

export const LoginPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<LoginTab>('email');

  // Email form
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Phone form
  const [phoneNumber, setPhoneNumber] = useState('');
  const [phoneCountryCode, setPhoneCountryCode] = useState('+91');
  const [phonePassword, setPhonePassword] = useState('');
  const [showPhonePassword, setShowPhonePassword] = useState(false);

  // Phone OTP flow
  const [otpStep, setOtpStep] = useState<'input_phone' | 'input_otp'>('input_phone');
  const [otpCode, setOtpCode] = useState('');
  const [cooldown, setCooldown] = useState(0);
  const [otpSentMessage, setOtpSentMessage] = useState<string | null>(null);

  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  const { login, loginWithPhonePassword, loginWithPhoneOtp, demoLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  // Cooldown timer effect
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((c) => (c > 0 ? c - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Please provide both your business email and password.');
      return;
    }

    setLoading(true);

    try {
      const res = await login(email.trim(), password);
      if (res && res.email_verified === false) {
        navigate('/verify-email', { state: { email: email.trim().toLowerCase() } });
      } else {
        navigate(from, { replace: true });
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify your email and password.');
    } finally {
      setLoading(false);
    }
  };

  const handlePhonePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!phoneNumber.trim() || !phonePassword) {
      setError('Please provide both your mobile phone number and password.');
      return;
    }

    setLoading(true);
    try {
      await loginWithPhonePassword(phoneNumber.trim(), phonePassword);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Phone authentication failed. Please verify your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestPhoneLoginOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!phoneNumber.trim()) {
      setError('Please enter your mobile phone number.');
      return;
    }

    setLoading(true);
    try {
      const res = await api.requestPhoneLoginOtp(phoneNumber.trim());
      setOtpStep('input_otp');
      setCooldown(res.cooldown_seconds || 60);
      setOtpSentMessage(`We sent a 6-digit login code via SMS to ${phoneNumber.trim()}.`);
    } catch (err: any) {
      setError(err.message || 'Failed to send SMS login code.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyPhoneLoginOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanOtp = otpCode.replace(/\D/g, '');
    if (cleanOtp.length !== 6) {
      setError('Please enter the 6-digit SMS verification code.');
      return;
    }

    setLoading(true);
    try {
      await loginWithPhoneOtp(phoneNumber.trim(), cleanOtp);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Invalid or expired SMS OTP code.');
    } finally {
      setLoading(false);
    }
  };

  const handleResendPhoneLoginOtp = async () => {
    if (cooldown > 0) return;
    setError(null);
    setLoading(true);
    try {
      const res = await api.requestPhoneLoginOtp(phoneNumber.trim());
      setCooldown(res.cooldown_seconds || 60);
      setOtpSentMessage('A fresh SMS login code has been sent.');
    } catch (err: any) {
      setError(err.message || 'Failed to resend SMS code.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    setGoogleLoading(true);
    try {
      const res = await api.getGoogleAuthUrl();
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

  const handleDemoSignIn = async () => {
    setError(null);
    setDemoLoading(true);
    try {
      await demoLogin();
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Demo initialization failed. Please try again.');
    } finally {
      setDemoLoading(false);
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
        <Link to="/" className="text-xs text-[var(--mu)] hover:text-[var(--tx)] transition-colors py-1.5">
          &larr; Back to Home
        </Link>
      </div>

      {/* Main Login Card */}
      <div className="max-w-md w-full mx-auto px-4 py-4 sm:py-6">
        <div className="ignara-card p-6 sm:p-8 space-y-5">
          <div className="space-y-1 text-center">
            <h1 className="ignara-h1 text-2xl font-semibold">Sign In</h1>
            <p className="text-xs text-[var(--mu)]">
              Access your real-time cashflow predictions and rescue inbox
            </p>
          </div>

          {(location.state as any)?.from && (
            <div className="p-3 rounded-[14px] bg-[var(--o1)]/10 border border-[var(--o1)]/25 text-[var(--o1)] text-xs flex items-center gap-2">
              <Sparkles className="w-4 h-4 shrink-0" />
              <span>Please sign in or use 1-Click Demo to access <strong>{from}</strong>.</span>
            </div>
          )}

          {error && (
            <div className="p-3.5 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="leading-relaxed break-words flex-1">{error}</div>
            </div>
          )}

          {/* Social Sign-In: Google */}
          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={googleLoading || loading}
            className="ignara-btn-secondary w-full py-2.5 text-xs font-semibold"
          >
            {googleLoading ? (
              <Loader2 className="w-4 h-4 animate-spin text-[var(--o1)] shrink-0" />
            ) : (
              <GoogleIcon className="w-4 h-4 shrink-0" />
            )}
            <span>Continue with Google</span>
          </button>

          {/* Divider */}
          <div className="relative flex items-center justify-center my-1">
            <div className="border-t border-[var(--line)] w-full" />
            <span className="bg-[var(--card)] px-3 text-[10.5px] font-mono uppercase tracking-wider text-[var(--dim)] absolute">
              or select method
            </span>
          </div>

          {/* Segmented Login Tabs */}
          <div className="grid grid-cols-3 gap-1 p-1 bg-[var(--side)] rounded-[999px] border border-[var(--line)]">
            <button
              type="button"
              onClick={() => {
                setActiveTab('email');
                setError(null);
              }}
              className={`py-1.5 px-1 text-center rounded-[999px] text-[11px] font-medium transition-all flex items-center justify-center space-x-1 min-h-[36px] ${
                activeTab === 'email'
                  ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                  : 'text-[var(--mu)] hover:text-[var(--tx)]'
              }`}
            >
              <Mail className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Email</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setActiveTab('phone_password');
                setError(null);
              }}
              className={`py-1.5 px-1 text-center rounded-[999px] text-[11px] font-medium transition-all flex items-center justify-center space-x-1 min-h-[36px] ${
                activeTab === 'phone_password'
                  ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                  : 'text-[var(--mu)] hover:text-[var(--tx)]'
              }`}
            >
              <Phone className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Phone + Pwd</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setActiveTab('phone_otp');
                setError(null);
              }}
              className={`py-1.5 px-1 text-center rounded-[999px] text-[11px] font-medium transition-all flex items-center justify-center space-x-1 min-h-[36px] ${
                activeTab === 'phone_otp'
                  ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                  : 'text-[var(--mu)] hover:text-[var(--tx)]'
              }`}
            >
              <KeyRound className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Phone OTP</span>
            </button>
          </div>

          {/* Tab 1: Email + Password */}
          {activeTab === 'email' && (
            <form onSubmit={handleEmailSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">
                  Work / Business Email
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="alex@freelance.org"
                    required
                    autoFocus
                    className="ignara-input w-full pl-9"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-[var(--tx)]">Password</label>
                  <Link
                    to="/forgot-password"
                    className="text-xs text-[var(--o1)] hover:underline font-medium"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="ignara-input w-full pl-9 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-3 text-[var(--dim)] hover:text-[var(--tx)] cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs pt-1">
                <label className="flex items-center space-x-2 text-[var(--mu)] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-3.5 h-3.5 rounded border-[var(--line)] text-[var(--o1)] focus:ring-0 cursor-pointer"
                  />
                  <span>Remember me on this browser</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Signing in...</span>
                  </>
                ) : (
                  <>
                    <span>Sign In with Email</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          )}

          {/* Tab 2: Phone + Password */}
          {activeTab === 'phone_password' && (
            <form onSubmit={handlePhonePasswordSubmit} className="space-y-4">
              <div className="p-3 rounded-[14px] bg-[var(--side)] border border-[var(--line)]">
                <PhoneInput
                  value={phoneNumber}
                  onChange={(full, code) => {
                    setPhoneNumber(full);
                    setPhoneCountryCode(code);
                  }}
                  defaultCountryCode="+91"
                  label="Registered Mobile Phone"
                  placeholder="98765 43210"
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-[var(--tx)]">Password</label>
                  <Link
                    to="/forgot-password"
                    className="text-xs text-[var(--o1)] hover:underline font-medium"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type={showPhonePassword ? 'text' : 'password'}
                    value={phonePassword}
                    onChange={(e) => setPhonePassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="ignara-input w-full pl-9 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPhonePassword(!showPhonePassword)}
                    className="absolute right-3 top-3 text-[var(--dim)] hover:text-[var(--tx)] cursor-pointer"
                  >
                    {showPhonePassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Signing in...</span>
                  </>
                ) : (
                  <>
                    <span>Sign In with Phone</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          )}

          {/* Tab 3: Phone + OTP */}
          {activeTab === 'phone_otp' && (
            <div>
              {otpStep === 'input_phone' ? (
                <form onSubmit={handleRequestPhoneLoginOtp} className="space-y-4">
                  <div className="p-3 rounded-[14px] bg-[var(--side)] border border-[var(--line)]">
                    <PhoneInput
                      value={phoneNumber}
                      onChange={(full, code) => {
                        setPhoneNumber(full);
                        setPhoneCountryCode(code);
                      }}
                      defaultCountryCode="+91"
                      label="Registered Mobile Phone"
                      placeholder="98765 43210"
                    />
                  </div>

                  <p className="text-[11.5px] text-[var(--mu)] leading-relaxed">
                    We will send a 6-digit one-time SMS verification code to your verified mobile number.
                  </p>

                  <button
                    type="submit"
                    disabled={loading || !phoneNumber.trim()}
                    className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Sending SMS OTP...</span>
                      </>
                    ) : (
                      <>
                        <span>Send 6-Digit SMS Code</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyPhoneLoginOtp} className="space-y-4">
                  {otpSentMessage && (
                    <div className="p-3 rounded-[14px] bg-[var(--g)]/15 border border-[var(--g)]/30 text-[var(--g)] text-xs flex items-center space-x-2">
                      <CheckCircle className="w-4 h-4 shrink-0" />
                      <span>{otpSentMessage}</span>
                    </div>
                  )}

                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="block text-xs font-semibold text-[var(--tx)]">
                        6-Digit SMS Code
                      </label>
                      <button
                        type="button"
                        onClick={() => {
                          setOtpStep('input_phone');
                          setOtpCode('');
                          setError(null);
                        }}
                        className="text-[11px] text-[var(--o1)] hover:underline cursor-pointer"
                      >
                        Change number
                      </button>
                    </div>

                    <input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                      placeholder="123456"
                      required
                      autoFocus
                      className="ignara-input w-full text-center tracking-[0.4em] font-mono text-xl py-3"
                    />
                  </div>

                  <div className="flex items-center justify-between text-xs text-[var(--mu)]">
                    <span>
                      {cooldown > 0 ? (
                        <span>Resend in <strong className="text-[var(--tx)] font-mono">{cooldown}s</strong></span>
                      ) : (
                        <button
                          type="button"
                          onClick={handleResendPhoneLoginOtp}
                          disabled={loading}
                          className="text-[var(--o1)] hover:underline font-semibold flex items-center space-x-1 cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Resend SMS Code</span>
                        </button>
                      )}
                    </span>
                    <span className="text-[11px]">Expires in 5 minutes</span>
                  </div>

                  <button
                    type="submit"
                    disabled={loading || otpCode.length !== 6}
                    className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Verifying &amp; Signing In...</span>
                      </>
                    ) : (
                      <>
                        <span>Verify &amp; Sign In</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          )}

          {/* Sandbox Demo Evaluation */}
          <div className="relative flex items-center justify-center my-1">
            <div className="border-t border-[var(--line)] w-full" />
            <span className="bg-[var(--card)] px-3 text-[10.5px] font-mono uppercase tracking-wider text-[var(--dim)] absolute">
              or sandbox evaluation
            </span>
          </div>

          <div className="space-y-2">
            <button
              type="button"
              onClick={handleDemoSignIn}
              disabled={demoLoading}
              className="ignara-btn-secondary w-full py-2.5 text-xs font-semibold"
            >
              {demoLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--o1)]" />
                  <span>Loading Demo Scenario...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-[var(--o1)] text-[var(--o1)]" />
                  <span>Explore Demo (Alex Morgan Persona)</span>
                </>
              )}
            </button>
            <p className="text-[10.5px] text-center text-[var(--dim)]">
              Pre-seeded with contractor shortfall &amp; PayPal sandbox data
            </p>
          </div>

          <div className="text-center pt-2 text-xs text-[var(--mu)]">
            Don&rsquo;t have an account?{' '}
            <Link to="/register" className="text-[var(--o1)] font-semibold hover:underline">
              Create account free
            </Link>
          </div>
        </div>
      </div>

      {/* Footer info */}
      <div className="py-6 text-center text-xs text-[var(--dim)]">
        PayPal AI Hackathon 2026 &bull; Strict multi-tenant isolation &bull; Encrypted sessions
      </div>
    </div>
  );
};
