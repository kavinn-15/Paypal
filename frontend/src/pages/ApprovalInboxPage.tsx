import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Action } from '../types';
import { ShieldCheck, Lock, CheckCircle2, Clock, AlertCircle, RefreshCw } from 'lucide-react';

export const ApprovalInboxPage: React.FC = () => {
  const [actions, setActions] = useState<Action[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [notification, setNotification] = useState<string | null>(null);

  const fetchActions = async () => {
    try {
      setIsLoading(true);
      const res = await fetch('/api/actions');
      if (res.ok) {
        const data = await res.json();
        setActions(data);
      }
    } catch {
      // ignore
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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 flex items-center space-x-2">
            <span>Guardrail Approval Inbox</span>
            <span className="text-xs bg-blue-100 text-blue-800 px-2.5 py-0.5 rounded-full font-bold">
              Deterministic Only
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Actions requiring owner review. All actions are cryptographically signed with HMAC-SHA256.
          </p>
        </div>
        <button
          onClick={fetchActions}
          className="p-2 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {notification && (
        <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-xs font-semibold">
          {notification}
        </div>
      )}

      {actions.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-2xl border border-slate-200">
          <ShieldCheck className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <p className="text-sm font-semibold text-slate-600">No actions generated yet.</p>
          <p className="text-xs text-slate-400">Run a forecast on the dashboard to generate rescue plans.</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden divide-y divide-slate-100">
          {actions.map((act) => (
            <div key={act.id} className="p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                      act.state === 'confirmed'
                        ? 'bg-emerald-100 text-emerald-800'
                        : act.state === 'executed'
                        ? 'bg-indigo-100 text-indigo-800'
                        : act.state === 'approved'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {act.state}
                  </span>
                  <span className="font-mono text-xs font-bold text-slate-700">{act.action_type}</span>
                  {act.is_simulated && (
                    <span className="text-[9px] font-semibold bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.2 rounded">
                      Simulated
                    </span>
                  )}
                </div>

                <div className="text-sm font-extrabold text-slate-900">
                  Target: {act.recipient} &mdash; ${act.amount.toFixed(2)} {act.currency}
                </div>

                <div className="flex items-center space-x-3 text-xs text-slate-500 font-mono">
                  <span>ID: {act.idempotency_key}</span>
                  <span>Sig: {act.approval_hash.slice(0, 16)}...</span>
                </div>
              </div>

              {act.state === 'proposed' && (
                <button
                  onClick={() => handleApprove(act)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl flex items-center space-x-1.5 shadow-sm"
                >
                  <Lock className="w-3.5 h-3.5" />
                  <span>Sign & Approve</span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

