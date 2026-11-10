import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../api/client';
import { ClientData } from '../types';
import { Users, ExternalLink, Calendar, Database, CheckCircle, Clock, AlertTriangle, Sparkles, DollarSign, Search, X } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';
import { CountUp } from '../components/CountUp';

export const ClientsPage: React.FC = () => {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const searchParam = searchParams.get('search')?.toLowerCase() || '';

  const { formatCurrency, currencySymbol } = useRegionalPreferences();
  const [clients, setClients] = useState<ClientData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [localSearch, setLocalSearch] = useState(searchParam);

  useEffect(() => {
    setLocalSearch(searchParam);
  }, [searchParam]);

  useEffect(() => {
    api.getClients().then(setClients).finally(() => setIsLoading(false));
  }, []);

  const getBehaviorBadge = (c: ClientData) => {
    if (c.avg_delay_days >= 10) {
      return { 
        label: `Chronically Late (~${c.avg_delay_days.toFixed(0)}d)`, 
        bg: 'bg-[var(--r)]/15 text-[var(--r)] border-[var(--r)]/30',
        dot: 'bg-[var(--r)]'
      };
    }
    if (c.avg_delay_days <= 1 && c.avg_delay_days >= 0) {
      return { 
        label: 'Rock-Solid On Time', 
        bg: 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30',
        dot: 'bg-[var(--g)]'
      };
    }
    if (c.avg_delay_days < 0) {
      return { 
        label: `Early Payer (${Math.abs(c.avg_delay_days).toFixed(0)}d early)`, 
        bg: 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30',
        dot: 'bg-[var(--g)]'
      };
    }
    if (c.country !== 'US') {
      return { 
        label: `Overseas Variable (~${c.avg_delay_days.toFixed(0)}d)`, 
        bg: 'bg-[var(--y)]/15 text-[var(--y)] border-[var(--y)]/30',
        dot: 'bg-[var(--y)]'
      };
    }
    return { 
      label: `Moderate Delay (~${c.avg_delay_days.toFixed(0)}d)`, 
      bg: 'bg-[var(--card2)] text-[var(--mu)] border-[var(--line)]',
      dot: 'bg-[var(--dim)]'
    };
  };

  const totalOpenInvoiced = clients.reduce((sum, c) => {
    return sum + c.open_invoices.reduce((acc, inv) => acc + inv.amount, 0);
  }, 0);

  const highRiskClient = clients.find(c => c.avg_delay_days >= 10);

  const displayedClients = localSearch.trim()
    ? clients.filter(
        (c) =>
          c.name.toLowerCase().includes(localSearch.toLowerCase()) ||
          c.email.toLowerCase().includes(localSearch.toLowerCase()) ||
          c.country.toLowerCase().includes(localSearch.toLowerCase())
      )
    : clients;

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-2 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">
              Client Behavioral Models
            </h1>
            <span className="text-[11px] bg-[var(--card2)] text-[var(--dim)] border border-[var(--line)] px-2.5 py-0.5 rounded-full font-semibold">
              {displayedClients.length} of {clients.length} Profiles
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Statistical behavioral profiles trained from 12-month sandbox transaction history
          </p>
        </div>

        {/* Top Summary Badges */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
          {localSearch && (
            <div className="px-3 py-1.5 rounded-[999px] bg-[var(--o1)]/15 border border-[var(--o1)]/30 text-[var(--o1)] text-xs flex items-center gap-2">
              <span>Filter: &ldquo;{localSearch}&rdquo;</span>
              <button
                onClick={() => setLocalSearch('')}
                className="hover:text-[var(--tx)] cursor-pointer"
                aria-label="Clear search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <div className="ignara-card p-3 flex items-center space-x-2.5">
            <DollarSign className="w-4 h-4 text-[var(--o1)] shrink-0" />
            <div className="text-left">
              <span className="text-[10px] uppercase font-semibold text-[var(--dim)] block leading-tight">Total Open</span>
              <span className="font-mono font-semibold text-sm text-[var(--tx)] leading-tight">
                {currencySymbol}
                <CountUp value={totalOpenInvoiced} prefix="" decimals={2} />
              </span>
            </div>
          </div>

          {highRiskClient && (
            <div className="p-3 bg-[var(--r)]/10 border border-[var(--r)]/25 rounded-[14px] flex items-center space-x-2.5">
              <AlertTriangle className="w-4 h-4 text-[var(--r)] shrink-0" />
              <div className="text-left">
                <span className="text-[10px] uppercase font-semibold text-[var(--r)] block leading-tight">Top Risk Driver</span>
                <span className="font-semibold text-xs text-[var(--tx)] leading-tight">
                  {highRiskClient.name} (+{highRiskClient.avg_delay_days.toFixed(0)}d)
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3-Column Item Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 ignara-stagger-1">
        {displayedClients.map((c) => {
          const badge = getBehaviorBadge(c);
          const isPrimaryTarget = c.avg_delay_days >= 10;

          return (
            <div
              key={c.id}
              className={`ignara-card p-5 space-y-4 transition-all duration-200 ignara-card-hover ${
                isPrimaryTarget ? 'border-[var(--r)]/50 ring-2 ring-[var(--r)]/15' : ''
              }`}
            >
              {/* Card Header with radial glow avatar */}
              <div className="flex justify-between items-start gap-2">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className="w-10 h-10 rounded-[12px] flex items-center justify-center text-white shrink-0 shadow-xs"
                    style={{
                      background: isPrimaryTarget ? 'linear-gradient(135deg, #fb7185, #e0352b)' : 'var(--grad-ember)'
                    }}
                  >
                    <span className="font-semibold text-xs">{c.name.slice(0, 2).toUpperCase()}</span>
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <h3 className="ignara-h3 truncate">{c.name}</h3>
                      {isPrimaryTarget && (
                        <span className="text-[10px] font-semibold uppercase bg-[var(--r)] text-white px-2 py-0.5 rounded-full shrink-0">
                          Critical
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[var(--mu)] mt-0.5 truncate">
                      {c.email} &bull; <span className="font-medium text-[var(--tx)]">{c.country}</span>
                    </p>
                  </div>
                </div>

                {c.is_seeded && (
                  <span className="text-[10px] font-semibold uppercase bg-[var(--card2)] text-[var(--dim)] border border-[var(--line)] px-2 py-0.5 rounded-full shrink-0">
                    Seeded
                  </span>
                )}
              </div>

              {/* Behavior Badge */}
              <div>
                <span className={`inline-flex items-center space-x-1.5 text-xs font-semibold px-2.5 py-1 rounded-[8px] border ${badge.bg}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`}></span>
                  <span>{badge.label}</span>
                </span>
              </div>

              {/* Stats Pod */}
              <div className="grid grid-cols-2 gap-3 bg-[var(--side)] p-3 rounded-[14px] text-xs border border-[var(--line)]">
                <div>
                  <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Avg Delay</span>
                  <span className={`font-mono font-semibold text-sm ${c.avg_delay_days > 5 ? 'text-[var(--r)]' : 'text-[var(--tx)]'}`}>
                    {c.avg_delay_days > 0 ? `+${c.avg_delay_days.toFixed(1)} days` : `${c.avg_delay_days.toFixed(1)} days`}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--dim)] block">Late Probability</span>
                  <span className="font-mono font-semibold text-sm text-[var(--tx)]">
                    {(c.p_late * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Open Invoices */}
              <div className="pt-3 border-t border-[var(--line)] space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--dim)] block">
                    Open Invoices ({c.open_invoices.length})
                  </span>
                  {c.open_invoices.length > 0 && (
                    <span className="font-mono text-xs font-semibold text-[var(--o1)]">
                      {formatCurrency(c.open_invoices.reduce((a, b) => a + b.amount, 0))}
                    </span>
                  )}
                </div>

                {c.open_invoices.length === 0 ? (
                  <div className="p-3 bg-[var(--side)] rounded-[12px] border border-dashed border-[var(--line)] text-center text-xs text-[var(--dim)]">
                    All historical invoices settled
                  </div>
                ) : (
                  c.open_invoices.map((inv) => (
                    <div
                      key={inv.id}
                      className="p-3 bg-[var(--card2)] rounded-[12px] border border-[var(--line)] hover:border-[var(--o1)]/40 transition-colors flex flex-col sm:flex-row justify-between items-start sm:items-center text-xs gap-2"
                    >
                      <div className="min-w-0">
                        <div className="font-semibold text-[var(--tx)] font-mono text-sm">
                          {formatCurrency(inv.amount, { currency: inv.currency, showCode: true })}
                        </div>
                        <div className="text-[11px] text-[var(--mu)] truncate">
                          Due: <span className="font-medium text-[var(--tx)]">{inv.due_date}</span> &bull; #{inv.paypal_invoice_id}
                        </div>
                      </div>

                      {inv.pay_link && (
                        <a
                          href={inv.pay_link}
                          target="_blank"
                          rel="noreferrer"
                          className="ignara-btn-secondary text-xs py-1.5 px-3 min-h-[36px]"
                        >
                          <span>PayPal Link</span>
                          <ExternalLink className="w-3 h-3 text-[var(--o1)]" />
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
