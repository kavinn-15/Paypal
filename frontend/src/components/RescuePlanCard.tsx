import React from 'react';
import { RescuePlan } from '../types';
import { ShieldAlert, CheckCircle2, Lock, Send, Percent, Split, Sparkles } from 'lucide-react';

interface RescuePlanCardProps {
  plan: RescuePlan;
  isSelected: boolean;
  onSelect: () => void;
  onApprove: (actionId: number, approvalHash: string) => Promise<void>;
  onExecute: (actionId: number, idempotencyKey: string) => Promise<void>;
  isLoading: boolean;
}

export const RescuePlanCard: React.FC<RescuePlanCardProps> = ({
  plan,
  isSelected,
  onSelect,
  onApprove,
  onExecute,
  isLoading,
}) => {
  const action = plan.primary_action;

  const planPills = {
    A: { bg: 'bg-electric-50 text-electric-600 border-electric-200/80', label: 'Plan A: Zero Concession' },
    B: { bg: 'bg-purple-50 text-purple-700 border-purple-200', label: 'Plan B: 3% Discount' },
    C: { bg: 'bg-emerald-50 text-emerald-800 border-emerald-200', label: 'Plan C: Agreed Split' },
  };

  const handleApproveClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await onApprove(action.id, action.approval_hash);
  };

  const handleExecuteClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await onExecute(action.id, action.idempotency_key);
  };

  return (
    <div
      onClick={onSelect}
      className={`bento-card p-6 transition-all cursor-pointer relative flex flex-col justify-between ${
        isSelected
          ? 'border-electric ring-2 ring-electric/15 shadow-bento-hover'
          : 'border-slate-200/90 hover:border-slate-300 shadow-bento'
      }`}
    >
      <div>
        {/* Header Badge */}
        <div className="flex justify-between items-center mb-3">
          <span
            className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
              planPills[plan.plan_type].bg
            }`}
          >
            {planPills[plan.plan_type].label}
          </span>

          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-md ${
              isSelected ? 'bg-electric text-white' : 'bg-slate-100 text-sardine-slate'
            }`}
          >
            {isSelected ? 'Active Preview' : 'Select'}
          </span>
        </div>

        <h3 className="font-extrabold text-base text-ink tracking-tight leading-snug">{plan.name}</h3>
        <p className="text-xs text-sardine-slate mt-1 leading-relaxed">{plan.description}</p>

        {/* Cost & Incoming Metrics Grid */}
        <div className="grid grid-cols-2 gap-2 my-4 p-3 bg-slate-50/80 rounded-xl border border-slate-100">
          <div>
            <span className="text-[10px] uppercase font-bold text-sardine-muted block tracking-wider">Plan Cost</span>
            <span
              className={`text-sm font-extrabold font-mono ${
                plan.cost === 0 ? 'text-emerald-600' : 'text-purple-600'
              }`}
            >
              ${plan.cost.toFixed(2)}
            </span>
            <span className="text-[10px] text-sardine-slate block truncate">{plan.cost_description}</span>
          </div>

          <div className="border-l border-slate-200 pl-3">
            <span className="text-[10px] uppercase font-bold text-sardine-muted block tracking-wider">Incoming Needed</span>
            <span className="text-sm font-extrabold font-mono text-ink">
              ${plan.incoming_needed.toFixed(2)}
            </span>
            <span className="text-[10px] text-sardine-slate block truncate">
              {plan.incoming_needed === 0 ? 'Covered Friday' : 'To bridge shortfall'}
            </span>
          </div>
        </div>

        {/* Strategy Rationale */}
        <div className="text-xs text-sardine-slate space-y-1 my-3">
          <span className="font-bold text-ink block text-[10px] uppercase tracking-wider">Engine Rationale:</span>
          <p className="bg-slate-50/70 p-2.5 rounded-lg border border-slate-200/60 leading-relaxed text-[11px]">
            {plan.rationale}
          </p>
        </div>

        {/* Remaining Risk Alert (Strictly using 'plausibly protects', never 'guarantees') */}
        <div className="p-3 bg-amber-50/50 rounded-xl border border-amber-200/70 my-3 text-[11px] leading-relaxed text-amber-950">
          <span className="font-bold block flex items-center space-x-1 text-amber-900">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span>Remaining Risk:</span>
          </span>
          <p className="mt-0.5 text-amber-800">{plan.remaining_risk}</p>
        </div>
      </div>

      {/* Action Execution Footer & Exact Parameters Bound */}
      <div className="pt-4 border-t border-slate-100 mt-2 space-y-3">
        {/* Bound Parameters Box */}
        <div className="bg-ink text-white p-3 rounded-xl text-[11px] font-mono space-y-1 border border-slate-800">
          <div className="flex justify-between text-sardine-muted text-[10px] border-b border-slate-800 pb-1 mb-1 font-sans">
            <span className="flex items-center space-x-1">
              <Lock className="w-2.5 h-2.5 text-electric-300" />
              <span>HMAC-SHA256 Bound</span>
            </span>
            <span className="text-[9px] text-sardine-muted truncate max-w-[120px] font-mono">
              {action.approval_hash.slice(0, 10)}...
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-sardine-muted">Action:</span>
            <span className="text-electric-300 font-bold">{action.action_type}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sardine-muted">Target:</span>
            <span className="text-white truncate max-w-[130px]">{action.recipient}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sardine-muted">Amount:</span>
            <span className="text-emerald-400 font-bold">${action.amount.toFixed(2)} USD</span>
          </div>
        </div>

        {/* Dynamic State Transition Button */}
        <div>
          {action.state === 'proposed' && (
            <button
              onClick={handleApproveClick}
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-electric hover:bg-electric-600 text-white text-xs font-bold rounded-xl transition-all shadow-xs flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Approve Exact Action ({action.recipient.split(' ')[0]} - ${action.amount.toFixed(0)})</span>
            </button>
          )}

          {action.state === 'approved' && (
            <button
              onClick={handleExecuteClick}
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-ink hover:bg-ink-800 text-white text-xs font-bold rounded-xl transition-all shadow-xs flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5 text-electric-300" />
              <span>Execute in PayPal Sandbox</span>
            </button>
          )}

          {action.state === 'executed' && (
            <div className="w-full py-2 px-3 bg-amber-50 border border-amber-300/80 text-amber-800 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
              <span>Executed: Awaiting Sandbox Settlement</span>
            </div>
          )}

          {action.state === 'confirmed' && (
            <div className="w-full py-2 px-3 bg-emerald-50 border border-emerald-300 text-emerald-800 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Payment Confirmed via Webhook</span>
            </div>
          )}

          {action.state === 'failed' && (
            <div className="w-full py-2 px-3 bg-rose-50 border border-rose-300 text-rose-800 rounded-xl text-xs font-semibold text-center">
              Failed: {action.error_message || 'Sandbox error'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
