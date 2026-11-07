import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { ShieldCheck, ArrowRight, RefreshCw, AlertCircle, CheckCircle2, KeyRound, Phone, Mail } from 'lucide-react';
import { api } from '../api/client';

export const VerifyOtpPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const searchParams = new URLSearchParams(location.search);
  const emailParam = searchParams.get('email') || (location.state as any)?.email || '';
  const phoneParam = searchParams.get('phone') || (location.state as any)?.phone || '';
  const typeParam = searchParams.get('type') || (location.state as any)?.type || (phoneParam ? 'phone' : 'email');

  const [type] = useState<'email' | 'phone'>(typeParam === 'phone' ? 'phone' : 'email');
  const [email, setEmail] = useState<string>(emailParam);
  const [phoneNumber, setPhoneNumber] = useState<string>(phoneParam);

  const [otpDigits, setOtpDigits] = useState<string[]>(['', '', '', '', '', '']);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [resendCooldown, setResendCooldown] = useState<number>(0);
  const [isResending, setIsResending] = useState<boolean>(false);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const interval = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [resendCooldown]);

  const handleDigitChange = (index: number, value: string) => {
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

    if (type === 'email') {
      if (!email.trim() || !email.includes('@')) {
        setError('Please provide a valid account email.');
        return;
      }
    } else {
      if (!phoneNumber.trim()) {
        setError('Please provide your registered mobile phone number.');
        return;
      }
    }

    if (fullOtp.length !== 6) {
      setError('Please enter all 6 digits of your reset code.');
      return;
    }

    setIsSubmitting(true);
    try {
      let resetToken = '';
      if (type === 'email') {
        const res = await api.verifyPasswordResetOtp(email.trim().toLowerCase(), fullOtp);
        resetToken = res.reset_token;
      } else {
        const res = await api.verifyPhonePasswordResetOtp(phoneNumber.trim(), fullOtp);
        resetToken = res.reset_token;
      }

      setSuccessMsg('Reset code verified! Proceeding to set a new password...');
      setTimeout(() => {
        navigate(`/reset-password?token=${encodeURIComponent(resetToken)}`, {
          replace: true,
          state: { email, phone: phoneNumber },
        });
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Invalid or expired password reset code.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResend = async () => {
    if (resendCooldown > 0 || isResending) return;
    setError(null);
    setSuccessMsg(null);

    setIsResending(true);
    try {
      if (type === 'email') {
        if (!email) {
          setError('Please enter your email address to request a new code.');
          return;
        }
        const res = await api.forgotPassword(email.trim().toLowerCase());
        setSuccessMsg(res.message || 'A new reset code has been sent to your email.');
      } else {
        if (!phoneNumber) {
          setError('Please enter your phone number to request a new SMS code.');
          return;
        }
        const res = await api.requestPhonePasswordReset(phoneNumber.trim());
        setSuccessMsg(res.message || 'A fresh SMS reset code has been sent.');
      }
      setResendCooldown(60);
    } catch (err: any) {
      setError(err.message || 'Unable to resend reset code.');
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink-950 flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8 selection:bg-electric selection:text-white relative overflow-hidden">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[350px] bg-electric/15 blur-[120px] rounded-full pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
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
            <KeyRound className="w-3.5 h-3.5" />
            <span>Step 2: Verify Recovery Code</span>
          </div>
          <h2 className="mt-4 text-2xl font-bold tracking-tight text-white">
            Enter 6-Digit Reset Code
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-sardine-muted">
            Enter the 6-digit recovery code delivered to{' '}
            <span className="text-white font-mono font-semibold">
              {type === 'phone' ? phoneNumber || 'your mobile phone' : email || 'your email'}
            </span>
            .
          </p>
        </div>

        <div className="mt-8 bg-ink-900/90 border border-ink-800 rounded-2xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl">
          {error && (
            <div className="mb-6 p-3.5 bg-rose-950/60 border border-rose-800/80 rounded-xl flex items-start space-x-2.5 text-xs text-rose-200 animate-fadeIn">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1">{error}</div>
            </div>
          )}

          {successMsg && (
            <div className="mb-6 p-3.5 bg-emerald-950/60 border border-emerald-800/80 rounded-xl flex items-start space-x-2.5 text-xs text-emerald-200 animate-fadeIn">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div className="flex-1">{successMsg}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {type === 'email' && !emailParam && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-sardine-muted mb-2">
                  Account Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  className="w-full px-4 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-white text-sm focus:outline-none focus:border-electric transition-colors"
                />
              </div>
            )}

            {type === 'phone' && !phoneParam && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-sardine-muted mb-2">
                  Registered Mobile Phone
                </label>
                <input
                  type="tel"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+919876543210"
                  required
                  className="w-full px-4 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-white text-sm font-mono focus:outline-none focus:border-electric transition-colors"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-sardine-muted text-center mb-3">
                6-Digit Reset Code
              </label>

              <div className="flex justify-center gap-2 sm:gap-3" onPaste={handlePaste}>
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
                    className="w-11 h-13 sm:w-12 sm:h-14 text-center text-xl sm:text-2xl font-mono font-bold bg-ink-950 border border-ink-700 rounded-xl text-white focus:outline-none focus:border-electric focus:ring-2 focus:ring-electric/30 transition-all"
                  />
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || fullOtp.length !== 6}
              className="w-full py-3 px-4 rounded-xl font-semibold text-xs uppercase tracking-wider bg-electric hover:bg-electric-600 active:bg-electric-700 text-white shadow-glow-electric transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Verifying Code...</span>
                </>
              ) : (
                <>
                  <span>Verify Code &amp; Continue</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-ink-800 flex items-center justify-between text-xs text-sardine-muted">
            <span>Didn&rsquo;t receive code?</span>
            {resendCooldown > 0 ? (
              <span className="font-mono text-sardine-slate bg-ink-950 px-2 py-0.5 rounded">
                Resend in {resendCooldown}s
              </span>
            ) : (
              <button
                type="button"
                onClick={handleResend}
                disabled={isResending}
                className="font-semibold text-electric hover:text-electric-300 transition-colors disabled:opacity-50"
              >
                {isResending ? 'Sending...' : 'Resend Code'}
              </button>
            )}
          </div>

          <div className="mt-4 pt-4 border-t border-ink-800/60 text-center">
            <Link
              to="/forgot-password"
              className="text-xs text-sardine-slate hover:text-white transition-colors"
            >
              &larr; Choose a different recovery method
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
