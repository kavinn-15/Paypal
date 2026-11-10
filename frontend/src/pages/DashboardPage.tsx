import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { PlansComparisonResponse, RescuePlan, Action } from '../types';
import { AtRiskBanner } from '../components/AtRiskBanner';
import { ForecastChart } from '../components/ForecastChart';
import { DriverExplanationCard } from '../components/DriverExplanationCard';
import { RescuePlanCard } from '../components/RescuePlanCard';
import { ActionTimeline } from '../components/ActionTimeline';
import { Zap, RefreshCw, AlertCircle, CheckCircle, SlidersHorizontal, Sparkles } from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

export const DashboardPage: React.FC = () => {
  const { formatCurrency } = useRegionalPreferences();
  const [data, setData] = useState<PlansComparisonResponse | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<RescuePlan | null>(null);
  const [activeAction, setActiveAction] = useState<Action | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSimulating, setIsSimulating] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Active view filters
  const [activeTab, setActiveTab] = useState<'30d' | '60d' | '90d'>('30d');
  const [filterChip, setFilterChip] = useState<'all' | 'risk' | 'contractors'>('all');

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

  // Auto-dismiss toast after 2.6s
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => {
        setNotification(null);
      }, 2600);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  const handleSelectPlan = (plan: RescuePlan) => {
    setSelectedPlan(plan);
    setActiveAction(plan.primary_action);
  };

  const handleApprove = async (actionId: number, approvalHash: string) => {
    try {
      const updated = await api.approveAction(actionId, approvalHash);
      setNotification({
        type: 'success',
        message: `Plan Approved! State is APPROVED. HMAC signature bound to ${updated.recipient}.`,
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
        message: `Dispatched to PayPal Sandbox! Ref: ${updated.paypal_ref || 'Invoicing Sandbox'}`,
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
        message: 'Simulated payment processed. Forecast recalculated.',
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
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3 p-6 text-center ignara-page-enter">
        <RefreshCw className="w-8 h-8 text-[var(--o1)] animate-spin" />
        <p className="text-sm font-medium text-[var(--tx)]">
          Running Forecaster Agent &amp; evaluating delay models...
        </p>
      </div>
    );
  }

  if (!data) return null;

  const isCovered = data.shortfall_amount === 0 || activeAction?.state === 'confirmed';

  const displayedPlans = data.plans.filter((plan) => {
    if (filterChip === 'all') return true;
    if (filterChip === 'risk') return plan.plan_type === 'A' || plan.plan_type === 'B';
    if (filterChip === 'contractors') return plan.plan_type === 'C' || plan.primary_action?.action_type?.includes('SPLIT');
    return true;
  });

  return (
    <div className="space-y-4 w-full overflow-hidden ignara-page-enter">
      {/* Toast Notification at bottom-center */}
      {notification && (
        <div className="ignara-toast">
          <div className="flex items-center gap-2">
            {notification.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-[var(--g)] shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-[var(--r)] shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
        </div>
      )}

      {/* 1. Page Header Pattern: Left Block (H1 + subtitle) and Right Buttons */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pt-1 pb-1">
        <div>
          <h1 className="ignara-h1 ignara-h1-reveal">
            Cashflow Forecast
          </h1>
          <p className="text-sm text-[var(--mu)] mt-1">
            Continuous Bayesian projection and deterministic autonomous safeguards
          </p>
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          <button
            onClick={fetchForecast}
            disabled={isLoading}
            className="ignara-btn-secondary flex-1 sm:flex-initial"
            title="Refresh current forecast"
          >
            <RefreshCw className={`w-4 h-4 text-[var(--mu)] ${isLoading ? 'animate-spin' : ''}`} />
            <span>Recalculate</span>
          </button>

          <button
            onClick={handleSimulatePayment}
            disabled={isSimulating}
            className="ignara-btn-primary flex-1 sm:flex-initial"
          >
            <Zap className={`w-4 h-4 text-white ${isSimulating ? 'animate-bounce' : ''}`} />
            <span>{isSimulating ? 'Processing...' : 'Simulate Inflow'}</span>
          </button>
        </div>
      </div>

      {/* 2. Under Header: Segmented Controls & Filter Chips */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-[var(--line)]">
        {/* Segmented Controls (pill group) */}
        <div className="inline-flex p-1 rounded-[999px] bg-[var(--side)] border border-[var(--line)]">
          <button
            onClick={() => setActiveTab('30d')}
            className={`px-3.5 py-1 rounded-[999px] text-xs font-medium transition-all ${
              activeTab === '30d'
                ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                : 'text-[var(--mu)] hover:text-[var(--tx)]'
            }`}
          >
            30-Day Horizon
          </button>
          <button
            onClick={() => setActiveTab('60d')}
            className={`px-3.5 py-1 rounded-[999px] text-xs font-medium transition-all ${
              activeTab === '60d'
                ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                : 'text-[var(--mu)] hover:text-[var(--tx)]'
            }`}
          >
            60-Day
          </button>
          <button
            onClick={() => setActiveTab('90d')}
            className={`px-3.5 py-1 rounded-[999px] text-xs font-medium transition-all ${
              activeTab === '90d'
                ? 'bg-[var(--card)] text-[var(--tx)] shadow-xs'
                : 'text-[var(--mu)] hover:text-[var(--tx)]'
            }`}
          >
            90-Day
          </button>
        </div>

        {/* Filter Chips (active = ember gradient) */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setFilterChip('all')}
            className={`px-3 py-1 rounded-[999px] text-xs font-medium transition-all ${
              filterChip === 'all'
                ? 'text-white shadow-xs'
                : 'bg-[var(--card)] text-[var(--mu)] border border-[var(--line)] hover:text-[var(--tx)]'
            }`}
            style={filterChip === 'all' ? { background: 'var(--grad-ember)' } : {}}
          >
            All Accounts
          </button>
          <button
            onClick={() => setFilterChip('risk')}
            className={`px-3 py-1 rounded-[999px] text-xs font-medium transition-all ${
              filterChip === 'risk'
                ? 'text-white shadow-xs'
                : 'bg-[var(--card)] text-[var(--mu)] border border-[var(--line)] hover:text-[var(--tx)]'
            }`}
            style={filterChip === 'risk' ? { background: 'var(--grad-ember)' } : {}}
          >
            At-Risk Flows
          </button>
          <button
            onClick={() => setFilterChip('contractors')}
            className={`px-3 py-1 rounded-[999px] text-xs font-medium transition-all ${
              filterChip === 'contractors'
                ? 'text-white shadow-xs'
                : 'bg-[var(--card)] text-[var(--mu)] border border-[var(--line)] hover:text-[var(--tx)]'
            }`}
            style={filterChip === 'contractors' ? { background: 'var(--grad-ember)' } : {}}
          >
            Contractor Payouts
          </button>
        </div>
      </div>

      {/* 3. Hero Obligation Card + 3 KPI Cards */}
      <div className="ignara-stagger-1">
        <AtRiskBanner
          obligation={data.obligation}
          shortfallAmount={data.shortfall_amount}
          firstShortfallDate={data.first_shortfall_date}
          startingBalance={data.starting_balance ?? 1800.0}
          isCovered={isCovered}
        />
      </div>

      {/* 4. Trajectory Chart (2 cols) + Risk Intelligence Side Card (1 col) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 ignara-stagger-2">
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

      {/* 5. Three Rescue Plan Options */}
      <div className="space-y-3 ignara-stagger-3">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-1.5">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="ignara-h3">Rescue Plan Options</h2>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 bg-[var(--card2)] text-[var(--o1)] border border-[var(--o1)]/30 rounded-full">
                Deterministic Safest Paths
              </span>
            </div>
            <p className="text-xs text-[var(--mu)] mt-0.5">
              Deterministic, costed options to plausibly protect Friday's payout.
            </p>
          </div>
          <span className="text-[11px] text-[var(--dim)] italic">
            *All plans state &lsquo;plausibly protects&rsquo;, never &lsquo;guarantees&rsquo;.
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {displayedPlans.map((plan) => (
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

      {/* 6. Action Progression Timeline */}
      {activeAction && (
        <div className="ignara-stagger-4">
          <ActionTimeline action={activeAction} />
        </div>
      )}

      {/* 7. Bottom Fast-Track Sandbox Strip */}
      <div className="ignara-card p-5 sm:p-6 border border-[var(--line)] bg-[var(--side)] w-full overflow-hidden ignara-stagger-5">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2 py-0.5 rounded-full bg-[var(--o1)]/15 text-[var(--o1)] border border-[var(--o1)]/30 text-[10px] font-semibold uppercase tracking-wider">
                PayPal AI Hackathon Fast-Track
              </span>
              <span className="text-xs text-[var(--dim)] font-medium">Under 3-Minute Live Verification</span>
            </div>
            <h3 className="ignara-h3">
              Simulate Client Payment Arrival (Development Testing)
            </h3>
            <p className="text-xs text-[var(--mu)] max-w-xl leading-relaxed">
              Fires a simulated <code className="text-[var(--o1)] bg-[var(--card)] px-1 py-0.5 rounded-[6px] text-[11px] border border-[var(--line)]">INVOICING.INVOICE.PAID</code> event to test cashflow recalculation.
              Visibly stamped as a <strong className="text-[var(--y)]">Simulated Payment</strong>. Genuine <strong className="text-[var(--g)]">CONFIRMED</strong> status requires verified PayPal webhook signatures.
            </p>
          </div>

          <button
            onClick={handleSimulatePayment}
            disabled={isSimulating}
            className="ignara-btn-primary w-full sm:w-auto"
          >
            <Zap className={`w-4 h-4 text-white ${isSimulating ? 'animate-bounce' : ''}`} />
            <span>{isSimulating ? 'Processing Webhook...' : `Simulate Payment (${formatCurrency(2000)})`}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
