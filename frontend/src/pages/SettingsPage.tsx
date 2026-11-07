import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { PayPalConnectionStatus } from '../types';
import { PhoneInput } from '../components/PhoneInput';
import {
  Settings,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Key,
  Globe,
  Shield,
  Lock,
  Bot,
  Radio,
  Mail,
  Phone,
  Edit2,
  X,
  Check,
  RotateCcw,
  Loader2
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { currentUser, refreshUser } = useAuth();
  const [status, setStatus] = useState<PayPalConnectionStatus | null>(null);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; token_preview?: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // Change / Add phone modal state
  const [showPhoneModal, setShowPhoneModal] = useState(false);
  const [phoneStep, setPhoneStep] = useState<'details' | 'verify_otp'>('details');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPhoneNumber, setNewPhoneNumber] = useState('');
  const [newPhoneCountryCode, setNewPhoneCountryCode] = useState('+91');
  const [changeOtpCode, setChangeOtpCode] = useState('');
  const [changeCooldown, setChangeCooldown] = useState(0);
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSuccess, setPhoneSuccess] = useState<string | null>(null);

  useEffect(() => {
    api.getPayPalConnection().then(setStatus).catch(() => {});
  }, []);

  // Cooldown timer
  useEffect(() => {
    if (changeCooldown <= 0) return;
    const timer = setInterval(() => {
      setChangeCooldown((c) => (c > 0 ? c - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [changeCooldown]);

  const handleTestConnection = async () => {
    try {
      setIsTesting(true);
      const res = await api.testPayPalConnection();
      setTestResult(res);
      const updated = await api.getPayPalConnection();
      setStatus(updated);
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || 'Connection test failed' });
    } finally {
      setIsTesting(false);
    }
  };

  const handleOpenPhoneModal = () => {
    setPhoneStep('details');
    setCurrentPassword('');
    setNewPhoneNumber('');
    setChangeOtpCode('');
    setPhoneError(null);
    setPhoneSuccess(null);
    setShowPhoneModal(true);
  };

  const handleRequestPhoneChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPhoneError(null);

    if (!newPhoneNumber.trim()) {
      setPhoneError('Please enter a valid new mobile phone number.');
      return;
    }

    if (!currentPassword) {
      setPhoneError('Please enter your current password to authorize this security change.');
      return;
    }

    setPhoneLoading(true);
    try {
      const res = await api.requestPhoneChange(currentPassword, newPhoneNumber.trim(), newPhoneCountryCode);
      setPhoneStep('verify_otp');
      setChangeCooldown(res.cooldown_seconds || 60);
      setPhoneSuccess('6-digit SMS verification code sent to the new phone number.');
    } catch (err: any) {
      setPhoneError(err.message || 'Failed to request phone number change. Check your current password.');
    } finally {
      setPhoneLoading(false);
    }
  };

  const handleVerifyPhoneChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPhoneError(null);

    const cleanOtp = changeOtpCode.replace(/\D/g, '');
    if (cleanOtp.length !== 6) {
      setPhoneError('Please enter the 6-digit SMS verification code.');
      return;
    }

    setPhoneLoading(true);
    try {
      await api.verifyPhoneChange(newPhoneNumber.trim(), cleanOtp);
      await refreshUser();
      setPhoneSuccess('Phone number successfully updated and verified! Security alert dispatched to prior number.');
      setTimeout(() => {
        setShowPhoneModal(false);
      }, 1500);
    } catch (err: any) {
      setPhoneError(err.message || 'Invalid or expired OTP code.');
    } finally {
      setPhoneLoading(false);
    }
  };

  const handleResendChangeOtp = async () => {
    if (changeCooldown > 0 || !newPhoneNumber.trim() || !currentPassword) return;
    setPhoneError(null);
    setPhoneLoading(true);
    try {
      const res = await api.requestPhoneChange(currentPassword, newPhoneNumber.trim(), newPhoneCountryCode);
      setChangeCooldown(res.cooldown_seconds || 60);
      setPhoneSuccess('A fresh SMS OTP has been sent.');
    } catch (err: any) {
      setPhoneError(err.message || 'Failed to resend SMS code.');
    } finally {
      setPhoneLoading(false);
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8 space-y-4 sm:space-y-6">
      {/* Bento Header */}
      <div className="border-b border-slate-200 pb-4 sm:pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl sm:text-2xl font-black text-ink tracking-tight font-display">
            System Settings &amp; Security Controls
          </h1>
          <span className="text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-0.5 rounded-full font-bold">
            Sandbox Guard Active
          </span>
        </div>
        <p className="text-xs text-sardine-slate mt-1">
          Verify PayPal sandbox connection, multi-channel authentication, deterministic guardrail limits, and AI safety bounds
        </p>
      </div>

      {/* Security & Contact Information Card */}
      <div className="bento-card p-4 sm:p-6 space-y-4 sm:space-y-5 bg-white">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-electric-50 border border-electric-200 flex items-center justify-center text-electric shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-base text-ink tracking-tight">Security &amp; Contact Credentials</h3>
              <p className="text-xs text-sardine-slate">Identity verification, contact channels, and multi-factor credentials</p>
            </div>
          </div>

          <button
            onClick={handleOpenPhoneModal}
            className="flex items-center justify-center space-x-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-ink text-xs font-semibold rounded-lg border border-slate-300 transition-colors min-h-[44px] sm:min-h-0 self-stretch sm:self-auto"
          >
            <Edit2 className="w-3.5 h-3.5 text-electric shrink-0" />
            <span>{currentUser?.phone_number ? 'Change Phone Number' : 'Add Phone Number'}</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4 pt-1 sm:pt-2">
          {/* Email Channel */}
          <div className="p-3.5 sm:p-4 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between gap-2">
            <div className="flex items-center space-x-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-sardine-slate shrink-0">
                <Mail className="w-4 h-4 text-electric" />
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-bold uppercase tracking-wider text-sardine-slate block">
                  Registered Work Email
                </span>
                <span className="font-semibold text-xs sm:text-sm text-ink block truncate max-w-[170px] sm:max-w-[240px]">
                  {currentUser?.email || 'N/A'}
                </span>
              </div>
            </div>

            {currentUser?.email_verified || currentUser?.is_demo ? (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-[11px] font-bold shrink-0">
                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                <span>Verified</span>
              </span>
            ) : (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded-full text-[11px] font-bold shrink-0">
                <AlertTriangle className="w-3 h-3 text-amber-600" />
                <span>Unverified</span>
              </span>
            )}
          </div>

          {/* Phone Channel */}
          <div className="p-3.5 sm:p-4 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between gap-2">
            <div className="flex items-center space-x-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-sardine-slate shrink-0">
                <Phone className="w-4 h-4 text-electric" />
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-bold uppercase tracking-wider text-sardine-slate block">
                  Mobile SMS Channel
                </span>
                <span className="font-mono font-semibold text-xs sm:text-sm text-ink block truncate">
                  {currentUser?.phone_number || 'No phone registered'}
                </span>
              </div>
            </div>

            {currentUser?.phone_number ? (
              currentUser.phone_verified || currentUser.is_demo ? (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-[11px] font-bold shrink-0">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  <span>Verified</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded-full text-[11px] font-bold shrink-0">
                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                  <span>Unverified</span>
                </span>
              )
            ) : (
              <button
                onClick={handleOpenPhoneModal}
                className="text-[11px] font-bold text-electric hover:underline shrink-0 p-1 min-h-[44px] flex items-center"
              >
                + Register Phone
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Sandbox Connection Card */}
        <div className="bento-card p-4 sm:p-6 space-y-4 sm:space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-electric-50 border border-electric-200/80 flex items-center justify-center text-electric shrink-0">
                <Key className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-black text-base text-ink tracking-tight">PayPal REST API Sandbox</h3>
                <p className="text-xs text-sardine-slate">Target: api-m.sandbox.paypal.com</p>
              </div>
            </div>

            <button
              onClick={handleTestConnection}
              disabled={isTesting}
              className="flex items-center justify-center space-x-1.5 px-3.5 py-2.5 bg-ink hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow-xs transition-all disabled:opacity-50 border border-slate-700 hover:border-electric min-h-[44px] self-stretch sm:self-auto"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-electric ${isTesting ? 'animate-spin' : ''}`} />
              <span>{isTesting ? 'Testing...' : 'Test Connection'}</span>
            </button>
          </div>

          {/* Test Result Message */}
          {testResult && (
            <div
              className={`p-3.5 sm:p-4 rounded-xl border text-xs shadow-2xs ${
                testResult.success
                  ? 'bg-emerald-50/90 text-emerald-900 border-emerald-300'
                  : 'bg-amber-50 text-amber-900 border-amber-300'
              }`}
            >
              <div className="font-bold flex items-center space-x-1.5">
                {testResult.success ? <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" /> : <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />}
                <span>{testResult.success ? 'Sandbox Authentication Verified' : 'Authentication Diagnostic'}</span>
              </div>
              <p className="mt-1 text-slate-700 break-words">{testResult.message}</p>
              {testResult.token_preview && (
                <p className="font-mono text-[11px] mt-1.5 bg-white/70 p-1.5 rounded-lg border border-emerald-200 text-emerald-900 break-all">
                  Token: {testResult.token_preview}
                </p>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 pt-3 text-xs border-t border-slate-100">
            <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Environment</span>
              <span className="font-black text-emerald-700 block mt-0.5">SANDBOX ONLY</span>
              <span className="text-[10px] text-sardine-slate block">Hard Refusal Active</span>
            </div>
            <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Client ID Preview</span>
              <span className="font-mono font-bold text-ink block mt-0.5 truncate">
                {status?.client_id_preview || 'Configured via .env'}
              </span>
              <span className="text-[10px] text-sardine-slate block">OAuth2 Cached</span>
            </div>
          </div>
        </div>

        {/* Safety Policy Limits Card */}
        <div className="bento-card p-6 space-y-5">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-center text-purple-700">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-base text-ink tracking-tight">Deterministic Policy Controls</h3>
              <p className="text-xs text-sardine-slate">Enforced by Guardrail Agent. Zero code paths bypass these bounds.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Early Discount</span>
              <span className="font-black text-ink text-base">5.0% Cap</span>
              <span className="text-[10px] text-sardine-slate block mt-0.5">Plan B capped at 3.0%</span>
            </div>

            <div className="p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Single Payout</span>
              <span className="font-black text-ink text-base">$10,000 Cap</span>
              <span className="text-[10px] text-sardine-slate block mt-0.5">Hard financial ceiling</span>
            </div>

            <div className="p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sardine-muted block">Currencies</span>
              <span className="font-black text-ink text-sm">USD, EUR, GBP</span>
              <span className="text-[10px] text-sardine-slate block mt-0.5">Strict ISO whitelist</span>
            </div>
          </div>
        </div>

        {/* LLM Safety & Fallback Pod */}
        <div className="bento-ink p-6 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-electric-soft">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-base text-white tracking-tight">LLM Safety Boundary</h3>
              <p className="text-xs text-sardine-muted">Google Gemini / Anthropic / Template Fallback</p>
            </div>
          </div>

          <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 text-xs space-y-2 text-slate-300">
            <div className="flex items-center space-x-2 text-emerald-400 font-bold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Zero-Execution Rule Enforced</span>
            </div>
            <p className="text-sardine-muted text-[11px] leading-relaxed">
              The AI layer is restricted to plain-language driver summaries and message drafts. It can never approve, execute, or modify any dollar amount or transaction.
            </p>
          </div>
        </div>

        {/* Webhook Ingress Architecture */}
        <div className="bento-card p-6 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
              <Radio className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-base text-ink tracking-tight">Webhook Ingress Pipeline</h3>
              <p className="text-xs text-sardine-slate">Cryptographically verified via PayPal API</p>
            </div>
          </div>

          <div className="p-4 bg-slate-50/80 rounded-xl border border-slate-200/60 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sardine-slate">Verification Endpoint:</span>
              <span className="font-mono text-ink font-bold">/v1/notifications/verify-webhook-signature</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sardine-slate">Queue Persistence:</span>
              <span className="font-mono text-emerald-700 font-bold">asyncio + SQLite / MySQL WAL</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sardine-slate">Auto-Recalculate on Pay:</span>
              <span className="font-mono text-electric font-bold">Enabled</span>
            </div>
          </div>
        </div>
      </div>

      {/* Change / Register Phone Modal */}
      {showPhoneModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-3 sm:p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl max-w-md w-full max-h-[92vh] flex flex-col p-4 sm:p-6 shadow-2xl border border-slate-200 space-y-4 sm:space-y-5">
            <div className="flex justify-between items-center shrink-0">
              <div className="flex items-center space-x-2">
                <Phone className="w-5 h-5 text-electric shrink-0" />
                <h3 className="font-black text-sm sm:text-base text-ink truncate">
                  {currentUser?.phone_number ? 'Update Mobile Phone' : 'Register Mobile Phone'}
                </h3>
              </div>
              <button
                onClick={() => setShowPhoneModal(false)}
                aria-label="Close phone modal"
                className="w-9 h-9 sm:w-8 sm:h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-ink hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto pr-1 space-y-4">
              {phoneError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-start space-x-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span className="break-words">{phoneError}</span>
                </div>
              )}

              {phoneSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700 flex items-start space-x-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                  <span className="break-words">{phoneSuccess}</span>
                </div>
              )}

              {phoneStep === 'details' ? (
                <form onSubmit={handleRequestPhoneChange} className="space-y-4">
                  <p className="text-xs text-sardine-slate leading-relaxed">
                    For account security, changing your mobile number requires confirming your account password. An SMS code will be sent to the new number.
                  </p>

                  <div className="space-y-1">
                    <label className="block text-xs font-semibold text-ink">
                      Current Account Password <span className="text-rose-500">*</span>
                    </label>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                      <input
                        type="password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        placeholder="••••••••"
                        required
                        className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm border border-slate-200 rounded-xl focus:outline-none focus:border-electric"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <PhoneInput
                      value={newPhoneNumber}
                      onChange={(full, code) => {
                        setNewPhoneNumber(full);
                        setNewPhoneCountryCode(code);
                      }}
                      defaultCountryCode="+91"
                      label="New Mobile Phone Number"
                      placeholder="98765 43210"
                      required
                    />
                  </div>

                  <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setShowPhoneModal(false)}
                      className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition-colors min-h-[44px] sm:min-h-0 flex items-center justify-center"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={phoneLoading}
                      className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-bold bg-electric hover:bg-electric-600 text-white rounded-xl shadow-xs transition-colors disabled:opacity-50 flex items-center justify-center space-x-1.5 min-h-[44px] sm:min-h-0"
                    >
                      {phoneLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>Send SMS Verification</span>
                    </button>
                  </div>
                </form>
              ) : (
                <form onSubmit={handleVerifyPhoneChange} className="space-y-4">
                  <p className="text-xs text-sardine-slate leading-relaxed">
                    Enter the 6-digit SMS code sent to <strong className="font-mono text-ink break-all">{newPhoneNumber}</strong>:
                  </p>

                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={changeOtpCode}
                    onChange={(e) => setChangeOtpCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="123456"
                    required
                    autoFocus
                    className="w-full text-center tracking-[0.25em] sm:tracking-[0.4em] font-mono text-lg sm:text-xl py-2.5 sm:py-3 border border-slate-200 rounded-xl focus:outline-none focus:border-electric"
                  />

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs text-sardine-slate">
                    <span>
                      {changeCooldown > 0 ? (
                        <span>Resend in <strong>{changeCooldown}s</strong></span>
                      ) : (
                        <button
                          type="button"
                          onClick={handleResendChangeOtp}
                          disabled={phoneLoading}
                          className="text-electric font-semibold flex items-center space-x-1 min-h-[44px] sm:min-h-0 py-1"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Resend SMS OTP</span>
                        </button>
                      )}
                    </span>
                    <span>Valid for 5 mins</span>
                  </div>

                  <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setPhoneStep('details')}
                      className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition-colors min-h-[44px] sm:min-h-0 flex items-center justify-center"
                    >
                      Back
                    </button>
                    <button
                      type="submit"
                      disabled={phoneLoading || changeOtpCode.length !== 6}
                      className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-bold bg-electric hover:bg-electric-600 text-white rounded-xl shadow-xs transition-colors disabled:opacity-50 flex items-center justify-center space-x-1.5 min-h-[44px] sm:min-h-0"
                    >
                      {phoneLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>Verify &amp; Update Phone</span>
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
