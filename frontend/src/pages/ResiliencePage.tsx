import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ResilienceScoreResponse } from '../types';
import { Shield, TrendingUp, AlertTriangle, CheckCircle2, Info, ArrowUpRight, ArrowDownRight, Compass } from 'lucide-react';
import { CountUp } from '../components/CountUp';

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
      <div className="max-w-[1080px] mx-auto py-16 text-center ignara-page-enter">
        <div className="animate-spin w-8 h-8 border-2 border-[var(--o1)] border-t-transparent rounded-full mx-auto"></div>
        <p className="text-xs text-[var(--mu)] mt-3">Computing Resilience Dimensions...</p>
      </div>
    );
  }

  const categoryColor =
    data.category === 'Excellent'
      ? 'text-[var(--g)] bg-[var(--g)]/15 border-[var(--g)]/30'
      : data.category === 'Good'
      ? 'text-blue-400 bg-blue-500/15 border-blue-500/30'
      : data.category === 'Moderate'
      ? 'text-[var(--y)] bg-[var(--y)]/15 border-[var(--y)]/30'
      : 'text-[var(--r)] bg-[var(--r)]/15 border-[var(--r)]/30';

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-2 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">
              Resilience Score
            </h1>
            <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-semibold border ${categoryColor}`}>
              {data.category} ({data.overall_score}/100)
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Explainable 6-dimension liquidity, concentration, and shock-tolerance diagnostic
          </p>
        </div>

        <div className="p-2.5 bg-[var(--side)] border border-[var(--line)] rounded-[14px] text-[11.5px] text-[var(--mu)] w-full sm:max-w-sm">
          <span className="font-semibold text-[var(--tx)]">Methodology Notice: </span>
          Deterministic diagnostic formula. Not a credit score or lending decision.
        </div>
      </div>

      {/* Hero Score Pod & Drivers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 ignara-stagger-1">
        {/* Main Score Pod */}
        <div className="ignara-card p-5 sm:p-6 flex flex-col justify-between space-y-6 bg-[var(--card)] border border-[var(--line)]">
          <div className="space-y-1">
            <span className="text-[10.5px] font-semibold uppercase tracking-wider text-[var(--o1)] block">Composite Score</span>
            <div className="flex items-baseline space-x-2">
              <span className="ignara-num-big text-4xl sm:text-5xl text-[var(--tx)]">
                <CountUp value={data.overall_score} prefix="" decimals={0} />
              </span>
              <span className="text-[var(--dim)] text-sm font-semibold">/ 100</span>
            </div>
            <p className="text-xs text-[var(--mu)] leading-relaxed mt-2">
              {data.category === 'Fragile' || data.category === 'Critical'
                ? 'High vulnerability to client payment delays before Friday contractor obligations.'
                : 'Balanced cash reserves and manageable payout exposure.'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-4 border-t border-[var(--line)] text-xs">
            <div>
              <span className="text-[10px] uppercase font-semibold text-[var(--dim)] block">Runway</span>
              <span className="font-mono font-semibold text-base text-[var(--tx)]">{data.reserve_runway_days} Days</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-semibold text-[var(--dim)] block">Debtor Reliability</span>
              <span className="font-mono font-semibold text-base text-[var(--tx)]">{data.debtor_reliability_pct}%</span>
            </div>
          </div>
        </div>

        {/* Improving Factors */}
        <div className="ignara-card p-5 sm:p-6 space-y-3 ignara-card-hover">
          <div className="flex items-center space-x-2 text-[var(--g)] font-semibold text-xs">
            <ArrowUpRight className="w-4 h-4 shrink-0" />
            <span>Factors Strengthening Your Score</span>
          </div>
          <ul className="space-y-2 text-xs text-[var(--mu)]">
            {data.improving_factors.map((item, idx) => (
              <li key={idx} className="flex items-start space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--g)] mt-1.5 shrink-0"></span>
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Reducing Factors */}
        <div className="ignara-card p-5 sm:p-6 space-y-3 ignara-card-hover">
          <div className="flex items-center space-x-2 text-[var(--r)] font-semibold text-xs">
            <ArrowDownRight className="w-4 h-4 shrink-0" />
            <span>Primary Vulnerability Drivers</span>
          </div>
          <ul className="space-y-2 text-xs text-[var(--mu)]">
            {data.reducing_factors.map((item, idx) => (
              <li key={idx} className="flex items-start space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--r)] mt-1.5 shrink-0"></span>
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* 6 Dimensions Grid */}
      <div className="space-y-3 ignara-stagger-2">
        <h3 className="ignara-h3">6-Factor Resilience Breakdown</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {data.factors.map((factor, idx) => {
            const isAtRisk = factor.status === 'at_risk';
            return (
              <div key={idx} className="ignara-card p-4 sm:p-5 space-y-3 ignara-card-hover">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-xs text-[var(--tx)] truncate">{factor.name}</span>
                  <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-[8px] border shrink-0 ${
                    isAtRisk ? 'bg-[var(--r)]/15 text-[var(--r)] border-[var(--r)]/30' : 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30'
                  }`}>
                    {factor.status.replace('_', ' ')}
                  </span>
                </div>

                <div className="flex items-baseline justify-between">
                  <span className="font-mono font-semibold text-xl sm:text-2xl text-[var(--tx)]">
                    <CountUp value={factor.score} prefix="" decimals={0} /> <span className="text-xs font-sans text-[var(--dim)]">/100</span>
                  </span>
                  <span className="text-[11px] font-medium text-[var(--mu)]">
                    Weight: {(factor.weight * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Progress Bar with ember / status color */}
                <div className="w-full h-1.5 bg-[var(--side)] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-1000 ${factor.score >= 60 ? 'bg-[var(--g)]' : factor.score >= 40 ? 'bg-[var(--y)]' : 'bg-[var(--r)]'}`}
                    style={{ width: `${factor.score}%` }}
                  ></div>
                </div>

                <p className="text-xs text-[var(--mu)] leading-relaxed pt-1">
                  {factor.detail}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Actionable Recommendations */}
      <div className="ignara-card p-5 sm:p-6 space-y-3 ignara-stagger-3 border-[var(--line)]">
        <div className="flex items-center space-x-2 text-[var(--tx)] font-semibold text-sm">
          <Compass className="w-4 h-4 text-[var(--o1)] shrink-0" />
          <span>Recommended Actions to Bolster Resilience</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
          {data.recommended_actions.map((rec, idx) => (
            <div key={idx} className="p-3.5 bg-[var(--side)] border border-[var(--line)] rounded-[14px] text-xs space-y-1">
              <span className="font-semibold text-[var(--o1)] block text-[11px]">Action Step #{idx + 1}</span>
              <p className="text-[var(--tx)] leading-relaxed">{rec}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
