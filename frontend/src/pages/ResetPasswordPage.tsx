import React, { useState, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { Eye, EyeOff, Lock, AlertCircle, CheckCircle2, ArrowRight, Loader2, ShieldCheck, Flame } from 'lucide-react';

export const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const navigate = useNavigate();

  const passwordStrength = useMemo(() => {
    let score = 0;
    if (newPassword.length >= 8) score += 1;
    if (/[A-Z]/.test(newPassword)) score += 1;
    if (/[0-9]/.test(newPassword)) score += 1;
    if (/[^A-Za-z0-9]/.test(newPassword)) score += 1;
    return score;
  }, [newPassword]);

  const strengthColor = useMemo(() => {
    if (passwordStrength <= 1) return 'bg-[var(--r)]';
    if (passwordStrength === 2) return 'bg-[var(--y)]';
    if (passwordStrength === 3) return 'bg-blue-400';
    return 'bg-[var(--g)]';
  }, [passwordStrength]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!token) {
      setError('Password reset token is missing from your link. Please request a new recovery link.');
      return;
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (passwordStrength < 2) {
      setError('Password must contain both letters and at least one number.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match. Please verify.');
      return;
    }

    setLoading(true);
    try {
      try {
        await api.confirmPasswordResetWithOtp(token, newPassword);
      } catch {
        await api.resetPassword(token, newPassword);
      }
      setSuccess(true);
      setTimeout(() => {
        navigate('/login', { replace: true });
      }, 2500);
    } catch (err: any) {
      setError(err.message || 'Invalid or expired password reset token. Please request a new link.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--tx)] flex flex-col justify-between selection:bg-[var(--o1)]/30 ignara-page-enter">
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
          <div className="space-y-1 text-center">
            <h1 className="ignara-h1 text-2xl font-semibold">Set New Password</h1>
            <p className="text-xs text-[var(--mu)]">
              Choose a strong password to protect your financial predictions and authorization credentials
            </p>
          </div>

          {!token && (
            <div className="p-3.5 rounded-[14px] bg-[var(--y)]/15 border border-[var(--y)]/30 text-[var(--y)] text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="leading-relaxed flex-1">
                No reset token was found in the URL. If you received an email, please ensure you clicked the full URL.
              </div>
            </div>
          )}

          {error && (
            <div className="p-3.5 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="leading-relaxed flex-1">{error}</div>
            </div>
          )}

          {success ? (
            <div className="space-y-4">
              <div className="p-4 rounded-[14px] bg-[var(--g)]/15 border border-[var(--g)]/30 text-[var(--g)] text-xs space-y-2">
                <div className="flex items-center space-x-2 font-semibold text-sm">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>Password Successfully Updated</span>
                </div>
                <p className="leading-relaxed text-[var(--mu)]">
                  Your credentials have been securely updated and all previous sessions have been invalidated.
                </p>
              </div>

              <div className="pt-2 text-center">
                <Link
                  to="/login"
                  className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
                >
                  <span>Sign In with New Password</span>
                  <ArrowRight className="w-4 h-4 shrink-0" />
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[var(--tx)]">New Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[var(--dim)] absolute left-3 top-3.5 pointer-events-none" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Min. 8 characters"
                    required
                    autoFocus
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
                <label className="block text-xs font-semibold text-[var(--tx)]">Confirm New Password</label>
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

              {/* Strength meter */}
              {newPassword && (
                <div className="space-y-1.5 pt-0.5">
                  <div className="h-1.5 w-full bg-[var(--side)] rounded-full overflow-hidden flex">
                    <div
                      className={`h-full transition-all duration-300 ${strengthColor}`}
                      style={{ width: `${Math.min(100, Math.max(15, passwordStrength * 25))}%` }}
                    />
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={loading || !token}
                className="ignara-btn-primary w-full py-2.5 text-xs font-semibold"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                    <span>Updating password...</span>
                  </>
                ) : (
                  <>
                    <span>Reset Password &amp; Invalidate Sessions</span>
                    <ArrowRight className="w-4 h-4 shrink-0" />
                  </>
                )}
              </button>
            </form>
          )}

          <div className="border-t border-[var(--line)] pt-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[var(--mu)]">
            <div className="flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-[var(--g)] shrink-0" />
              <span>Token revoked upon use</span>
            </div>
            <Link to="/login" className="text-[var(--o1)] font-semibold hover:underline py-1">
              Return to Sign In &rarr;
            </Link>
          </div>
        </div>
      </div>

      <div className="py-6 text-center text-xs text-[var(--dim)]">
        PayPal AI Hackathon 2026 &bull; Strict token invalidation and session purge
      </div>
    </div>
  );
};
