import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, Lock, Mail, AlertCircle, ArrowRight, Play, Loader2, Sparkles } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  const { login, demoLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Please provide both your business email and password.');
      return;
    }

    setLoading(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify your email and password.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoSignIn = async () => {
    setError(null);
    setDemoLoading(true);
    try {
      await demoLogin();
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      setError(err.message || 'Demo initialization failed. Please try again.');
    } finally {
      setDemoLoading(false);
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
        <Link to="/" className="text-xs text-sardine-muted hover:text-white transition-colors">
          &larr; Back to Home
        </Link>
      </div>

      {/* Main Login Card */}
      <div className="max-w-md w-full mx-auto px-4 py-8">
        <div className="rounded-2xl border border-ink-800 bg-ink-900/90 backdrop-blur-xl p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="space-y-1.5 text-center">
            <h1 className="text-2xl font-black text-white tracking-tight">Sign In</h1>
            <p className="text-xs text-sardine-muted">
              Access your real-time cashflow predictions and rescue inbox
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
              <div className="leading-relaxed">{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-slate-300">
                Work / Business Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@freelance.org"
                  required
                  autoFocus
                  className="w-full pl-9 pr-3 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-electric transition-colors"
                />
              </div>
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-semibold text-slate-300">
                  Password
                </label>
                <Link
                  to="/forgot-password"
                  className="text-xs text-electric-300 hover:text-electric transition-colors font-medium"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-sardine-muted absolute left-3 top-3.5 pointer-events-none" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"
                  required
                  className="w-full pl-9 pr-10 py-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-electric transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-3 text-sardine-muted hover:text-white"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs pt-1">
              <label className="flex items-center space-x-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-3.5 h-3.5 rounded border-ink-700 bg-ink-950 text-electric focus:ring-0"
                />
                <span>Remember me on this browser</span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-electric hover:bg-electric-600 text-white font-bold text-xs sm:text-sm shadow-glow-electric transition-all flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Separation Divider */}
          <div className="relative flex items-center justify-center">
            <div className="border-t border-ink-800 w-full" />
            <span className="bg-ink-900 px-3 text-[10px] font-mono uppercase tracking-wider text-sardine-muted absolute">
              or sandbox evaluation
            </span>
          </div>

          {/* Dedicated Demo Button */}
          <div className="space-y-2">
            <button
              type="button"
              onClick={handleDemoSignIn}
              disabled={demoLoading}
              className="w-full py-2.5 rounded-xl bg-ink-950 border border-electric/30 hover:border-electric text-electric-300 font-semibold text-xs transition-all flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-50"
            >
              {demoLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-electric" />
                  <span>Loading Demo Scenario...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-electric-300" />
                  <span>Explore Demo (Alex Morgan Persona)</span>
                </>
              )}
            </button>
            <p className="text-[10px] text-center text-sardine-muted">
              Pre-seeded with contractor shortfall &amp; PayPal sandbox data
            </p>
          </div>

          <div className="text-center pt-2 text-xs text-sardine-muted">
            Don&rsquo;t have an account?{' '}
            <Link to="/register" className="text-electric-300 font-bold hover:underline">
              Create account free
            </Link>
          </div>
        </div>
      </div>

      {/* Footer info */}
      <div className="py-6 text-center text-[11px] text-sardine-muted">
        PayPal AI Hackathon 2026 &bull; Strict multi-tenant isolation &bull; Encrypted sessions
      </div>
    </div>
  );
};

