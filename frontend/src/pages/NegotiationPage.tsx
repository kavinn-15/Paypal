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
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-2 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">
              Negotiation Center
            </h1>
            <span className="text-[11px] bg-[var(--card2)] text-[var(--o1)] border border-[var(--o1)]/30 px-2.5 py-0.5 rounded-full font-semibold">
              AI Negotiation Agent
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Personalized, economically bounded message drafts with human-in-the-loop authorization
          </p>
        </div>

        {/* Target Switcher: Segmented Pill Group */}
        <div className="inline-flex p-1 rounded-[999px] bg-[var(--side)] border border-[var(--line)] self-start md:self-auto">
          <button
            onClick={() => fetchNegotiations('client_discount')}
            disabled={isLoading}
            className={`px-3.5 py-1.5 rounded-[999px] text-xs font-medium transition-all ${
              targetType === 'client_discount'
                ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                : 'text-[var(--mu)] hover:text-[var(--tx)]'
            }`}
          >
            Client Early Discount (Plan B)
          </button>
          <button
            onClick={() => fetchNegotiations('contractor_split')}
            disabled={isLoading}
            className={`px-3.5 py-1.5 rounded-[999px] text-xs font-medium transition-all ${
              targetType === 'contractor_split'
                ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                : 'text-[var(--mu)] hover:text-[var(--tx)]'
            }`}
          >
            Contractor Split (Plan C)
          </button>
        </div>
      </div>

      {/* Context Banner */}
      {tonesData && (
        <div className="ignara-card p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 w-full overflow-hidden ignara-stagger-1 border border-[var(--line)] bg-[var(--card)]">
          <div className="space-y-1">
            <span className="text-[10.5px] font-semibold uppercase tracking-wider text-[var(--o1)] block">
              Negotiation Target
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-base sm:text-lg font-semibold text-[var(--tx)]">{tonesData.recipient_name}</span>
              <span className="text-xs text-[var(--mu)]">({tonesData.recipient_email})</span>
            </div>
            <p className="text-xs text-[var(--mu)] leading-relaxed">{tonesData.context_summary}</p>
          </div>

          <div className="bg-[var(--side)] border border-[var(--line)] p-3 rounded-[14px] text-xs space-y-1 shrink-0 self-start sm:self-auto">
            <span className="text-[10px] uppercase font-semibold text-[var(--dim)] block">Policy Cap</span>
            <span className="font-semibold text-[var(--g)]">Strictly Enforced (Max 5.0% / 50% split)</span>
          </div>
        </div>
      )}

      {/* 3 Tone Variations */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 ignara-stagger-2">
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
              ? 'bg-[var(--side)] text-[var(--tx)] border-[var(--line)]'
              : draft.tone === 'friendly'
              ? 'bg-[var(--g)]/15 text-[var(--g)] border-[var(--g)]/30'
              : 'bg-[var(--o1)]/15 text-[var(--o1)] border-[var(--o1)]/30';

          return (
            <div key={draft.id} className="ignara-card p-5 sm:p-6 flex flex-col justify-between space-y-4 ignara-card-hover">
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-[10px] font-semibold uppercase px-2.5 py-1 rounded-[8px] border truncate ${toneBadge}`}>
                    {toneLabel}
                  </span>
                  {isApproved && (
                    <span className="inline-flex items-center space-x-1 text-[10.5px] font-semibold text-[var(--g)] bg-[var(--g)]/15 border border-[var(--g)]/30 px-2.5 py-0.5 rounded-full shrink-0">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Approved</span>
                    </span>
                  )}
                </div>

                <div>
                  <span className="text-[10px] uppercase font-semibold text-[var(--dim)] block">Subject Line</span>
                  <p className="text-xs font-semibold text-[var(--tx)] mt-0.5 leading-snug">{draft.subject}</p>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-semibold text-[var(--dim)] block">Message Body</span>
                  <div className="mt-1.5 p-3.5 bg-[var(--side)] border border-[var(--line)] rounded-[14px] text-xs text-[var(--tx)] font-sans whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                    {draft.body}
                  </div>
                </div>
              </div>

              {/* Action Footer */}
              <div className="pt-3 border-t border-[var(--line)] flex items-center justify-between gap-2">
                <button
                  onClick={() => handleCopy(draft.id, `${draft.subject}\n\n${draft.body}`)}
                  className="ignara-btn-secondary text-xs"
                >
                  <Copy className="w-3.5 h-3.5 text-[var(--mu)]" />
                  <span>{isCopied ? 'Copied!' : 'Copy'}</span>
                </button>

                <button
                  onClick={() => handleApprove(draft.id)}
                  disabled={isApproved}
                  className={isApproved ? "px-3.5 py-2 text-xs font-semibold rounded-[14px] bg-[var(--g)]/15 text-[var(--g)] border border-[var(--g)]/30 flex items-center space-x-1.5" : "ignara-btn-primary text-xs"}
                >
                  <UserCheck className="w-3.5 h-3.5" />
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
