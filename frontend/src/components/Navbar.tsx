import React from 'react';
import { ShieldCheck, Activity, Users, FileText, Settings, RefreshCw, Sparkles } from 'lucide-react';

interface NavbarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  onResetDemo: () => void;
  isResetting: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onTabChange,
  onResetDemo,
  isResetting,
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Forecast & Plans', icon: Activity },
    { id: 'inbox', label: 'Approval Inbox', icon: ShieldCheck },
    { id: 'clients', label: 'Clients & Invoices', icon: Users },
    { id: 'audit', label: 'Audit Trail', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <header className="bg-white/95 backdrop-blur-md border-b border-slate-200/80 sticky top-0 z-50 w-full overflow-hidden">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-3">
          {/* Brand */}
          <div
            className="flex items-center space-x-3 cursor-pointer shrink-0 select-none group"
            onClick={() => onTabChange('dashboard')}
          >
            <div className="w-9 h-9 rounded-xl bg-ink text-white flex items-center justify-center font-extrabold text-sm border border-slate-700/80 shadow-xs group-hover:border-electric transition-colors">
              <span className="text-electric font-mono">CL</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-base lg:text-lg text-ink tracking-tight whitespace-nowrap">
                Cashflow Lifeline
              </span>
              <span className="hidden sm:inline-flex items-center space-x-1 text-[10px] font-bold uppercase tracking-wider bg-electric-50 text-electric-600 border border-electric-200/80 px-2 py-0.5 rounded-full whitespace-nowrap">
                <Sparkles className="w-2.5 h-2.5 text-electric" />
                <span>PayPal AI</span>
              </span>
            </div>
          </div>

          {/* Navigation Links - Swiss minimal tabs */}
          <nav className="flex items-center space-x-1 shrink-0 overflow-hidden">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onTabChange(item.id)}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs lg:text-sm font-medium transition-all whitespace-nowrap shrink-0 ${
                    isActive
                      ? 'bg-ink text-white shadow-xs font-semibold'
                      : 'text-sardine-slate hover:text-ink hover:bg-slate-100/80'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-electric-300' : 'text-sardine-slate'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Sandbox Indicator & Reset Button */}
          <div className="flex items-center space-x-2.5 shrink-0">
            <div className="hidden md:flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-50/80 border border-emerald-200 rounded-full text-emerald-800 text-[11px] font-semibold whitespace-nowrap">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Sandbox Mode</span>
            </div>

            <button
              onClick={onResetDemo}
              disabled={isResetting}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 text-ink text-xs font-semibold rounded-lg border border-slate-300/80 transition-colors disabled:opacity-50 whitespace-nowrap shadow-2xs"
              title="Reset scenario to clean initial state"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-sardine-slate ${isResetting ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Reset Demo</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
