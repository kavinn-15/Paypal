import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { PlansComparisonResponse, RescuePlan, Action } from '../types';
import { AtRiskBanner } from '../components/AtRiskBanner';
import { ForecastChart } from '../components/ForecastChart';
import { DriverExplanationCard } from '../components/DriverExplanationCard';
import { RescuePlanCard } from '../components/RescuePlanCard';
import { ActionTimeline } from '../components/ActionTimeline';
import { Zap, RefreshCw, AlertCircle, CheckCircle, ShieldCheck } from 'lucide-react';

export const DashboardPage: React.FC = () => {
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
        // Default to Plan A or keep currently selected plan type
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
        message: `Plan Approved! Action state is now APPROVED. Cryptographic HMAC bound to ${updated.recipient}.`,
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
      const res = await api.simulateWebhook();
      setNotification({
        type: 'success',
        message: `PayPal Sandbox Webhook Fired! Verified payment received. Action moved to CONFIRMED. Cashflow recalculated.`,
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
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-3">
        <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
        <p className="text-sm font-semibold text-slate-600">Running Forecaster Agent & training delay models...</p>
      </div>
    );
  }

  if (!data) return null;

  const isCovered = data.shortfall_amount === 0 || activeAction?.state === 'confirmed';

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Notifications Banner */}
      {notification && (
        <div
          className={`p-4 rounded-xl border text-sm flex items-center justify-between shadow-sm ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
              : 'bg-rose-50 text-rose-800 border-rose-300'
          }`}
        >
          <div className="flex items-center space-x-2">
            {notification.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-xs font-bold text-slate-500 hover:text-slate-800 ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 1. At-Risk Obligation Banner */}
      <AtRiskBanner
        obligation={data.obligation}
        shortfallAmount={data.shortfall_amount}
        firstShortfallDate={data.first_shortfall_date}
        startingBalance={1800.0}
        isCovered={isCovered}
      />

      {/* 2. Interactive Forecast Chart & Driver Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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
            driverRankings={[]}
            isSourceSeeded={true}
          />
        </div>
      </div>

      {/* 3. Three Rescue Plans Side-by-Side Comparison */}
      <div>
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-4">
          <div>
            <h3 className="text-lg font-extrabold text-slate-900 flex items-center space-x-2">
              <span>Rescue Plan Comparison</span>
              <span className="text-xs font-semibold px-2.5 py-0.5 bg-blue-100 text-blue-800 rounded-full">
                Heart of Product
              </span>
            </h3>
            <p className="text-xs text-slate-500">
              Deterministic, costed options to plausibly protect Friday's contractor payout. Approve one exact action.
            </p>
          </div>
          <span className="text-xs text-slate-400 font-medium italic">
            *Wording guarantees nothing; all options state plausibly protects.
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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

      {/* 4. Action State Lifecycle Timeline */}
      {activeAction && <ActionTimeline action={activeAction} />}

      {/* 5. Demo Scenario Action Bar (Under 3 Minutes Complete Demo) */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 text-white shadow-xl border border-indigo-800/50">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 text-[10px] font-bold uppercase tracking-wider">
                Hackathon Demo Fast-Track
              </span>
              <span className="text-xs text-slate-400 font-medium">3-Minute Live Workflow</span>
            </div>
            <h4 className="text-base font-bold text-white mt-1">
              Simulate Client Payment Arrival (Sandbox Webhook)
            </h4>
            <p className="text-xs text-slate-300 max-w-xl mt-0.5">
              Fires verified <code className="text-indigo-300">INVOICING.INVOICE.PAID</code> webhook event. Moves Action to{' '}
              <strong className="text-emerald-400">CONFIRMED</strong> and recalculates cash balance to show the obligation is protected.
            </p>
          </div>

          <button
            onClick={handleSimulatePayment}
            disabled={isSimulating}
            className="flex items-center space-x-2 px-5 py-3 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white font-extrabold text-sm rounded-xl shadow-lg transition-all disabled:opacity-50 shrink-0"
          >
            <Zap className={`w-4 h-4 text-amber-300 ${isSimulating ? 'animate-bounce' : ''}`} />
            <span>{isSimulating ? 'Processing Webhook...' : 'Simulate Client Payment ($2,000)'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

