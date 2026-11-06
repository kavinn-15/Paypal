import React from 'react';
import { Action } from '../types';
import { Check, Clock, AlertCircle, Sparkles, Shield, Send } from 'lucide-react';

interface ActionTimelineProps {
  action?: Action;
}

export const ActionTimeline: React.FC<ActionTimelineProps> = ({ action }) => {
  if (!action) return null;

  const states = [
    { id: 'proposed', label: '1. Proposed', desc: 'Engine generated rescue plan' },
    { id: 'approved', label: '2. Approved', desc: 'Owner signed HMAC approval' },
    { id: 'executed', label: '3. Executed', desc: 'Dispatched to PayPal Sandbox' },
    { id: 'confirmed', label: '4. Confirmed', desc: 'Verified sandbox webhook' },
  ];

  const stateIndexMap: Record<string, number> = {
    proposed: 0,
    approved: 1,
    executed: 2,
    confirmed: 3,
    failed: 2,
  };

  const currentIndex = stateIndexMap[action.state] ?? 0;

  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h4 className="font-extrabold text-sm text-slate-900 flex items-center space-x-2">
            <span>Guardrail Action Lifecycle</span>
            {action.is_simulated && (
              <span className="text-[10px] font-bold uppercase bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full">
                Simulated Event
              </span>
            )}
          </h4>
          <p className="text-xs text-slate-500">
            Enforced 4-state sequence: proposed &rarr; approved &rarr; executed &rarr; confirmed
          </p>
        </div>

        <div className="text-right">
          <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200">
            ID: {action.idempotency_key.slice(0, 16)}...
          </span>
        </div>
      </div>

      {/* Progress Stepper */}
      <div className="relative flex items-center justify-between mt-2">
        <div className="absolute left-0 top-1/2 -translate-y-1/2 h-1 bg-slate-100 w-full z-0"></div>
        <div
          className="absolute left-0 top-1/2 -translate-y-1/2 h-1 bg-blue-600 transition-all duration-500 z-0"
          style={{ width: `${(currentIndex / 3) * 100}%` }}
        ></div>

        {states.map((step, idx) => {
          const isCompleted = idx < currentIndex || action.state === 'confirmed';
          const isCurrent = idx === currentIndex && action.state !== 'confirmed';
          return (
            <div key={step.id} className="relative z-10 flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs transition-all shadow-sm ${
                  isCompleted
                    ? 'bg-blue-600 text-white ring-4 ring-blue-100'
                    : isCurrent
                    ? 'bg-blue-700 text-white ring-4 ring-blue-200 animate-pulse'
                    : 'bg-white text-slate-400 border-2 border-slate-300'
                }`}
              >
                {isCompleted ? <Check className="w-4 h-4 stroke-[3]" /> : idx + 1}
              </div>
              <span
                className={`text-xs mt-2 font-bold ${
                  isCompleted || isCurrent ? 'text-slate-900' : 'text-slate-400'
                }`}
              >
                {step.label}
              </span>
              <span className="text-[10px] text-slate-500 hidden sm:block">{step.desc}</span>
            </div>
          );
        })}
      </div>

      {/* Meta details footer */}
      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-wrap items-center justify-between text-xs text-slate-600 gap-2">
        <div className="flex items-center space-x-3">
          <span>
            <strong className="text-slate-700">Type:</strong> {action.action_type}
          </span>
          <span>
            <strong className="text-slate-700">Recipient:</strong> {action.recipient}
          </span>
          <span>
            <strong className="text-slate-700">Amount:</strong> ${action.amount.toFixed(2)} USD
          </span>
        </div>

        {action.paypal_ref && (
          <div className="text-[11px] font-mono text-slate-500">
            <strong>PayPal Ref:</strong> {action.paypal_ref}
          </div>
        )}
      </div>
    </div>
  );
};

