import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { SupervisorRunResponse, AgentTraceStep } from '../types';
import { Bot, CheckCircle2, AlertTriangle, ArrowRight, Sparkles, RefreshCw, Layers, ShieldCheck, Compass } from 'lucide-react';

export const SupervisorPage: React.FC = () => {
  const [runData, setRunData] = useState<SupervisorRunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const executeWorkflow = async () => {
    try {
      setIsLoading(true);
      const res = await api.runSupervisor();
      setRunData(res);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    executeWorkflow();
  }, []);

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 space-y-4 sm:space-y-6 w-full overflow-hidden">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 border-b border-slate-200 pb-4 sm:pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-black text-ink tracking-tight font-display">
              Autonomous Agent Orchestrator &amp; Supervisor
            </h1>
            <span className="text-[10px] sm:text-xs bg-electric-50 text-electric-700 border border-electric-200 px-2.5 py-0.5 rounded-full font-bold">
              Multi-Agent Coordination
            </span>
          </div>
          <p className="text-xs text-sardine-slate mt-1">
            Supervises specialized agents, validates outputs against financial guardrails, and resolves trade-offs
          </p>
        </div>

        <button
          onClick={executeWorkflow}
          disabled={isLoading}
          className="flex items-center justify-center space-x-2 px-4 py-2.5 bg-ink hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow-xs transition-all disabled:opacity-50 border border-slate-700 hover:border-electric w-full sm:w-auto min-h-[44px]"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-electric-soft ${isLoading ? 'animate-spin' : ''}`} />
          <span>{isLoading ? 'Orchestrating Agents...' : 'Re-run Supervisor'}</span>
        </button>
      </div>

      {/* Supervisory Recommendation Banner */}
      {runData && (
        <div className="bento-ink p-4 sm:p-6 space-y-4 w-full overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <Bot className="w-5 h-5 text-electric-soft shrink-0" />
              <span className="text-[10px] sm:text-[11px] font-bold uppercase tracking-wider text-electric-soft">
                Supervisory Strategic Decision
              </span>
            </div>
            <span className="text-xs font-mono font-bold bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-lg text-emerald-400 self-start sm:self-auto">
              Confidence Score: {(runData.confidence_score * 100).toFixed(0)}%
            </span>
          </div>

          <div className="space-y-2">
            <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3">
              <h2 className="text-lg sm:text-xl font-black text-white">Recommended Strategy: Plan {runData.recommended_plan}</h2>
              <span className="text-xs text-sardine-muted">
                Targeting: {runData.obligation_evaluated} (${runData.shortfall_amount.toLocaleString()} shortfall)
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed max-w-3xl">
              {runData.final_recommendation}
            </p>
          </div>
        </div>
      )}

      {/* Step-by-Step Agent Trace */}
      <div className="space-y-4">
        <h3 className="font-black text-sm sm:text-base text-ink tracking-tight flex items-center space-x-2">
          <Layers className="w-4 h-4 text-electric" />
          <span>Agent Workflow Execution Trace</span>
        </h3>

        <div className="space-y-3">
          {runData?.steps_trace.map((step, idx) => (
            <div
              key={idx}
              className="bento-card p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 shadow-2xs hover:border-electric/30"
            >
              <div className="flex items-start space-x-3 min-w-0">
                <div className="w-8 h-8 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-xs text-ink shrink-0 mt-0.5">
                  #{idx + 1}
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                    <span className="font-black text-sm text-ink">{step.agent_name}</span>
                    {(step.step_type || step.summary) && (
                      <span className="text-[10px] font-mono px-2 py-0.5 bg-slate-100 border border-slate-200 rounded text-sardine-slate">
                        {step.step_type || step.summary}
                      </span>
                    )}
                    <span className="text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded font-bold">
                      {step.status}
                    </span>
                  </div>
                  <p className="text-xs text-sardine-slate mt-1 leading-relaxed">
                    {step.details || step.key_finding}
                  </p>
                </div>
              </div>

              <div className="text-left md:text-right text-[11px] font-mono text-sardine-slate shrink-0 pl-11 md:pl-0 border-t md:border-t-0 pt-2 md:pt-0 border-slate-100">
                <span>{step.duration_ms !== undefined ? `Latency: ${step.duration_ms}ms` : step.timestamp}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
