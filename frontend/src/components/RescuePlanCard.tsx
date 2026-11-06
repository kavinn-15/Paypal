import React, { useState } from 'react';
import { RescuePlan } from '../types';
import {
  ShieldAlert,
  CheckCircle2,
  DollarSign,
  ArrowRight,
  Send,
  Percent,
  Split,
  Lock,
  ExternalLink,
  Info,
} from 'lucide-react';

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
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const action = plan.primary_action;

  const planIcons = {
    A: Send,
    B: Percent,
    C: Split,
  };
  const Icon = planIcons[plan.plan_type] || Send;

  const planPills = {
    A: { bg: 'bg-blue-50 text-blue-700 border-blue-200', label: 'Plan A: Zero Concession' },
    B: { bg: 'bg-purple-50 text-purple-700 border-purple-200', label: 'Plan B: Early Concession' },
    C: { bg: 'bg-emerald-50 text-emerald-700 border-emerald-200', label: 'Plan C: Payment Split' },
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
      className={`rounded-2xl p-6 border transition-all cursor-pointer relative flex flex-col justify-between ${
        isSelected
          ? 'bg-white border-blue-600 shadow-md ring-2 ring-blue-600/20'
          : 'bg-white border-slate-200 hover:border-slate-300 shadow-sm'
      }`}
    >
      {/* Top Header */}
      <div>
        <div className="flex justify-between items-start gap-2 mb-3">
          <span
            className={`text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
              planPills[plan.plan_type].bg
            }`}
          >
            {planPills[plan.plan_type].label}
          </span>

          {/* Selection indicator */}
          <span
            className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
              isSelected ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500'
            }`}
          >
            {isSelected ? 'Chart Active' : 'Click to Preview'}
          </span>
        </div>

        <h3 className="font-extrabold text-base text-slate-900 leading-snug">{plan.name}</h3>
        <p className="text-xs text-slate-500 mt-1 leading-relaxed">{plan.description}</p>

        {/* Cost & Incoming Metrics Grid */}
        <div className="grid grid-cols-2 gap-2 my-4 p-3 bg-slate-50 rounded-xl border border-slate-100">
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">Plan Cost</span>
            <span
              className={`text-sm font-extrabold font-mono ${
                plan.cost === 0 ? 'text-emerald-700' : 'text-purple-700'
              }`}
            >
              ${plan.cost.toFixed(2)}
            </span>
            <span className="text-[10px] text-slate-500 block truncate">{plan.cost_description}</span>
          </div>

          <div className="border-l border-slate-200 pl-3">
            <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">Incoming Needed</span>
            <span className="text-sm font-extrabold font-mono text-slate-800">
              ${plan.incoming_needed.toFixed(2)}
            </span>
            <span className="text-[10px] text-slate-500 block truncate">
              {plan.incoming_needed === 0 ? 'Fully covered on Friday' : 'Required to bridge gap'}
            </span>
          </div>
        </div>

        {/* Rationale & Target Candidate */}
        <div className="text-xs text-slate-600 space-y-1.5 my-3">
          <span className="font-bold text-slate-800 block text-[11px] uppercase tracking-wider">Strategy Rationale:</span>
          <p className="bg-slate-50/80 p-2.5 rounded-lg border border-slate-200/60 leading-relaxed text-[11px]">
            {plan.rationale}
          </p>
        </div>

        {/* Remaining Risk Alert (Strictly using 'plausibly protects') */}
        <div className="p-3 bg-amber-50/60 rounded-xl border border-amber-200/80 my-3 text-[11px] leading-relaxed text-amber-900">
          <span className="font-bold block text-amber-950 flex items-center space-x-1">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span>Remaining Risk Profile:</span>
          </span>
          <p className="mt-1">{plan.remaining_risk}</p>
        </div>
      </div>

      {/* Action Execution Footer & Exact Parameters Bound */}
      <div className="pt-4 border-t border-slate-100 mt-2 space-y-3">
        {/* Bound Parameters Box */}
        <div className="bg-slate-900 text-slate-200 p-3 rounded-xl text-[11px] font-mono space-y-1 border border-slate-800">
          <div className="flex justify-between text-slate-400 text-[10px] border-b border-slate-800 pb-1 mb-1">
            <span className="flex items-center space-x-1">
              <Lock className="w-2.5 h-2.5 text-blue-400" />
              <span>HMAC Bound Parameters</span>
            </span>
            <span className="text-[9px] text-slate-500 truncate max-w-[120px]">
              Sig: {action.approval_hash.slice(0, 10)}...
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Action:</span>
            <span className="text-sky-300 font-bold">{action.action_type}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Recipient:</span>
            <span className="text-white truncate max-w-[140px]">{action.recipient}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Amount:</span>
            <span className="text-emerald-400 font-bold">${action.amount.toFixed(2)} USD</span>
          </div>
        </div>

        {/* Dynamic State Transition Button */}
        <div>
          {action.state === 'proposed' && (
            <button
              onClick={handleApproveClick}
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl transition-all shadow-sm hover:shadow flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Approve Exact Action ({action.recipient.split(' ')[0]} - ${action.amount.toFixed(0)})</span>
            </button>
          )}

          {action.state === 'approved' && (
            <button
              onClick={handleExecuteClick}
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl transition-all shadow-sm hover:shadow flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Execute in PayPal Sandbox</span>
            </button>
          )}

          {action.state === 'executed' && (
            <div className="w-full py-2 px-3 bg-amber-50 border border-amber-300 text-amber-800 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
              <span>Executed: Awaiting Client Settlement</span>
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
