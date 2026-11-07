import React, { useState } from 'react';
import {
  Sparkles,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  X,
  Building,
  DollarSign,
  CreditCard,
  Users,
  Calendar,
  Activity,
  Check
} from 'lucide-react';
import { api } from '../api/client';
import { UserProfile } from '../types';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile | null;
  onCompleted: () => void;
}

export const OnboardingModal: React.FC<OnboardingModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  onCompleted,
}) => {
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [businessName, setBusinessName] = useState(currentUser?.name || '');
  const [currency, setCurrency] = useState(currentUser?.currency || 'USD');
  const [clientName, setClientName] = useState('');
  const [clientEmail, setClientEmail] = useState('');
  const [invoiceAmount, setInvoiceAmount] = useState('2500');
  const [payeeName, setPayeeName] = useState('');
  const [obligationAmount, setObligationAmount] = useState('1500');
  const [saving, setSaving] = useState(false);

  if (!isOpen) return null;

  const handleNext = () => {
    if (currentStep < 8) {
      setCurrentStep(currentStep + 1);
    } else {
      onCompleted();
      onClose();
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    onCompleted();
    onClose();
  };

  const handleSaveClientAndInvoice = async () => {
    if (!clientName.trim() || !clientEmail.trim()) {
      handleNext();
      return;
    }
    setSaving(true);
    try {
      // In a real flow, create client
      handleNext();
    } finally {
      setSaving(false);
    }
  };

  const handleSaveObligation = async () => {
    if (!payeeName.trim()) {
      handleNext();
      return;
    }
    setSaving(true);
    try {
      const dueDate = new Date();
      dueDate.setDate(dueDate.getDate() + 7);
      await api.createObligation({
        payee_name: payeeName.trim(),
        payee_email: `${payeeName.toLowerCase().replace(/\s+/g, '')}@contractor.org`,
        amount: parseFloat(obligationAmount) || 1000.0,
        currency,
        due_date: dueDate.toISOString(),
        split_allowed: true,
      });
      handleNext();
    } catch {
      handleNext();
    } finally {
      setSaving(false);
    }
  };

  const handleRunFirstForecast = async () => {
    setSaving(true);
    try {
      await api.runForecast(2000.0, 3.0);
    } catch {
      // ignore
    } finally {
      setSaving(false);
      setCurrentStep(8);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-ink-950/80 backdrop-blur-md">
      <div className="w-full max-w-xl max-h-[92vh] rounded-2xl border border-ink-700 bg-ink-900 text-white shadow-2xl overflow-hidden flex flex-col">
        {/* Header with progress */}
        <div className="p-4 sm:p-5 border-b border-ink-800 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-2 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-electric/20 border border-electric/40 text-electric flex items-center justify-center font-bold text-xs shrink-0">
              {currentStep}/8
            </div>
            <div className="min-w-0">
              <span className="text-xs font-bold text-white uppercase tracking-wider block truncate">
                Getting Started with Cashflow Lifeline
              </span>
              <div className="text-[10px] text-sardine-muted truncate">
                Step {currentStep} of 8 &bull; Can be updated anytime in Settings
              </div>
            </div>
          </div>
          <button
            onClick={handleSkip}
            className="text-sardine-muted hover:text-white p-1.5 rounded-lg text-xs flex items-center space-x-1 shrink-0 min-h-[36px]"
          >
            <span>Skip Tour</span>
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Step Progress Bar */}
        <div className="w-full bg-ink-950 h-1 shrink-0">
          <div
            className="bg-electric h-1 transition-all duration-300"
            style={{ width: `${(currentStep / 8) * 100}%` }}
          />
        </div>

        {/* Step Content */}
        <div className="p-4 sm:p-6 sm:p-8 flex-1 min-h-[220px] overflow-y-auto">
          {/* Step 1: Welcome */}
          {currentStep === 1 && (
            <div className="space-y-4 text-center py-4">
              <div className="w-14 h-14 rounded-2xl bg-electric/20 border border-electric/40 text-electric flex items-center justify-center mx-auto shadow-glow-electric">
                <Sparkles className="w-7 h-7" />
              </div>
              <h2 className="text-2xl font-black text-white">Welcome, {currentUser?.name || 'Partner'}!</h2>
              <p className="text-sm text-sardine-muted max-w-md mx-auto leading-relaxed">
                Cashflow Lifeline is designed to protect your most critical upcoming obligations by analyzing client payment latencies and recommending fee-optimized rescue plans.
              </p>
              <div className="pt-2 text-xs text-electric-300 font-mono">
                Let&rsquo;s set up your ledger in 60 seconds.
              </div>
            </div>
          )}

          {/* Step 2: Business Info */}
          {currentStep === 2 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-ink-800 text-electric flex items-center justify-center">
                  <Building className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-white">Confirm Business Details</h3>
                  <p className="text-xs text-sardine-muted">
                    This personalizes your risk thresholds and currency display
                  </p>
                </div>
              </div>
              <div className="space-y-3 pt-2">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Trading / Business Name</label>
                  <input
                    type="text"
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                    className="w-full p-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Registered Email</label>
                  <input
                    type="text"
                    value={currentUser?.email || ''}
                    disabled
                    className="w-full p-2.5 bg-ink-950/60 border border-ink-800 rounded-xl text-xs text-slate-400 cursor-not-allowed"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Base Currency */}
          {currentStep === 3 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-ink-800 text-electric flex items-center justify-center">
                  <DollarSign className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-white">Select Base Operating Currency</h3>
                  <p className="text-xs text-sardine-muted">
                    Your financial projections and shortfall amounts will be calculated in this currency
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 pt-2">
                {['USD', 'EUR', 'GBP', 'INR', 'CAD', 'AUD'].map((cur) => (
                  <button
                    key={cur}
                    onClick={() => setCurrency(cur)}
                    className={`p-3 rounded-xl border text-left flex items-center justify-between text-xs font-bold transition-all ${
                      currency === cur
                        ? 'border-electric bg-electric/15 text-white'
                        : 'border-ink-800 bg-ink-950 text-slate-300 hover:border-slate-700'
                    }`}
                  >
                    <span>{cur}</span>
                    {currency === cur && <Check className="w-4 h-4 text-electric" />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 4: PayPal Connect */}
          {currentStep === 4 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-ink-800 text-electric flex items-center justify-center">
                  <CreditCard className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-white">Connect PayPal Sandbox</h3>
                  <p className="text-xs text-sardine-muted">
                    Allows Cashflow Lifeline to track invoice statuses and prepare payouts
                  </p>
                </div>
              </div>
              <div className="p-4 rounded-xl border border-ink-800 bg-ink-950 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300">Environment:</span>
                  <span className="font-mono text-emerald-400 font-bold">PayPal Sandbox</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300">Integration Status:</span>
                  <span className="font-bold text-slate-200">Ready to sync</span>
                </div>
                <p className="text-[11px] text-sardine-muted leading-relaxed">
                  You can connect your sandbox API credentials directly from Settings at any time, or continue with manual ledger entries now.
                </p>
              </div>
            </div>
          )}

          {/* Step 5: Add Client / Invoice */}
          {currentStep === 5 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-ink-800 text-electric flex items-center justify-center">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-white">Add Your First Client (Optional)</h3>
                  <p className="text-xs text-sardine-muted">
                    Enter an invoice you are currently awaiting payment for
                  </p>
                </div>
              </div>
              <div className="space-y-3 pt-1">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Client / Company Name</label>
                  <input
                    type="text"
                    value={clientName}
                    onChange={(e) => setClientName(e.target.value)}
                    placeholder="e.g. Acme Studio"
                    className="w-full p-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs text-white"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-300">Client Email</label>
                    <input
                      type="email"
                      value={clientEmail}
                      onChange={(e) => setClientEmail(e.target.value)}
                      placeholder="billing@acme.org"
                      className="w-full p-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-300">Invoice Amount ({currency})</label>
                    <input
                      type="number"
                      value={invoiceAmount}
                      onChange={(e) => setInvoiceAmount(e.target.value)}
                      placeholder="2500"
                      className="w-full p-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs text-white"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 6: Add Upcoming Obligation */}
          {currentStep === 6 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-ink-800 text-electric flex items-center justify-center">
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-white">Add an Upcoming Payout Obligation</h3>
                  <p className="text-xs text-sardine-muted">
                    The platform tracks this obligation against expected client receipts
                  </p>
                </div>
              </div>
              <div className="space-y-3 pt-1">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Contractor / Vendor Name</label>
                  <input
                    type="text"
                    value={payeeName}
                    onChange={(e) => setPayeeName(e.target.value)}
                    placeholder="e.g. John Miller (Lead Designer)"
                    className="w-full p-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Amount Due ({currency})</label>
                  <input
                    type="number"
                    value={obligationAmount}
                    onChange={(e) => setObligationAmount(e.target.value)}
                    placeholder="1500"
                    className="w-full p-2.5 bg-ink-950 border border-ink-700 rounded-xl text-xs text-white"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 7: First Forecast */}
          {currentStep === 7 && (
            <div className="space-y-4 text-center py-4">
              <div className="w-12 h-12 rounded-2xl bg-electric/20 border border-electric/40 text-electric flex items-center justify-center mx-auto">
                <Activity className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-xl text-white">Generate Your First Forecast</h3>
              <p className="text-xs text-sardine-muted max-w-sm mx-auto leading-relaxed">
                The Forecaster Agent will combine your active invoices and obligations to evaluate 14-day shortfall probabilities.
              </p>
              <button
                type="button"
                onClick={handleRunFirstForecast}
                disabled={saving}
                className="px-6 py-3 rounded-xl bg-electric hover:bg-electric-600 text-white font-bold text-xs shadow-glow-electric transition-all cursor-pointer disabled:opacity-50"
              >
                {saving ? 'Synthesizing Trajectories...' : 'Execute Baseline Forecast'}
              </button>
            </div>
          )}

          {/* Step 8: Dashboard Ready */}
          {currentStep === 8 && (
            <div className="space-y-4 text-center py-4">
              <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h2 className="text-2xl font-black text-white">You Are All Set!</h2>
              <p className="text-xs text-sardine-muted max-w-md mx-auto leading-relaxed">
                Your private dashboard is active. You can add further invoices, simulate what-if scenarios, and inspect AI rescue plans at any time.
              </p>
            </div>
          )}
        </div>

        {/* Footer controls */}
        <div className="p-3.5 sm:p-4 bg-ink-950 border-t border-ink-800 flex items-center justify-between shrink-0">
          {currentStep > 1 && currentStep < 8 ? (
            <button
              onClick={handleBack}
              className="px-3 sm:px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:text-white flex items-center space-x-1 min-h-[40px]"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back</span>
            </button>
          ) : (
            <div />
          )}

          <div className="flex items-center space-x-2">
            {currentStep < 7 ? (
              <>
                <button
                  onClick={handleNext}
                  className="px-2.5 sm:px-3 py-2 text-xs text-sardine-muted hover:text-white min-h-[40px] flex items-center"
                >
                  Skip Step
                </button>
                <button
                  onClick={() => {
                    if (currentStep === 5) handleSaveClientAndInvoice();
                    else if (currentStep === 6) handleSaveObligation();
                    else handleNext();
                  }}
                  className="px-4 sm:px-5 py-2 rounded-xl bg-electric hover:bg-electric-600 text-white text-xs font-bold shadow-glow-electric flex items-center space-x-1.5 cursor-pointer min-h-[40px]"
                >
                  <span>Continue</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </>
            ) : currentStep === 8 ? (
              <button
                onClick={() => {
                  onCompleted();
                  onClose();
                }}
                className="px-5 sm:px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold flex items-center space-x-1.5 cursor-pointer min-h-[44px]"
              >
                <span>Enter Dashboard</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

