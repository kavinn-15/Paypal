import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { ShieldCheck, Mail, ArrowRight, RefreshCw, AlertCircle, CheckCircle2, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const EmailVerificationPage: React.FC = () => {
  const { currentUser, isEmailVerified, verifyEmailOtp, resendVerificationOtp, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Get email from query params, location state, currentUser, or localStorage
  const searchParams = new URLSearchParams(location.search);
  const emailParam = searchParams.get('email') || (location.state as any)?.email;
  const email = emailParam || currentUser?.email || localStorage.getItem('cashflow_user_email') || '';

  const [otpDigits, setOtpDigits] = useState<string[]>(['', '', '', '', '', '']);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [resendCooldown, setResendCooldown] = useState<number>(0);
  const [isResending, setIsResending] = useState<boolean>(false);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // If user is already verified, take them straight to dashboard
  useEffect(() => {
    if (isEmailVerified) {
      navigate('/dashboard', { replace: true });
    }
  }, [isEmailVerified, navigate]);

  // Resend cooldown timer countdown
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const interval = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [resendCooldown]);

  const handleDigitChange = (index: number, value: string) => {
    // If pasted string has length > 1
    if (value.length > 1) {
      const cleaned = value.replace(/\D/g, '').slice(0, 6);
      const newDigits = [...otpDigits];
      for (let i = 0; i < 6; i++) {
        newDigits[i] = cleaned[i] || '';
      }
      setOtpDigits(newDigits);
      const nextFocus = Math.min(cleaned.length, 5);
      inputRefs.current[nextFocus]?.focus();
      return;
    }

    const cleaned = value.replace(/\D/g, '');
    const newDigits = [...otpDigits];
    newDigits[index] = cleaned;
    setOtpDigits(newDigits);

    // Auto-advance
    if (cleaned && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!pasted) return;
    const newDigits = [...otpDigits];
    for (let i = 0; i < 6; i++) {
      newDigits[i] = pasted[i] || '';
    }
    setOtpDigits(newDigits);
    const focusIndex = Math.min(pasted.length, 5);
    inputRefs.current[focusIndex]?.focus();
  };

  const fullOtp = otpDigits.join('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    if (fullOtp.length !== 6) {
      setError('Please enter all 6 digits of your verification code.');
      return;
    }

    if (!email) {
      setError('No target email address identified. Please return to login.');
      return;
    }

    setIsSubmitting(true);
    try {
      await verifyEmailOtp(email, fullOtp);
      setSuccessMsg('Email verified successfully! Redirecting to your financial dashboard...');
      setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 1200);
    } catch (err: any) {
      setError(err.message || 'Invalid or expired verification code.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResend = async () => {
    if (resendCooldown > 0 || isResending) return;
    setError(null);
    setSuccessMsg(null);

    if (!email) {
      setError('No email found to resend verification code to.');
      return;
    }

    setIsResending(true);
    try {
      const res = await resendVerificationOtp(email);
      setSuccessMsg(res.message || 'A new verification code has been dispatched.');
      setResendCooldown(res.cooldown_seconds || 60);
    } catch (err: any) {
      setError(err.message || 'Unable to resend verification code right now.');
    } finally {
      setIsResending(false);
    }
  };

  const maskEmail = (val: string) => {
    if (!val || !val.includes('@')) return val;
    const [name, domain] = val.split('@');
    if (name.length <= 2) return `${name}***@${domain}`;
    return `${name[0]}***${name[name.length - 1]}@${domain}`;
  };

  return (
    <div className="min-h-screen bg-ink-950 flex flex-col justify-center items-center py-8 sm:py-12 px-3 sm:px-6 lg:px-8 selection:bg-electric selection:text-white relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[350px] bg-electric/15 blur-[120px] rounded-full pointer-events-none" />

      <div className="w-full sm:max-w-md relative z-10">
        {/* Brand */}
        <div className="text-center">
          <Link to="/" className="inline-flex items-center space-x-2.5 group">
            <div className="w-10 h-10 rounded-xl bg-ink-900 border border-electric/40 flex items-center justify-center font-mono font-bold text-electric text-base shadow-glow-electric group-hover:border-electric transition-colors">
              CL
            </div>
            <span className="font-extrabold text-xl tracking-tight text-white">
              Cashflow Lifeline
            </span>
          </Link>
          <div className="mt-3 inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-electric/10 border border-electric/30 text-electric-300 text-xs font-semibold">
            <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
            <span>Secure Email Verification</span>
          </div>
          <h2 className="mt-4 text-xl sm:text-2xl font-bold tracking-tight text-white">
            Verify Your Email Address
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-sardine-muted break-words">
            We sent a 6-digit confirmation code to{' '}
            <span className="text-white font-mono font-semibold break-all">
              {email ? maskEmail(email) : 'your inbox'}
            </span>
            . Enter the code below to unlock your financial workspace.
          </p>
        </div>

        {/* Card */}
        <div className="mt-6 sm:mt-8 bg-ink-900/90 border border-ink-800 rounded-2xl p-4 sm:p-8 backdrop-blur-xl shadow-2xl">
          {error && (
            <div className="mb-4 sm:mb-6 p-3 sm:p-3.5 bg-rose-950/60 border border-rose-800/80 rounded-xl flex items-start space-x-2.5 text-xs text-rose-200 animate-fadeIn">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1 break-words">{error}</div>
            </div>
          )}

          {successMsg && (
            <div className="mb-4 sm:mb-6 p-3 sm:p-3.5 bg-emerald-950/60 border border-emerald-800/80 rounded-xl flex items-start space-x-2.5 text-xs text-emerald-200 animate-fadeIn">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div className="flex-1 break-words">{successMsg}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5 sm:space-y-6">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-sardine-muted text-center mb-3">
                6-Digit Security Code
              </label>

              {/* 6 Digit Input Boxes */}
              <div className="flex justify-center gap-1.5 sm:gap-3" onPaste={handlePaste}>
                {otpDigits.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => (inputRefs.current[index] = el)}
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleDigitChange(index, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(index, e)}
                    className="w-9 h-11 sm:w-12 sm:h-14 text-center text-lg sm:text-2xl font-mono font-bold bg-ink-950 border border-ink-700 rounded-lg sm:rounded-xl text-white focus:outline-none focus:border-electric focus:ring-2 focus:ring-electric/30 transition-all"
                  />
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || fullOtp.length !== 6}
              className="w-full py-3 px-4 rounded-xl font-semibold text-xs uppercase tracking-wider bg-electric hover:bg-electric-600 active:bg-electric-700 text-white shadow-glow-electric transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 min-h-[44px]"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin shrink-0" />
                  <span>Verifying Code...</span>
                </>
              ) : (
                <>
                  <span>Verify Email &amp; Continue</span>
                  <ArrowRight className="w-4 h-4 shrink-0" />
                </>
              )}
            </button>
          </form>

          {/* Resend Action with Cooldown */}
          <div className="mt-5 sm:mt-6 pt-4 sm:pt-5 border-t border-ink-800 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-sardine-muted">
            <span className="flex items-center space-x-1.5">
              <Mail className="w-3.5 h-3.5 text-sardine-slate shrink-0" />
              <span>Didn&rsquo;t get the code?</span>
            </span>

            {resendCooldown > 0 ? (
              <span className="font-mono text-sardine-slate bg-ink-950 px-2.5 py-1 rounded-md border border-ink-800">
                Resend in {resendCooldown}s
              </span>
            ) : (
              <button
                type="button"
                onClick={handleResend}
                disabled={isResending}
                className="font-semibold text-electric hover:text-electric-300 transition-colors disabled:opacity-50 flex items-center space-x-1 min-h-[44px] sm:min-h-0 py-1"
              >
                {isResending ? (
                  <>
                    <RefreshCw className="w-3 h-3 animate-spin shrink-0" />
                    <span>Sending...</span>
                  </>
                ) : (
                  <span>Resend Verification Code</span>
                )}
              </button>
            )}
          </div>

          {/* Logout / Switch Account */}
          <div className="mt-4 pt-4 border-t border-ink-800/60 flex items-center justify-center">
            <button
              type="button"
              onClick={async () => {
                await logout();
                navigate('/login');
              }}
              className="inline-flex items-center space-x-1.5 text-xs text-sardine-slate hover:text-rose-400 transition-colors py-1.5 min-h-[44px] sm:min-h-0"
            >
              <LogOut className="w-3.5 h-3.5 shrink-0" />
              <span>Sign out or use a different account</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

