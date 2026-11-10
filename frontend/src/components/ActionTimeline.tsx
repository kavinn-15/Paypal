import React from 'react';
import { Action } from '../types';
import { Check } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

interface ActionTimelineProps {
  action?: Action;
}

export const ActionTimeline: React.FC<ActionTimelineProps> = ({ action }) => {
  const { formatCurrency } = useRegionalPreferences();
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
    <div className="ignara-card p-5 sm:p-6 space-y-4 w-full overflow-hidden">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="ignara-h3">Deterministic State Progression</h2>
            {action.state === 'simulated' ? (
              <span className="text-[10px] font-semibold uppercase tracking-wider bg-purple-500/15 text-purple-400 border border-purple-500/30 px-2.5 py-0.5 rounded-full">
                Simulated Payment (Demo Forecast)
              </span>
            ) : action.state === 'confirmed' ? (
              <span className="text-[10px] font-semibold uppercase tracking-wider bg-[var(--g)]/15 text-[var(--g)] border border-[var(--g)]/30 px-2.5 py-0.5 rounded-full">
                Verified PayPal Confirmed
              </span>
            ) : action.is_simulated ? (
              <span className="text-[10px] font-semibold uppercase tracking-wider bg-[var(--y)]/15 text-[var(--y)] border border-[var(--y)]/30 px-2.5 py-0.5 rounded-full">
                Simulated Event
              </span>
            ) : null}
          </div>
          <p className="text-xs text-[var(--mu)] mt-0.5">
            Enforced 4-state sequence: proposed &rarr; approved &rarr; executed &rarr; confirmed
          </p>
        </div>

        <span className="text-xs font-mono font-medium text-[var(--mu)] bg-[var(--side)] px-3 py-1 rounded-[10px] border border-[var(--line)] truncate max-w-full">
          ID: {action.idempotency_key.slice(0, 16)}...
        </span>
      </div>

      {/* Progress Stepper with Ember line */}
      <div className="relative flex items-center justify-between pt-4 pb-2 px-2">
        <div className="absolute left-6 right-6 top-1/2 -translate-y-1/2 h-0.5 bg-[var(--line)] z-0"></div>
        <div
          className="absolute left-6 top-1/2 -translate-y-1/2 h-0.5 bg-[var(--o1)] transition-all duration-500 ease-[var(--ease-ignara)] z-0"
          style={{ width: `calc(${(currentIndex / 3) * 100}% - 24px)` }}
        ></div>

        {states.map((step, idx) => {
          const isCompleted = idx < currentIndex || action.state === 'confirmed';
          const isCurrent = idx === currentIndex && action.state !== 'confirmed';
          return (
            <div key={step.id} className="relative z-10 flex flex-col items-center max-w-[80px] sm:max-w-none">
              <div
                className={`w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center font-semibold text-xs transition-all shadow-xs ${
                  isCompleted
                    ? 'bg-[var(--o1)] text-white ring-4 ring-[var(--o1)]/20'
                    : isCurrent
                    ? 'bg-[var(--o1)] text-white ring-4 ring-[var(--o1)]/30 animate-pulse'
                    : 'bg-[var(--card)] text-[var(--dim)] border-2 border-[var(--line)]'
                }`}
              >
                {isCompleted ? <Check className="w-3.5 h-3.5 stroke-[2.5] text-white" /> : idx + 1}
              </div>
              <span
                className={`text-[11px] sm:text-xs mt-2 font-medium text-center leading-tight ${
                  isCompleted || isCurrent ? 'text-[var(--tx)]' : 'text-[var(--dim)]'
                }`}
              >
                {step.label}
              </span>
              <span className="text-[10px] text-[var(--mu)] hidden md:block text-center mt-0.5">{step.desc}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
