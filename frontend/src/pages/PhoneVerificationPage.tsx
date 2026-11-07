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
  Mail
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

  // If user is already loaded, fallback to their profile phone
  useEffect(() => {
    if (!phoneNumber && currentUser?.phone_number) {
      setPhoneNumber(currentUser.phone_number);
    }
  }, [currentUser, phoneNumber]);

  // Resend cooldown timer
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

      // Proceed to email verification or dashboard
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
          &larr; Back to Sign In
        </Link>
      </div>

      {/* Main Verification Card */}
      <div className="max-w-md w-full mx-auto px-4 py-8">
        <div className="rounded-2xl border border-ink-800 bg-ink-900/90 backdrop-blur-xl p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="w-12 h-12 rounded-2xl bg-electric/10 border border-electric/30 text-electric flex items-center justify-center mx-auto shadow-glow-electric">
            <Phone className="w-6 h-6" />
          </div>

          <div className="space-y-1.5 text-center">
            <h1 className="text-2xl font-black text-white tracking-tight">Verify Your Mobile Number</h1>
            <p className="text-xs text-sardine-muted leading-relaxed">
              We sent a 6-digit SMS verification code to
            </p>
            <div className="inline-block px-3 py-1 bg-ink-950 border border-ink-800 rounded-lg font-mono text-xs font-bold text-electric-300">
              {phoneNumber || 'your registered number'}
            </div>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
              <div className="leading-relaxed">{error}</div>
            </div>
          )}

          {successMessage && (
            <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-start space-x-2.5">
              <CheckCircle className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
              <div className="leading-relaxed">{successMessage}</div>
            </div>
          )}

          <form onSubmit={handleVerify} className="space-y-4">
            <div className="space-y-2">
              <label className="block text-center text-xs font-semibold text-slate-300">
                Enter 6-Digit SMS OTP
              </label>

              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                required
                autoFocus
                className="w-full text-center tracking-[0.4em] font-mono text-2xl py-3.5 bg-ink-950 border border-ink-700 rounded-xl text-white placeholder-slate-600 focus:outline-none focus:border-electric transition-colors"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-sardine-muted">
              <span>
                {cooldown > 0 ? (
                  <span>Resend in <strong className="text-white font-mono">{cooldown}s</strong></span>
                ) : (
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={resending}
                    className="text-electric-300 hover:text-white font-semibold flex items-center space-x-1"
                  >
                    <RotateCcw className={`w-3 h-3 ${resending ? 'animate-spin' : ''}`} />
                    <span>Resend SMS Code</span>
                  </button>
                )}
              </span>
              <span className="text-[11px]">Valid for 5 minutes</span>
            </div>

            <button
              type="submit"
              disabled={loading || otpCode.length !== 6}
              className="w-full py-3.5 rounded-xl bg-electric hover:bg-electric-600 text-white font-bold text-xs sm:text-sm shadow-glow-electric transition-all flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Verifying SMS Code...</span>
                </>
              ) : (
                <>
                  <span>Verify Phone Number</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Additional Links */}
          <div className="border-t border-ink-800 pt-4 flex flex-col space-y-2 text-center text-xs text-sardine-muted">
            {emailParam && (
              <Link
                to={`/verify-email?email=${encodeURIComponent(emailParam)}`}
                className="text-electric-300 hover:underline flex items-center justify-center space-x-1"
              >
                <Mail className="w-3.5 h-3.5" />
                <span>Verify Email Address instead</span>
              </Link>
            )}

            <Link to="/dashboard" className="text-sardine-muted hover:text-white text-[11px] pt-1">
              Skip for now &amp; proceed to Dashboard &rarr;
            </Link>
          </div>

          <div className="border-t border-ink-800 pt-3 flex items-center justify-center space-x-1.5 text-[11px] text-sardine-muted">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Keyed HMAC-SHA256 OTP Protection &bull; Anti-tamper</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="py-6 text-center text-[11px] text-sardine-muted">
        PayPal AI Hackathon 2026 &bull; Secure Multi-Factor &bull; Multi-Tenant Privacy
      </div>
    </div>
  );
};

