import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Action } from '../types';
import { ShieldCheck, Lock, RefreshCw, Key, AlertCircle, CheckCircle } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

export const ApprovalInboxPage: React.FC = () => {
  const { formatCurrency } = useRegionalPreferences();
  const [actions, setActions] = useState<Action[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [notification, setNotification] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchActions = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await api.getActions();
      setActions(data);
    } catch (err: any) {
      const msg = err.message || 'Failed to load actions from server.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchActions();
  }, []);

  useEffect(() => {
    if (notification) {
      const t = setTimeout(() => setNotification(null), 2400);
      return () => clearTimeout(t);
    }
  }, [notification]);

  const handleApprove = async (action: Action) => {
    try {
      setApprovingId(action.id);
      await api.approveAction(action.id, action.approval_hash);
      setNotification(`Action #${action.id} signed and approved successfully!`);
      await fetchActions();
    } catch (err: any) {
      setNotification(`Approval failed: ${err.message}`);
    } finally {
      setApprovingId(null);
    }
  };

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Toast */}
      {notification && (
        <div className="ignara-toast">
          <div className="flex items-center gap-2">
            {notification.includes('failed') ? (
              <AlertCircle className="w-4 h-4 text-[var(--r)] shrink-0" />
            ) : (
              <CheckCircle className="w-4 h-4 text-[var(--g)] shrink-0" />
            )}
            <span>{notification}</span>
          </div>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-2 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">Approval Inbox</h1>
            <span className="text-[11px] bg-[var(--card2)] text-[var(--o1)] border border-[var(--o1)]/30 px-2.5 py-0.5 rounded-full font-semibold uppercase tracking-wider">
              Deterministic Guardrail
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Actions requiring explicit owner authorization. All actions cryptographically bound via HMAC-SHA256 signatures.
          </p>
        </div>

        <button
          onClick={fetchActions}
          className="ignara-btn-secondary"
          title="Refresh actions"
        >
          <RefreshCw className={`w-4 h-4 text-[var(--mu)] ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="p-3.5 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] text-xs font-semibold flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {actions.length === 0 ? (
        <div className="text-center py-16 ignara-card p-6">
          <ShieldCheck className="w-10 h-10 text-[var(--dim)] mx-auto mb-2" />
          <p className="text-sm font-semibold text-[var(--tx)]">No actions currently pending approval.</p>
          <p className="text-xs text-[var(--mu)] mt-0.5">Run a forecast on the dashboard to generate rescue plans.</p>
        </div>
      ) : (
        <div className="space-y-3 ignara-stagger-1">
          {actions.map((act) => {
            const isProposed = act.state === 'proposed';
            return (
              <div
                key={act.id}
                className={`ignara-card p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 ignara-card-hover ${
                  isProposed ? 'border-l-4 border-l-[var(--o1)]' : ''
                }`}
              >
                <div className="space-y-1.5 w-full md:w-auto min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`text-[10px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
                        act.state === 'confirmed'
                          ? 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30'
                          : act.state === 'simulated'
                          ? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
                          : act.state === 'executed'
                          ? 'bg-[var(--side)] text-[var(--tx)] border-[var(--line)]'
                          : act.state === 'approved'
                          ? 'bg-[var(--o1)]/15 text-[var(--o1)] border-[var(--o1)]/30'
                          : 'bg-[var(--y)]/15 text-[var(--y)] border-[var(--y)]/30'
                      }`}
                    >
                      {act.state === 'simulated' ? 'Simulated Payment' : act.state}
                    </span>
                    <span className="font-mono text-xs font-semibold text-[var(--tx)]">{act.action_type}</span>
                    {act.is_simulated && (
                      <span className="text-[10px] font-semibold bg-[var(--y)]/15 text-[var(--y)] border border-[var(--y)]/30 px-2 py-0.5 rounded-[6px]">
                        Simulated
                      </span>
                    )}
                  </div>

                  <div className="text-sm font-semibold text-[var(--tx)] font-mono truncate">
                    Target: {act.recipient} &mdash; {formatCurrency(act.amount, { currency: act.currency, showCode: true })}
                  </div>

                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--mu)] font-mono">
                    <span className="truncate max-w-[200px]">ID: {act.idempotency_key}</span>
                    <span className="text-[var(--o1)] font-semibold truncate max-w-[200px]">HMAC: {act.approval_hash.slice(0, 16)}...</span>
                  </div>
                </div>

                {isProposed && (
                  <button
                    onClick={() => handleApprove(act)}
                    disabled={approvingId === act.id}
                    className="ignara-btn-primary w-full md:w-auto text-xs min-h-[44px] disabled:opacity-50"
                  >
                    <Lock className={`w-3.5 h-3.5 ${approvingId === act.id ? 'animate-spin' : ''}`} />
                    <span>{approvingId === act.id ? 'Authorizing...' : 'Sign & Approve'}</span>
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
