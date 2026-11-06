import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { PlansComparisonResponse, RescuePlan, Action } from '../types';

export function useCashflow() {
  const [data, setData] = useState<PlansComparisonResponse | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<RescuePlan | null>(null);
  const [activeAction, setActiveAction] = useState<Action | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSimulating, setIsSimulating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshForecast = useCallback(async (startingBalance = 1800.0, discountPct = 3.0) => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.runForecast(startingBalance, discountPct);
      setData(res);
      if (res.plans && res.plans.length > 0) {
        setSelectedPlan((prev) => {
          if (!prev) return res.plans[0];
          return res.plans.find((p) => p.plan_type === prev.plan_type) || res.plans[0];
        });
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch cashflow forecast');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshForecast();
  }, [refreshForecast]);

  useEffect(() => {
    if (selectedPlan) {
      setActiveAction(selectedPlan.primary_action);
    }
  }, [selectedPlan]);

  const approvePlanAction = async (actionId: number, approvalHash: string) => {
    const updated = await api.approveAction(actionId, approvalHash);
    setActiveAction(updated);
    await refreshForecast();
    return updated;
  };

  const executePlanAction = async (actionId: number, idempotencyKey: string) => {
    const updated = await api.executeAction(actionId, idempotencyKey);
    setActiveAction(updated);
    await refreshForecast();
    return updated;
  };

  const triggerPaymentSimulation = async (paypalInvoiceId?: string) => {
    setIsSimulating(true);
    try {
      const res = await api.simulateWebhook(paypalInvoiceId);
      await refreshForecast();
      return res;
    } finally {
      setIsSimulating(false);
    }
  };

  return {
    data,
    selectedPlan,
    setSelectedPlan,
    activeAction,
    isLoading,
    isSimulating,
    error,
    refreshForecast,
    approvePlanAction,
    executePlanAction,
    triggerPaymentSimulation,
  };
}
