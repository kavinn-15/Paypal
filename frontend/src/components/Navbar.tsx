import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import {
  ShieldCheck,
  Activity,
  Users,
  FileText,
  Settings,
  RefreshCw,
  Sparkles,
  Sliders,
  Bot,
  MessageSquare,
  Compass,
  Clock,
  LogIn,
  LogOut,
  UserCheck,
  Menu,
  X
} from 'lucide-react';

interface NavbarProps {
  currentTab?: string;
  onTabChange?: (tab: string) => void;
  onResetDemo?: () => void;
  isResetting?: boolean;
  currentUser?: any;
  onOpenAuth?: () => void;
  onLogout?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onTabChange,
  onResetDemo,
  isResetting = false,
  currentUser,
  onOpenAuth,
  onLogout,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { id: 'dashboard', path: '/dashboard', label: 'Forecast', icon: Activity },
    { id: 'whatif', path: '/whatif', label: 'What-If', icon: Sliders },
    { id: 'supervisor', path: '/supervisor', label: 'Supervisor', icon: Bot },
    { id: 'negotiation', path: '/negotiation', label: 'Negotiation', icon: MessageSquare },
    { id: 'resilience', path: '/resilience', label: 'Resilience', icon: Compass },
    { id: 'timeline', path: '/timeline', label: 'Timeline', icon: Clock },
    { id: 'clients', path: '/clients', label: 'Clients', icon: Users },
    { id: 'inbox', path: '/inbox', label: 'Inbox', icon: ShieldCheck },
    { id: 'audit', path: '/audit', label: 'Audit', icon: FileText },
    { id: 'settings', path: '/settings', label: 'Settings', icon: Settings },
  ];

  const handleNavClick = (item: { id: string; path: string }) => {
    if (onTabChange) {
      onTabChange(item.id);
    }
    navigate(item.path);
    setMobileMenuOpen(false);
  };

  const getIsActive = (item: { id: string; path: string }) => {
    if (currentTab) return currentTab === item.id;
    return location.pathname === item.path;
  };

  return (
    <header className="bg-white/95 backdrop-blur-md border-b border-slate-200/80 sticky top-0 z-50 w-full pt-2.5 pb-2.5 px-3 sm:px-6">
      <div className="max-w-[1440px] mx-auto">
        <div className="flex items-center justify-between min-h-[56px] gap-2 sm:gap-4">
          {/* Brand */}
          <Link
            to="/dashboard"
            className="flex items-center space-x-2.5 cursor-pointer shrink-0 select-none group"
          >
            <div className="w-9 h-9 rounded-xl bg-ink text-white flex items-center justify-center font-extrabold text-xs border border-slate-700/80 shadow-xs group-hover:border-electric transition-colors">
              <span className="text-electric font-mono font-bold">CL</span>
            </div>
            <div className="flex flex-col justify-center">
              <div className="flex items-center space-x-1.5">
                <span className="font-black text-sm lg:text-base text-ink tracking-tight whitespace-nowrap leading-none">
                  Cashflow Lifeline
                </span>
                <span className="hidden xl:inline-flex items-center space-x-1 text-[9px] font-bold uppercase tracking-wider bg-electric-50 text-electric-700 border border-electric-200/80 px-1.5 py-0.5 rounded-full whitespace-nowrap">
                  <Sparkles className="w-2.5 h-2.5 text-electric" />
                  <span>PayPal AI</span>
                </span>
              </div>
              <span className="text-[10px] text-sardine-slate hidden md:block mt-0.5 font-medium leading-none">
                Predict &bull; Protect &bull; Execute
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Links - Swiss minimal tabs (zero slide bar) */}
          <nav
            className="hidden lg:flex items-center space-x-0.5 xl:space-x-1 shrink select-none py-1 overflow-hidden"
          >
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = getIsActive(item);
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item)}
                  className={`flex items-center space-x-1.5 px-2 xl:px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap shrink-0 ${
                    isActive
                      ? 'bg-ink text-white shadow-xs'
                      : 'text-sardine-slate hover:text-ink hover:bg-slate-100/80'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-electric-soft' : 'text-sardine-slate'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* User Account, Sandbox Indicator & Actions */}
          <div className="flex items-center space-x-2 shrink-0">
            {currentUser ? (
              <div className="flex items-center space-x-2">
                <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 bg-slate-100 border border-slate-200 rounded-lg text-ink text-xs font-semibold">
                  <UserCheck className="w-3.5 h-3.5 text-electric" />
                  <span className="max-w-[120px] truncate">{currentUser.name || currentUser.email}</span>
                  {currentUser.is_demo ? (
                    <span className="text-[9px] bg-electric/10 text-electric font-bold px-1 rounded-sm">DEMO</span>
                  ) : (
                    <span className="text-[9px] bg-emerald-100 text-emerald-800 font-bold px-1 rounded-sm">
                      {currentUser.currency || 'USD'}
                    </span>
                  )}
                </div>

                {onLogout && (
                  <button
                    onClick={onLogout}
                    className="p-1.5 text-sardine-slate hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors border border-transparent hover:border-rose-200"
                    title="Sign Out"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                )}
              </div>
            ) : onOpenAuth ? (
              <button
                onClick={onOpenAuth}
                className="flex items-center space-x-1 px-2.5 py-1.5 bg-electric hover:bg-electric/90 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors whitespace-nowrap"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Sign In</span>
              </button>
            ) : null}

            <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-50/80 border border-emerald-200 rounded-full text-emerald-800 text-[11px] font-semibold whitespace-nowrap">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Sandbox</span>
            </div>

            {currentUser?.is_demo && onResetDemo && (
              <button
                onClick={onResetDemo}
                disabled={isResetting}
                className="flex items-center space-x-1 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200/80 text-ink text-xs font-semibold rounded-lg border border-slate-300/80 transition-colors disabled:opacity-50 whitespace-nowrap shadow-2xs"
                title="Reset scenario to clean initial state"
              >
                <RefreshCw className={`w-3 h-3 text-sardine-slate ${isResetting ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">Reset</span>
              </button>
            )}

            {/* Mobile Nav Toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-1.5 text-sardine-slate hover:text-ink rounded-lg focus:outline-none"
              title="Toggle Menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav Drawer */}
        {mobileMenuOpen && (
          <div className="lg:hidden pt-3 pb-2 border-t border-slate-200 mt-2 grid grid-cols-2 sm:grid-cols-3 gap-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = getIsActive(item);
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item)}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-semibold text-left transition-colors ${
                    isActive
                      ? 'bg-ink text-white'
                      : 'text-sardine-slate hover:bg-slate-100 hover:text-ink'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-electric-soft' : 'text-sardine-slate'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </header>
  );
};
