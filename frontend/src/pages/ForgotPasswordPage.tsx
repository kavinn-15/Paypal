import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Mail, AlertCircle, CheckCircle2, ArrowRight, Loader2, KeyRound } from 'lucide-react';

export const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devResetLink, setDevResetLink] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setDevResetLink(null);

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
  };

  return (
    <div className="min-h-screen bg-ink-950 flex flex-col justify-between text-white selection:bg-electric selection:text-white">
      {/* Header */}
      <div className="max-w-[1440px] mx-auto w-full px-4 sm:px-6 py-6 flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-ink-900 border border-electric/40 flex items-center justify-center font-mono font-bold text-electric text-xs shadow-glow-electric">
            CL
          </div>
          <span className="font-extrabold text-base tracking-tight text-white flex items-center gap-1.5">
            Cashflow Lifeline
          </span>
        </Link>
        <Link to="/login" className="text-xs text-sardine-muted hover:text-white transition-colors">
          &larr; Back to Sign In
        </Link>
      </div>

      {/* Main Card */}
      <div className="max-w-md w-full mx-auto px-4 py-8">
        <div className="rounded-2xl border border-ink-800 bg-ink-900/90 backdrop-blur-xl p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="w-12 h-12 rounded-2xl bg-electric/15 border border-electric/30 text-electric flex items-center justify-center mx-auto">
            <KeyRound className="w-6 h-6" />
          </div>

          <div className="space-y-1.5 text-center">
            <h1 className="text-2xl font-black text-white tracking-tight">Account Recovery</h1>
            <p className="text-xs text-sardine-muted">
              Enter your registered email to receive single-use password reset instructions
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
              <div className="leading-relaxed">{error}</div>
            </div>
          )}

          {submitted ? (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs space-y-2">
                <div className="flex items-center space-x-2 font-bold text-sm text-emerald-200">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Recovery Instructions Generated</span>
                </div>
                <p className="leading-relaxed text-slate-300">
                  If an account exists for <strong className="text-white">{email}</strong>, a cryptographically signed reset token has been issued with a 15-minute expiration period.
                </p>
              </div>

              {devResetLink && (
                <div className="p-4 rounded-xl bg-electric/10 border border-electric/30 space-y-2 text-xs">
                  <div className="font-bold text-electric-300 uppercase tracking-wider text-[10px]">
                    Development Sandbox Mode Preview
                  </div>
                  <p className="text-slate-300 text-[11px]">
                    SMTP email delivery is in sandbox mode. You can test token completion directly:
                  </p>
                  <Link
                    to={devResetLink}
                    className="inline-flex items-center space-x-1.5 font-mono text-xs text-electric-300 hover:text-white underline font-semibold"
                  >
                    <span>Click to open reset token workflow &rarr;</span>
                  </Link>
                </div>
              )}

              <div className="pt-2 text-center">
                <Link
                  to="/login"
                  className="w-full py-2.5 rounded-xl bg-ink-950 border border-slate-700 hover:border-slate-500 text-xs font-semibold text-white inline-block transition-colors"
                >
                  Return to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-300">
                  Registered Work Email
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="sarah@agency.com"
                    required
                    autoFocus
                    className="w-full pl-9 pr-3 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-electric transition-colors"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-xl bg-electric hover:bg-electric-600 text-white font-bold text-xs sm:text-sm shadow-glow-electric transition-all flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Generating token...</span>
                  </>
                ) : (
                  <>
                    <span>Send Password Reset Instructions</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          )}

          <div className="border-t border-ink-800 pt-4 text-center text-xs text-sardine-muted">
            Remembered your credentials?{' '}
            <Link to="/login" className="text-electric-300 font-bold hover:underline">
              Sign In
            </Link>
          </div>
        </div>
      </div>

      <div className="py-6 text-center text-[11px] text-sardine-muted">
        PayPal AI Hackathon 2026 &bull; Cryptographic single-use token invalidation
      </div>
    </div>
  );
};

