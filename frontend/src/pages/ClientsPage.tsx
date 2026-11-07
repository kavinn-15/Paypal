import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ClientData } from '../types';
import { Users, ExternalLink, Calendar, Database, CheckCircle, Clock, AlertTriangle, Sparkles, DollarSign } from 'lucide-react';

export const ClientsPage: React.FC = () => {
  const [clients, setClients] = useState<ClientData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.getClients().then(setClients).finally(() => setIsLoading(false));
  }, []);

  const getBehaviorBadge = (c: ClientData) => {
    if (c.avg_delay_days >= 10) {
      return { 
        label: `Chronically Late (~${c.avg_delay_days.toFixed(0)}d)`, 
        bg: 'bg-rose-50 text-rose-700 border-rose-200/80',
        dot: 'bg-rose-500'
      };
    }
    if (c.avg_delay_days <= 1 && c.avg_delay_days >= 0) {
      return { 
        label: 'Rock-Solid On Time', 
        bg: 'bg-emerald-50 text-emerald-700 border-emerald-200/80',
        dot: 'bg-emerald-500'
      };
    }
    if (c.avg_delay_days < 0) {
      return { 
        label: `Early Payer (${Math.abs(c.avg_delay_days).toFixed(0)}d early)`, 
        bg: 'bg-teal-50 text-teal-700 border-teal-200/80',
        dot: 'bg-teal-500'
      };
    }
    if (c.country !== 'US') {
      return { 
        label: `Overseas Variable (~${c.avg_delay_days.toFixed(0)}d)`, 
        bg: 'bg-amber-50 text-amber-700 border-amber-200/80',
        dot: 'bg-amber-500'
      };
    }
    return { 
      label: `Moderate Delay (~${c.avg_delay_days.toFixed(0)}d)`, 
      bg: 'bg-slate-100 text-slate-700 border-slate-200',
      dot: 'bg-slate-500'
    };
  };

  const totalOpenInvoiced = clients.reduce((sum, c) => {
    return sum + c.open_invoices.reduce((acc, inv) => acc + inv.amount, 0);
  }, 0);

  const highRiskClient = clients.find(c => c.avg_delay_days >= 10);

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 space-y-4 sm:space-y-6 w-full overflow-hidden">
      {/* Bento Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 border-b border-slate-200 pb-4 sm:pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-black text-ink tracking-tight font-display">
              Clients &amp; Payment Patterns
            </h1>
            <span className="text-[10px] sm:text-xs bg-slate-100 text-sardine-slate border border-slate-200 px-2.5 py-0.5 rounded-full font-bold">
              {clients.length} Seeded Profiles
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-1">
            Statistical behavioral profiles trained from 12-month sandbox transaction history
          </p>
        </div>

        {/* Top Summary Badges */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <div className="bg-white border border-slate-200 rounded-xl px-3.5 py-2 flex items-center space-x-2 shadow-2xs">
            <DollarSign className="w-4 h-4 text-electric shrink-0" />
            <div className="text-left">
              <span className="text-[10px] uppercase font-bold text-sardine-muted block leading-tight">Total Open</span>
              <span className="font-mono font-black text-sm text-ink leading-tight">
                ${totalOpenInvoiced.toLocaleString()} USD
              </span>
            </div>
          </div>

          {highRiskClient && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl px-3.5 py-2 flex items-center space-x-2 shadow-2xs">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <div className="text-left">
                <span className="text-[10px] uppercase font-bold text-rose-500 block leading-tight">Top Risk Driver</span>
                <span className="font-bold text-xs text-rose-800 leading-tight">
                  {highRiskClient.name} (+{highRiskClient.avg_delay_days.toFixed(0)}d)
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
        {clients.map((c) => {
          const badge = getBehaviorBadge(c);
          const isPrimaryTarget = c.avg_delay_days >= 10;

          return (
            <div
              key={c.id}
              className={`bento-card p-4 sm:p-6 space-y-4 sm:space-y-5 transition-all ${
                isPrimaryTarget ? 'ring-2 ring-rose-500/30 border-rose-200 bg-gradient-to-b from-white to-rose-50/20' : ''
              }`}
            >
              {/* Card Header */}
              <div className="flex justify-between items-start gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <h3 className="font-black text-base text-ink tracking-tight truncate">{c.name}</h3>
                    {isPrimaryTarget && (
                      <span className="text-[10px] font-extrabold uppercase bg-rose-600 text-white px-2 py-0.5 rounded-full shadow-2xs shrink-0">
                        Critical
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-sardine-slate mt-0.5 truncate">
                    {c.email} &bull; <span className="font-semibold text-slate-700">{c.country}</span>
                  </p>
                </div>
                {c.is_seeded && (
                  <span className="text-[10px] font-bold uppercase bg-slate-100 text-sardine-slate border border-slate-200 px-2 py-0.5 rounded-full shrink-0">
                    Seeded
                  </span>
                )}
              </div>

              {/* Behavior Badge */}
              <div>
                <span className={`inline-flex items-center space-x-1.5 text-xs font-bold px-2.5 py-1 rounded-lg border ${badge.bg}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`}></span>
                  <span>{badge.label}</span>
                </span>
              </div>

              {/* Stats Pod */}
              <div className="grid grid-cols-2 gap-3 bg-slate-50/80 p-3 sm:p-3.5 rounded-xl text-xs border border-slate-200/60">
                <div>
                  <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Avg Delay</span>
                  <span className={`font-mono font-bold text-sm ${c.avg_delay_days > 5 ? 'text-rose-600' : 'text-ink'}`}>
                    {c.avg_delay_days > 0 ? `+${c.avg_delay_days.toFixed(1)} days` : `${c.avg_delay_days.toFixed(1)} days`}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Late Probability</span>
                  <span className="font-mono font-bold text-sm text-ink">
                    {(c.p_late * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Open Invoices */}
              <div className="pt-3 border-t border-slate-100 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-sardine-muted block">
                    Open Invoices ({c.open_invoices.length})
                  </span>
                  {c.open_invoices.length > 0 && (
                    <span className="font-mono text-xs font-bold text-electric">
                      ${c.open_invoices.reduce((a, b) => a + b.amount, 0).toLocaleString()} USD
                    </span>
                  )}
                </div>

                {c.open_invoices.length === 0 ? (
                  <div className="p-3 bg-slate-50 rounded-xl border border-dashed border-slate-200 text-center text-xs text-sardine-slate">
                    All historical invoices settled
                  </div>
                ) : (
                  c.open_invoices.map((inv) => (
                    <div
                      key={inv.id}
                      className="p-3 bg-white rounded-xl border border-slate-200 hover:border-electric/40 transition-colors flex flex-col sm:flex-row justify-between items-start sm:items-center text-xs shadow-2xs gap-2"
                    >
                      <div className="min-w-0">
                        <div className="font-black text-ink font-mono text-sm">
                          ${inv.amount.toLocaleString()} <span className="text-[11px] font-sans font-semibold text-sardine-slate">{inv.currency}</span>
                        </div>
                        <div className="text-[11px] text-sardine-slate truncate">
                          Due: <span className="font-semibold text-slate-700">{inv.due_date}</span> &bull; #{inv.paypal_invoice_id}
                        </div>
                      </div>

                      {inv.pay_link && (
                        <a
                          href={inv.pay_link}
                          target="_blank"
                          rel="noreferrer"
                          className="w-full sm:w-auto px-3 py-1.5 bg-ink hover:bg-slate-800 text-white text-xs font-bold rounded-lg flex items-center justify-center space-x-1 shadow-2xs transition-all shrink-0 min-h-[36px]"
                        >
                          <span>PayPal Link</span>
                          <ExternalLink className="w-3 h-3 text-electric-soft" />
                        </a>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
