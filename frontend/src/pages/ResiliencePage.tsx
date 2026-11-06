import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ResilienceScoreResponse } from '../types';
import { Shield, TrendingUp, AlertTriangle, CheckCircle2, Info, ArrowUpRight, ArrowDownRight, Compass } from 'lucide-react';

export const ResiliencePage: React.FC = () => {
  const [data, setData] = useState<ResilienceScoreResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.getResilienceScore()
      .then(setData)
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading || !data) {
    return (
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
        <div className="animate-spin w-8 h-8 border-2 border-electric border-t-transparent rounded-full mx-auto"></div>
        <p className="text-xs text-sardine-slate mt-3">Computing Financial Resilience Dimensions...</p>
      </div>
    );
  }

  const categoryColor =
    data.category === 'Excellent'
      ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
      : data.category === 'Good'
      ? 'text-blue-700 bg-blue-50 border-blue-200'
      : data.category === 'Moderate'
      ? 'text-amber-700 bg-amber-50 border-amber-200'
      : 'text-rose-700 bg-rose-50 border-rose-200';

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-black text-ink tracking-tight font-display">
              Financial Resilience Score
            </h1>
            <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold border ${categoryColor}`}>
              {data.category} ({data.overall_score}/100)
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-1">
            Explainable 6-dimension liquidity, concentration, and shock-tolerance diagnostic
          </p>
        </div>

        <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-[11px] text-sardine-slate max-w-sm">
          <span className="font-bold text-ink">Methodology Notice: </span>
          Deterministic diagnostic formula. Not a credit score or lending decision.
        </div>
      </div>

      {/* Hero Score Pod & Drivers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Score Pod */}
        <div className="bento-ink p-6 flex flex-col justify-between space-y-6">
          <div className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-electric-soft block">Composite Score</span>
            <div className="flex items-baseline space-x-3">
              <span className="font-mono font-black text-5xl text-white">{data.overall_score}</span>
              <span className="text-sardine-muted text-sm font-bold">/ 100</span>
            </div>
            <p className="text-xs text-slate-300">
              {data.category === 'Fragile' || data.category === 'Critical'
                ? 'High vulnerability to client payment delays before Friday contractor obligations.'
                : 'Balanced cash reserves and manageable payout exposure.'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-4 border-t border-slate-800 text-xs">
            <div>
              <span className="text-[10px] uppercase font-bold text-sardine-muted block">Runway</span>
              <span className="font-mono font-black text-base text-white">{data.reserve_runway_days} Days</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-sardine-muted block">Debtor Reliability</span>
              <span className="font-mono font-black text-base text-white">{data.debtor_reliability_pct}%</span>
            </div>
          </div>
        </div>

        {/* Improving Factors */}
        <div className="bento-card p-6 space-y-3">
          <div className="flex items-center space-x-2 text-emerald-700 font-bold text-xs">
            <ArrowUpRight className="w-4 h-4" />
            <span>Factors Strengthening Your Score</span>
          </div>
          <ul className="space-y-2 text-xs text-slate-700">
            {data.improving_factors.map((item, idx) => (
              <li key={idx} className="flex items-start space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0"></span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Reducing Factors */}
        <div className="bento-card p-6 space-y-3">
          <div className="flex items-center space-x-2 text-rose-600 font-bold text-xs">
            <ArrowDownRight className="w-4 h-4" />
            <span>Primary Vulnerability Drivers</span>
          </div>
          <ul className="space-y-2 text-xs text-slate-700">
            {data.reducing_factors.map((item, idx) => (
              <li key={idx} className="flex items-start space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 shrink-0"></span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* 6 Dimensions Grid */}
      <div>
        <h3 className="font-black text-base text-ink tracking-tight mb-4">6-Factor Resilience Breakdown</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.factors.map((factor, idx) => {
            const isAtRisk = factor.status === 'at_risk';
            return (
              <div key={idx} className="bento-card p-5 space-y-3 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-ink">{factor.name}</span>
                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-md border ${
                    isAtRisk ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  }`}>
                    {factor.status.replace('_', ' ')}
                  </span>
                </div>

                <div className="flex items-baseline justify-between">
                  <span className="font-mono font-black text-2xl text-ink">
                    {factor.score.toFixed(0)} <span className="text-xs font-sans text-sardine-muted">/100</span>
                  </span>
                  <span className="text-[11px] font-semibold text-sardine-slate">
                    Weight: {(factor.weight * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Mini Progress Bar */}
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${factor.score >= 60 ? 'bg-emerald-500' : factor.score >= 40 ? 'bg-amber-500' : 'bg-rose-500'}`}
                    style={{ width: `${factor.score}%` }}
                  ></div>
                </div>

                <p className="text-xs text-sardine-slate leading-relaxed pt-1">
                  {factor.detail}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Actionable Recommendations */}
      <div className="bento-card p-6 space-y-3 bg-linear-to-r from-white to-blue-50/20 border-electric/30">
        <div className="flex items-center space-x-2 text-ink font-black text-sm">
          <Compass className="w-4 h-4 text-electric" />
          <span>Recommended Actions to Bolster Resilience</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {data.recommended_actions.map((rec, idx) => (
            <div key={idx} className="p-3.5 bg-white border border-slate-200 rounded-xl text-xs space-y-1 shadow-2xs">
              <span className="font-bold text-electric block text-[11px]">Action Step #{idx + 1}</span>
              <p className="text-slate-800 leading-normal">{rec}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
