import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from 'recharts';
import { DailyProjection, RescuePlan } from '../types';
import { ShieldCheck, Activity } from 'lucide-react';

interface ForecastChartProps {
  projections: DailyProjection[];
  selectedPlan?: RescuePlan | null;
  obligationDateStr?: string;
  obligationAmount?: number;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({
  projections,
  selectedPlan,
  obligationDateStr,
  obligationAmount,
}) => {
  const [showUncertaintyBand, setShowUncertaintyBand] = useState(true);

  const chartData = projections.map((p, idx) => {
    const planP = selectedPlan?.forecast_with_plan?.[idx];
    const dateFormatted = new Date(p.date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });

    return {
      date: dateFormatted,
      fullDate: p.date,
      baselineBalance: p.ending_balance,
      planBalance: planP ? planP.ending_balance : undefined,
      ciLow: p.ci_low ?? p.ending_balance - 400,
      ciHigh: p.ci_high ?? p.ending_balance + 600,
      ciBand: [p.ci_low ?? p.ending_balance - 400, p.ci_high ?? p.ending_balance + 600],
      inflows: p.inflows,
      outflows: p.outflows,
      isShortfall: p.is_shortfall,
      shortfallAmount: p.shortfall_amount,
    };
  });

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-ink text-white p-3.5 rounded-xl shadow-xl border border-slate-700/80 text-xs backdrop-blur-md">
          <div className="font-bold text-slate-200 border-b border-slate-800 pb-1.5 mb-2 flex items-center justify-between">
            <span>{data.fullDate}</span>
            {data.isShortfall && (
              <span className="bg-rose-500/20 text-rose-300 border border-rose-500/40 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                Shortfall Alert
              </span>
            )}
          </div>

          <div className="space-y-1.5 font-mono">
            <div className="flex justify-between items-center space-x-4">
              <span className="text-sardine-muted font-sans">Baseline:</span>
              <span className={`font-bold ${data.baselineBalance < 0 ? 'text-rose-400' : 'text-slate-100'}`}>
                ${data.baselineBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            </div>

            {data.planBalance !== undefined && (
              <div className="flex justify-between items-center space-x-4 text-electric-300 font-bold">
                <span className="font-sans text-electric-200">With {selectedPlan?.name?.split(':')[0]}:</span>
                <span>${data.planBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              </div>
            )}

            {data.inflows > 0 && (
              <div className="flex justify-between items-center space-x-4 text-emerald-400">
                <span className="font-sans text-slate-400">Inflows:</span>
                <span>+${data.inflows.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              </div>
            )}

            {data.outflows > 0 && (
              <div className="flex justify-between items-center space-x-4 text-rose-300">
                <span className="font-sans text-slate-400">Outflows:</span>
                <span>-${data.outflows.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              </div>
            )}

            {showUncertaintyBand && (
              <div className="flex justify-between items-center space-x-4 text-sardine-muted pt-1 border-t border-slate-800 text-[10px]">
                <span className="font-sans">Monte Carlo 80% CI:</span>
                <span>
                  ${Math.round(data.ciLow)} &rarr; ${Math.round(data.ciHigh)}
                </span>
              </div>
            )}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bento-card p-6 border border-slate-200/90 shadow-bento">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-4 border-b border-slate-100">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="font-extrabold text-base text-ink tracking-tight">Cashflow Forecast Trajectory</h2>
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 bg-electric-50 text-electric-600 rounded-md border border-electric-200/60">
              Stochastic Model
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-0.5">
            Day-by-day projected balance and real-time protection overlay
          </p>
        </div>

        {/* Toggle */}
        <label className="flex items-center space-x-2 cursor-pointer bg-slate-50 hover:bg-slate-100/80 px-2.5 py-1.5 rounded-lg border border-slate-200/80 text-xs transition-colors select-none">
          <input
            type="checkbox"
            checked={showUncertaintyBand}
            onChange={(e) => setShowUncertaintyBand(e.target.checked)}
            className="rounded text-electric focus:ring-electric w-3.5 h-3.5"
          />
          <span className="font-medium text-ink">Monte Carlo Confidence Band</span>
        </label>
      </div>

      {/* Chart */}
      <div className="h-80 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 15, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6b7c99' }} tickLine={false} axisLine={{ stroke: '#CBD5E1' }} />
            <YAxis
              tick={{ fontSize: 11, fill: '#6b7c99' }}
              tickLine={false}
              axisLine={{ stroke: '#CBD5E1' }}
              tickFormatter={(v) => `$${v}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '12px' }} />

            <ReferenceLine y={0} stroke="#CBD5E1" strokeWidth={1.5} />

            {obligationDateStr && (
              <ReferenceLine
                x={new Date(obligationDateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                stroke="#4b5bfc"
                strokeDasharray="4 4"
                label={{
                  value: 'Contractor Due',
                  fill: '#4b5bfc',
                  fontSize: 10,
                  position: 'top',
                  fontWeight: 600,
                }}
              />
            )}

            {showUncertaintyBand && (
              <Area
                type="monotone"
                dataKey="ciBand"
                stroke="none"
                fill="#4b5bfc"
                fillOpacity={0.08}
                name="Confidence Range (10th-90th %ile)"
              />
            )}

            <Line
              type="monotone"
              dataKey="baselineBalance"
              stroke="#081026"
              strokeWidth={2}
              dot={{ r: 3, fill: '#081026' }}
              activeDot={{ r: 5 }}
              name="Baseline Forecast (Without Plan)"
            />

            {selectedPlan && (
              <Line
                type="monotone"
                dataKey="planBalance"
                stroke="#4b5bfc"
                strokeWidth={2.5}
                strokeDasharray="5 5"
                dot={{ r: 3.5, fill: '#4b5bfc' }}
                activeDot={{ r: 6 }}
                name={`With ${selectedPlan.name.split(':')[0]} Overlay`}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex items-center justify-between text-[11px] text-sardine-slate border-t border-slate-100 pt-3">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-ink"></span>
          <span>Baseline drops into negative balance ($1,400 shortfall) on Friday</span>
        </div>
        <div className="flex items-center space-x-1.5 font-medium text-electric">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Active Plan Overlay: {selectedPlan?.name?.split(':')[0] || 'Select Below'}</span>
        </div>
      </div>
    </div>
  );
};
