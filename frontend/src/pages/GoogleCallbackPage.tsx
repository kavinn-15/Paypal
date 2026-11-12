import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Loader2, AlertCircle, ShieldCheck, Flame } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const GoogleCallbackPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { loginWithGoogleCode } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const searchParams = new URLSearchParams(location.search);
      const code = searchParams.get('code');
      const state = searchParams.get('state') || undefined;
      const errorParam = searchParams.get('error');

      if (errorParam) {
        setError(`Google authentication failed: ${errorParam}`);
        return;
      }

      if (!code) {
        setError('Missing Google authorization code in callback URL.');
        return;
      }

      try {
        const redirectUri = `${window.location.origin}/auth/callback/google`;
        await loginWithGoogleCode(code, state, redirectUri);
        navigate('/dashboard', { replace: true });
      } catch (err: any) {
        setError(err.message || 'Failed to complete Google authentication.');
      }
    };

    handleCallback();
  }, [location.search, loginWithGoogleCode, navigate]);

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--tx)] flex flex-col justify-center items-center py-12 px-4 selection:bg-[var(--o1)]/30 ignara-page-enter">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-6">
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

        <div className="ignara-card p-8">
          {error ? (
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] flex items-center justify-center mx-auto">
                <AlertCircle className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-semibold text-[var(--tx)]">Authentication Failed</h2>
              <p className="text-xs text-[var(--r)]">{error}</p>
              <div className="pt-4">
                <Link
                  to="/login"
                  className="ignara-btn-primary w-full py-2.5 text-xs font-semibold uppercase tracking-wider block"
                >
                  Return to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <Loader2 className="w-10 h-10 text-[var(--o1)] animate-spin mx-auto" />
              <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-[var(--card2)] border border-[var(--line)] text-[var(--o1)] text-xs font-semibold">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Google OAuth 2.0</span>
              </div>
              <h2 className="text-base font-semibold text-[var(--tx)]">Completing Secure Sign-In</h2>
              <p className="text-xs text-[var(--mu)]">
                Verifying your Google identity and establishing encrypted session...
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
