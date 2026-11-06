import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { AuditLogEntry, AuditVerifyResponse } from '../types';
import { ShieldCheck, CheckCircle2, AlertTriangle, RefreshCw, Lock, Link as LinkIcon } from 'lucide-react';

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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 flex items-center space-x-2">
            <span>Cryptographic Audit Trail</span>
            <span className="text-xs bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded-full font-bold">
              SHA-256 Hash Chained
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Append-only tamper-resistant ledger of every system decision, approval signature, and webhook event
          </p>
        </div>

        <button
          onClick={handleVerifyChain}
          disabled={isVerifying}
          className="flex items-center space-x-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-sm transition-all disabled:opacity-50"
        >
          <ShieldCheck className={`w-4 h-4 ${isVerifying ? 'animate-spin' : ''}`} />
          <span>{isVerifying ? 'Traversing Chain...' : 'Verify Chain Integrity'}</span>
        </button>
      </div>

      {/* Verification Result Banner */}
      {verification && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between text-xs ${
            verification.chain_valid
              ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
              : 'bg-rose-50 text-rose-800 border-rose-300'
          }`}
        >
          <div className="flex items-center space-x-3">
            {verification.chain_valid ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            )}
            <div>
              <span className="font-bold text-sm block">
                {verification.chain_valid ? 'Audit Chain 100% Intact' : 'Audit Chain Tampering Detected!'}
              </span>
              <span>{verification.message}</span>
            </div>
          </div>
          <span className="font-mono font-bold bg-white/60 px-3 py-1 rounded-lg border border-slate-200">
            {verification.total_blocks} Blocks Verified
          </span>
        </div>
      )}

      {/* Ledger Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-4 py-3">Block ID</th>
                <th className="px-4 py-3">Timestamp (UTC)</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Event Type</th>
                <th className="px-4 py-3">Prev Hash</th>
                <th className="px-4 py-3">Block SHA-256 Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="px-4 py-3 font-bold text-slate-900">#{log.id}</td>
                  <td className="px-4 py-3 text-slate-500 font-sans text-xs">
                    {new Date(log.ts).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded font-sans text-[10px] font-bold uppercase ${
                        log.actor === 'owner'
                          ? 'bg-blue-100 text-blue-800'
                          : log.actor === 'system'
                          ? 'bg-purple-100 text-purple-800'
                          : log.actor === 'webhook'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-slate-100 text-slate-800'
                      }`}
                    >
                      {log.actor}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-bold font-sans text-xs text-slate-800">{log.event}</td>
                  <td className="px-4 py-3 text-slate-400 text-[10px]">
                    {log.prev_hash.slice(0, 12)}...
                  </td>
                  <td className="px-4 py-3 text-emerald-700 font-semibold text-[10px]">
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
