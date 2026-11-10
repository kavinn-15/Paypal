import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import {
  Phone,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  RotateCcw,
  Loader2,
  ShieldCheck,
  Mail,
  Flame
} from 'lucide-react';

export const PhoneVerificationPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const phoneParam = searchParams.get('phone') || '';
  const emailParam = searchParams.get('email') || '';

  const [phoneNumber, setPhoneNumber] = useState(phoneParam);
  const [otpCode, setOtpCode] = useState('');
  const [cooldown, setCooldown] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  const { verifyPhoneOtp, refreshUser, currentUser } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!phoneNumber && currentUser?.phone_number) {
      setPhoneNumber(currentUser.phone_number);
    }
  }, [currentUser, phoneNumber]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((c) => (c > 0 ? c - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    const cleanOtp = otpCode.replace(/\D/g, '');
    if (cleanOtp.length !== 6) {
      setError('Please enter the full 6-digit SMS verification code.');
      return;
    }

    if (!phoneNumber) {
      setError('Mobile phone number is missing.');
      return;
    }

    setLoading(true);
    try {
      await verifyPhoneOtp(phoneNumber, cleanOtp);
      setSuccessMessage('Mobile phone verified successfully!');
      await refreshUser();

      setTimeout(() => {
        if (emailParam) {
          navigate(`/verify-email?email=${encodeURIComponent(emailParam)}`, { replace: true });
        } else {
          navigate('/dashboard', { replace: true });
        }
      }, 1200);
    } catch (err: any) {
      setError(err.message || 'Invalid or expired SMS OTP code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (cooldown > 0 || !phoneNumber) return;
    setError(null);
    setResending(true);
    try {
      const res = await api.resendPhoneOtp(phoneNumber);
      setCooldown(res.cooldown_seconds || 60);
      setSuccessMessage('A fresh 6-digit SMS verification code has been dispatched.');
    } catch (err: any) {
      setError(err.message || 'Failed to resend SMS code. Please wait before retrying.');
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--tx)] flex flex-col justify-between selection:bg-[var(--o1)]/30 ignara-page-enter">
      {/* Top Simple Header */}
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

      {/* Main Verification Card */}
      <div className="max-w-md w-full mx-auto px-4 py-4 sm:py-8">
        <div className="ignara-card p-6 sm:p-8 space-y-5">
          <div className="w-12 h-12 rounded-[14px] bg-[var(--o1)]/15 border border-[var(--o1)]/30 text-[var(--o1)] flex items-center justify-center mx-auto">
            <Phone className="w-6 h-6" />
          </div>

          <div className="space-y-1.5 text-center">
            <h1 className="ignara-h1 text-2xl font-semibold">Verify Your Mobile Number</h1>
            <p className="text-xs text-[var(--mu)] leading-relaxed">
              We sent a 6-digit SMS verification code to
            </p>
            <div className="inline-block px-3 py-1 bg-[var(--side)] border border-[var(--line)] rounded-[8px] font-mono text-xs font-semibold text-[var(--o1)] break-all max-w-full">
              {phoneNumber || 'your registered number'}
            </div>
          </div>

          {error && (
            <div className="p-3.5 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="leading-relaxed break-words flex-1">{error}</div>
            </div>
          )}

          {successMessage && (
            <div className="p-3.5 rounded-[14px] bg-[var(--g)]/15 border border-[var(--g)]/30 text-[var(--g)] text-xs flex items-start space-x-2.5">
              <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="leading-relaxed break-words flex-1">{successMessage}</div>
            </div>
          )}

          <form onSubmit={handleVerify} className="space-y-4">
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--dim)] text-center">
                Enter 6-Digit SMS Code
              </label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                placeholder="123456"
                required
                autoFocus
                className="ignara-input w-full text-center tracking-[0.4em] font-mono text-2xl py-3"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-[var(--mu)]">
              <span>
                {cooldown > 0 ? (
                  <span>Resend SMS in <strong className="font-mono text-[var(--tx)]">{cooldown}s</strong></span>
                ) : (
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={resending}
                    className="text-[var(--o1)] hover:underline font-semibold flex items-center space-x-1 cursor-pointer"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Resend SMS code</span>
                  </button>
                )}
              </span>
              <span className="text-[11px]">Valid for 10 minutes</span>
            </div>

            <button
              type="submit"
              disabled={loading || otpCode.replace(/\D/g, '').length !== 6}
              className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                  <span>Verifying SMS Code...</span>
                </>
              ) : (
                <>
                  <span>Verify Mobile Number</span>
                  <ArrowRight className="w-4 h-4 shrink-0" />
                </>
              )}
            </button>
          </form>

          <div className="border-t border-[var(--line)] pt-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[var(--mu)]">
            <div className="flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-[var(--g)] shrink-0" />
              <span>Carrier SMS delivered</span>
            </div>
            {emailParam && (
              <Link
                to={`/verify-email?email=${encodeURIComponent(emailParam)}`}
                className="text-[var(--o1)] font-semibold hover:underline flex items-center space-x-1 py-1"
              >
                <span>Verify email instead</span>
                <Mail className="w-3.5 h-3.5" />
              </Link>
            )}
          </div>

          <div className="pt-2 text-center">
            <Link
              to="/dashboard"
              className="text-xs text-[var(--dim)] hover:text-[var(--tx)] transition-colors py-1 inline-block"
            >
              Skip for now &amp; proceed to Dashboard &rarr;
            </Link>
          </div>
        </div>
      </div>

      <div className="py-6 text-center text-xs text-[var(--dim)]">
        PayPal AI Hackathon 2026 &bull; SMS one-time passcode verification
      </div>
    </div>
  );
};
