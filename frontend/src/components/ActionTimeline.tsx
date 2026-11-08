import React from 'react';
import { Action } from '../types';
import { Check } from 'lucide-react';

interface ActionTimelineProps {
  action?: Action;
}

export const ActionTimeline: React.FC<ActionTimelineProps> = ({ action }) => {
  if (!action) return null;

  const states = [
    { id: 'proposed', label: '1. Proposed', desc: 'Deterministic engine generation' },
    { id: 'approved', label: '2. Approved', desc: 'Owner HMAC signature' },
    { id: 'executed', label: '3. Executed', desc: 'PayPal Sandbox dispatched' },
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
    <div className="bento-card p-6 border border-slate-200/90 shadow-bento space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="font-extrabold text-sm text-ink tracking-tight">Deterministic State Progression</h2>
            {action.is_simulated && (
              <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-50 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full">
                Simulated Event
              </span>
            )}
          </div>
          <p className="text-xs text-sardine-slate">
            Enforced 4-state sequence: proposed &rarr; approved &rarr; executed &rarr; confirmed
          </p>
        </div>

        <span className="text-xs font-mono font-bold text-sardine-slate bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200">
          ID: {action.idempotency_key.slice(0, 16)}...
        </span>
      </div>

      {/* Progress Stepper */}
      <div className="relative flex items-center justify-between pt-2">
        <div className="absolute left-0 top-1/2 -translate-y-1/2 h-0.5 bg-slate-200 w-full z-0"></div>
        <div
          className="absolute left-0 top-1/2 -translate-y-1/2 h-0.5 bg-electric transition-all duration-500 z-0"
          style={{ width: `${(currentIndex / 3) * 100}%` }}
        ></div>

        {states.map((step, idx) => {
          const isCompleted = idx < currentIndex || action.state === 'confirmed';
          const isCurrent = idx === currentIndex && action.state !== 'confirmed';
          return (
            <div key={step.id} className="relative z-10 flex flex-col items-center">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs transition-all shadow-xs ${
                  isCompleted
                    ? 'bg-ink text-white ring-4 ring-slate-100'
                    : isCurrent
                    ? 'bg-electric text-white ring-4 ring-electric-100 animate-pulse'
                    : 'bg-white text-sardine-muted border-2 border-slate-300'
                }`}
              >
                {isCompleted ? <Check className="w-3.5 h-3.5 stroke-[3] text-electric-300" /> : idx + 1}
              </div>
              <span
                className={`text-xs mt-2 font-bold ${
                  isCompleted || isCurrent ? 'text-ink' : 'text-sardine-muted'
                }`}
              >
                {step.label}
              </span>
              <span className="text-[10px] text-sardine-slate hidden sm:block">{step.desc}</span>
            </div>
          );
        })}
      </div>

      {/* Footer Details */}
      <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-100 flex flex-wrap items-center justify-between text-xs text-sardine-slate gap-2 font-mono">
        <div className="flex items-center space-x-3">
          <span>Type: <strong className="text-ink">{action.action_type}</strong></span>
          <span>Target: <strong className="text-ink">{action.recipient}</strong></span>
          <span>Amount: <strong className="text-ink">${action.amount.toFixed(2)} USD</strong></span>
        </div>

        {action.paypal_ref && (
          <div className="text-[11px] text-sardine-slate">
            PayPal Ref: <span className="text-ink font-semibold">{action.paypal_ref}</span>
          </div>
        )}
      </div>
    </div>
  );
};
