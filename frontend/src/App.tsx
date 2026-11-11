import React, { useState, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { RegionalPreferencesProvider } from './context/RegionalPreferencesContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { PublicRoute } from './components/PublicRoute';
import { Navbar } from './components/Navbar';
import { IgnaraSidebar } from './components/IgnaraSidebar';
import { IgnaraHeader } from './components/IgnaraHeader';
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
  const location = useLocation();
  const mainScrollRef = useRef<HTMLElement | null>(null);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [showOnboarding, setShowOnboarding] = useState<boolean>(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [pendingInboxCount, setPendingInboxCount] = useState<number>(0);

  // Scroll to top of main area on route transition
  useEffect(() => {
    if (mainScrollRef.current) {
      mainScrollRef.current.scrollTo(0, 0);
    }
  }, [location.pathname]);

  useEffect(() => {
    if (sessionStorage.getItem('cashflow_show_onboarding') === 'true') {
      setShowOnboarding(true);
    }
    // Fetch real pending actions for the sidebar badge
    api.getActions()
      .then((acts) => {
        const count = acts.filter((a) => a.state === 'proposed').length;
        setPendingInboxCount(count);
      })
      .catch(() => {});
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
    try {
      await logout();
    } catch {
      // ignore
    } finally {
      window.location.href = '/login';
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex bg-[var(--bg)] text-[var(--tx)] font-sans antialiased">
      {/* Ignara 276px Left Sidebar */}
      <IgnaraSidebar
        isOpenMobile={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        pendingInboxCount={pendingInboxCount}
      />

      {/* Main column */}
      <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden">
        {/* Ignara Top Header */}
        <IgnaraHeader
          onToggleMobileMenu={() => setMobileMenuOpen(true)}
          currentUser={currentUser}
          onLogout={handleLogout}
          onResetDemo={handleResetDemo}
          isResetting={isResetting}
        />

        {/* Ignara Main Scroll Container: max-width 1080px, padding 14px 28px 40px, gap 16px */}
        <main ref={mainScrollRef} className="flex-1 overflow-y-auto ignara-scroll px-4 sm:px-7 py-3.5 sm:py-[14px] pb-10">
          <div key={location.pathname} className="max-w-[1080px] mx-auto flex flex-col gap-4">
            <Outlet />
          </div>
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
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <RegionalPreferencesProvider>
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
              <Route path="/what-if" element={<WhatIfPage />} />
              <Route path="/supervisor" element={<SupervisorPage />} />
              <Route path="/negotiation" element={<NegotiationPage />} />
              <Route path="/negotiations" element={<NegotiationPage />} />
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
              <Route path="/setting" element={<SettingsPage />} />
            </Route>

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </RegionalPreferencesProvider>
    </AuthProvider>
  );
};
