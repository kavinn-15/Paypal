import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Loader2, AlertCircle, ShieldCheck } from 'lucide-react';
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
        await loginWithGoogleCode(code, state);
        navigate('/dashboard', { replace: true });
      } catch (err: any) {
        setError(err.message || 'Failed to complete Google authentication.');
      }
    };

    handleCallback();
  }, [location.search, loginWithGoogleCode, navigate]);

  return (
    <div className="min-h-screen bg-ink-950 flex flex-col justify-center items-center py-12 px-4 selection:bg-electric selection:text-white">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-6">
        <Link to="/" className="inline-flex items-center space-x-2.5">
          <div className="w-10 h-10 rounded-xl bg-ink-900 border border-electric/40 flex items-center justify-center font-mono font-bold text-electric text-base shadow-glow-electric">
            CL
          </div>
          <span className="font-extrabold text-xl tracking-tight text-white">
            Cashflow Lifeline
          </span>
        </Link>

        <div className="bg-ink-900/90 border border-ink-800 rounded-2xl p-8 backdrop-blur-xl shadow-2xl">
          {error ? (
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-full bg-rose-950/80 border border-rose-800 text-rose-400 flex items-center justify-center mx-auto">
                <AlertCircle className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-bold text-white">Authentication Failed</h2>
              <p className="text-xs text-rose-300">{error}</p>
              <div className="pt-4">
                <Link
                  to="/login"
                  className="inline-block w-full py-2.5 px-4 rounded-xl bg-electric hover:bg-electric-600 text-white font-semibold text-xs tracking-wider uppercase transition-colors"
                >
                  Return to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <Loader2 className="w-10 h-10 text-electric animate-spin mx-auto" />
              <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-electric/10 border border-electric/30 text-electric-300 text-xs font-semibold">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Google OAuth 2.0</span>
              </div>
              <h2 className="text-base font-bold text-white">Completing Secure Sign-In</h2>
              <p className="text-xs text-sardine-muted">
                Verifying your Google identity and establishing encrypted session...
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

