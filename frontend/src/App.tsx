import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { PublicRoute } from './components/PublicRoute';
import { Navbar } from './components/Navbar';
import { OnboardingModal } from './components/OnboardingModal';

// Pages
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { VerifyOtpPage } from './pages/VerifyOtpPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { EmailVerificationPage } from './pages/EmailVerificationPage';
import { PhoneVerificationPage } from './pages/PhoneVerificationPage';
import { GoogleCallbackPage } from './pages/GoogleCallbackPage';
import { DashboardPage } from './pages/DashboardPage';
import { WhatIfPage } from './pages/WhatIfPage';
import { SupervisorPage } from './pages/SupervisorPage';
import { NegotiationPage } from './pages/NegotiationPage';
import { ResiliencePage } from './pages/ResiliencePage';
import { TimelinePage } from './pages/TimelinePage';
import { ApprovalInboxPage } from './pages/ApprovalInboxPage';
import { ClientsPage } from './pages/ClientsPage';
import { AuditPage } from './pages/AuditPage';
import { SettingsPage } from './pages/SettingsPage';
import { api } from './api/client';

const AuthenticatedLayout: React.FC = () => {
  const { currentUser, logout } = useAuth();
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [showOnboarding, setShowOnboarding] = useState<boolean>(false);

  useEffect(() => {
    if (sessionStorage.getItem('cashflow_show_onboarding') === 'true') {
      setShowOnboarding(true);
    }
  }, []);

  const handleResetDemo = async () => {
    try {
      setIsResetting(true);
      await api.loadDemoScenario();
      await api.runForecast(1800.0, 3.0);
      window.location.reload();
    } catch {
      // ignore
    } finally {
      setIsResetting(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    window.location.href = '/';
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-between w-full overflow-x-hidden">
      <div className="flex-1 flex flex-col w-full">
        <Navbar
          onResetDemo={handleResetDemo}
          isResetting={isResetting}
          currentUser={currentUser}
          onLogout={handleLogout}
        />

        <main className="flex-1 w-full">
          <Outlet />
        </main>
      </div>

      <OnboardingModal
        isOpen={showOnboarding}
        onClose={() => {
          sessionStorage.removeItem('cashflow_show_onboarding');
          setShowOnboarding(false);
        }}
        currentUser={currentUser}
        onCompleted={() => {
          sessionStorage.removeItem('cashflow_show_onboarding');
          setShowOnboarding(false);
        }}
      />

      <footer className="border-t border-slate-200 py-5 sm:py-6 text-xs text-sardine-slate bg-white w-full">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row justify-between items-center gap-3 text-center sm:text-left">
          <div className="text-xs">
            <strong className="text-ink">Cashflow Lifeline</strong> &mdash; Built for PayPal AI Hackathon 2026 (&ldquo;Build What&rsquo;s Next with PayPal and AI&rdquo;)
          </div>
          <div className="flex flex-wrap items-center justify-center sm:justify-end gap-x-2 sm:gap-x-3 gap-y-1 text-[11px] sm:text-xs">
            <span>PayPal Sandbox Verified</span>
            <span className="hidden sm:inline">&bull;</span>
            <span>Deterministic Guardrails</span>
            <span className="hidden sm:inline">&bull;</span>
            <span>SHA-256 Merkle Chain Audit</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Landing Page */}
          <Route path="/" element={<LandingPage />} />

          {/* Authentication Pages (redirect if already logged in) */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />
          <Route
            path="/forgot-password"
            element={
              <PublicRoute>
                <ForgotPasswordPage />
              </PublicRoute>
            }
          />
          <Route
            path="/verify-otp"
            element={
              <PublicRoute>
                <VerifyOtpPage />
              </PublicRoute>
            }
          />
          <Route
            path="/reset-password"
            element={
              <PublicRoute>
                <ResetPasswordPage />
              </PublicRoute>
            }
          />
          <Route path="/verify-email" element={<EmailVerificationPage />} />
          <Route path="/verify-phone" element={<PhoneVerificationPage />} />
          <Route path="/auth/callback/google" element={<GoogleCallbackPage />} />

          {/* Protected Financial Routes */}
          <Route
            element={
              <ProtectedRoute>
                <AuthenticatedLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/whatif" element={<WhatIfPage />} />
            <Route path="/supervisor" element={<SupervisorPage />} />
            <Route path="/negotiation" element={<NegotiationPage />} />
            <Route path="/resilience" element={<ResiliencePage />} />
            <Route path="/timeline" element={<TimelinePage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/invoices" element={<ClientsPage />} />
            <Route path="/obligations" element={<DashboardPage />} />
            <Route path="/forecast" element={<DashboardPage />} />
            <Route path="/plans" element={<DashboardPage />} />
            <Route path="/inbox" element={<ApprovalInboxPage />} />
            <Route path="/approvals" element={<ApprovalInboxPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};
