import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { PlansComparisonResponse, RescuePlan, Action } from '../types';
import { AtRiskBanner } from '../components/AtRiskBanner';
import { ForecastChart } from '../components/ForecastChart';
import { DriverExplanationCard } from '../components/DriverExplanationCard';
import { RescuePlanCard } from '../components/RescuePlanCard';
import { ActionTimeline } from '../components/ActionTimeline';
import { Zap, RefreshCw, AlertCircle, CheckCircle } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

export const DashboardPage: React.FC = () => {
  const { formatCurrency } = useRegionalPreferences();
  const [data, setData] = useState<PlansComparisonResponse | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<RescuePlan | null>(null);
  const [activeAction, setActiveAction] = useState<Action | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSimulating, setIsSimulating] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fetchForecast = async () => {
    try {
      setIsLoading(true);
      const res = await api.getLatestForecast();
      setData(res);
      if (res.plans && res.plans.length > 0) {
        const match = selectedPlan
          ? res.plans.find((p) => p.plan_type === selectedPlan.plan_type) || res.plans[0]
          : res.plans[0];
        setSelectedPlan(match);
        setActiveAction(match.primary_action);
      }
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Failed to load forecast data' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast();
  }, []);

  const handleSelectPlan = (plan: RescuePlan) => {
    setSelectedPlan(plan);
    setActiveAction(plan.primary_action);
  };

  const handleApprove = async (actionId: number, approvalHash: string) => {
    try {
      const updated = await api.approveAction(actionId, approvalHash);
      setNotification({
        type: 'success',
        message: `Plan Approved! Action state is now APPROVED. HMAC cryptographic signature bound to ${updated.recipient}.`,
      });
      await fetchForecast();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Approval failed' });
    }
  };

  const handleExecute = async (actionId: number, idempotencyKey: string) => {
    try {
      const updated = await api.executeAction(actionId, idempotencyKey);
      setNotification({
        type: 'success',
        message: `Dispatched to PayPal Sandbox! Action state is EXECUTED. Ref: ${updated.paypal_ref || 'Invoicing Sandbox'}`,
      });
      await fetchForecast();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Execution failed' });
    }
  };

  const handleSimulatePayment = async () => {
    try {
      setIsSimulating(true);
      await api.simulateWebhook();
      setNotification({
        type: 'success',
        message: 'Simulated payment processed successfully. Demo forecast recalculated. This is not a verified PayPal payment.',
      });
      await fetchForecast();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Webhook simulation failed' });
    } finally {
      setIsSimulating(false);
    }
  };

  if (isLoading && !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-3 p-4">
        <RefreshCw className="w-8 h-8 text-electric animate-spin" />
        <p className="text-xs sm:text-sm font-semibold text-ink text-center">
          Running Forecaster Agent &amp; training delay models...
        </p>
      </div>
    );
  }

  if (!data) return null;

  const isCovered = data.shortfall_amount === 0 || activeAction?.state === 'confirmed';

  return (
    <div className="space-y-4 sm:space-y-6 max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 w-full overflow-hidden">
      {/* Notifications Banner */}
      {notification && (
        <div
          className={`p-3.5 sm:p-4 rounded-xl border text-xs sm:text-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shadow-xs ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
              : 'bg-rose-50 text-rose-800 border-rose-300'
          }`}
        >
          <div className="flex items-start space-x-2">
            {notification.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            )}
            <span className="leading-relaxed">{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-xs font-bold text-sardine-slate hover:text-ink self-end sm:self-auto shrink-0 min-h-[32px] px-2 flex items-center"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Bento Tile: At-Risk Obligation Hero */}
      <AtRiskBanner
        obligation={data.obligation}
        shortfallAmount={data.shortfall_amount}
        firstShortfallDate={data.first_shortfall_date}
        startingBalance={data.starting_balance ?? 1800.0}
        isCovered={isCovered}
      />

      {/* 2. Bento Grid: Trajectory Chart (2 cols on lg) + Agentic Risk Intelligence (1 col) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        <div className="lg:col-span-2">
          <ForecastChart
            projections={data.plans[0]?.forecast_without_plan || []}
            selectedPlan={selectedPlan}
            obligationDateStr={data.obligation.due_date}
            obligationAmount={data.obligation.amount}
          />
        </div>
        <div>
          <DriverExplanationCard
            explanationText={data.tradeoff_summary}
            driverRankings={data.driver_rankings || []}
            isSourceSeeded={false}
          />
        </div>
      </div>

      {/* 3. Bento Grid: Three Rescue Plans Side-by-Side Comparison */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-1.5 sm:gap-2">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base sm:text-lg font-extrabold text-ink tracking-tight">
                Rescue Plan Options
              </h2>
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 bg-ink text-white rounded-md">
                Cheapest Safe Fixes
              </span>
            </div>
            <p className="text-xs text-sardine-slate mt-0.5">
              Deterministic, costed options to plausibly protect Friday's payout. Approve one exact action.
            </p>
          </div>
          <span className="text-[11px] text-sardine-slate font-medium italic">
            *All plans state 'plausibly protects', never 'guarantees'.
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
          {data.plans.map((plan) => (
            <RescuePlanCard
              key={plan.id}
              plan={plan}
              isSelected={selectedPlan?.id === plan.id}
              onSelect={() => handleSelectPlan(plan)}
              onApprove={handleApprove}
              onExecute={handleExecute}
              isLoading={isLoading}
            />
          ))}
        </div>
      </div>

      {/* 4. Action State Progression Stepper */}
      {activeAction && <ActionTimeline action={activeAction} />}

      {/* 5. Bento Tile: Hackathon Fast-Track Sandbox Bar */}
      <div className="bento-ink p-4 sm:p-6 border border-slate-800 shadow-bento w-full overflow-hidden">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2 py-0.5 rounded-full bg-electric-500/20 text-electric-300 border border-electric-400/30 text-[10px] font-bold uppercase tracking-wider">
                PayPal AI Hackathon Fast-Track
              </span>
              <span className="text-xs text-sardine-muted font-medium">Under 3-Minute Live Verification</span>
            </div>
            <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
              Simulate Client Payment Arrival (Development Testing)
            </h3>
            <p className="text-xs text-sardine-muted max-w-xl leading-relaxed">
              Fires a simulated <code className="text-electric-300 bg-slate-900 px-1 py-0.5 rounded text-[11px]">INVOICING.INVOICE.PAID</code> event to test cashflow recalculation.
              Visibly stamped as a <strong className="text-amber-400">Simulated Payment</strong>. Genuine <strong className="text-emerald-400">CONFIRMED</strong> status requires verified PayPal webhook signatures.
            </p>
          </div>

          <button
            onClick={handleSimulatePayment}
            disabled={isSimulating}
            className="w-full sm:w-auto flex items-center justify-center space-x-2 px-5 py-3 bg-electric hover:bg-electric-600 text-white font-extrabold text-xs sm:text-sm rounded-xl shadow-glow-electric transition-all disabled:opacity-50 shrink-0 min-h-[44px]"
          >
            <Zap className={`w-4 h-4 text-white ${isSimulating ? 'animate-bounce' : ''}`} />
            <span>{isSimulating ? 'Processing Webhook...' : `Simulate Client Payment (${formatCurrency(2000)})`}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
