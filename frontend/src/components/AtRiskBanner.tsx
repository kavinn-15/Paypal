import React from 'react';
import { CheckCircle2, TrendingDown, TrendingUp, AlertTriangle, Wallet, Calendar, AlertOctagon } from 'lucide-react';
import { Obligation } from '../types';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';
import { CountUp } from './CountUp';

interface AtRiskBannerProps {
  obligation?: Obligation;
  shortfallAmount: number;
  firstShortfallDate?: string;
  startingBalance: number;
  isCovered?: boolean;
  webhookVerified?: boolean;
  paymentReceived?: boolean;
}

export const AtRiskBanner: React.FC<AtRiskBannerProps> = ({
  obligation,
  shortfallAmount,
  firstShortfallDate,
  startingBalance,
  isCovered = false,
  webhookVerified = false,
  paymentReceived = false,
}) => {
  const { formatCurrency, formatDate, currencySymbol } = useRegionalPreferences();
  if (!obligation) return null;

  const dueFormatted = obligation.due_date
    ? formatDate(obligation.due_date, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      })
    : 'Friday';

  // Calculate percentage of obligation covered by initial balance
  const coveragePercent = Math.min(Math.round((startingBalance / (obligation.amount || 1)) * 100), 100);

  const getHeroMessage = () => {
    if (webhookVerified) {
      return `PayPal Sandbox webhook verified payment receipt. Available balance comfortably covers Friday's ${formatCurrency(obligation.amount, { currency: obligation.currency })} payout.`;
    }
    if (paymentReceived || isCovered) {
      return `Forecast recalculation indicates sufficient cashflow to cover Friday's ${formatCurrency(obligation.amount, { currency: obligation.currency })} contractor payout to ${obligation.payee_name}.`;
    }
    return `Current PayPal balance is ${formatCurrency(startingBalance)}. Due to predictable client payment delays, available liquidity cannot cover the ${formatCurrency(obligation.amount, { currency: obligation.currency })} contractor payout.`;
  };

  return (
    <div className="space-y-4 w-full">
      {/* 1. Hero Card: Ember Gradient with thin white progress bar & shadow */}
      <div className="ignara-card-hero p-5 sm:p-7 relative overflow-hidden">
        {/* Subtle background glow */}
        <div className="absolute -right-16 -top-16 w-56 h-56 rounded-full bg-white/10 blur-2xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-5">
          <div className="space-y-2 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-white/20 text-white backdrop-blur-xs border border-white/25">
                {isCovered ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                    <span>Obligation Protected</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5 text-white" />
                    <span>Autonomous Warning &bull; Target #{obligation.id}</span>
                  </>
                )}
              </span>
              <span className="text-[12px] text-white/80 font-medium">
                Due: {dueFormatted} ({obligation.payee_name})
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-medium tracking-tight text-white leading-tight">
              {isCovered ? (
                <span>Contractor Payout to {obligation.payee_name} is Fully Protected</span>
              ) : (
                <span>
                  Projected Shortfall of{' '}
                  <span className="font-semibold underline decoration-white/40">
                    <CountUp value={shortfallAmount} formatFn={(v) => formatCurrency(v)} />
                  </span>{' '}
                  Before Friday
                </span>
              )}
            </h1>

            <p className="text-[13px] sm:text-[14px] text-white/90 leading-relaxed max-w-xl">
              {getHeroMessage()}
            </p>
          </div>

          {/* Hero Metric & White Progress Bar */}
          <div className="w-full lg:w-auto shrink-0 bg-black/20 backdrop-blur-md p-4 rounded-[18px] border border-white/20 min-w-[240px]">
            <div className="flex justify-between items-baseline mb-2">
              <span className="text-[11px] uppercase font-semibold tracking-wider text-white/80">
                Runway Coverage
              </span>
              <span className="text-xl font-semibold text-white font-mono">
                {isCovered ? '100%' : `${coveragePercent}%`}
              </span>
            </div>

            {/* Thin White Progress Bar */}
            <div className="w-full h-1.5 bg-white/20 rounded-full overflow-hidden">
              <div
                className="h-full bg-white rounded-full transition-all duration-1000 ease-[var(--ease-ignara)]"
                style={{ width: isCovered ? '100%' : `${coveragePercent}%` }}
              />
            </div>

            <div className="flex justify-between items-center mt-2.5 text-[11px] text-white/80">
              <span>{formatCurrency(startingBalance)} Start</span>
              <span>{formatCurrency(obligation.amount)} Target</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Three KPI Cards: Icon + Muted Label + Big Number + Delta Pill + Tiny Sparkline */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        {/* KPI 1: Balance Today */}
        <div className="ignara-card p-4 sm:p-5 flex flex-col justify-between relative ignara-card-hover">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-[var(--mu)] text-xs font-medium">
              <Wallet className="w-4 h-4 text-[var(--o1)]" strokeWidth={1.8} />
              <span>Balance Today</span>
            </div>
            <span className="ignara-status-up">
              <TrendingUp className="w-3 h-3" />
              <span>Available</span>
            </span>
          </div>

          <div className="flex items-baseline justify-between mt-1">
            <div className="ignara-num-big">
              <CountUp value={startingBalance} formatFn={(v) => formatCurrency(v)} />
            </div>

            {/* Tiny SVG Sparkline */}
            <svg className="w-16 h-7 text-[var(--g)] overflow-visible shrink-0" viewBox="0 0 64 28">
              <path
                d="M 0 20 Q 16 12 32 18 T 64 4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                className="ignara-sparkline-path"
              />
            </svg>
          </div>
          <span className="text-[11px] text-[var(--dim)] mt-1">Primary PayPal balance</span>
        </div>

        {/* KPI 2: Due Friday */}
        <div className="ignara-card p-4 sm:p-5 flex flex-col justify-between relative ignara-card-hover">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-[var(--mu)] text-xs font-medium">
              <Calendar className="w-4 h-4 text-[var(--mu)]" strokeWidth={1.8} />
              <span>Due Friday</span>
            </div>
            <span className="text-[11px] font-medium text-[var(--mu)] bg-[var(--card2)] px-2 py-0.5 rounded-[8px]">
              Contractor
            </span>
          </div>

          <div className="flex items-baseline justify-between mt-1">
            <div className="ignara-num-big">
              <CountUp value={obligation.amount} formatFn={(v) => formatCurrency(v, { currency: obligation.currency })} />
            </div>

            {/* Tiny SVG Sparkline */}
            <svg className="w-16 h-7 text-[var(--mu)] overflow-visible shrink-0" viewBox="0 0 64 28">
              <path
                d="M 0 14 Q 16 14 32 14 T 64 14"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeDasharray="4 3"
                className="ignara-sparkline-path"
              />
            </svg>
          </div>
          <span className="text-[11px] text-[var(--dim)] mt-1">Payee: {obligation.payee_name}</span>
        </div>

        {/* KPI 3: Protection Gap / Shortfall */}
        <div className="ignara-card p-4 sm:p-5 flex flex-col justify-between relative ignara-card-hover">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-[var(--mu)] text-xs font-medium">
              <AlertOctagon className={`w-4 h-4 ${isCovered ? 'text-[var(--g)]' : 'text-[var(--r)]'}`} strokeWidth={1.8} />
              <span>Protection Gap</span>
            </div>
            {isCovered ? (
              <span className="ignara-status-up">
                <CheckCircle2 className="w-3 h-3" />
                <span>Protected</span>
              </span>
            ) : (
              <span className="ignara-status-down">
                <TrendingDown className="w-3 h-3" />
                <span>Shortfall</span>
              </span>
            )}
          </div>

          <div className="flex items-baseline justify-between mt-1">
            <div className={`ignara-num-big ${isCovered ? 'text-[var(--g)]' : 'text-[var(--r)]'}`}>
              <CountUp value={isCovered ? 0 : shortfallAmount} formatFn={(v) => formatCurrency(v)} />
            </div>

            {/* Tiny SVG Sparkline */}
            <svg
              className={`w-16 h-7 overflow-visible shrink-0 ${isCovered ? 'text-[var(--g)]' : 'text-[var(--r)]'}`}
              viewBox="0 0 64 28"
            >
              <path
                d={isCovered ? "M 0 24 Q 24 16 48 8 T 64 4" : "M 0 4 Q 20 10 40 18 T 64 24"}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                className="ignara-sparkline-path"
              />
            </svg>
          </div>
          <span className="text-[11px] text-[var(--dim)] mt-1">
            {isCovered ? 'Zero deficit remaining' : 'Must bridge before Friday payout'}
          </span>
        </div>
      </div>
    </div>
  );
};
