import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { TimelineEntry, FinancialSummaryResponse } from '../types';
import { Clock, ArrowDownLeft, ArrowUpRight, DollarSign, Shield, CheckCircle2, Calendar, FileText } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';
import { CountUp } from '../components/CountUp';

export const TimelinePage: React.FC = () => {
  const { formatCurrency, currencySymbol } = useRegionalPreferences();
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
        return 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30';
      case 'expected':
        return 'bg-[var(--o1)]/15 text-[var(--o1)] border-[var(--o1)]/30';
      case 'estimated':
        return 'bg-purple-500/15 text-purple-400 border-purple-500/30';
      case 'simulated':
        return 'bg-[var(--y)]/15 text-[var(--y)] border-[var(--y)]/30';
      default:
        return 'bg-[var(--card2)] text-[var(--mu)] border-[var(--line)]';
    }
  };

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-2 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">
              Financial Timeline
            </h1>
            <span className="text-[11px] bg-[var(--card2)] text-[var(--mu)] border border-[var(--line)] px-2.5 py-0.5 rounded-full font-semibold">
              Cashflow Chronology
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Verified incoming and outgoing cash flows. Never conflates expected income with confirmed balance.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs self-start md:self-auto">
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 bg-[var(--g)]/15 text-[var(--g)] rounded-full font-semibold border border-[var(--g)]/30">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--g)]"></span>
            <span>Confirmed</span>
          </span>
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 bg-[var(--o1)]/15 text-[var(--o1)] rounded-full font-semibold border border-[var(--o1)]/30">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--o1)]"></span>
            <span>Expected</span>
          </span>
        </div>
      </div>

      {/* Authoritative Position Cards */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 ignara-stagger-1">
          <div className="ignara-card p-4 sm:p-5 space-y-1 ignara-card-hover">
            <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Confirmed Available Cash</span>
            <span className="ignara-num-big text-xl sm:text-2xl text-[var(--tx)] block">
              <CountUp value={summary.current_confirmed_balance} formatFn={(v) => formatCurrency(v)} />
            </span>
            <span className="text-[11px] text-[var(--g)] font-medium block">Authoritative Liquid Balance</span>
          </div>

          <div className="ignara-card p-4 sm:p-5 space-y-1 ignara-card-hover">
            <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Expected Inflows (30d)</span>
            <span className="ignara-num-big text-xl sm:text-2xl text-[var(--g)] block">
              +<CountUp value={summary.expected_inflows_30d} formatFn={(v) => formatCurrency(v)} />
            </span>
            <span className="text-[11px] text-[var(--mu)] block">{summary.expected_inflows_count} pending receivables</span>
          </div>

          <div className="ignara-card p-4 sm:p-5 space-y-1 ignara-card-hover">
            <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Expected Outflows (30d)</span>
            <span className="ignara-num-big text-xl sm:text-2xl text-[var(--r)] block">
              -<CountUp value={summary.expected_outflows_30d} formatFn={(v) => formatCurrency(v)} />
            </span>
            <span className="text-[11px] text-[var(--mu)] block">{summary.pending_obligations_count} commitments</span>
          </div>

          <div className="ignara-card p-4 sm:p-5 space-y-1 ignara-card-hover">
            <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Emergency Reserve Ratio</span>
            <span className="ignara-num-big text-xl sm:text-2xl text-[var(--tx)] block">
              <CountUp value={summary.reserve_coverage_ratio * 100} prefix="" suffix="%" decimals={0} />
            </span>
            <span className="text-[11px] text-[var(--mu)] block">Target: {formatCurrency(summary.emergency_reserve_target)}</span>
          </div>
        </div>
      )}

      {/* Chronological Table (Desktop: Full Table, Mobile: Responsive Card List) */}
      <div className="ignara-card p-0 overflow-hidden ignara-stagger-2">
        {/* Mobile View: Cards on screens < md */}
        <div className="block md:hidden divide-y divide-[var(--line)]">
          {timeline.map((item) => (
            <div key={item.id} className="p-4 space-y-2.5 hover:bg-[var(--card2)] transition-colors">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center space-x-2">
                  {item.direction === 'inflow' ? (
                    <ArrowDownLeft className="w-4 h-4 text-[var(--g)] shrink-0" />
                  ) : (
                    <ArrowUpRight className="w-4 h-4 text-[var(--r)] shrink-0" />
                  )}
                  <span className="font-semibold text-xs text-[var(--tx)]">{item.title}</span>
                </div>
                <span className={`font-mono font-semibold text-sm shrink-0 ${
                  item.direction === 'inflow' ? 'text-[var(--g)]' : 'text-[var(--tx)]'
                }`}>
                  {item.direction === 'inflow' ? '+' : '-'}{formatCurrency(item.amount, { currency: item.currency })}
                </span>
              </div>

              <div className="flex flex-wrap items-center justify-between text-[11px] text-[var(--mu)] gap-2 pt-1 border-t border-[var(--line)]/50">
                <div className="flex items-center space-x-2">
                  <span className="font-mono">{item.date}</span>
                  <span>&bull;</span>
                  <span className="capitalize">{item.category.replace('_', ' ')}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-0.5 rounded-[6px] text-[10px] font-semibold uppercase border ${getStatusBadge(item.status)}`}>
                    {item.status}
                  </span>
                  {item.reference_id && (
                    <span className="font-mono text-[10px] text-[var(--dim)] truncate max-w-[100px]">
                      #{item.reference_id}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop View: Full Table with Ignara Table Style on screens >= md */}
        <div className="hidden md:block responsive-table-container">
          <table className="ignara-table text-left text-xs">
            <thead className="bg-[var(--side)] text-[var(--dim)] font-semibold uppercase tracking-wider text-[10.5px]">
              <tr>
                <th className="px-5 py-3.5">Date</th>
                <th className="px-5 py-3.5">Flow Description</th>
                <th className="px-5 py-3.5">Category</th>
                <th className="px-5 py-3.5">Status Tier</th>
                <th className="px-5 py-3.5 text-right">Amount</th>
                <th className="px-5 py-3.5">Source Ref</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)] font-sans text-xs">
              {timeline.map((item) => (
                <tr key={item.id} className="hover:bg-[var(--card2)] transition-colors">
                  <td className="px-5 py-3.5 font-mono text-[var(--mu)] whitespace-nowrap">{item.date}</td>
                  <td className="px-5 py-3.5 font-semibold text-[var(--tx)] flex items-center space-x-2">
                    {item.direction === 'inflow' ? (
                      <ArrowDownLeft className="w-4 h-4 text-[var(--g)] shrink-0" />
                    ) : (
                      <ArrowUpRight className="w-4 h-4 text-[var(--r)] shrink-0" />
                    )}
                    <span>{item.title}</span>
                  </td>
                  <td className="px-5 py-3.5 text-[var(--mu)] capitalize">
                    {item.category.replace('_', ' ')}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`px-2.5 py-0.5 rounded-[8px] text-[10.5px] font-semibold uppercase border ${getStatusBadge(item.status)}`}>
                      {item.status}
                    </span>
                  </td>
                  <td className={`px-5 py-3.5 font-mono font-semibold text-sm text-right whitespace-nowrap ${
                    item.direction === 'inflow' ? 'text-[var(--g)]' : 'text-[var(--tx)]'
                  }`}>
                    {item.direction === 'inflow' ? '+' : '-'}{formatCurrency(item.amount, { currency: item.currency })}
                  </td>
                  <td className="px-5 py-3.5 font-mono text-[11px] text-[var(--dim)] truncate max-w-[140px]">
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
