import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { SimulationPreset, WhatIfComparisonResponse } from '../types';
import { Sliders, AlertTriangle, ArrowRight, TrendingDown, DollarSign, CheckCircle2, RefreshCw, Sparkles, HelpCircle } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';

export const WhatIfPage: React.FC = () => {
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

  const formatCurrency = (val: number) => `$${Math.round(val).toLocaleString()}`;
  const formatDelta = (val: number) => {
    if (val > 0) return `+$${Math.round(val).toLocaleString()}`;
    if (val < 0) return `-$${Math.round(Math.abs(val)).toLocaleString()}`;
    return '$0';
  };

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 space-y-4 sm:space-y-6 w-full overflow-hidden">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 border-b border-slate-200 pb-4 sm:pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-black text-ink tracking-tight font-display">
              What-If Financial Simulation Studio
            </h1>
            <span className="text-[10px] sm:text-xs bg-electric-50 text-electric-700 border border-electric-200 px-2.5 py-0.5 rounded-full font-bold">
              In-Memory Isolated
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-1">
            Simulate delays, emergency shocks, and split agreements without altering live records or executing transactions
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-emerald-50/80 border border-emerald-200 text-emerald-800 px-3 py-1.5 rounded-xl text-xs font-semibold self-start md:self-auto shrink-0">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>Zero Real Transactions Dispatched</span>
        </div>
      </div>

      {/* Preset Selector Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3">
        {presets.map((preset) => {
          const isSelected = activePreset === preset.scenario_type;
          return (
            <button
              key={preset.id}
              onClick={() => runScenario(preset.scenario_type, preset.name)}
              disabled={isLoading}
              className={`p-3 sm:p-3.5 rounded-xl text-left border transition-all min-h-[44px] ${
                isSelected
                  ? 'bg-ink text-white border-slate-800 shadow-md ring-2 ring-electric/40'
                  : 'bg-white text-ink border-slate-200 hover:border-slate-300 shadow-2xs'
              }`}
            >
              <span className={`text-[9px] sm:text-[10px] font-bold uppercase tracking-wider block truncate ${isSelected ? 'text-electric-soft' : 'text-sardine-muted'}`}>
                {preset.impact_hint}
              </span>
              <span className="font-bold text-xs mt-1 block leading-tight truncate">
                {preset.name}
              </span>
            </button>
          );
        })}
      </div>

      {/* Comparison Metrics Grid */}
      {comparison && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <div className="bento-card p-4 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Projected Shortfall</span>
            <div className="flex items-baseline space-x-2">
              <span className="font-mono font-black text-xl text-ink">
                ${comparison.simulated.shortfall_amount.toLocaleString()}
              </span>
              <span className={`text-xs font-bold ${comparison.delta.shortfall_change > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                {formatDelta(comparison.delta.shortfall_change)}
              </span>
            </div>
            <span className="text-[11px] text-sardine-slate block">Baseline: {formatCurrency(comparison.baseline.shortfall_amount)}</span>
          </div>

          <div className="bento-card p-4 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Shortfall Probability</span>
            <div className="flex items-baseline space-x-2">
              <span className="font-mono font-black text-xl text-ink">
                {(comparison.simulated.p_shortfall * 100).toFixed(0)}%
              </span>
              <span className={`text-xs font-bold ${comparison.delta.p_shortfall_change > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                {comparison.delta.p_shortfall_change > 0 ? `+${(comparison.delta.p_shortfall_change * 100).toFixed(0)}%` : `${(comparison.delta.p_shortfall_change * 100).toFixed(0)}%`}
              </span>
            </div>
            <span className="text-[11px] text-sardine-slate block">Baseline: {(comparison.baseline.p_shortfall * 100).toFixed(0)}%</span>
          </div>

          <div className="bento-card p-4 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Min Projected Balance</span>
            <div className="flex items-baseline space-x-2">
              <span className={`font-mono font-black text-xl ${comparison.simulated.min_projected_balance < 0 ? 'text-rose-600' : 'text-ink'}`}>
                ${comparison.simulated.min_projected_balance.toLocaleString()}
              </span>
              <span className={`text-xs font-bold ${comparison.delta.min_balance_change < 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                {formatDelta(comparison.delta.min_balance_change)}
              </span>
            </div>
            <span className="text-[11px] text-sardine-slate block">Baseline: {formatCurrency(comparison.baseline.min_projected_balance)}</span>
          </div>

          <div className="bento-card p-4 space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Additional Cash Needed</span>
            <div className="flex items-baseline space-x-2">
              <span className="font-mono font-black text-xl text-electric">
                ${comparison.delta.additional_capital_needed.toLocaleString()}
              </span>
            </div>
            <span className="text-[11px] text-sardine-slate block">To keep balance non-negative</span>
          </div>
        </div>
      )}

      {/* Interactive Trajectory Chart */}
      <div className="bento-card p-4 sm:p-6 space-y-4 w-full overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="font-black text-sm sm:text-base text-ink tracking-tight">14-Day Trajectory Comparison</h3>
            <p className="text-xs text-sardine-slate">Solid blue is baseline forecast; dotted purple is simulated outcome</p>
          </div>
          {comparison && (
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs w-full sm:max-w-md text-sardine-slate">
              <span className="font-bold text-ink">Scenario Effect: </span>
              {comparison.explanation}
            </div>
          )}
        </div>

        <div className="h-[250px] sm:h-[320px] w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="simGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4b5bfc" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#4b5bfc" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
              <XAxis dataKey="date" stroke="#6b7c99" fontSize={10} tickLine={false} />
              <YAxis stroke="#6b7c99" fontSize={10} tickLine={false} tickFormatter={(v) => `$${v}`} />
              <Tooltip
                formatter={(val: number) => [`$${val.toLocaleString()}`, 'Balance']}
                contentStyle={{ backgroundColor: '#081026', borderColor: '#1E293B', borderRadius: '12px', color: '#fff' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
              <Area type="monotone" dataKey="Baseline" stroke="#4b5bfc" strokeWidth={2.5} fill="url(#simGrad)" />
              <Area type="monotone" dataKey="Simulated" stroke="#9333ea" strokeWidth={2.5} strokeDasharray="4 4" fill="none" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
