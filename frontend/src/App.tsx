import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
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

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [isResetting, setIsResetting] = useState<boolean>(false);

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

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-between">
      <div>
        <Navbar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          onResetDemo={handleResetDemo}
          isResetting={isResetting}
        />

        <main>
          {currentTab === 'dashboard' && <DashboardPage />}
          {currentTab === 'whatif' && <WhatIfPage />}
          {currentTab === 'supervisor' && <SupervisorPage />}
          {currentTab === 'negotiation' && <NegotiationPage />}
          {currentTab === 'resilience' && <ResiliencePage />}
          {currentTab === 'timeline' && <TimelinePage />}
          {currentTab === 'clients' && <ClientsPage />}
          {currentTab === 'inbox' && <ApprovalInboxPage />}
          {currentTab === 'audit' && <AuditPage />}
          {currentTab === 'settings' && <SettingsPage />}
        </main>
      </div>

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
            <span>Zero Hallucinations</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
