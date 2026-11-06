import React from 'react';
import { Brain, Sparkles, TrendingDown, Database, ArrowRight } from 'lucide-react';
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
    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
            <Brain className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-extrabold text-base text-slate-900">Forecast Driver Analysis</h3>
            <p className="text-xs text-slate-500">Why your balance drops before Friday's payout</p>
          </div>
        </div>

        {/* Source Badge */}
        <div className="flex items-center space-x-2">
          {isSourceSeeded && (
            <span className="flex items-center space-x-1 text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200 px-2.5 py-1 rounded-full">
              <Database className="w-3 h-3 text-amber-600" />
              <span>Seeded 12-Mo History</span>
            </span>
          )}
          <span className="flex items-center space-x-1 text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 px-2.5 py-1 rounded-full">
            <Sparkles className="w-3 h-3 text-indigo-500" />
            <span>LLM Reasoning (Validated)</span>
          </span>
        </div>
      </div>

      {/* Primary Plain-Language Explanation Callout */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-slate-50 to-indigo-50/40 border border-slate-200/90 text-sm leading-relaxed text-slate-800 font-medium shadow-xs">
        <p className="flex items-start space-x-2">
          <span className="text-indigo-600 font-bold shrink-0 mt-0.5">Summary:</span>
          <span>{explanationText}</span>
        </p>
      </div>

      {/* Driver Contribution Rankings */}
      {driverRankings.length > 0 && (
        <div className="space-y-2 pt-1">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Marginal Shortfall Impact by Client
          </h4>
          <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
            {driverRankings.map((driver, index) => (
              <div
                key={driver.client_id}
                className="p-3 bg-white hover:bg-slate-50/80 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div className="flex items-center space-x-3">
                  <span className="w-5 h-5 rounded-full bg-slate-100 text-slate-600 font-mono text-xs font-bold flex items-center justify-center shrink-0">
                    {index + 1}
                  </span>
                  <div>
                    <span className="font-bold text-xs text-slate-900 block">{driver.client_name}</span>
                    <span className="text-[11px] text-slate-500">
                      Typically pays <span className="font-semibold text-rose-600">{driver.expected_days_late.toFixed(0)} days late</span> on ${driver.invoice_amount.toLocaleString()} invoice
                    </span>
                  </div>
                </div>

                <div className="flex items-center space-x-3 sm:text-right shrink-0">
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Marginal Gap Impact</span>
                    <span className="text-xs font-extrabold text-rose-700 font-mono">
                      +${driver.marginal_shortfall_delta.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

