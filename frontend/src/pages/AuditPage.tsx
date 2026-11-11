import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { AuditLogEntry, AuditVerifyResponse } from '../types';
import { ShieldCheck, CheckCircle2, AlertTriangle, RefreshCw, Lock, Link as LinkIcon, Hash, Database } from 'lucide-react';
import { CountUp } from '../components/CountUp';

export const AuditPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [verification, setVerification] = useState<AuditVerifyResponse | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.getAuditLogs();
      setLogs(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load cryptographic audit logs.');
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
      setError(null);
      const res = await api.verifyAuditChain();
      setVerification(res);
    } catch (err: any) {
      setError(err.message || 'Verification of audit chain failed.');
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-2 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">
              Cryptographic Audit Trail
            </h1>
            <span className="text-[11px] bg-[var(--card2)] text-[var(--mu)] border border-[var(--line)] px-2.5 py-0.5 rounded-full font-semibold">
              SHA-256 Chained
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Append-only tamper-resistant ledger of every system decision, approval signature, and webhook event
          </p>
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          <button
            onClick={fetchLogs}
            disabled={isLoading}
            className="ignara-btn-secondary"
            title="Refresh logs"
          >
            <RefreshCw className={`w-4 h-4 text-[var(--mu)] ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={handleVerifyChain}
            disabled={isVerifying}
            className="ignara-btn-primary"
          >
            <ShieldCheck className={`w-4 h-4 text-white ${isVerifying ? 'animate-spin' : ''}`} />
            <span>{isVerifying ? 'Traversing Chain...' : 'Verify Chain Integrity'}</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-3.5 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchLogs}
            className="font-semibold underline hover:opacity-80 cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Verification Result Banner */}
      {verification && (
        <div
          className={`p-4 rounded-[18px] border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs transition-all ${
            verification.chain_valid
              ? 'bg-[var(--g)]/15 text-[var(--tx)] border-[var(--g)]/30'
              : 'bg-[var(--r)]/15 text-[var(--tx)] border-[var(--r)]/30'
          }`}
        >
          <div className="flex items-center space-x-3">
            {verification.chain_valid ? (
              <div className="w-8 h-8 rounded-[10px] bg-[var(--g)] text-white flex items-center justify-center font-semibold shrink-0">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-[10px] bg-[var(--r)] text-white flex items-center justify-center font-semibold shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
            )}
            <div>
              <span className="font-semibold text-sm block text-[var(--tx)]">
                {verification.chain_valid ? 'Audit Ledger 100% Cryptographically Intact' : 'Audit Chain Tampering Detected!'}
              </span>
              <span className="text-[var(--mu)] text-[11px] leading-relaxed">{verification.message}</span>
            </div>
          </div>
          <span className="font-mono font-semibold bg-[var(--card)] px-3 py-1.5 rounded-[10px] border border-[var(--line)] text-[var(--g)] shrink-0 self-end sm:self-auto">
            {verification.total_blocks} Verified Blocks
          </span>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 ignara-stagger-1">
        <div className="ignara-card p-4 sm:p-5 flex items-center space-x-3 ignara-card-hover">
          <div className="w-10 h-10 rounded-[12px] bg-[var(--side)] border border-[var(--line)] flex items-center justify-center text-[var(--o1)] shrink-0">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--dim)] block">Total Blocks</span>
            <span className="ignara-num-big text-lg text-[var(--tx)]">
              <CountUp value={logs.length} prefix="" decimals={0} /> Blocks
            </span>
          </div>
        </div>

        <div className="ignara-card p-4 sm:p-5 flex items-center space-x-3 ignara-card-hover">
          <div className="w-10 h-10 rounded-[12px] bg-[var(--side)] border border-[var(--line)] flex items-center justify-center text-[var(--tx)] shrink-0">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--dim)] block">Ledger Mode</span>
            <span className="font-mono font-semibold text-sm text-[var(--tx)]">Append-Only / WAL</span>
          </div>
        </div>

        <div className="ignara-card p-4 sm:p-5 flex items-center space-x-3 ignara-card-hover">
          <div className="w-10 h-10 rounded-[12px] bg-[var(--side)] border border-[var(--line)] flex items-center justify-center text-[var(--g)] shrink-0">
            <Hash className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--dim)] block">Genesis Block</span>
            <span className="font-mono font-semibold text-xs text-[var(--mu)] truncate max-w-[150px] block">
              0000000000000000...
            </span>
          </div>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="ignara-card p-0 overflow-hidden ignara-stagger-2">
        {/* Mobile View */}
        <div className="block md:hidden divide-y divide-[var(--line)]">
          {logs.map((log) => (
            <div key={log.id} className="p-4 space-y-2 hover:bg-[var(--card2)] transition-colors">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center space-x-2">
                  <span className="font-semibold text-xs text-[var(--tx)] font-mono">#{log.id}</span>
                  <span
                    className={`px-2 py-0.5 rounded-[6px] text-[9.5px] font-semibold uppercase border ${
                      log.actor === 'owner'
                        ? 'bg-[var(--o1)]/15 text-[var(--o1)] border-[var(--o1)]/30'
                        : log.actor === 'system'
                        ? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
                        : log.actor === 'webhook'
                        ? 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30'
                        : 'bg-[var(--card2)] text-[var(--mu)] border-[var(--line)]'
                    }`}
                  >
                    {log.actor}
                  </span>
                </div>
                <span className="font-sans text-[11px] text-[var(--dim)]">
                  {new Date(log.ts).toLocaleDateString()} {new Date(log.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>

              <div className="font-semibold text-xs text-[var(--tx)]">{log.event}</div>

              <div className="text-[10.5px] font-mono text-[var(--mu)] space-y-0.5 bg-[var(--side)] p-2.5 rounded-[10px] border border-[var(--line)]">
                <div className="truncate">Prev: <span className="text-[var(--dim)]">{log.prev_hash.slice(0, 16)}...</span></div>
                <div className="truncate">Hash: <span className="text-[var(--g)] font-semibold">{log.hash.slice(0, 20)}...</span></div>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop View */}
        <div className="hidden md:block responsive-table-container">
          <table className="ignara-table text-left text-xs">
            <thead className="bg-[var(--side)] text-[var(--dim)] font-semibold uppercase tracking-wider text-[10.5px]">
              <tr>
                <th className="px-5 py-3.5">Block ID</th>
                <th className="px-5 py-3.5">Timestamp (UTC)</th>
                <th className="px-5 py-3.5">Actor</th>
                <th className="px-5 py-3.5">Event Type</th>
                <th className="px-5 py-3.5">Prev Hash</th>
                <th className="px-5 py-3.5">Block SHA-256 Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)] font-mono text-[11px]">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-[var(--card2)] transition-colors">
                  <td className="px-5 py-3.5 font-semibold text-[var(--tx)]">#{log.id}</td>
                  <td className="px-5 py-3.5 text-[var(--mu)] font-sans text-xs whitespace-nowrap">
                    {new Date(log.ts).toLocaleString()}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`px-2.5 py-0.5 rounded-[6px] font-sans text-[10px] font-semibold uppercase border ${
                        log.actor === 'owner'
                          ? 'bg-[var(--o1)]/15 text-[var(--o1)] border-[var(--o1)]/30'
                          : log.actor === 'system'
                          ? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
                          : log.actor === 'webhook'
                          ? 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30'
                          : 'bg-[var(--card2)] text-[var(--mu)] border-[var(--line)]'
                      }`}
                    >
                      {log.actor}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 font-semibold font-sans text-xs text-[var(--tx)]">{log.event}</td>
                  <td className="px-5 py-3.5 text-[var(--dim)] text-[11px]">
                    {log.prev_hash.slice(0, 12)}...
                  </td>
                  <td className="px-5 py-3.5 text-[var(--g)] font-semibold text-[11px]">
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
