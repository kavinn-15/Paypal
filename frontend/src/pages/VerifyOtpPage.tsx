import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { ShieldCheck, ArrowRight, RefreshCw, AlertCircle, CheckCircle2, KeyRound, Phone, Mail, Flame } from 'lucide-react';
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
    <div className="min-h-screen bg-[var(--bg)] text-[var(--tx)] flex flex-col justify-center items-center py-8 sm:py-12 px-4 selection:bg-[var(--o1)]/30 ignara-page-enter">
      <div className="w-full sm:max-w-md relative z-10">
        <div className="text-center">
          <Link to="/" className="inline-flex items-center gap-3 group">
            <div
              className="w-10 h-10 rounded-[12px] flex items-center justify-center text-white shrink-0 shadow-md"
              style={{ background: 'var(--grad-ember)' }}
            >
              <Flame className="w-5 h-5 text-white fill-white/20" strokeWidth={2.2} />
            </div>
            <span className="font-semibold text-xl tracking-tight text-[var(--tx)]">
              Cashflow Lifeline
            </span>
          </Link>
          <div className="mt-3 inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-[var(--card2)] border border-[var(--line)] text-[var(--o1)] text-xs font-semibold">
            <KeyRound className="w-3.5 h-3.5 shrink-0" />
            <span>Step 2: Verify Recovery Code</span>
          </div>
          <h2 className="mt-4 text-xl sm:text-2xl font-semibold tracking-tight text-[var(--tx)]">
            Enter 6-Digit Reset Code
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-[var(--mu)] break-words">
            Enter the 6-digit recovery code delivered to{' '}
            <span className="text-[var(--tx)] font-mono font-semibold break-all">
              {type === 'phone' ? phoneNumber || 'your mobile phone' : email || 'your email'}
            </span>
            .
          </p>
        </div>

        <div className="mt-6 sm:mt-8 ignara-card p-6 sm:p-8 space-y-5">
          {error && (
            <div className="p-3.5 bg-[var(--r)]/15 border border-[var(--r)]/30 rounded-[14px] flex items-start space-x-2.5 text-xs text-[var(--r)]">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 break-words">{error}</div>
            </div>
          )}

          {successMsg && (
            <div className="p-3.5 bg-[var(--g)]/15 border border-[var(--g)]/30 rounded-[14px] flex items-start space-x-2.5 text-xs text-[var(--g)]">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 break-words">{successMsg}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            {type === 'email' && !emailParam && (
              <div className="space-y-1">
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--dim)]">
                  Account Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  className="ignara-input w-full"
                />
              </div>
            )}

            {type === 'phone' && !phoneParam && (
              <div className="space-y-1">
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--dim)]">
                  Registered Mobile Phone
                </label>
                <input
                  type="tel"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+919876543210"
                  required
                  className="ignara-input w-full font-mono"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--dim)] text-center mb-3">
                6-Digit Reset Code
              </label>

              <div className="flex justify-center gap-1.5 sm:gap-2.5" onPaste={handlePaste}>
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
                    className="w-9 h-11 sm:w-11 sm:h-14 text-center text-lg sm:text-2xl font-mono font-semibold ignara-input"
                  />
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || fullOtp.length !== 6}
              className="ignara-btn-primary w-full py-2.5 text-xs font-semibold uppercase tracking-wider min-h-[44px]"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin shrink-0" />
                  <span>Verifying Code...</span>
                </>
              ) : (
                <>
                  <span>Verify Code &amp; Continue</span>
                  <ArrowRight className="w-4 h-4 shrink-0" />
                </>
              )}
            </button>
          </form>

          <div className="pt-4 border-t border-[var(--line)] flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[var(--mu)]">
            <span>Didn&rsquo;t receive code?</span>
            {resendCooldown > 0 ? (
              <span className="font-mono text-[var(--dim)] bg-[var(--side)] px-2.5 py-1 rounded-[8px] border border-[var(--line)]">
                Resend in {resendCooldown}s
              </span>
            ) : (
              <button
                type="button"
                onClick={handleResend}
                disabled={isResending}
                className="font-semibold text-[var(--o1)] hover:underline transition-colors disabled:opacity-50 min-h-[44px] sm:min-h-0 flex items-center cursor-pointer"
              >
                {isResending ? 'Sending...' : 'Resend Code'}
              </button>
            )}
          </div>

          <div className="pt-3 border-t border-[var(--line)] text-center">
            <Link
              to="/forgot-password"
              className="text-xs text-[var(--mu)] hover:text-[var(--tx)] transition-colors inline-block py-1"
            >
              &larr; Choose a different recovery method
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
