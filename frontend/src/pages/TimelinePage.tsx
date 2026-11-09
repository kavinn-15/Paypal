import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { TimelineEntry, FinancialSummaryResponse } from '../types';
import { Clock, ArrowDownLeft, ArrowUpRight, DollarSign, Shield, CheckCircle2, Calendar, FileText } from 'lucide-react';

export const TimelinePage: React.FC = () => {
  const [summary, setSummary] = useState<FinancialSummaryResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getFinancialSummary(), api.getFinancialTimeline()])
      .then(([sum, tl]) => {
        setSummary(sum);
        setTimeline(tl);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'confirmed':
        return 'bg-emerald-50 text-emerald-800 border-emerald-200';
      case 'expected':
        return 'bg-electric-50 text-electric-700 border-electric-200';
      case 'estimated':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'simulated':
        return 'bg-amber-50 text-amber-800 border-amber-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 space-y-4 sm:space-y-6 w-full overflow-hidden">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 border-b border-slate-200 pb-4 sm:pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-black text-ink tracking-tight font-display">
              Intelligent Financial Timeline
            </h1>
            <span className="text-[10px] sm:text-xs bg-slate-100 text-sardine-slate border border-slate-200 px-2.5 py-0.5 rounded-full font-bold">
              Cashflow Chronology
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-1">
            Verified incoming and outgoing cash flows. Never conflates expected income with confirmed balance.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs self-start md:self-auto">
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-emerald-50 text-emerald-800 rounded-full font-bold border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span>Confirmed</span>
          </span>
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-electric-50 text-electric-700 rounded-full font-bold border border-electric-200">
            <span className="w-1.5 h-1.5 rounded-full bg-electric"></span>
            <span>Expected</span>
          </span>
        </div>
      </div>

      {/* Authoritative Position Cards */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <div className="bento-card p-4 sm:p-5 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Confirmed Available Cash</span>
            <span className="font-mono font-black text-xl sm:text-2xl text-ink block">
              ${summary.current_confirmed_balance.toLocaleString()} {summary.currency}
            </span>
            <span className="text-[11px] text-emerald-700 font-semibold block">Authoritative Liquid Balance</span>
          </div>

          <div className="bento-card p-4 sm:p-5 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Expected Inflows (30d)</span>
            <span className="font-mono font-black text-xl sm:text-2xl text-emerald-600 block">
              +${summary.expected_inflows_30d.toLocaleString()} {summary.currency}
            </span>
            <span className="text-[11px] text-sardine-slate block">{summary.expected_inflows_count} pending receivables</span>
          </div>

          <div className="bento-card p-4 sm:p-5 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Expected Outflows (30d)</span>
            <span className="font-mono font-black text-xl sm:text-2xl text-rose-600 block">
              -${summary.expected_outflows_30d.toLocaleString()} {summary.currency}
            </span>
            <span className="text-[11px] text-sardine-slate block">{summary.pending_obligations_count} commitments</span>
          </div>

          <div className="bento-card p-4 sm:p-5 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Emergency Reserve Ratio</span>
            <span className="font-mono font-black text-xl sm:text-2xl text-ink block">
              {(summary.reserve_coverage_ratio * 100).toFixed(0)}%
            </span>
            <span className="text-[11px] text-sardine-slate block">Target: ${summary.emergency_reserve_target.toLocaleString()}</span>
          </div>
        </div>
      )}

      {/* Chronological Table (Desktop: Full Table, Mobile: Responsive Card List) */}
      <div className="bento-card overflow-hidden shadow-xs">
        {/* Mobile View: Cards on screens < md */}
        <div className="block md:hidden divide-y divide-slate-100">
          {timeline.map((item) => (
            <div key={item.id} className="p-4 space-y-2.5">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center space-x-2">
                  {item.direction === 'inflow' ? (
                    <ArrowDownLeft className="w-4 h-4 text-emerald-600 shrink-0" />
                  ) : (
                    <ArrowUpRight className="w-4 h-4 text-rose-600 shrink-0" />
                  )}
                  <span className="font-bold text-xs text-ink">{item.title}</span>
                </div>
                <span className={`font-mono font-black text-sm shrink-0 ${
                  item.direction === 'inflow' ? 'text-emerald-700' : 'text-slate-900'
                }`}>
                  {item.direction === 'inflow' ? '+' : '-'}${item.amount.toLocaleString()} {item.currency}
                </span>
              </div>

              <div className="flex flex-wrap items-center justify-between text-[11px] text-sardine-slate gap-2 pt-1 border-t border-slate-50">
                <div className="flex items-center space-x-2">
                  <span className="font-mono">{item.date}</span>
                  <span>&bull;</span>
                  <span className="capitalize">{item.category.replace('_', ' ')}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getStatusBadge(item.status)}`}>
                    {item.status}
                  </span>
                  {item.reference_id && (
                    <span className="font-mono text-[10px] text-sardine-muted truncate max-w-[100px]">
                      #{item.reference_id}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop View: Full Table on screens >= md */}
        <div className="hidden md:block responsive-table-container">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50/80 text-sardine-slate font-bold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-5 py-3.5">Date</th>
                <th className="px-5 py-3.5">Flow Description</th>
                <th className="px-5 py-3.5">Category</th>
                <th className="px-5 py-3.5">Status Tier</th>
                <th className="px-5 py-3.5 text-right">Amount</th>
                <th className="px-5 py-3.5">Source Ref</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans text-xs">
              {timeline.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="px-5 py-3.5 font-mono text-sardine-slate whitespace-nowrap">{item.date}</td>
                  <td className="px-5 py-3.5 font-bold text-ink flex items-center space-x-2">
                    {item.direction === 'inflow' ? (
                      <ArrowDownLeft className="w-4 h-4 text-emerald-600 shrink-0" />
                    ) : (
                      <ArrowUpRight className="w-4 h-4 text-rose-600 shrink-0" />
                    )}
                    <span>{item.title}</span>
                  </td>
                  <td className="px-5 py-3.5 text-sardine-slate capitalize">
                    {item.category.replace('_', ' ')}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase border ${getStatusBadge(item.status)}`}>
                      {item.status}
                    </span>
                  </td>
                  <td className={`px-5 py-3.5 font-mono font-black text-sm text-right whitespace-nowrap ${
                    item.direction === 'inflow' ? 'text-emerald-700' : 'text-slate-900'
                  }`}>
                    {item.direction === 'inflow' ? '+' : '-'}${item.amount.toLocaleString()} {item.currency}
                  </td>
                  <td className="px-5 py-3.5 font-mono text-[11px] text-sardine-muted truncate max-w-[140px]">
                    {item.reference_id || item.data_source}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
