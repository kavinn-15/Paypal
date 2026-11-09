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
    simulated: 2,
    confirmed: 3,
    failed: 2,
  };

  const currentIndex = stateIndexMap[action.state] ?? 0;

  return (
    <div className="bento-card p-4 sm:p-6 border border-slate-200/90 shadow-bento space-y-4 w-full overflow-hidden">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            <h2 className="font-extrabold text-sm sm:text-base text-ink tracking-tight">
              Deterministic State Progression
            </h2>
            {action.state === 'simulated' ? (
              <span className="text-[10px] font-bold uppercase tracking-wider bg-purple-50 text-purple-800 border border-purple-300 px-2 py-0.5 rounded-full">
                Simulated Payment (Demo Forecast)
              </span>
            ) : action.state === 'confirmed' ? (
              <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-300 px-2 py-0.5 rounded-full">
                Verified PayPal Confirmed
              </span>
            ) : action.is_simulated ? (
              <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-50 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full">
                Simulated Event
              </span>
            ) : null}
          </div>
          <p className="text-xs text-sardine-slate mt-0.5">
            Enforced 4-state sequence: proposed &rarr; approved &rarr; executed &rarr; confirmed
          </p>
        </div>

        <span className="text-xs font-mono font-bold text-sardine-slate bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200 truncate max-w-full">
          ID: {action.idempotency_key.slice(0, 16)}...
        </span>
      </div>

      {/* Progress Stepper */}
      <div className="relative flex items-center justify-between pt-4 pb-2 px-2">
        <div className="absolute left-4 right-4 top-1/2 -translate-y-1/2 h-0.5 bg-slate-200 z-0"></div>
        <div
          className="absolute left-4 top-1/2 -translate-y-1/2 h-0.5 bg-electric transition-all duration-500 z-0"
          style={{ width: `calc(${(currentIndex / 3) * 100}% - 16px)` }}
        ></div>

        {states.map((step, idx) => {
          const isCompleted = idx < currentIndex || action.state === 'confirmed';
          const isCurrent = idx === currentIndex && action.state !== 'confirmed';
          return (
            <div key={step.id} className="relative z-10 flex flex-col items-center max-w-[70px] sm:max-w-none">
              <div
                className={`w-6 h-6 sm:w-7 sm:h-7 rounded-full flex items-center justify-center font-bold text-xs transition-all shadow-xs ${
                  isCompleted
                    ? 'bg-ink text-white ring-4 ring-slate-100'
                    : isCurrent
                    ? 'bg-electric text-white ring-4 ring-electric-100 animate-pulse'
                    : 'bg-white text-sardine-muted border-2 border-slate-300'
                }`}
              >
                {isCompleted ? <Check className="w-3 h-3 sm:w-3.5 sm:h-3.5 stroke-[3] text-electric-300" /> : idx + 1}
              </div>
              <span
                className={`text-[10px] sm:text-xs mt-1.5 font-bold text-center leading-tight ${
                  isCompleted || isCurrent ? 'text-ink' : 'text-sardine-muted'
                }`}
              >
                {step.label}
              </span>
              <span className="text-[9px] text-sardine-slate hidden md:block text-center">{step.desc}</span>
            </div>
          );
        })}
      </div>

      {/* Footer Details */}
      <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-100 flex flex-col sm:flex-row flex-wrap items-start sm:items-center justify-between text-xs text-sardine-slate gap-2 font-mono">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>Type: <strong className="text-ink">{action.action_type}</strong></span>
          <span>Target: <strong className="text-ink truncate max-w-[150px] inline-block align-bottom">{action.recipient}</strong></span>
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
