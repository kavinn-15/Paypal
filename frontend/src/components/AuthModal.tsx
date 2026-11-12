import React, { useState } from 'react';
import { ShieldCheck, Sparkles, Lock, Mail, User, ArrowRight, AlertCircle, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

interface AuthModalProps {
  isOpen: boolean;
  onClose?: () => void;
  onSuccess: (user: any) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [tab, setTab] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (tab === 'register' && !termsAccepted) {
      setError('You must accept the terms and conditions to register.');
      return;
    }

    setLoading(true);

    try {
      if (tab === 'login') {
        const res = await api.login(email, password);
        onSuccess(res);
      } else {
        const res = await api.register({
          name,
          email,
          password,
          currency,
          terms_accepted: termsAccepted,
        });
        onSuccess(res);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.demoLogin();
      onSuccess(res);
    } catch (err: any) {
      setError(err.message || 'Demo login failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-3 sm:p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-md w-full max-h-[92vh] overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="bg-ink p-4 sm:p-6 text-white relative shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-electric font-bold font-mono shrink-0">
              CL
            </div>
            <div className="min-w-0">
              <h2 className="text-base sm:text-lg font-bold tracking-tight truncate">Cashflow Lifeline</h2>
              <p className="text-xs text-sardine-slate truncate">Fintech Cashflow Intelligence Platform</p>
            </div>
          </div>
          <div className="mt-3 inline-flex items-center space-x-1.5 text-[11px] bg-electric/20 text-electric-300 border border-electric/30 px-2.5 py-0.5 rounded-full font-medium">
            <Sparkles className="w-3 h-3 text-electric shrink-0" />
            <span>PayPal AI Hackathon 2026</span>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-slate-200 bg-slate-50/50 shrink-0">
          <button
            type="button"
            onClick={() => { setTab('login'); setError(null); }}
            className={`flex-1 py-3 text-xs font-bold transition-colors min-h-[44px] ${
              tab === 'login'
                ? 'text-ink border-b-2 border-electric bg-white'
                : 'text-sardine-slate hover:text-ink'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setTab('register'); setError(null); }}
            className={`flex-1 py-3 text-xs font-bold transition-colors min-h-[44px] ${
              tab === 'register'
                ? 'text-ink border-b-2 border-electric bg-white'
                : 'text-sardine-slate hover:text-ink'
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Form Body */}
        <div className="p-4 sm:p-6 space-y-4 overflow-y-auto">
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-2 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="break-words">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5">
            {tab === 'register' && (
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-sardine-slate mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Jane Doe"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:border-electric focus:ring-1 focus:ring-electric"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-sardine-slate mb-1">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="freelancer@example.com"
                  className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:border-electric focus:ring-1 focus:ring-electric"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-sardine-slate mb-1">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"
                  className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-hidden focus:border-electric focus:ring-1 focus:ring-electric"
                />
              </div>
            </div>

            {tab === 'register' && (
              <>
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-sardine-slate mb-1">
                    Base Operating Currency
                  </label>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-[var(--line)] rounded-xl focus:outline-hidden focus:border-[var(--o1)] focus:ring-1 focus:ring-[var(--o1)] bg-[var(--card)] text-[var(--tx)]"
                  >
                    <option value="USD" className="bg-[var(--card)] text-[var(--tx)]">USD ($ - United States Dollar)</option>
                    <option value="EUR" className="bg-[var(--card)] text-[var(--tx)]">EUR (€ - Euro)</option>
                    <option value="GBP" className="bg-[var(--card)] text-[var(--tx)]">GBP (£ - British Pound)</option>
                    <option value="CAD" className="bg-[var(--card)] text-[var(--tx)]">CAD ($ - Canadian Dollar)</option>
                    <option value="AUD" className="bg-[var(--card)] text-[var(--tx)]">AUD ($ - Australian Dollar)</option>
                  </select>
                </div>

                <div className="flex items-start space-x-2 pt-1">
                  <input
                    id="modal-terms-checkbox"
                    type="checkbox"
                    required
                    checked={termsAccepted}
                    onChange={(e) => setTermsAccepted(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 text-electric focus:ring-electric"
                  />
                  <label htmlFor="modal-terms-checkbox" className="text-xs text-sardine-slate select-none">
                    I agree to the <a href="/terms" target="_blank" rel="noreferrer" className="text-electric underline hover:text-electric/80">Terms of Service</a> and <a href="/privacy" target="_blank" rel="noreferrer" className="text-electric underline hover:text-electric/80">Privacy Policy</a>
                  </label>
                </div>
              </>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 sm:py-3 bg-electric hover:bg-electric/90 text-white font-bold text-xs rounded-xl shadow-xs transition-colors flex items-center justify-center space-x-1.5 disabled:opacity-50 min-h-[44px]"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin shrink-0" />
              ) : (
                <>
                  <span>{tab === 'login' ? 'Sign In to Dashboard' : 'Create Free Account'}</span>
                  <ArrowRight className="w-3.5 h-3.5 shrink-0" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Access Divider */}
          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200"></div>
            </div>
            <div className="relative flex justify-center text-[10px] uppercase tracking-wider text-sardine-slate font-bold">
              <span className="bg-white px-2">Or for Hackathon Review</span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleDemoLogin}
            disabled={loading}
            className="w-full py-2.5 sm:py-3 bg-slate-100 hover:bg-slate-200 text-ink font-bold text-xs rounded-xl border border-slate-300 transition-colors flex items-center justify-center space-x-2 min-h-[44px]"
          >
            <ShieldCheck className="w-4 h-4 text-electric shrink-0" />
            <span>Explore Demo as Alex Morgan</span>
          </button>
        </div>
      </div>
    </div>
  );
};

