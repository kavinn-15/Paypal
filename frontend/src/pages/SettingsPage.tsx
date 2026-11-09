import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { PayPalConnectionStatus } from '../types';
import { Settings, ShieldCheck, CheckCircle2, AlertTriangle, RefreshCw, Key, Globe, Shield, Lock, Bot, Radio } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [status, setStatus] = useState<PayPalConnectionStatus | null>(null);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; token_preview?: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    api.getPayPalConnection().then(setStatus).catch(() => {});
  }, []);

  const handleTestConnection = async () => {
    try {
      setIsTesting(true);
      const res = await api.testPayPalConnection();
      setTestResult(res);
      const updated = await api.getPayPalConnection();
      setStatus(updated);
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || 'Connection test failed' });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Bento Header */}
      <div className="border-b border-slate-200 pb-5">
        <div className="flex items-center space-x-2">
          <h1 className="text-2xl font-black text-ink tracking-tight font-display">
            System Settings & Security Controls
          </h1>
          <span className="text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-0.5 rounded-full font-bold">
            Sandbox Guard Active
          </span>
        </div>
        <p className="text-xs text-sardine-slate mt-1">
          Verify PayPal sandbox connection, deterministic guardrail limits, and AI safety bounds
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sandbox Connection Card */}
        <div className="bento-card p-6 space-y-5">
          <div className="flex justify-between items-start">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-electric-50 border border-electric-200/80 flex items-center justify-center text-electric">
                <Key className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-black text-base text-ink tracking-tight">PayPal REST API Sandbox</h3>
                <p className="text-xs text-sardine-slate">Target: api-m.sandbox.paypal.com</p>
              </div>
            </div>

            <button
              onClick={handleTestConnection}
              disabled={isTesting}
              className="flex items-center space-x-1.5 px-3.5 py-2 bg-ink hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow-xs transition-all disabled:opacity-50 border border-slate-700 hover:border-electric"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-electric ${isTesting ? 'animate-spin' : ''}`} />
              <span>{isTesting ? 'Testing...' : 'Test Connection'}</span>
            </button>
          </div>

          {/* Test Result Message */}
          {testResult && (
            <div
              className={`p-4 rounded-xl border text-xs shadow-2xs ${
                testResult.success
                  ? 'bg-emerald-50/90 text-emerald-900 border-emerald-300'
                  : 'bg-amber-50 text-amber-900 border-amber-300'
              }`}
            >
              <div className="font-bold flex items-center space-x-1.5">
                {testResult.success ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <AlertTriangle className="w-4 h-4 text-amber-600" />}
                <span>{testResult.success ? 'Sandbox Authentication Verified' : 'Authentication Diagnostic'}</span>
              </div>
              <p className="mt-1 text-slate-700">{testResult.message}</p>
              {testResult.token_preview && (
                <p className="font-mono text-[11px] mt-1.5 bg-white/70 p-1.5 rounded-lg border border-emerald-200 text-emerald-900">
                  Token: {testResult.token_preview}
                </p>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 pt-3 text-xs border-t border-slate-100">
            <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Environment</span>
              <span className="font-black text-emerald-700 block mt-0.5">SANDBOX ONLY</span>
              <span className="text-[10px] text-sardine-slate block">Hard Refusal Active</span>
            </div>
            <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Client ID Preview</span>
              <span className="font-mono font-bold text-ink block mt-0.5 truncate">
                {status?.client_id_preview || 'Configured via .env'}
              </span>
              <span className="text-[10px] text-sardine-slate block">OAuth2 Cached</span>
            </div>
          </div>
        </div>

        {/* Safety Policy Limits Card */}
        <div className="bento-card p-6 space-y-5">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-center text-purple-700">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-base text-ink tracking-tight">Deterministic Policy Controls</h3>
              <p className="text-xs text-sardine-slate">Enforced by Guardrail Agent. Zero code paths bypass these bounds.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Early Discount</span>
              <span className="font-black text-ink text-base">5.0% Cap</span>
              <span className="text-[10px] text-sardine-slate block mt-0.5">Plan B capped at 3.0%</span>
            </div>

            <div className="p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Single Payout</span>
              <span className="font-black text-ink text-base">$10,000 Cap</span>
              <span className="text-[10px] text-sardine-slate block mt-0.5">Hard financial ceiling</span>
            </div>

            <div className="p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Currencies</span>
              <span className="font-black text-ink text-sm">USD, EUR, GBP</span>
              <span className="text-[10px] text-sardine-slate block mt-0.5">Strict ISO whitelist</span>
            </div>
          </div>
        </div>

        {/* LLM Safety & Fallback Pod */}
        <div className="bento-ink p-6 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-electric-soft">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-base text-white tracking-tight">LLM Safety Boundary</h3>
              <p className="text-xs text-sardine-muted">Google Gemini / Anthropic / Template Fallback</p>
            </div>
          </div>

          <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 text-xs space-y-2 text-slate-300">
            <div className="flex items-center space-x-2 text-emerald-400 font-bold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Zero-Execution Rule Enforced</span>
            </div>
            <p className="text-sardine-muted text-[11px] leading-relaxed">
              The AI layer is restricted to plain-language driver summaries and message drafts. It can never approve, execute, or modify any dollar amount or transaction.
            </p>
          </div>
        </div>

        {/* Webhook Ingress Architecture */}
        <div className="bento-card p-6 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
              <Radio className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-base text-ink tracking-tight">Webhook Ingress Pipeline</h3>
              <p className="text-xs text-sardine-slate">Cryptographically verified via PayPal API</p>
            </div>
          </div>

          <div className="p-4 bg-slate-50/80 rounded-xl border border-slate-200/60 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sardine-slate">Verification Endpoint:</span>
              <span className="font-mono text-ink font-bold">/v1/notifications/verify-webhook-signature</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sardine-slate">Queue Persistence:</span>
              <span className="font-mono text-emerald-700 font-bold">asyncio + SQLite / MySQL WAL</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sardine-slate">Auto-Recalculate on Pay:</span>
              <span className="font-mono text-electric font-bold">Enabled</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
