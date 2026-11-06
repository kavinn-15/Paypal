import React from 'react';
import { AlertTriangle, CheckCircle2, Calendar, DollarSign, Clock, ShieldAlert } from 'lucide-react';
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

  const shortfallDateFormatted = firstShortfallDate
    ? new Date(firstShortfallDate).toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      })
    : dueFormatted;

  return (
    <div
      className={`rounded-2xl p-6 border shadow-sm transition-all ${
        isCovered
          ? 'bg-gradient-to-r from-emerald-50 via-teal-50 to-emerald-100/60 border-emerald-300'
          : 'bg-gradient-to-r from-rose-50 via-amber-50/70 to-rose-100/50 border-rose-300'
      }`}
    >
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        {/* Left Side: Status & Message */}
        <div className="flex items-start space-x-4">
          <div
            className={`p-3 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${
              isCovered ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'
            }`}
          >
            {isCovered ? <CheckCircle2 className="w-7 h-7" /> : <ShieldAlert className="w-7 h-7" />}
          </div>

          <div>
            <div className="flex items-center space-x-2">
              <span
                className={`text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
                  isCovered
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                    : 'bg-rose-100 text-rose-800 border-rose-300'
                }`}
              >
                {isCovered ? 'Obligation Protected' : 'Imminent Payout at Risk'}
              </span>
              <span className="text-xs text-slate-500 font-medium">Sole Obligation Target</span>
            </div>

            <h2 className="text-xl font-extrabold text-slate-900 mt-1">
              {isCovered ? (
                <span>Contractor Payout to {obligation.payee_name} is Fully Covered</span>
              ) : (
                <span>
                  Projected Shortfall of <span className="text-rose-700">${shortfallAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span> before Friday
                </span>
              )}
            </h2>

            <p className="text-xs text-slate-600 mt-1 max-w-2xl leading-relaxed">
              {isCovered
                ? `Payment confirmed via PayPal sandbox webhook. Your balance now covers the $${obligation.amount.toLocaleString()} contractor obligation.`
                : `Your current PayPal balance of $${startingBalance.toLocaleString()} is healthy today, but cannot cover Friday's $${obligation.amount.toLocaleString()} payout to ${obligation.payee_name} due to overseas client payment lags.`}
            </p>
          </div>
        </div>

        {/* Right Side: Quick Metrics Badges */}
        <div className="grid grid-cols-3 gap-2 shrink-0 bg-white/80 backdrop-blur-sm p-3 rounded-xl border border-slate-200/80 shadow-xs">
          <div className="text-center px-3 py-1">
            <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Balance Today</span>
            <span className="text-sm font-bold text-slate-800">
              ${startingBalance.toLocaleString('en-US', { minimumFractionDigits: 0 })}
            </span>
          </div>

          <div className="text-center px-3 py-1 border-x border-slate-200">
            <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Friday Due</span>
            <span className="text-sm font-bold text-rose-700">
              ${obligation.amount.toLocaleString('en-US', { minimumFractionDigits: 0 })}
            </span>
          </div>

          <div className="text-center px-3 py-1">
            <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Gap to Fix</span>
            <span className={`text-sm font-extrabold ${isCovered ? 'text-emerald-700' : 'text-rose-600'}`}>
              {isCovered ? '$0.00' : `$${shortfallAmount.toLocaleString('en-US', { minimumFractionDigits: 0 })}`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

