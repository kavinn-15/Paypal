import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { PayPalConnectionStatus } from '../types';
import { Settings, ShieldCheck, CheckCircle2, AlertTriangle, RefreshCw, Key, Globe, Shield } from 'lucide-react';

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
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h2 className="text-xl font-extrabold text-slate-900">System Settings & PayPal Sandbox Connection</h2>
        <p className="text-xs text-slate-500 mt-1">
          Verify sandbox credentials, policy bounds, and webhook ingress
        </p>
      </div>

      {/* Sandbox Connection Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div className="flex justify-between items-start">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-700">
              <Key className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-sm text-slate-900">PayPal REST API Sandbox</h3>
              <p className="text-xs text-slate-500">Targeting: https://api-m.sandbox.paypal.com</p>
            </div>
          </div>

          <button
            onClick={handleTestConnection}
            disabled={isTesting}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-sm transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />
            <span>{isTesting ? 'Pinging Sandbox...' : 'Test Connection'}</span>
          </button>
        </div>

        {/* Test Result Message */}
        {testResult && (
          <div
            className={`p-3.5 rounded-xl border text-xs ${
              testResult.success
                ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                : 'bg-amber-50 text-amber-800 border-amber-300'
            }`}
          >
            <div className="font-bold flex items-center space-x-1.5">
              {testResult.success ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <AlertTriangle className="w-4 h-4 text-amber-600" />}
              <span>{testResult.success ? 'Sandbox Authentication Verified' : 'Authentication Diagnostic'}</span>
            </div>
            <p className="mt-1">{testResult.message}</p>
            {testResult.token_preview && (
              <p className="font-mono text-[11px] mt-1 text-slate-600">Token: {testResult.token_preview}</p>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 pt-2 text-xs border-t border-slate-100">
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-400 block">Environment</span>
            <span className="font-bold text-slate-800">SANDBOX ONLY (Hard Refusal Guard Active)</span>
          </div>
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-400 block">Client ID Preview</span>
            <span className="font-mono text-slate-600">{status?.client_id_preview || 'Configured via .env'}</span>
          </div>
        </div>
      </div>

      {/* Safety Policy Limits Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-center text-purple-700">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-extrabold text-sm text-slate-900">Deterministic Policy Controls</h3>
            <p className="text-xs text-slate-500">Enforced by Guardrail Agent. No code path bypasses these rules.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400 block">Max Early Discount</span>
            <span className="font-bold text-slate-900 text-sm">5.0% Cap</span>
            <span className="text-[10px] text-slate-500 block mt-0.5">Plan B capped at 3.0%</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400 block">Max Single Payout</span>
            <span className="font-bold text-slate-900 text-sm">$10,000.00 USD</span>
            <span className="text-[10px] text-slate-500 block mt-0.5">Hard financial ceiling</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400 block">Allowed Currencies</span>
            <span className="font-bold text-slate-900 text-sm">USD, EUR, GBP, CAD</span>
            <span className="text-[10px] text-slate-500 block mt-0.5">Strict ISO whitelist</span>
          </div>
        </div>
      </div>
    </div>
  );
};
