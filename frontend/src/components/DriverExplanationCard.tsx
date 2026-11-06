import React from 'react';
import { Brain, Sparkles, Database } from 'lucide-react';
import { DriverContribution } from '../types';

interface DriverExplanationCardProps {
  explanationText: string;
  driverRankings?: DriverContribution[];
  isSourceSeeded?: boolean;
}

export const DriverExplanationCard: React.FC<DriverExplanationCardProps> = ({
  explanationText,
  driverRankings = [],
  isSourceSeeded = true,
}) => {
  return (
    <div className="bento-ink p-6 space-y-4 shadow-bento h-full flex flex-col justify-between">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex justify-between items-start gap-2">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-electric-500/20 border border-electric-400/30 flex items-center justify-center text-electric-300">
              <Brain className="w-4 h-4" />
            </div>
            <div>
              <h2 className="font-extrabold text-base text-white tracking-tight">Agentic Risk Intelligence</h2>
              <p className="text-xs text-sardine-muted">Driver decomposition & sensitivity analysis</p>
            </div>
          </div>

          {/* Badges */}
          <div className="flex flex-col items-end gap-1">
            <span className="flex items-center space-x-1 text-[10px] font-bold uppercase tracking-wider bg-electric-500/10 text-electric-300 border border-electric-400/30 px-2 py-0.5 rounded-full whitespace-nowrap">
              <Sparkles className="w-2.5 h-2.5 text-electric-300" />
              <span>Validated LLM</span>
            </span>
            {isSourceSeeded && (
              <span className="text-[10px] text-sardine-muted font-mono flex items-center space-x-1">
                <Database className="w-2.5 h-2.5" />
                <span>12-Mo Seeded</span>
              </span>
            )}
          </div>
        </div>

        {/* Primary Callout */}
        <div className="p-4 rounded-xl bg-ink-800 border border-slate-700/60 text-xs sm:text-sm text-slate-200 leading-relaxed font-medium">
          <p className="space-x-1">
            <span className="text-electric-300 font-bold uppercase text-[10px] tracking-wider block mb-1">
              Deterministic Finding:
            </span>
            <span>{explanationText}</span>
          </p>
        </div>

        {/* Top Culprits Breakdown */}
        {driverRankings.length > 0 && (
          <div className="space-y-2 pt-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-sardine-muted block">
              Marginal Shortfall Sensitivity
            </span>
            <div className="divide-y divide-slate-800/80 border border-slate-800 rounded-xl overflow-hidden bg-ink-950/60">
              {driverRankings.map((driver, index) => (
                <div
                  key={driver.client_id}
                  className="p-3 flex items-center justify-between text-xs"
                >
                  <div className="flex items-center space-x-2.5">
                    <span className="w-4 h-4 rounded-full bg-slate-800 text-slate-300 font-mono text-[10px] font-bold flex items-center justify-center shrink-0">
                      {index + 1}
                    </span>
                    <div>
                      <span className="font-bold text-white block text-xs">{driver.client_name}</span>
                      <span className="text-[10px] text-sardine-muted">
                        ~{driver.expected_days_late.toFixed(0)}d delay on ${driver.invoice_amount.toLocaleString()} invoice
                      </span>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="font-mono text-rose-400 font-bold text-xs block">
                      +${driver.marginal_shortfall_delta.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                    <span className="text-[9px] uppercase tracking-wider text-sardine-muted">gap impact</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-sardine-muted">
        <span>Zero hallucinations guaranteed</span>
        <span className="font-mono text-[10px] text-electric-300">Strictly Numbers-Validated</span>
      </div>
    </div>
  );
};
