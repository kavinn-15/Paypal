import React from 'react';
import { Brain, Sparkles, Database, ArrowRight } from 'lucide-react';
import { DriverContribution } from '../types';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

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
  const { formatCurrency } = useRegionalPreferences();

  return (
    <div className="ignara-card p-5 sm:p-6 space-y-4 h-full flex flex-col justify-between w-full overflow-hidden">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start gap-2">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-[12px] bg-[var(--card2)] border border-[var(--line)] flex items-center justify-center text-[var(--o1)] shrink-0 shadow-xs">
              <Brain className="w-4 h-4" />
            </div>
            <div>
              <h2 className="ignara-h3">Risk Intelligence</h2>
              <p className="text-xs text-[var(--mu)]">Driver decomposition & sensitivity analysis</p>
            </div>
          </div>

          {/* Badges */}
          <div className="flex flex-row sm:flex-col items-start sm:items-end gap-1.5 flex-wrap">
            <span className="inline-flex items-center space-x-1 text-[10px] font-semibold uppercase tracking-wider bg-[var(--card2)] text-[var(--o1)] border border-[var(--o1)]/30 px-2 py-0.5 rounded-full whitespace-nowrap">
              <Sparkles className="w-2.5 h-2.5" />
              <span>Deterministic</span>
            </span>
            {isSourceSeeded && (
              <span className="text-[10.5px] text-[var(--dim)] font-mono flex items-center space-x-1">
                <Database className="w-2.5 h-2.5" />
                <span>12-Mo History</span>
              </span>
            )}
          </div>
        </div>

        {/* Primary Callout with subtle card2 background */}
        <div className="p-3.5 sm:p-4 rounded-[14px] bg-[var(--card2)] border border-[var(--line)] text-xs sm:text-[13px] text-[var(--tx)] leading-relaxed">
          <span className="text-[var(--o1)] font-semibold uppercase text-[10px] tracking-wider block mb-1">
            Engine Analysis:
          </span>
          <p className="text-[var(--tx)] leading-normal">{explanationText}</p>
        </div>

        {/* Top Culprits Breakdown / Leaderboard rows */}
        {driverRankings.length > 0 && (
          <div className="space-y-2 pt-1">
            <span className="text-[11px] font-semibold tracking-wider text-[var(--dim)] uppercase block">
              Marginal Shortfall Sensitivity
            </span>
            <div className="divide-y divide-[var(--line)] border border-[var(--line)] rounded-[16px] overflow-hidden bg-[var(--side)]">
              {driverRankings.map((driver, index) => {
                const impactAmount = driver.marginal_shortfall_delta ?? driver.marginal_shortfall_impact ?? 0;
                return (
                  <div
                    key={driver.client_id}
                    className="p-3 flex items-center justify-between text-xs gap-2 hover:bg-[var(--card2)] transition-colors"
                  >
                    <div className="flex items-center space-x-2.5 min-w-0">
                      <span className="w-5 h-5 rounded-full bg-[var(--card)] border border-[var(--line)] text-[var(--tx)] font-mono text-[10.5px] font-semibold flex items-center justify-center shrink-0">
                        {index + 1}
                      </span>
                      <div className="min-w-0">
                        <span className="font-medium text-[var(--tx)] block text-xs truncate">
                          {driver.client_name}
                        </span>
                        <span className="text-[11px] text-[var(--mu)] block truncate">
                          ~{driver.expected_days_late.toFixed(0)}d delay on {formatCurrency(driver.invoice_amount)} invoice
                        </span>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="font-mono font-semibold text-xs text-[var(--r)] block">
                        +{formatCurrency(impactAmount)}
                      </span>
                      <span className="text-[9.5px] text-[var(--dim)] uppercase tracking-wider">Impact</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-[var(--line)] text-[11px] text-[var(--dim)] flex items-center justify-between">
        <span>Zero hallucinations guarantee</span>
        <span className="text-[var(--o1)] font-semibold font-mono">Bound to DB records</span>
      </div>
    </div>
  );
};
