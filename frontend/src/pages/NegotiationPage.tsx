import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { NegotiationTonesResponse, NegotiationDraft } from '../types';
import { MessageSquare, CheckCircle2, Copy, Send, Sparkles, Shield, UserCheck, RefreshCw } from 'lucide-react';

export const NegotiationPage: React.FC = () => {
  const [targetType, setTargetType] = useState<'client_discount' | 'contractor_split'>('client_discount');
  const [tonesData, setTonesData] = useState<NegotiationTonesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [approvedIds, setApprovedIds] = useState<number[]>([]);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const fetchNegotiations = async (type: 'client_discount' | 'contractor_split') => {
    try {
      setIsLoading(true);
      setTargetType(type);
      const res = await api.generateNegotiation({
        target_type: type,
        discount_pct: 3.0,
        split_pct: 50.0,
      });
      setTonesData(res);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchNegotiations('client_discount');
  }, []);

  const handleApprove = async (draftId: number) => {
    try {
      await api.approveNegotiationDraft(draftId);
      setApprovedIds((prev) => [...prev, draftId]);
    } catch {
      // ignore
    }
  };

  const handleCopy = (id: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-black text-ink tracking-tight font-display">
              Financial Negotiation Center
            </h1>
            <span className="text-xs bg-purple-50 text-purple-700 border border-purple-200 px-2.5 py-0.5 rounded-full font-bold">
              AI Negotiation Agent
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-1">
            Personalized, economically bounded message drafts with human-in-the-loop authorization before dispatch
          </p>
        </div>

        {/* Target Switcher */}
        <div className="flex items-center space-x-2 bg-slate-100 p-1.5 rounded-xl border border-slate-200">
          <button
            onClick={() => fetchNegotiations('client_discount')}
            disabled={isLoading}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              targetType === 'client_discount'
                ? 'bg-ink text-white shadow-xs'
                : 'text-sardine-slate hover:text-ink'
            }`}
          >
            Client Early Discount (Plan B)
          </button>
          <button
            onClick={() => fetchNegotiations('contractor_split')}
            disabled={isLoading}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              targetType === 'contractor_split'
                ? 'bg-ink text-white shadow-xs'
                : 'text-sardine-slate hover:text-ink'
            }`}
          >
            Contractor Payout Split (Plan C)
          </button>
        </div>
      </div>

      {/* Context Banner */}
      {tonesData && (
        <div className="bento-ink p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-electric-soft block">
              Negotiation Target
            </span>
            <div className="flex items-center space-x-2">
              <span className="text-lg font-black text-white">{tonesData.recipient_name}</span>
              <span className="text-xs text-sardine-muted">({tonesData.recipient_email})</span>
            </div>
            <p className="text-xs text-slate-300">{tonesData.context_summary}</p>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs space-y-1">
            <span className="text-[10px] uppercase font-bold text-sardine-muted block">Policy Cap</span>
            <span className="font-bold text-emerald-400">Strictly Enforced (Max 5.0% / 50% split)</span>
          </div>
        </div>
      )}

      {/* 3 Tone Variations */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {tonesData?.options.map((draft) => {
          const isApproved = approvedIds.includes(draft.id) || draft.status === 'approved';
          const isCopied = copiedId === draft.id;

          const toneLabel =
            draft.tone === 'professional'
              ? 'Professional Standard'
              : draft.tone === 'friendly'
              ? 'Friendly & Collaborative'
              : 'Urgent & Respectful';

          const toneBadge =
            draft.tone === 'professional'
              ? 'bg-blue-50 text-blue-700 border-blue-200'
              : draft.tone === 'friendly'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-amber-50 text-amber-700 border-amber-200';

          return (
            <div key={draft.id} className="bento-card p-6 flex flex-col justify-between space-y-4 shadow-xs">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] font-extrabold uppercase px-2.5 py-1 rounded-md border ${toneBadge}`}>
                    {toneLabel}
                  </span>
                  {isApproved && (
                    <span className="inline-flex items-center space-x-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Approved</span>
                    </span>
                  )}
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-sardine-muted block">Subject Line</span>
                  <p className="text-xs font-bold text-ink mt-0.5">{draft.subject}</p>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-bold text-sardine-muted block">Message Body</span>
                  <div className="mt-1.5 p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 font-sans whitespace-pre-wrap leading-relaxed">
                    {draft.body}
                  </div>
                </div>
              </div>

              {/* Action Footer */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleCopy(draft.id, `${draft.subject}\n\n${draft.body}`)}
                  className="px-3 py-1.5 bg-white hover:bg-slate-50 text-sardine-slate hover:text-ink text-xs font-semibold rounded-lg border border-slate-200 flex items-center space-x-1.5 transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>{isCopied ? 'Copied!' : 'Copy'}</span>
                </button>

                <button
                  onClick={() => handleApprove(draft.id)}
                  disabled={isApproved}
                  className={`px-3.5 py-1.5 text-xs font-bold rounded-lg flex items-center space-x-1.5 transition-all ${
                    isApproved
                      ? 'bg-emerald-100 text-emerald-800 cursor-default'
                      : 'bg-ink hover:bg-slate-800 text-white shadow-2xs hover:border-electric border border-slate-700'
                  }`}
                >
                  <UserCheck className="w-3.5 h-3.5 text-electric-soft" />
                  <span>{isApproved ? 'Approved' : 'Approve Draft'}</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
