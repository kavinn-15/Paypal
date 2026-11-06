import React from 'react';
import { ShieldAlert, CheckCircle2, ArrowUpRight, Clock, AlertTriangle } from 'lucide-react';
import { Obligation } from '../types';

interface AtRiskBannerProps {
  obligation?: Obligation;
  shortfallAmount: number;
  firstShortfallDate?: string;
  startingBalance: number;
  isCovered?: boolean;
}

export const AtRiskBanner: React.FC<AtRiskBannerProps> = ({
  obligation,
  shortfallAmount,
  firstShortfallDate,
  startingBalance,
  isCovered = false,
}) => {
  if (!obligation) return null;

  const dueFormatted = new Date(obligation.due_date).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });

  return (
    <div
      className={`bento-card p-6 md:p-8 transition-all ${
        isCovered
          ? 'bg-gradient-to-br from-emerald-500/10 via-white to-white border-emerald-300/80'
          : 'bg-white border-slate-200/90 shadow-bento'
      }`}
    >
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
        {/* Left Side: Problem Statement */}
        <div className="space-y-2 max-w-2xl">
          <div className="flex items-center space-x-2.5">
            <span
              className={`text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
                isCovered
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                  : 'bg-rose-50 text-rose-700 border-rose-200'
              }`}
            >
              {isCovered ? 'Obligation Protected' : 'Critical Cashflow Risk'}
            </span>
            <span className="text-xs text-sardine-slate font-medium">
              Target Obligation: #{obligation.id}
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-ink tracking-tight leading-tight">
            {isCovered ? (
              <span>Contractor Payout to {obligation.payee_name} is Fully Covered</span>
            ) : (
              <span>
                Projected Shortfall of{' '}
                <span className="text-rose-600 font-mono">
                  ${shortfallAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>{' '}
                before Friday
              </span>
            )}
          </h1>

          <p className="text-xs sm:text-sm text-sardine-slate leading-relaxed">
            {isCovered
              ? `PayPal Sandbox webhook verified payment. Your available balance now comfortably covers Friday's $${obligation.amount.toLocaleString()} contractor obligation.`
              : `Current PayPal balance is $${startingBalance.toLocaleString()} today. Due to predictable client payment lags, your balance cannot cover the $${obligation.amount.toLocaleString()} contractor payout to ${obligation.payee_name} due ${dueFormatted}.`}
          </p>
        </div>

        {/* Right Side: Bento Metrics Pod */}
        <div className="w-full lg:w-auto shrink-0 grid grid-cols-3 gap-3 p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/70">
          <div className="px-3 py-1">
            <span className="text-[10px] font-bold uppercase text-sardine-slate block tracking-wider">Balance Today</span>
            <span className="text-base sm:text-lg font-bold font-mono text-ink">
              ${startingBalance.toLocaleString('en-US', { minimumFractionDigits: 0 })}
            </span>
            <span className="text-[10px] text-emerald-600 font-medium block">Healthy initial</span>
          </div>

          <div className="px-3 py-1 border-x border-slate-200">
            <span className="text-[10px] font-bold uppercase text-sardine-slate block tracking-wider">Due Friday</span>
            <span className="text-base sm:text-lg font-bold font-mono text-rose-600">
              ${obligation.amount.toLocaleString('en-US', { minimumFractionDigits: 0 })}
            </span>
            <span className="text-[10px] text-sardine-slate font-medium block">Contractor</span>
          </div>

          <div className="px-3 py-1">
            <span className="text-[10px] font-bold uppercase text-sardine-slate block tracking-wider">Protection Gap</span>
            <span className={`text-base sm:text-lg font-extrabold font-mono ${isCovered ? 'text-emerald-600' : 'text-rose-600'}`}>
              {isCovered ? '$0.00' : `$${shortfallAmount.toLocaleString('en-US', { minimumFractionDigits: 0 })}`}
            </span>
            <span className="text-[10px] text-sardine-slate font-medium block">
              {isCovered ? 'Protected' : 'Shortfall'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
