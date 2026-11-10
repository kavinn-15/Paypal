import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { SimulationPreset, WhatIfComparisonResponse } from '../types';
import { Sliders, AlertTriangle, ArrowRight, TrendingDown, DollarSign, CheckCircle2, RefreshCw, Sparkles, HelpCircle } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';
import { CountUp } from '../components/CountUp';

export const WhatIfPage: React.FC = () => {
  const { formatCurrency, currencySymbol } = useRegionalPreferences();
  const [presets, setPresets] = useState<SimulationPreset[]>([]);
  const [activePreset, setActivePreset] = useState<string>('client_delay_5d');
  const [comparison, setComparison] = useState<WhatIfComparisonResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    api.getSimulationPresets().then((data) => {
      setPresets(data);
      if (data.length > 0) {
        runScenario(data[0].scenario_type, data[0].name);
      }
    });
  }, []);

  const runScenario = async (scenarioType: string, runName: string) => {
    try {
      setIsLoading(true);
      setActivePreset(scenarioType);
      const res = await api.runSimulation({
        run_name: runName,
        scenario_type: scenarioType,
        delay_days: scenarioType === 'client_delay_10d' ? 10 : 5,
        emergency_amount: 500.0,
        contractor_split_pct: 50.0,
      });
      setComparison(res);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  const chartData = comparison
    ? comparison.projections_baseline.map((base, idx) => {
        const sim = comparison.projections_simulated[idx];
        return {
          date: base.date.slice(5),
          Baseline: base.ending_balance,
          Simulated: sim ? sim.ending_balance : base.ending_balance,
        };
      })
    : [];

  const formatDelta = (val: number) => {
    if (val > 0) return `+${formatCurrency(val)}`;
    if (val < 0) return `-${formatCurrency(Math.abs(val))}`;
    return formatCurrency(0);
  };

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-2 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">
              Simulation Studio
            </h1>
            <span className="text-[11px] bg-[var(--card2)] text-[var(--o1)] border border-[var(--o1)]/30 px-2.5 py-0.5 rounded-full font-semibold">
              In-Memory Isolated
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Simulate delays, emergency shocks, and split agreements without altering live records
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-[var(--g)]/15 border border-[var(--g)]/30 text-[var(--g)] px-3 py-1.5 rounded-[999px] text-xs font-semibold self-start md:self-auto shrink-0">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>Zero Live Dispatches</span>
        </div>
      </div>

      {/* Preset Selector Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 ignara-stagger-1">
        {presets.map((preset) => {
          const isSelected = activePreset === preset.scenario_type;
          return (
            <button
              key={preset.id}
              onClick={() => runScenario(preset.scenario_type, preset.name)}
              disabled={isLoading}
              className={`p-3 rounded-[16px] text-left border transition-all min-h-[44px] cursor-pointer ${
                isSelected
                  ? 'border-[var(--o1)] bg-[var(--card)] ring-2 ring-[var(--o1)]/20 shadow-md'
                  : 'bg-[var(--side)] text-[var(--tx)] border-[var(--line)] hover:border-[var(--o1)]/40 hover:bg-[var(--card)]'
              }`}
            >
              <span className={`text-[10px] font-semibold uppercase tracking-wider block truncate ${isSelected ? 'text-[var(--o1)]' : 'text-[var(--dim)]'}`}>
                {preset.impact_hint}
              </span>
              <span className="font-semibold text-xs mt-1 block leading-tight truncate text-[var(--tx)]">
                {preset.name}
              </span>
            </button>
          );
        })}
      </div>

      {/* Comparison Metrics Grid */}
      {comparison && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 ignara-stagger-2">
          <div className="ignara-card p-4 space-y-1 ignara-card-hover">
            <span className="text-[10.5px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Projected Shortfall</span>
            <div className="flex items-baseline space-x-2">
              <span className="ignara-num-big text-xl text-[var(--tx)]">
                <CountUp value={comparison.simulated.shortfall_amount} formatFn={(v) => formatCurrency(v)} />
              </span>
              <span className={`text-xs font-semibold ${comparison.delta.shortfall_change > 0 ? 'text-[var(--r)]' : 'text-[var(--g)]'}`}>
                {formatDelta(comparison.delta.shortfall_change)}
              </span>
            </div>
            <span className="text-[11px] text-[var(--mu)] block">Baseline: {formatCurrency(comparison.baseline.shortfall_amount)}</span>
          </div>

          <div className="ignara-card p-4 space-y-1 ignara-card-hover">
            <span className="text-[10.5px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Shortfall Probability</span>
            <div className="flex items-baseline space-x-2">
              <span className="ignara-num-big text-xl text-[var(--tx)]">
                <CountUp value={comparison.simulated.p_shortfall * 100} prefix="" suffix="%" decimals={0} />
              </span>
              <span className={`text-xs font-semibold ${comparison.delta.p_shortfall_change > 0 ? 'text-[var(--r)]' : 'text-[var(--g)]'}`}>
                {comparison.delta.p_shortfall_change > 0 ? `+${(comparison.delta.p_shortfall_change * 100).toFixed(0)}%` : `${(comparison.delta.p_shortfall_change * 100).toFixed(0)}%`}
              </span>
            </div>
            <span className="text-[11px] text-[var(--mu)] block">Baseline: {(comparison.baseline.p_shortfall * 100).toFixed(0)}%</span>
          </div>

          <div className="ignara-card p-4 space-y-1 ignara-card-hover">
            <span className="text-[10.5px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Min Projected Balance</span>
            <div className="flex items-baseline space-x-2">
              <span className={`ignara-num-big text-xl ${comparison.simulated.min_projected_balance < 0 ? 'text-[var(--r)]' : 'text-[var(--tx)]'}`}>
                <CountUp value={comparison.simulated.min_projected_balance} formatFn={(v) => formatCurrency(v)} />
              </span>
              <span className={`text-xs font-semibold ${comparison.delta.min_balance_change < 0 ? 'text-[var(--r)]' : 'text-[var(--g)]'}`}>
                {formatDelta(comparison.delta.min_balance_change)}
              </span>
            </div>
            <span className="text-[11px] text-[var(--mu)] block">Baseline: {formatCurrency(comparison.baseline.min_projected_balance)}</span>
          </div>

          <div className="ignara-card p-4 space-y-1 ignara-card-hover">
            <span className="text-[10.5px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Additional Cash Needed</span>
            <div className="flex items-baseline space-x-2">
              <span className="ignara-num-big text-xl text-[var(--o1)]">
                <CountUp value={comparison.delta.additional_capital_needed} formatFn={(v) => formatCurrency(v)} />
              </span>
            </div>
            <span className="text-[11px] text-[var(--mu)] block">To maintain positive liquidity</span>
          </div>
        </div>
      )}

      {/* Interactive Trajectory Chart */}
      <div className="ignara-card p-5 sm:p-6 space-y-4 w-full overflow-hidden ignara-stagger-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="ignara-h3">14-Day Trajectory Comparison</h3>
            <p className="text-xs text-[var(--mu)]">Solid line is baseline forecast; dashed line is simulated outcome</p>
          </div>
          {comparison && (
            <div className="p-3 bg-[var(--card2)] border border-[var(--line)] rounded-[14px] text-xs w-full sm:max-w-md text-[var(--mu)]">
              <span className="font-semibold text-[var(--tx)]">Scenario Effect: </span>
              {comparison.explanation}
            </div>
          )}
        </div>

        <div className="h-[250px] sm:h-[320px] w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="simGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--o1)" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="var(--o1)" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--line)" opacity={0.6} />
              <XAxis dataKey="date" stroke="var(--mu)" fontSize={11} tickLine={false} fontFamily="Outfit, sans-serif" />
              <YAxis stroke="var(--mu)" fontSize={11} tickLine={false} tickFormatter={(v) => `${currencySymbol}${v}`} fontFamily="Outfit, sans-serif" />
              <Tooltip
                formatter={(val: number) => [formatCurrency(val), 'Balance']}
                contentStyle={{
                  backgroundColor: 'var(--inv)',
                  borderColor: 'var(--line)',
                  borderRadius: '12px',
                  color: 'var(--invt)',
                  fontSize: '12px',
                  fontFamily: 'Outfit, sans-serif'
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11.5px', paddingTop: '8px', color: 'var(--mu)', fontFamily: 'Outfit, sans-serif' }} />
              <Area type="monotone" dataKey="Baseline" stroke="var(--tx)" strokeWidth={2.5} fill="url(#simGrad)" />
              <Area type="monotone" dataKey="Simulated" stroke="var(--o1)" strokeWidth={2.5} strokeDasharray="4 4" fill="none" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
