import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ClientData } from '../types';
import { Users, ExternalLink, Calendar, Database, CheckCircle, Clock } from 'lucide-react';

export const ClientsPage: React.FC = () => {
  const [clients, setClients] = useState<ClientData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.getClients().then(setClients).finally(() => setIsLoading(false));
  }, []);

  const getBehaviorBadge = (c: ClientData) => {
    if (c.avg_delay_days >= 10) {
      return { label: `Chronically Late (~${c.avg_delay_days.toFixed(0)}d)`, bg: 'bg-rose-100 text-rose-800 border-rose-200' };
    }
    if (c.avg_delay_days <= 1 && c.avg_delay_days >= 0) {
      return { label: 'Rock-Solid On Time', bg: 'bg-emerald-100 text-emerald-800 border-emerald-200' };
    }
    if (c.avg_delay_days < 0) {
      return { label: `Early Payer (${Math.abs(c.avg_delay_days).toFixed(0)}d early)`, bg: 'bg-teal-100 text-teal-800 border-teal-200' };
    }
    if (c.country !== 'US') {
      return { label: `Overseas Variable (~${c.avg_delay_days.toFixed(0)}d)`, bg: 'bg-amber-100 text-amber-800 border-amber-200' };
    }
    return { label: `Moderate Delay (~${c.avg_delay_days.toFixed(0)}d)`, bg: 'bg-slate-100 text-slate-800 border-slate-200' };
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 flex items-center space-x-2">
            <span>Clients & Payment Patterns</span>
            <span className="text-xs bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded-full font-bold">
              6 Seeded Profiles
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Statistical behavioral profiles trained from 12-month transaction history
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {clients.map((c) => {
          const badge = getBehaviorBadge(c);
          return (
            <div key={c.id} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
              <div className="flex justify-between items-start gap-2">
                <div>
                  <h3 className="font-extrabold text-base text-slate-900">{c.name}</h3>
                  <p className="text-xs text-slate-500">{c.email} &bull; Country: {c.country}</p>
                </div>
                {c.is_seeded && (
                  <span className="text-[10px] font-bold uppercase bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-full shrink-0">
                    Seeded Data
                  </span>
                )}
              </div>

              {/* Behavior Badge */}
              <div>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${badge.bg}`}>
                  {badge.label}
                </span>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-2 bg-slate-50 p-3 rounded-xl text-xs border border-slate-100">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Avg Payment Lag</span>
                  <span className="font-mono font-bold text-slate-800 text-sm">
                    {c.avg_delay_days > 0 ? `+${c.avg_delay_days.toFixed(1)} days` : `${c.avg_delay_days.toFixed(1)} days`}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Late Probability</span>
                  <span className="font-mono font-bold text-slate-800 text-sm">
                    {(c.p_late * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Open Invoices */}
              <div className="pt-2 border-t border-slate-100 space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
                  Open Invoices ({c.open_invoices.length})
                </span>
                {c.open_invoices.length === 0 ? (
                  <span className="text-xs text-slate-400 italic">No open invoices currently</span>
                ) : (
                  c.open_invoices.map((inv) => (
                    <div
                      key={inv.id}
                      className="p-3 bg-blue-50/50 rounded-xl border border-blue-100 flex justify-between items-center text-xs"
                    >
                      <div>
                        <div className="font-bold text-slate-900">
                          ${inv.amount.toLocaleString()} {inv.currency}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          Due: {inv.due_date} &bull; #{inv.paypal_invoice_id}
                        </div>
                      </div>

                      {inv.pay_link && (
                        <a
                          href={inv.pay_link}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2.5 py-1 bg-white hover:bg-slate-100 text-blue-700 text-xs font-semibold rounded-lg border border-blue-200 flex items-center space-x-1 shadow-xs"
                        >
                          <span>Pay Link</span>
                          <ExternalLink className="w-3 h-3" />
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

