import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { AuditLogEntry, AuditVerifyResponse } from '../types';
import { ShieldCheck, CheckCircle2, AlertTriangle, RefreshCw, Lock, Link as LinkIcon, Hash, Database } from 'lucide-react';

export const AuditPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [verification, setVerification] = useState<AuditVerifyResponse | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const fetchLogs = async () => {
    try {
      setIsLoading(true);
      const res = await api.getAuditLogs();
      setLogs(res);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const handleVerifyChain = async () => {
    try {
      setIsVerifying(true);
      const res = await api.verifyAuditChain();
      setVerification(res);
    } catch {
      // ignore
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Bento Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-black text-ink tracking-tight font-display">
              Cryptographic Audit Trail
            </h1>
            <span className="text-xs bg-slate-100 text-sardine-slate border border-slate-200 px-2.5 py-0.5 rounded-full font-bold">
              SHA-256 Chained
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-1">
            Append-only tamper-resistant ledger of every system decision, approval signature, and webhook event
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchLogs}
            disabled={isLoading}
            className="p-2.5 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl text-sardine-slate hover:text-ink transition-colors shadow-2xs"
            title="Refresh logs"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={handleVerifyChain}
            disabled={isVerifying}
            className="flex items-center space-x-2 px-4 py-2.5 bg-ink hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow-xs transition-all disabled:opacity-50 border border-slate-700 hover:border-electric"
          >
            <ShieldCheck className={`w-4 h-4 text-electric ${isVerifying ? 'animate-spin' : ''}`} />
            <span>{isVerifying ? 'Traversing Chain...' : 'Verify Chain Integrity'}</span>
          </button>
        </div>
      </div>

      {/* Verification Result Banner */}
      {verification && (
        <div
          className={`p-4 rounded-2xl border flex items-center justify-between text-xs shadow-xs transition-all ${
            verification.chain_valid
              ? 'bg-emerald-50/90 text-emerald-900 border-emerald-300'
              : 'bg-rose-50 text-rose-900 border-rose-300'
          }`}
        >
          <div className="flex items-center space-x-3">
            {verification.chain_valid ? (
              <div className="w-8 h-8 rounded-xl bg-emerald-500 text-white flex items-center justify-center font-bold">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-xl bg-rose-500 text-white flex items-center justify-center font-bold">
                <AlertTriangle className="w-5 h-5" />
              </div>
            )}
            <div>
              <span className="font-black text-sm block">
                {verification.chain_valid ? 'Audit Ledger 100% Cryptographically Intact' : 'Audit Chain Tampering Detected!'}
              </span>
              <span className="text-emerald-800/90">{verification.message}</span>
            </div>
          </div>
          <span className="font-mono font-bold bg-white px-3 py-1.5 rounded-xl border border-emerald-200 text-emerald-800 shadow-2xs">
            {verification.total_blocks} Verified Blocks
          </span>
        </div>
      )}

      {/* Bento Grid Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bento-card p-4 flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-electric-50 border border-electric-200/80 flex items-center justify-center text-electric">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-sardine-muted block">Total Blocks</span>
            <span className="font-mono font-black text-lg text-ink">{logs.length} Blocks</span>
          </div>
        </div>

        <div className="bento-card p-4 flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-sardine-muted block">Ledger Mode</span>
            <span className="font-mono font-black text-sm text-ink">Append-Only / WAL</span>
          </div>
        </div>

        <div className="bento-card p-4 flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
            <Hash className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-sardine-muted block">Genesis Block</span>
            <span className="font-mono font-bold text-xs text-sardine-slate">0000000000000000...</span>
          </div>
        </div>
      </div>

      {/* Ledger Table - Bento Card Container */}
      <div className="bento-card overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50/80 text-sardine-slate font-bold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-5 py-3.5">Block ID</th>
                <th className="px-5 py-3.5">Timestamp (UTC)</th>
                <th className="px-5 py-3.5">Actor</th>
                <th className="px-5 py-3.5">Event Type</th>
                <th className="px-5 py-3.5">Prev Hash</th>
                <th className="px-5 py-3.5">Block SHA-256 Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="px-5 py-3.5 font-bold text-ink">#{log.id}</td>
                  <td className="px-5 py-3.5 text-sardine-slate font-sans text-xs">
                    {new Date(log.ts).toLocaleString()}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`px-2 py-0.5 rounded-md font-sans text-[10px] font-bold uppercase border ${
                        log.actor === 'owner'
                          ? 'bg-electric-50 text-electric-700 border-electric-200'
                          : log.actor === 'system'
                          ? 'bg-purple-50 text-purple-700 border-purple-200'
                          : log.actor === 'webhook'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-slate-100 text-slate-700 border-slate-200'
                      }`}
                    >
                      {log.actor}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 font-black font-sans text-xs text-ink">{log.event}</td>
                  <td className="px-5 py-3.5 text-sardine-muted text-[11px]">
                    {log.prev_hash.slice(0, 12)}...
                  </td>
                  <td className="px-5 py-3.5 text-emerald-700 font-bold text-[11px]">
                    {log.hash.slice(0, 16)}...
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
