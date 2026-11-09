import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Action } from '../types';
import { ShieldCheck, Lock, RefreshCw, Key, AlertCircle } from 'lucide-react';

export const ApprovalInboxPage: React.FC = () => {
  const [actions, setActions] = useState<Action[]>([]);
  const [isLoading, setIsLoading] = useState(true);
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

  const handleApprove = async (action: Action) => {
    try {
      await api.approveAction(action.id, action.approval_hash);
      setNotification(`Action #${action.id} approved successfully!`);
      await fetchActions();
    } catch (err: any) {
      setNotification(`Approval failed: ${err.message}`);
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 space-y-4 sm:space-y-6 w-full overflow-hidden">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-slate-200 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-extrabold text-ink tracking-tight">Guardrail Approval Inbox</h2>
            <span className="text-[10px] bg-ink text-white px-2 py-0.5 rounded-md font-bold uppercase tracking-wider">
              Deterministic Guardrail
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-1">
            Actions requiring explicit owner authorization. All actions cryptographically bound via HMAC-SHA256 signatures.
          </p>
        </div>
        <button
          onClick={fetchActions}
          className="p-2.5 text-sardine-slate hover:text-ink rounded-xl hover:bg-slate-100 transition-colors border border-slate-200 bg-white min-h-[44px] min-w-[44px] flex items-center justify-center self-end sm:self-auto shadow-2xs"
          title="Refresh actions"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {notification && (
        <div className="p-3.5 rounded-xl bg-electric-50 border border-electric-200 text-electric-600 text-xs font-semibold">
          {notification}
        </div>
      )}

      {actions.length === 0 ? (
        <div className="text-center py-16 bento-card border border-slate-200/90 p-4">
          <ShieldCheck className="w-10 h-10 text-sardine-muted mx-auto mb-2" />
          <p className="text-sm font-semibold text-ink">No actions currently pending approval.</p>
          <p className="text-xs text-sardine-slate mt-0.5">Run a forecast on the dashboard to generate rescue plans.</p>
        </div>
      ) : (
        <div className="bento-card border border-slate-200/90 shadow-bento overflow-hidden divide-y divide-slate-100">
          {actions.map((act) => (
            <div key={act.id} className="p-4 sm:p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 sm:gap-4 hover:bg-slate-50/50 transition-colors">
              <div className="space-y-1.5 w-full md:w-auto min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                      act.state === 'confirmed'
                        ? 'bg-emerald-100 text-emerald-800'
                        : act.state === 'simulated'
                        ? 'bg-purple-100 text-purple-800 border border-purple-300'
                        : act.state === 'executed'
                        ? 'bg-ink text-white'
                        : act.state === 'approved'
                        ? 'bg-electric-50 text-electric-600 border border-electric-200'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {act.state === 'simulated' ? 'Simulated Payment' : act.state}
                  </span>
                  <span className="font-mono text-xs font-bold text-ink">{act.action_type}</span>
                  {act.is_simulated && (
                    <span className="text-[9px] font-semibold bg-amber-50 text-amber-800 border border-amber-300 px-1.5 py-0.2 rounded">
                      Simulated
                    </span>
                  )}
                </div>

                <div className="text-sm font-extrabold text-ink font-mono truncate">
                  Target: {act.recipient} &mdash; ${act.amount.toFixed(2)} {act.currency}
                </div>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-sardine-slate font-mono">
                  <span className="truncate max-w-[200px]">ID: {act.idempotency_key}</span>
                  <span className="text-electric font-semibold truncate max-w-[200px]">HMAC: {act.approval_hash.slice(0, 16)}...</span>
                </div>
              </div>

              {act.state === 'proposed' && (
                <button
                  onClick={() => handleApprove(act)}
                  className="w-full md:w-auto px-4 py-2.5 bg-electric hover:bg-electric-600 text-white text-xs font-bold rounded-xl flex items-center justify-center space-x-1.5 shadow-xs transition-colors shrink-0 min-h-[44px]"
                >
                  <Lock className="w-3.5 h-3.5" />
                  <span>Sign &amp; Approve</span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
