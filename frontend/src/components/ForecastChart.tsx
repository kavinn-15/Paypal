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
import { ShieldCheck, TrendingDown, Layers } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

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
  const { formatCurrency, convertAmount } = useRegionalPreferences();

  const chartData = projections.map((p, idx) => {
    const planP = selectedPlan?.forecast_with_plan?.[idx];
    const dateFormatted = new Date(p.date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });

    const baselineBalance = convertAmount(p.ending_balance);
    const planBalance = planP ? convertAmount(planP.ending_balance) : undefined;
    const rawCiLow = p.ci_low ?? p.ending_balance - 400;
    const rawCiHigh = p.ci_high ?? p.ending_balance + 600;
    const ciLow = convertAmount(rawCiLow);
    const ciHigh = convertAmount(rawCiHigh);

    return {
      date: dateFormatted,
      fullDate: p.date,
      baselineBalance,
      planBalance,
      ciLow,
      ciHigh,
      ciBand: [ciLow, ciHigh],
      inflows: convertAmount(p.inflows),
      outflows: convertAmount(p.outflows),
      isShortfall: p.is_shortfall,
      shortfallAmount: convertAmount(p.shortfall_amount),
    };
  });

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="p-3.5 rounded-[14px] bg-[var(--inv)] text-[var(--invt)] shadow-2xl border border-[var(--line)] text-xs backdrop-blur-md max-w-[280px]">
          <div className="font-semibold pb-1.5 mb-2 border-b border-black/10 flex items-center justify-between">
            <span>{data.fullDate}</span>
            {data.isShortfall && (
              <span className="bg-[var(--r)]/20 text-[var(--r)] px-1.5 py-0.5 rounded-[6px] text-[10px] font-bold">
                Deficit Risk
              </span>
            )}
          </div>

          <div className="space-y-1.5 font-mono text-[11.5px]">
            <div className="flex justify-between items-center space-x-3">
              <span className="font-sans text-[var(--mu)]">Baseline Balance:</span>
              <span className={`font-semibold ${data.baselineBalance < 0 ? 'text-[var(--r)]' : ''}`}>
                {formatCurrency(data.baselineBalance, { noConvert: true })}
              </span>
            </div>

            {data.planBalance !== undefined && (
              <div className="flex justify-between items-center space-x-3 text-[var(--o1)] font-semibold">
                <span className="font-sans">With Plan:</span>
                <span>{formatCurrency(data.planBalance, { noConvert: true })}</span>
              </div>
            )}

            {data.inflows > 0 && (
              <div className="flex justify-between items-center space-x-3 text-[var(--g)]">
                <span className="font-sans text-[var(--mu)]">Inflows:</span>
                <span>+{formatCurrency(data.inflows, { noConvert: true })}</span>
              </div>
            )}

            {data.outflows > 0 && (
              <div className="flex justify-between items-center space-x-3 text-[var(--r)]">
                <span className="font-sans text-[var(--mu)]">Outflows:</span>
                <span>-{formatCurrency(data.outflows, { noConvert: true })}</span>
              </div>
            )}

            {showUncertaintyBand && (
              <div className="flex justify-between items-center space-x-3 pt-1 border-t border-black/10 text-[10.5px] text-[var(--dim)]">
                <span className="font-sans">Monte Carlo 80% CI:</span>
                <span>
                  {formatCurrency(Math.round(data.ciLow), { noConvert: true })} &rarr; {formatCurrency(Math.round(data.ciHigh), { noConvert: true })}
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
    <div className="ignara-card p-5 sm:p-6 w-full overflow-hidden flex flex-col justify-between">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-4 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="ignara-h3">Cashflow Trajectory</h2>
            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-[999px] bg-[var(--card2)] text-[var(--o1)] border border-[var(--o1)]/30">
              Stochastic Model
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-0.5">
            Day-by-day projected balance and real-time mitigation overlay
          </p>
        </div>

        {/* Toggle */}
        <label className="flex items-center space-x-2 cursor-pointer bg-[var(--side)] hover:bg-[var(--card2)] px-3 py-1.5 rounded-[999px] border border-[var(--line)] text-xs transition-colors select-none">
          <input
            type="checkbox"
            checked={showUncertaintyBand}
            onChange={(e) => setShowUncertaintyBand(e.target.checked)}
            className="rounded text-[var(--o1)] focus:ring-[var(--o1)] w-3.5 h-3.5"
          />
          <span className="font-medium text-[var(--tx)]">Monte Carlo Band</span>
        </label>
      </div>

      {/* Responsive Chart Container */}
      <div className="h-64 sm:h-80 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 15, right: 10, left: -10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} opacity={0.6} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: 'var(--mu)', fontFamily: 'Outfit, sans-serif' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--line)' }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--mu)', fontFamily: 'Outfit, sans-serif' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--line)' }}
              tickFormatter={(v) => formatCurrency(v, { noConvert: true, minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{
                paddingTop: '12px',
                fontSize: '11.5px',
                color: 'var(--mu)',
                fontFamily: 'Outfit, sans-serif',
              }}
            />

            <ReferenceLine y={0} stroke="var(--line)" strokeWidth={1.5} />

            {/* Target line with dashed ember stroke */}
            {obligationDateStr && (
              <ReferenceLine
                x={new Date(obligationDateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                stroke="var(--o1)"
                strokeDasharray="4 4"
                label={{
                  value: 'Contractor Due',
                  fill: 'var(--o1)',
                  fontSize: 11,
                  position: 'top',
                  fontWeight: 600,
                  fontFamily: 'Outfit, sans-serif',
                }}
              />
            )}

            {showUncertaintyBand && (
              <Area
                type="monotone"
                dataKey="ciBand"
                stroke="none"
                fill="var(--o1)"
                fillOpacity={0.09}
                name="Confidence Range (10th-90th %ile)"
              />
            )}

            {/* Baseline Line with glowing dot heads */}
            <Line
              type="monotone"
              dataKey="baselineBalance"
              stroke="var(--tx)"
              strokeWidth={2}
              dot={{ r: 3, fill: 'var(--tx)', stroke: 'var(--card)', strokeWidth: 1.5 }}
              activeDot={{ r: 6, fill: 'var(--o1)' }}
              name="Baseline (Without Plan)"
            />

            {/* Plan Line with glowing dot heads */}
            {selectedPlan && (
              <Line
                type="monotone"
                dataKey="planBalance"
                stroke="var(--o1)"
                strokeWidth={2.5}
                strokeDasharray="4 4"
                dot={{ r: 3.5, fill: 'var(--o1)', stroke: 'var(--card)', strokeWidth: 1.5 }}
                activeDot={{ r: 7, fill: 'var(--o2)' }}
                name={`With ${selectedPlan.name.split(':')[0]} Overlay`}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-[var(--mu)] border-t border-[var(--line)] pt-3">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-[var(--r)] shrink-0"></span>
          <span>
            Baseline drops into negative balance ({formatCurrency(obligationAmount || 1400)} shortfall) on Friday
          </span>
        </div>
        <div className="flex items-center space-x-1.5 font-medium text-[var(--o1)]">
          <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
          <span className="truncate">Active Plan: {selectedPlan?.name?.split(':')[0] || 'Select Below'}</span>
        </div>
      </div>
    </div>
  );
};
