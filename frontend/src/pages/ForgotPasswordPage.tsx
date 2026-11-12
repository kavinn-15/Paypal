import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { PhoneInput } from '../components/PhoneInput';
import {
  Mail,
  Phone,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  Loader2,
  KeyRound,
  ShieldCheck,
  Flame
} from 'lucide-react';

type RecoveryMethod = 'email' | 'phone';

export const ForgotPasswordPage: React.FC = () => {
  const [method, setMethod] = useState<RecoveryMethod>('email');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [phoneCountryCode, setPhoneCountryCode] = useState('+91');

  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devResetLink, setDevResetLink] = useState<string | null>(null);

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setDevResetLink(null);

    if (method === 'email') {
      if (!email.trim() || !email.includes('@')) {
        setError('Please provide a valid business email address.');
        return;
      }

      setLoading(true);
      try {
        const res = await api.forgotPassword(email.trim().toLowerCase());
        setSubmitted(true);
        if (res.dev_reset_link) {
          setDevResetLink(res.dev_reset_link);
        }
      } catch (err: any) {
        setError(err.message || 'Unable to process recovery request. Please try again.');
      } finally {
        setLoading(false);
      }
    } else {
      if (!phoneNumber.trim()) {
        setError('Please provide your registered mobile phone number.');
        return;
      }

      setLoading(true);
      try {
        await api.requestPhonePasswordReset(phoneNumber.trim());
        setSubmitted(true);
      } catch (err: any) {
        setError(err.message || 'Unable to send SMS reset code. Please verify the number.');
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--tx)] flex flex-col justify-between ignara-page-enter">
      {/* Header */}
      <div className="max-w-[1080px] mx-auto w-full px-4 sm:px-6 py-4 sm:py-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div
            className="w-10 h-10 rounded-[12px] flex items-center justify-center text-white shrink-0 shadow-md"
            style={{ background: 'var(--grad-ember)' }}
          >
            <Flame className="w-5 h-5 text-white fill-white/20" strokeWidth={2.2} />
          </div>
          <span className="font-semibold text-base sm:text-lg tracking-tight text-[var(--tx)]">
            Cashflow Lifeline
          </span>
        </Link>
        <Link to="/login" className="text-xs text-[var(--mu)] hover:text-[var(--tx)] transition-colors py-1.5">
          &larr; Back to Sign In
        </Link>
      </div>

      {/* Main Card */}
      <div className="max-w-md w-full mx-auto px-4 py-4 sm:py-8">
        <div className="ignara-card p-6 sm:p-8 space-y-5">
          <div className="w-12 h-12 rounded-[14px] bg-[var(--o1)]/15 border border-[var(--o1)]/30 text-[var(--o1)] flex items-center justify-center mx-auto">
            <KeyRound className="w-6 h-6" />
          </div>

          <div className="space-y-1 text-center">
            <h1 className="ignara-h1 text-2xl font-semibold">Account Recovery</h1>
            <p className="text-xs text-[var(--mu)]">
              Choose your recovery channel to receive single-use password reset instructions
            </p>
          </div>

          {/* Recovery Channel Selector */}
          <div className="grid grid-cols-2 gap-1 p-1 bg-[var(--side)] rounded-[999px] border border-[var(--line)]">
            <button
              type="button"
              onClick={() => {
                setMethod('email');
                setError(null);
                setSubmitted(false);
              }}
              className={`py-1.5 px-2 text-center rounded-[999px] text-xs font-medium transition-all flex items-center justify-center space-x-1.5 min-h-[36px] ${
                method === 'email'
                  ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                  : 'text-[var(--mu)] hover:text-[var(--tx)]'
              }`}
            >
              <Mail className="w-3.5 h-3.5 shrink-0" />
              <span>Email Reset</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setMethod('phone');
                setError(null);
                setSubmitted(false);
              }}
              className={`py-1.5 px-2 text-center rounded-[999px] text-xs font-medium transition-all flex items-center justify-center space-x-1.5 min-h-[36px] ${
                method === 'phone'
                  ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                  : 'text-[var(--mu)] hover:text-[var(--tx)]'
              }`}
            >
              <Phone className="w-3.5 h-3.5 shrink-0" />
              <span>SMS Phone Code</span>
            </button>
          </div>

          {error && (
            <div className="p-3.5 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="leading-relaxed flex-1">{error}</div>
            </div>
          )}

          {submitted ? (
            <div className="space-y-4 text-center">
              <div className="w-12 h-12 rounded-[14px] bg-[var(--g)]/15 border border-[var(--g)]/30 text-[var(--g)] flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>

              <div className="space-y-1">
                <h3 className="ignara-h3 text-base">Check Your {method === 'email' ? 'Inbox' : 'Mobile Messages'}</h3>
                <p className="text-xs text-[var(--mu)] leading-relaxed">
                  {method === 'email' ? (
                    <>
                      We sent password reset instructions to <strong className="text-[var(--tx)]">{email}</strong>.
                    </>
                  ) : (
                    <>
                      We sent a 6-digit recovery code via SMS to <strong className="text-[var(--tx)]">{phoneNumber}</strong>.
                    </>
                  )}
                </p>
              </div>

              {devResetLink && (
                <div className="p-3 rounded-[12px] bg-[var(--side)] border border-[var(--line)] text-left text-xs space-y-1">
                  <span className="text-[10px] uppercase font-semibold text-[var(--o1)] block">Development Helper</span>
                  <a
                    href={devResetLink}
                    className="text-[var(--o1)] font-mono text-[11px] hover:underline break-all block"
                  >
                    Click to open reset link
                  </a>
                </div>
              )}

              {method === 'phone' && (
                <button
                  type="button"
                  onClick={() =>
                    navigate(
                      `/verify-otp?type=phone&phone=${encodeURIComponent(phoneNumber.trim())}&next=reset-password`,
                      { state: { phone: phoneNumber.trim(), type: 'phone', next: 'reset-password' } }
                    )
                  }
                  className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
                >
                  <span>Enter 6-Digit SMS Code</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              )}

              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setSubmitted(false)}
                  className="text-xs text-[var(--mu)] hover:text-[var(--tx)] hover:underline"
                >
                  Try another address or number
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {method === 'email' ? (
                <div className="space-y-1">
                  <label className="block text-xs font-semibold text-[var(--tx)]">
                    Registered Business Email
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="name@company.com"
                      required
                      autoFocus
                      className="ignara-input w-full pl-9"
                    />
                  </div>
                </div>
              ) : (
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
              )}

              <button
                type="submit"
                disabled={loading}
                className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                    <span>Transmitting Recovery Instructions...</span>
                  </>
                ) : (
                  <>
                    <span>Send {method === 'email' ? 'Reset Email' : 'SMS Code'}</span>
                    <ArrowRight className="w-4 h-4 shrink-0" />
                  </>
                )}
              </button>
            </form>
          )}

          <div className="border-t border-[var(--line)] pt-4 text-center text-xs text-[var(--mu)]">
            Remembered your credentials?{' '}
            <Link to="/login" className="text-[var(--o1)] font-semibold hover:underline">
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>

      <div className="py-6 text-center text-xs text-[var(--dim)]">
        PayPal AI Hackathon 2026 &bull; Cryptographic single-use token invalidation
      </div>
    </div>
  );
};
