import React from 'react';
import { RescuePlan } from '../types';
import { ShieldAlert, CheckCircle2, Lock, Send, Sparkles } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

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
  const { formatCurrency } = useRegionalPreferences();
  const action = plan.primary_action;

  const planPills = {
    A: { bg: 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30', label: 'Plan A: Zero Concession' },
    B: { bg: 'bg-[var(--o1)]/15 text-[var(--o1)] border-[var(--o1)]/30', label: 'Plan B: 3% Discount' },
    C: { bg: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30', label: 'Plan C: Agreed Split' },
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
      className={`ignara-card p-5 sm:p-6 transition-all duration-300 cursor-pointer relative flex flex-col justify-between ${
        isSelected
          ? 'border-[var(--o1)] ring-2 ring-[var(--o1)]/20 shadow-xl'
          : 'border-[var(--line)] hover:border-[var(--o1)]/40 ignara-card-hover'
      }`}
    >
      <div>
        {/* Header Badge */}
        <div className="flex justify-between items-center mb-3 gap-2">
          <span
            className={`text-[10.5px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full border truncate ${
              planPills[plan.plan_type].bg
            }`}
          >
            {planPills[plan.plan_type].label}
          </span>

          <span
            className={`text-[11px] font-medium px-2.5 py-0.5 rounded-[999px] shrink-0 transition-colors ${
              isSelected
                ? 'bg-[var(--o1)] text-white shadow-xs'
                : 'bg-[var(--card2)] text-[var(--dim)]'
            }`}
          >
            {isSelected ? 'Active Preview' : 'Select'}
          </span>
        </div>

        <h3 className="ignara-h3 tracking-tight leading-snug">{plan.name}</h3>
        <p className="text-xs text-[var(--mu)] mt-1 leading-relaxed">{plan.description}</p>

        {/* Cost & Incoming Metrics Grid */}
        <div className="grid grid-cols-2 gap-2 my-4 p-3 bg-[var(--card2)] rounded-[14px] border border-[var(--line)]">
          <div>
            <span className="text-[10px] uppercase font-semibold text-[var(--dim)] block tracking-wider">Plan Cost</span>
            <span
              className={`text-sm font-semibold font-mono ${
                plan.cost === 0 ? 'text-[var(--g)]' : 'text-[var(--o1)]'
              }`}
            >
              {formatCurrency(plan.cost)}
            </span>
            <span className="text-[10px] text-[var(--mu)] block truncate">{plan.cost_description}</span>
          </div>

          <div className="border-l border-[var(--line)] pl-3">
            <span className="text-[10px] uppercase font-semibold text-[var(--dim)] block tracking-wider">Incoming Needed</span>
            <span className="text-sm font-semibold font-mono text-[var(--tx)]">
              {formatCurrency(plan.incoming_needed)}
            </span>
            <span className="text-[10px] text-[var(--mu)] block truncate">
              {plan.incoming_needed === 0 ? 'Covered Friday' : 'To bridge shortfall'}
            </span>
          </div>
        </div>

        {/* Strategy Rationale */}
        <div className="text-xs text-[var(--mu)] space-y-1 my-3">
          <span className="font-semibold text-[var(--tx)] block text-[10.5px] uppercase tracking-wider">
            Engine Rationale:
          </span>
          <p className="bg-[var(--side)] p-2.5 rounded-[12px] border border-[var(--line)] leading-relaxed text-[11.5px] text-[var(--tx)]">
            {plan.rationale}
          </p>
        </div>

        {/* Remaining Risk Alert (enforcing 'plausibly protects' wording) */}
        <div className="p-3 bg-[var(--y)]/10 rounded-[14px] border border-[var(--y)]/25 my-3 text-[11.5px] leading-relaxed text-[var(--tx)]">
          <span className="font-semibold block flex items-center space-x-1.5 text-[var(--y)]">
            <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
            <span>Remaining Risk:</span>
          </span>
          <p className="mt-1 text-[var(--mu)]">{plan.remaining_risk}</p>
        </div>
      </div>

      {/* Action Execution Footer & Exact Parameters Bound */}
      <div className="pt-4 border-t border-[var(--line)] mt-2 space-y-3">
        {/* Bound Parameters Box */}
        <div className="bg-[var(--side)] text-[var(--tx)] p-3 rounded-[14px] text-[11.5px] font-mono space-y-1.5 border border-[var(--line)]">
          <div className="flex justify-between text-[var(--dim)] text-[10.5px] border-b border-[var(--line)] pb-1 mb-1 font-sans">
            <span className="flex items-center space-x-1 text-[var(--o1)]">
              <Lock className="w-3 h-3" />
              <span className="font-medium">HMAC-SHA256 Bound</span>
            </span>
            <span className="text-[10px] text-[var(--mu)] truncate max-w-[120px] font-mono">
              {action.approval_hash.slice(0, 10)}...
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--mu)]">Action:</span>
            <span className="text-[var(--o1)] font-semibold truncate max-w-[140px] text-right">{action.action_type}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--mu)]">Target:</span>
            <span className="text-[var(--tx)] truncate max-w-[140px] text-right">{action.recipient}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--mu)]">Amount:</span>
            <span className="text-[var(--g)] font-semibold">{formatCurrency(action.amount, { fromCurrency: action.currency })}</span>
          </div>
        </div>

        {/* Dynamic State Transition Button */}
        <div>
          {action.state === 'proposed' && (
            <button
              onClick={handleApproveClick}
              disabled={isLoading}
              className="ignara-btn-primary w-full py-2.5 px-3 rounded-[14px] text-xs font-semibold shadow-btn flex items-center justify-center space-x-2 disabled:opacity-50 min-h-[44px] text-center"
            >
              <Lock className="w-3.5 h-3.5 shrink-0" />
              <span>Approve Action ({action.recipient.split(' ')[0]} - {formatCurrency(action.amount, { fromCurrency: action.currency })})</span>
            </button>
          )}

          {action.state === 'approved' && (
            <button
              onClick={handleExecuteClick}
              disabled={isLoading}
              className="ignara-btn-primary w-full py-2.5 px-3 rounded-[14px] text-xs font-semibold shadow-btn flex items-center justify-center space-x-2 disabled:opacity-50 min-h-[44px]"
            >
              <Send className="w-3.5 h-3.5 shrink-0" />
              <span>Execute in PayPal Sandbox</span>
            </button>
          )}

          {action.state === 'executed' && (
            <div className="w-full py-2.5 px-3 bg-[var(--y)]/15 border border-[var(--y)]/30 text-[var(--y)] rounded-[14px] text-xs font-semibold flex items-center justify-center space-x-2 min-h-[44px]">
              <span className="w-2 h-2 rounded-full bg-[var(--y)] animate-pulse shrink-0"></span>
              <span>Executed: Awaiting Sandbox Settlement</span>
            </div>
          )}

          {action.state === 'confirmed' && (
            <div className="w-full py-2.5 px-3 bg-[var(--g)]/15 border border-[var(--g)]/30 text-[var(--g)] rounded-[14px] text-xs font-semibold flex items-center justify-center space-x-2 min-h-[44px]">
              <CheckCircle2 className="w-4 h-4 text-[var(--g)] shrink-0" />
              <span>Payment Confirmed via Webhook</span>
            </div>
          )}

          {action.state === 'failed' && (
            <div className="w-full py-2.5 px-3 bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] rounded-[14px] text-xs font-semibold text-center min-h-[44px] flex items-center justify-center">
              Failed: {action.error_message || 'Sandbox error'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
