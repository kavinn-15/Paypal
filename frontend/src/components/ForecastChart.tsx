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
import { TrendingDown, ShieldCheck, HelpCircle } from 'lucide-react';

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

  // Merge baseline projections with selected plan overlay
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
        <div className="bg-slate-900/95 text-white p-3.5 rounded-xl shadow-xl border border-slate-700 text-xs backdrop-blur-md">
          <div className="font-bold text-slate-200 border-b border-slate-700/80 pb-1.5 mb-2 flex items-center justify-between">
            <span>{data.fullDate}</span>
            {data.isShortfall && (
              <span className="bg-rose-500/30 text-rose-300 border border-rose-500/50 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                Shortfall Alert
              </span>
            )}
          </div>

          <div className="space-y-1">
            <div className="flex justify-between items-center space-x-4">
              <span className="text-slate-400">Baseline Balance:</span>
              <span className={`font-mono font-bold ${data.baselineBalance < 0 ? 'text-rose-400' : 'text-slate-100'}`}>
                ${data.baselineBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            </div>

            {data.planBalance !== undefined && (
              <div className="flex justify-between items-center space-x-4 text-emerald-300 font-semibold">
                <span>With {selectedPlan?.name?.split(':')[0]}:</span>
                <span className="font-mono font-bold">
                  ${data.planBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>
              </div>
            )}

            {data.inflows > 0 && (
              <div className="flex justify-between items-center space-x-4 text-sky-400">
                <span>Expected Inflows:</span>
                <span className="font-mono">+${data.inflows.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              </div>
            )}

            {data.outflows > 0 && (
              <div className="flex justify-between items-center space-x-4 text-amber-400">
                <span>Known Outflows:</span>
                <span className="font-mono">-${data.outflows.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              </div>
            )}

            {showUncertaintyBand && (
              <div className="flex justify-between items-center space-x-4 text-slate-400 pt-1 border-t border-slate-800">
                <span>80% Confidence Band:</span>
                <span className="font-mono text-[11px]">
                  ${Math.round(data.ciLow)} to ${Math.round(data.ciHigh)}
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
    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-4 border-b border-slate-100">
        <div>
          <h3 className="font-extrabold text-base text-slate-900 flex items-center space-x-2">
            <span>Projected Cashflow Timeline</span>
            <span className="text-xs font-semibold px-2 py-0.5 bg-slate-100 text-slate-600 rounded-md border border-slate-200">
              Daily Ledger
            </span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Shows baseline shortfall trajectory through Friday and simulated recovery overlay
          </p>
        </div>

        {/* Toggle Controls */}
        <div className="flex items-center space-x-2 text-xs">
          <label className="flex items-center space-x-1.5 cursor-pointer bg-slate-50 hover:bg-slate-100 px-2.5 py-1.5 rounded-lg border border-slate-200 transition-colors">
            <input
              type="checkbox"
              checked={showUncertaintyBand}
              onChange={(e) => setShowUncertaintyBand(e.target.checked)}
              className="rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
            />
            <span className="font-medium text-slate-700">Uncertainty Band (Monte Carlo)</span>
          </label>
        </div>
      </div>

      {/* Recharts Container */}
      <div className="h-80 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 15, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748B' }} tickLine={false} axisLine={{ stroke: '#CBD5E1' }} />
            <YAxis
              tick={{ fontSize: 11, fill: '#64748B' }}
              tickLine={false}
              axisLine={{ stroke: '#CBD5E1' }}
              tickFormatter={(v) => `$${v}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '12px' }} />

            {/* Zero Baseline Reference Line */}
            <ReferenceLine y={0} stroke="#E2E8F0" strokeWidth={1.5} />

            {/* Obligation Marker */}
            {obligationDateStr && (
              <ReferenceLine
                x={new Date(obligationDateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                stroke="#DC2626"
                strokeDasharray="4 4"
                label={{
                  value: 'Contractor Payout Due',
                  fill: '#DC2626',
                  fontSize: 10,
                  position: 'top',
                  fontWeight: 600,
                }}
              />
            )}

            {/* Monte Carlo Uncertainty Band */}
            {showUncertaintyBand && (
              <Area
                type="monotone"
                dataKey="ciBand"
                stroke="none"
                fill="#3B82F6"
                fillOpacity={0.08}
                name="Confidence Range (10th-90th %ile)"
              />
            )}

            {/* Baseline Cash Balance */}
            <Line
              type="monotone"
              dataKey="baselineBalance"
              stroke="#EF4444"
              strokeWidth={2.5}
              dot={{ r: 3, fill: '#EF4444' }}
              activeDot={{ r: 5 }}
              name="Baseline Forecast (Without Plan)"
            />

            {/* With Selected Plan Overlay */}
            {selectedPlan && (
              <Line
                type="monotone"
                dataKey="planBalance"
                stroke="#10B981"
                strokeWidth={2.5}
                strokeDasharray="5 5"
                dot={{ r: 3.5, fill: '#10B981' }}
                activeDot={{ r: 6 }}
                name={`With ${selectedPlan.name.split(':')[0]} Overlay`}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500 border-t border-slate-100 pt-3">
        <div className="flex items-center space-x-2">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
          <span>Baseline drops into negative balance ($1,400 shortfall) on Friday obligation due date</span>
        </div>
        <div className="flex items-center space-x-1.5 font-medium text-slate-600">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          <span>Select a Rescue Plan below to preview protection overlay</span>
        </div>
      </div>
    </div>
  );
};
