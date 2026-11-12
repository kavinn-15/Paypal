import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { SupervisorRunResponse, AgentTraceStep } from '../types';
import { Bot, CheckCircle2, AlertTriangle, ArrowRight, Sparkles, RefreshCw, Layers, ShieldCheck, Compass } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

export const SupervisorPage: React.FC = () => {
  const { formatCurrency } = useRegionalPreferences();
  const [runData, setRunData] = useState<SupervisorRunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeWorkflow = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.runSupervisor();
      setRunData(res);
    } catch (err: any) {
      setError(err.message || 'Multi-agent supervisor execution failed.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    executeWorkflow();
  }, []);

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-2 border-b border-[var(--line)]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="ignara-h1 ignara-h1-reveal">
              Agent Orchestrator
            </h1>
            <span className="text-[11px] bg-[var(--card2)] text-[var(--o1)] border border-[var(--o1)]/30 px-2.5 py-0.5 rounded-full font-semibold">
              Multi-Agent Supervisor
            </span>
          </div>
          <p className="text-xs text-[var(--mu)] mt-1">
            Supervises specialized agents, validates outputs against financial guardrails, and resolves trade-offs
          </p>
        </div>

        <button
          onClick={executeWorkflow}
          disabled={isLoading}
          className="ignara-btn-primary w-full sm:w-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-white ${isLoading ? 'animate-spin' : ''}`} />
          <span>{isLoading ? 'Orchestrating Agents...' : 'Re-run Supervisor'}</span>
        </button>
      </div>

      {/* Error Alert or Empty Onboarding State */}
      {error && (error.toLowerCase().includes('obligation') || error.toLowerCase().includes('404') || error.toLowerCase().includes('failed to fetch')) ? (
        <div className="ignara-card p-8 max-w-lg mx-auto text-center space-y-4 border-[var(--line)] shadow-lg my-6">
          <div className="w-12 h-12 rounded-[14px] bg-[var(--o1)]/10 text-[var(--o1)] flex items-center justify-center mx-auto">
            <Compass className="w-6 h-6" />
          </div>
          <h2 className="ignara-h3">No Active Contractor Obligations</h2>
          <p className="text-xs text-[var(--mu)] leading-relaxed">
            The Multi-Agent Orchestrator coordinates Forecaster, Collector, Treasurer, and Planner agents to safeguard your contractor payroll payouts against delayed invoices. Add your first contractor obligation to activate autonomous multi-agent supervision.
          </p>
          <div className="pt-2">
            <Link to="/dashboard" className="ignara-btn-primary inline-flex items-center gap-2">
              <span>Go to Dashboard &amp; Add Obligation</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      ) : error ? (
        <div className="p-3.5 rounded-[14px] bg-[var(--r)]/15 border border-[var(--r)]/30 text-[var(--r)] text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={executeWorkflow}
            className="font-semibold underline hover:opacity-80 cursor-pointer"
          >
            Retry
          </button>
        </div>
      ) : null}

      {/* Supervisory Recommendation Banner */}
      {runData && (
        <div className="ignara-card p-5 sm:p-6 space-y-4 w-full overflow-hidden ignara-stagger-1 border border-[var(--line)] bg-[var(--card)]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[var(--line)]">
            <div className="flex items-center space-x-2">
              <Bot className="w-5 h-5 text-[var(--o1)] shrink-0" />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--o1)]">
                Supervisory Strategic Decision
              </span>
            </div>
            <span className="text-xs font-mono font-semibold bg-[var(--side)] border border-[var(--line)] px-2.5 py-1 rounded-[10px] text-[var(--g)] self-start sm:self-auto">
              Confidence Score: {(runData.confidence_score * 100).toFixed(0)}%
            </span>
          </div>

          <div className="space-y-2">
            <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3">
              <h2 className="ignara-h3 text-lg font-semibold text-[var(--tx)]">
                Recommended Strategy: Plan {runData.recommended_plan}
              </h2>
              <span className="text-xs text-[var(--mu)]">
                Targeting: {runData.obligation_evaluated} ({formatCurrency(runData.shortfall_amount)} shortfall)
              </span>
            </div>
            <p className="text-[13px] text-[var(--mu)] leading-relaxed max-w-3xl">
              {runData.final_recommendation}
            </p>
          </div>
        </div>
      )}

      {/* Step-by-Step Agent Trace */}
      {runData && (
        <div className="space-y-3 ignara-stagger-2">
          <h3 className="ignara-h3 flex items-center space-x-2">
            <Layers className="w-4 h-4 text-[var(--o1)]" />
            <span>Agent Execution Trace</span>
          </h3>

          <div className="space-y-2.5">
            {runData.steps_trace.map((step, idx) => (
              <div
                key={idx}
                className="ignara-card p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 hover:border-[var(--o1)]/40 ignara-card-hover"
              >
                <div className="flex items-start space-x-3 min-w-0">
                  <div className="w-8 h-8 rounded-[10px] bg-[var(--side)] border border-[var(--line)] flex items-center justify-center font-semibold text-xs text-[var(--tx)] shrink-0 mt-0.5">
                    #{idx + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                      <span className="font-semibold text-sm text-[var(--tx)]">{step.agent_name}</span>
                      {(step.step_type || step.summary) && (
                        <span className="text-[10px] font-mono px-2 py-0.5 bg-[var(--card2)] border border-[var(--line)] rounded-[6px] text-[var(--mu)]">
                          {step.step_type || step.summary}
                        </span>
                      )}
                      <span className="text-[10px] text-[var(--g)] bg-[var(--g)]/15 border border-[var(--g)]/30 px-2 py-0.5 rounded-[6px] font-semibold">
                        {step.status}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--mu)] mt-1 leading-relaxed">
                      {step.details || step.key_finding}
                    </p>
                  </div>
                </div>

                <div className="text-left md:text-right text-[11px] font-mono text-[var(--dim)] shrink-0 pl-11 md:pl-0 border-t md:border-t-0 pt-2 md:pt-0 border-[var(--line)]">
                  <span>{step.duration_ms !== undefined ? `Latency: ${step.duration_ms}ms` : step.timestamp}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
