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
import { ResetPasswordPage } from './pages/ResetPasswordPage';
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
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-between">
      <div>
        <Navbar
          onResetDemo={handleResetDemo}
          isResetting={isResetting}
          currentUser={currentUser}
          onLogout={handleLogout}
        />

        <main>
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

      <footer className="border-t border-slate-200 py-6 text-center text-xs text-sardine-slate bg-white">
        <div className="max-w-[1440px] mx-auto px-4 flex flex-col sm:flex-row justify-between items-center gap-2">
          <div>
            <strong>Cashflow Lifeline</strong> &mdash; Built for PayPal AI Hackathon 2026 (&ldquo;Build What&rsquo;s Next with PayPal and AI&rdquo;)
          </div>
          <div className="flex items-center space-x-3">
            <span>PayPal Sandbox Verified</span>
            <span>&bull;</span>
            <span>Deterministic Guardrail Security</span>
            <span>&bull;</span>
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
            path="/reset-password"
            element={
              <PublicRoute>
                <ResetPasswordPage />
              </PublicRoute>
            }
          />

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
