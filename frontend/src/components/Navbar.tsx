import React, { useState, useEffect } from 'react';
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
  X,
  ChevronRight
} from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

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
  const { country, currency, currencySymbol, countryName, flag } = useRegionalPreferences();

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

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen]);

  // Handle escape key to close menu
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileMenuOpen]);

  // Auto close on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

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
    <>
      <header className="bg-white/95 backdrop-blur-md border-b border-slate-200/80 sticky top-0 z-40 w-full py-3.5 sm:py-4 px-3 sm:px-6 overflow-visible shadow-xs">
        <div className="max-w-[1440px] mx-auto">
          <div className="flex items-center justify-between min-h-[58px] gap-2 sm:gap-4">
            {/* Brand Logo & Title */}
            <Link
              to="/dashboard"
              className="flex items-center space-x-2.5 cursor-pointer shrink-0 select-none group py-1"
            >
              <div className="w-9 h-9 rounded-xl bg-ink text-white flex items-center justify-center font-extrabold text-xs border border-slate-700/80 shadow-xs group-hover:border-electric transition-colors shrink-0">
                <span className="text-electric font-mono font-bold">CL</span>
              </div>
              <div className="flex flex-col justify-center">
                <div className="flex items-center space-x-1.5">
                  <span className="font-black text-sm lg:text-base text-ink tracking-tight whitespace-nowrap leading-normal">
                    Cashflow Lifeline
                  </span>
                  <span className="hidden xl:inline-flex items-center space-x-1 text-[9px] font-bold uppercase tracking-wider bg-electric-50 text-electric-700 border border-electric-200/80 px-1.5 py-0.5 rounded-full whitespace-nowrap">
                    <Sparkles className="w-2.5 h-2.5 text-electric" />
                    <span>PayPal AI</span>
                  </span>
                </div>
                <span className="text-[10px] text-sardine-slate hidden md:block mt-0.5 font-medium leading-normal">
                  Predict &bull; Protect &bull; Execute
                </span>
              </div>
            </Link>

            {/* Desktop Navigation Links - Swiss minimal tabs (zero slide bar) */}
            <nav className="hidden lg:flex items-center space-x-0.5 xl:space-x-1 shrink select-none py-1 overflow-visible">
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

            {/* Desktop User Account, Sandbox Indicator & Actions */}
            <div className="flex items-center space-x-1.5 sm:space-x-2 shrink-0">
              {currentUser ? (
                <div className="flex items-center space-x-1.5 sm:space-x-2">
                  <div className="flex items-center space-x-1 sm:space-x-1.5 px-2 sm:px-2.5 py-1 bg-slate-100 border border-slate-200 rounded-lg text-ink text-xs font-semibold">
                    <UserCheck className="w-3.5 h-3.5 text-electric shrink-0" />
                    <span className="max-w-[90px] sm:max-w-[130px] truncate">{currentUser.name || currentUser.email}</span>
                    <Link
                      to="/settings"
                      className="inline-flex items-center space-x-1 text-[10px] bg-slate-200/80 hover:bg-slate-300 text-slate-800 font-bold px-1.5 py-0.5 rounded transition-colors"
                      title={`Country: ${countryName} (${country}), Preferred Currency: ${currency} (${currencySymbol})`}
                    >
                      <span>{flag}</span>
                      <span>{currency}</span>
                    </Link>
                    {currentUser.is_demo && (
                      <span className="text-[9px] bg-amber-100 text-amber-800 border border-amber-300 font-bold px-1 rounded-sm">
                        DEMO
                      </span>
                    )}
                  </div>

                  {onLogout && (
                    <button
                      onClick={onLogout}
                      className={`flex items-center space-x-1 px-2 sm:px-2.5 py-1 text-xs font-bold rounded-lg transition-colors border shadow-2xs ${
                        currentUser.is_demo
                          ? 'bg-rose-50 hover:bg-rose-100 text-rose-700 border-rose-300 hover:border-rose-400'
                          : 'bg-slate-100 hover:bg-rose-50 text-slate-700 hover:text-rose-700 border-slate-200 hover:border-rose-300'
                      }`}
                      title={currentUser.is_demo ? 'Exit Demo Account' : 'Sign Out Account'}
                    >
                      <LogOut className="w-3.5 h-3.5 shrink-0" />
                      <span>{currentUser.is_demo ? 'Exit Demo' : 'Sign Out'}</span>
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

              {/* Sandbox Badge */}
              <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-50/80 border border-emerald-200 rounded-full text-emerald-800 text-[11px] font-semibold whitespace-nowrap">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Sandbox</span>
              </div>

              {/* Reset Demo Button */}
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

              {/* Mobile Navigation Drawer Toggle */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="lg:hidden p-2 text-sardine-slate hover:text-ink hover:bg-slate-100 rounded-xl transition-colors focus:outline-none min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label={mobileMenuOpen ? 'Close Navigation Menu' : 'Open Navigation Menu'}
                title="Toggle Navigation Menu"
              >
                {mobileMenuOpen ? <X className="w-5 h-5 text-ink" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Backdrop Overlay */}
      {mobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs transition-opacity animate-fadeIn"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Navigation Drawer */}
      <div
        className={`lg:hidden fixed inset-y-0 right-0 z-50 w-full max-w-[320px] sm:max-w-xs bg-white shadow-2xl flex flex-col justify-between transition-transform duration-300 ease-in-out ${
          mobileMenuOpen ? 'translate-x-0' : 'translate-x-full pointer-events-none'
        }`}
        role="dialog"
        aria-modal="true"
        aria-label="Mobile Navigation"
      >
        <div className="flex flex-col h-full overflow-hidden">
          {/* Drawer Header */}
          <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
            <div className="flex items-center space-x-2">
              <div className="w-7 h-7 rounded-lg bg-ink text-white flex items-center justify-center font-bold text-xs">
                CL
              </div>
              <span className="font-bold text-sm text-ink">Cashflow Lifeline</span>
            </div>
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="p-2 rounded-lg text-slate-400 hover:text-ink hover:bg-slate-200/60 min-h-[44px] min-w-[44px] flex items-center justify-center"
              aria-label="Close Menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* User Status Card inside Drawer */}
          {currentUser && (
            <div className="p-4 border-b border-slate-100 bg-slate-50/50">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-full bg-electric-100 text-electric flex items-center justify-center font-bold text-xs shrink-0">
                  <UserCheck className="w-4 h-4" />
                </div>
                <div className="overflow-hidden flex-1">
                  <span className="text-xs font-bold text-ink block truncate">
                    {currentUser.name || currentUser.email}
                  </span>
                  <div className="flex items-center space-x-1.5 mt-0.5">
                    <Link
                      to="/settings"
                      onClick={() => setMobileMenuOpen(false)}
                      className="inline-flex items-center space-x-1 text-[10px] bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold px-1.5 py-0.5 rounded transition-colors w-fit"
                      title={`Country: ${countryName} (${country}), Preferred Currency: ${currency} (${currencySymbol})`}
                    >
                      <span>{flag}</span>
                      <span>{currency} ({currencySymbol})</span>
                    </Link>
                    {currentUser.is_demo && (
                      <span className="text-[9px] bg-electric/10 text-electric font-bold px-1.5 py-0.5 rounded w-fit">
                        DEMO PERSONA
                      </span>
                    )}
                    <span className="text-[10px] text-sardine-slate truncate">
                      {currentUser.email}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Nav Links List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = getIsActive(item);
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all min-h-[44px] text-left ${
                    isActive
                      ? 'bg-ink text-white shadow-xs'
                      : 'text-slate-700 hover:bg-slate-100 hover:text-ink'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-electric-soft' : 'text-slate-500'}`} />
                    <span>{item.label}</span>
                  </div>
                  <ChevronRight className={`w-3.5 h-3.5 opacity-60 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                </button>
              );
            })}
          </div>

          {/* Drawer Footer Actions */}
          <div className="p-4 border-t border-slate-200 bg-slate-50/80 space-y-2.5">
            <div className="flex items-center justify-between text-xs text-sardine-slate px-1">
              <span className="flex items-center space-x-1.5 font-semibold">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>PayPal Sandbox Mode</span>
              </span>
              {currentUser?.is_demo && onResetDemo && (
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onResetDemo();
                  }}
                  disabled={isResetting}
                  className="text-xs font-bold text-electric hover:underline flex items-center space-x-1"
                >
                  <RefreshCw className={`w-3 h-3 ${isResetting ? 'animate-spin' : ''}`} />
                  <span>Reset Demo</span>
                </button>
              )}
            </div>

            {currentUser && onLogout ? (
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  onLogout();
                }}
                className="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-300 transition-colors flex items-center justify-center space-x-2 min-h-[44px]"
              >
                <LogOut className="w-4 h-4" />
                <span>{currentUser.is_demo ? 'Exit Demo Sandbox' : 'Sign Out Account'}</span>
              </button>
            ) : onOpenAuth ? (
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  onOpenAuth();
                }}
                className="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-electric hover:bg-electric-600 transition-colors flex items-center justify-center space-x-2 min-h-[44px]"
              >
                <LogIn className="w-4 h-4" />
                <span>Sign In to Account</span>
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </>
  );
};
