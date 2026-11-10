import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Sun,
  Moon,
  Bell,
  Menu,
  RotateCcw,
  LogOut,
  Settings as SettingsIcon,
  CheckCircle2,
  Sparkles
} from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

interface IgnaraHeaderProps {
  onToggleMobileMenu?: () => void;
  currentUser?: any;
  onLogout?: () => void;
  onResetDemo?: () => void;
  isResetting?: boolean;
}

export const IgnaraHeader: React.FC<IgnaraHeaderProps> = ({
  onToggleMobileMenu,
  currentUser,
  onLogout,
  onResetDemo,
  isResetting = false,
}) => {
  const navigate = useNavigate();
  const { flag, currency, currencySymbol, countryName, country } = useRegionalPreferences();
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Theme toggle state
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('ignara_theme') || localStorage.getItem('theme');
      if (saved === 'light' || saved === 'dark') return saved;
      return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    }
    return 'dark';
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement | null>(null);
  const notificationsRef = useRef<HTMLDivElement | null>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (userMenuOpen && userMenuRef.current && !userMenuRef.current.contains(target)) {
        setUserMenuOpen(false);
      }
      if (notificationsOpen && notificationsRef.current && !notificationsRef.current.contains(target)) {
        setNotificationsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [userMenuOpen, notificationsOpen]);

  // Handle Enter on search input
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      navigate(`/clients?search=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
    }
  };

  // Sync theme changes to html data-theme and localStorage
  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('ignara_theme', nextTheme);
    localStorage.setItem('theme', nextTheme);
  };

  // Keyboard shortcut: ⌘K or Ctrl+K to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Format current date: e.g. "Tuesday, Nov 10"
  const formattedDate = new Intl.DateTimeFormat('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(new Date());

  // User initials & display name
  const displayName = currentUser?.name || currentUser?.email || 'Alex Rivera';
  const displayRole = currentUser?.is_demo ? 'Demo Sandbox' : 'Account Owner';
  const initials = displayName
    .split(' ')
    .map((n: string) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase() || 'AR';

  return (
    <header className="h-[68px] shrink-0 border-b border-[var(--line)] bg-[var(--side)]/80 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between gap-3 select-none z-30">
      {/* Mobile Menu Button (< 900px) */}
      <button
        onClick={onToggleMobileMenu}
        className="lg:hidden p-2 rounded-[12px] bg-[var(--card)] border border-[var(--line)] text-[var(--tx)] hover:border-[var(--o1)]/40 transition-colors cursor-pointer"
        aria-label="Open navigation drawer"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Search Pill (max 465px, hidden < 900px) */}
      <div className="hidden lg:flex items-center flex-1 max-w-[465px] relative">
        <div className="w-full relative flex items-center">
          <Search className="w-4 h-4 text-[var(--mu)] absolute left-3.5 pointer-events-none" />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search cashflow, clients, actions... (Press Enter)"
            className="w-full h-[40px] pl-10 pr-12 rounded-[999px] bg-[var(--side)] border border-[var(--line)] text-[var(--tx)] text-[13.5px] placeholder:text-[var(--dim)] focus:outline-none focus:border-[var(--o1)] focus:ring-1 focus:ring-[var(--o1)]/30 transition-all"
          />
          <kbd className="absolute right-3 inline-flex items-center justify-center h-5 px-1.5 rounded-[6px] text-[10.5px] font-mono text-[var(--dim)] bg-[var(--card)] border border-[var(--line)] pointer-events-none">
            ⌘K
          </kbd>
        </div>
      </div>

      {/* Flexible Spacer */}
      <div className="flex-1" />

      {/* Right Controls */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Date with glowing red dot (hidden < 900px) */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-[999px] bg-[var(--card)] border border-[var(--line)] text-[12.5px] font-medium text-[var(--mu)]">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--o2)] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--o2)]"></span>
          </span>
          <span>{formattedDate}</span>
        </div>

        {/* Regional Indicator Pill */}
        <Link
          to="/settings"
          className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[999px] bg-[var(--card)] border border-[var(--line)] text-[12px] font-medium text-[var(--tx)] hover:border-[var(--o1)]/40 transition-colors"
          title={`Country: ${countryName} (${country}), Preferred Currency: ${currency} (${currencySymbol})`}
        >
          <span className="text-[14px] leading-none">{flag}</span>
          <span>{currency}</span>
        </Link>

        {/* Reset Demo Button (if demo) */}
        {currentUser?.is_demo && onResetDemo && (
          <button
            onClick={onResetDemo}
            disabled={isResetting}
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-2 rounded-[14px] bg-[var(--card)] border border-[var(--line)] text-[12.5px] font-medium text-[var(--mu)] hover:text-[var(--tx)] hover:border-[var(--o1)]/40 transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
            title="Reset demo scenario"
          >
            <RotateCcw className={`w-3.5 h-3.5 text-[var(--o1)] ${isResetting ? 'animate-spin' : ''}`} />
            <span>Reset</span>
          </button>
        )}

        {/* Theme Toggle Square Button (46px, radius 14px) */}
        <button
          onClick={toggleTheme}
          className="w-[46px] h-[46px] rounded-[14px] bg-[var(--card)] border border-[var(--line)] text-[var(--tx)] flex items-center justify-center hover:border-[var(--o1)]/50 hover:text-[var(--o1)] transition-colors cursor-pointer shadow-2xs"
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? (
            <Sun className="w-5 h-5 text-[var(--y)]" strokeWidth={1.8} />
          ) : (
            <Moon className="w-5 h-5 text-[var(--o1)]" strokeWidth={1.8} />
          )}
        </button>

        {/* Notification Button with red count badge */}
        <div className="relative" ref={notificationsRef}>
          <button
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            className="w-[46px] h-[46px] rounded-[14px] bg-[var(--card)] border border-[var(--line)] text-[var(--tx)] flex items-center justify-center hover:border-[var(--o1)]/50 transition-colors relative cursor-pointer shadow-2xs"
            aria-label="View notifications"
          >
            <Bell className="w-5 h-5 text-[var(--mu)]" strokeWidth={1.8} />
            <span className="absolute top-2.5 right-2.5 w-2 h-2 rounded-full bg-[var(--r)] ring-2 ring-[var(--card)]"></span>
          </button>

          {/* Notifications Dropdown */}
          {notificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 rounded-[18px] bg-[var(--card)] border border-[var(--line)] shadow-xl p-3 z-50 ignara-card-enter">
              <div className="flex items-center justify-between pb-2 border-b border-[var(--line)]">
                <span className="text-[13px] font-semibold text-[var(--tx)]">Notifications</span>
                <span className="text-[11px] font-medium text-[var(--o1)]">Live</span>
              </div>
              <div className="py-2 space-y-2 text-xs">
                <Link
                  to="/inbox"
                  onClick={() => setNotificationsOpen(false)}
                  className="block p-2.5 rounded-[12px] bg-[var(--card2)] hover:border-[var(--o1)]/30 border border-transparent transition-all cursor-pointer text-left"
                >
                  <p className="font-medium text-[var(--tx)]">Plan A &bull; Early Payment Reminder</p>
                  <p className="text-[11px] text-[var(--mu)] mt-0.5">Apex Design Studio &bull; Awaiting Authorization</p>
                </Link>
                <Link
                  to="/whatif"
                  onClick={() => setNotificationsOpen(false)}
                  className="block p-2.5 rounded-[12px] bg-[var(--card2)] hover:border-[var(--o1)]/30 border border-transparent transition-all cursor-pointer text-left"
                >
                  <p className="font-medium text-[var(--tx)]">Cashflow Early-Warning Active</p>
                  <p className="text-[11px] text-[var(--mu)] mt-0.5">Friday contractor payout protected</p>
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* User Chip: 36px round avatar + name + role */}
        <div className="relative" ref={userMenuRef}>
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2.5 p-1.5 pr-3 rounded-[999px] bg-[var(--card)] border border-[var(--line)] hover:border-[var(--o1)]/40 transition-colors cursor-pointer text-left shadow-2xs"
          >
            {/* 36px round avatar */}
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center font-semibold text-xs text-white shrink-0 shadow-xs"
              style={{ background: 'var(--grad-ember)' }}
            >
              {initials}
            </div>

            <div className="hidden sm:flex flex-col min-w-0 pr-1">
              <span className="text-[13px] font-medium text-[var(--tx)] truncate max-w-[110px]">
                {displayName}
              </span>
              <span className="text-[10px] text-[var(--mu)] font-normal truncate">
                {displayRole}
              </span>
            </div>
          </button>

          {/* User Menu Dropdown */}
          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-[18px] bg-[var(--card)] border border-[var(--line)] shadow-xl p-2 z-50 ignara-card-enter">
              <div className="px-3 py-2 border-b border-[var(--line)] mb-1">
                <p className="text-xs font-semibold text-[var(--tx)] truncate">{displayName}</p>
                <p className="text-[11px] text-[var(--mu)] truncate">{currentUser?.email || 'alex@example.com'}</p>
              </div>

              <Link
                to="/settings"
                onClick={() => setUserMenuOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-[12.5px] text-[var(--tx)] hover:bg-[var(--card2)] transition-colors"
              >
                <SettingsIcon className="w-4 h-4 text-[var(--mu)]" />
                <span>Regional & Settings</span>
              </Link>

              {onResetDemo && currentUser?.is_demo && (
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    onResetDemo();
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-[12.5px] text-[var(--o1)] hover:bg-[var(--card2)] transition-colors text-left"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>Reset Demo Scenario</span>
                </button>
              )}

              {onLogout && (
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-[12.5px] text-[var(--r)] hover:bg-[var(--card2)] transition-colors text-left mt-1 border-t border-[var(--line)] pt-2"
                >
                  <LogOut className="w-4 h-4" />
                  <span>{currentUser?.is_demo ? 'Exit Demo Account' : 'Sign Out'}</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

