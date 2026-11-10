import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  Flame,
  Activity,
  Sliders,
  Bot,
  MessageSquare,
  Compass,
  Clock,
  Users,
  ShieldCheck,
  FileText,
  Settings,
  Plus,
  X,
  LucideIcon
} from 'lucide-react';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';

interface IgnaraSidebarProps {
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
  onNewAction?: () => void;
  pendingInboxCount?: number;
}

interface NavItemDef {
  id: string;
  path: string;
  label: string;
  icon: LucideIcon;
  badge?: string | number;
}

interface NavGroupDef {
  label: string;
  items: NavItemDef[];
}

export const IgnaraSidebar: React.FC<IgnaraSidebarProps> = ({
  isOpenMobile = false,
  onCloseMobile,
  onNewAction,
  pendingInboxCount = 2,
}) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { currencySymbol, formatCurrency } = useRegionalPreferences();

  const navGroups: NavGroupDef[] = [
    {
      label: 'INTELLIGENCE',
      items: [
        { id: 'dashboard', path: '/dashboard', label: 'Forecast', icon: Activity },
        { id: 'whatif', path: '/whatif', label: 'What-If', icon: Sliders },
        { id: 'supervisor', path: '/supervisor', label: 'Supervisor', icon: Bot },
      ],
    },
    {
      label: 'OPERATIONS',
      items: [
        { id: 'negotiation', path: '/negotiation', label: 'Negotiation', icon: MessageSquare },
        { id: 'resilience', path: '/resilience', label: 'Resilience', icon: Compass },
        { id: 'timeline', path: '/timeline', label: 'Timeline', icon: Clock },
        { id: 'clients', path: '/clients', label: 'Clients', icon: Users },
      ],
    },
    {
      label: 'GOVERNANCE',
      items: [
        { id: 'inbox', path: '/inbox', label: 'Inbox', icon: ShieldCheck, badge: pendingInboxCount },
        { id: 'audit', path: '/audit', label: 'Audit', icon: FileText },
        { id: 'settings', path: '/settings', label: 'Settings', icon: Settings },
      ],
    },
  ];

  // Map of item id to nav DOM element
  const itemRefs = useRef<Record<string, HTMLElement | null>>({});
  const navContainerRef = useRef<HTMLDivElement | null>(null);

  // Active pill state
  const [pillStyle, setPillStyle] = useState<{
    top: number;
    height: number;
    opacity: number;
    stretching?: boolean;
  }>({
    top: 0,
    height: 44,
    opacity: 0,
    stretching: false,
  });

  const isPathActive = (item: NavItemDef) => {
    const current = location.pathname;
    if (item.id === 'dashboard') {
      return (
        current === '/' ||
        current === '/dashboard' ||
        current === '/forecast' ||
        current === '/obligations' ||
        current === '/plans'
      );
    }
    if (item.id === 'whatif') {
      return current === '/whatif' || current === '/what-if';
    }
    if (item.id === 'supervisor') {
      return current === '/supervisor';
    }
    if (item.id === 'negotiation') {
      return current === '/negotiation' || current === '/negotiations';
    }
    if (item.id === 'resilience') {
      return current === '/resilience';
    }
    if (item.id === 'timeline') {
      return current === '/timeline';
    }
    if (item.id === 'clients') {
      return current === '/clients' || current === '/invoices';
    }
    if (item.id === 'inbox') {
      return current === '/inbox' || current === '/approvals';
    }
    if (item.id === 'audit') {
      return current === '/audit';
    }
    if (item.id === 'settings') {
      return current === '/settings' || current === '/setting';
    }
    return current === item.path;
  };

  const activeItem = navGroups
    .flatMap((g) => g.items)
    .find((item) => isPathActive(item));

  useEffect(() => {
    if (!activeItem || !navContainerRef.current) return;
    const el = itemRefs.current[activeItem.id];
    if (el) {
      const containerRect = navContainerRef.current.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      const newTop = elRect.top - containerRect.top + navContainerRef.current.scrollTop;
      const newHeight = elRect.height;

      // Stretch animation trigger
      setPillStyle((prev) => ({
        top: newTop,
        height: newHeight,
        opacity: 1,
        stretching: Math.abs(prev.top - newTop) > 10,
      }));

      const timer = setTimeout(() => {
        setPillStyle((prev) => ({ ...prev, stretching: false }));
      }, 520);

      return () => clearTimeout(timer);
    }
  }, [location.pathname, activeItem]);

  // Listen to 'n' shortcut for New action
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // ignore if inside an input or textarea
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName)) {
        return;
      }
      if (e.key === 'n' || e.key === 'N') {
        if (!e.metaKey && !e.ctrlKey && !e.altKey) {
          e.preventDefault();
          if (onNewAction) {
            onNewAction();
          } else {
            navigate('/whatif');
          }
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigate, onNewAction]);

  const handleNavClick = (path: string) => {
    navigate(path);
    if (onCloseMobile) onCloseMobile();
  };

  const handleNewClick = () => {
    if (onNewAction) {
      onNewAction();
    } else {
      navigate('/whatif');
    }
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs lg:hidden transition-opacity"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed lg:static top-0 bottom-0 left-0 z-50 w-[276px] shrink-0 bg-[var(--side)] border-r border-[var(--line)] p-[18px] flex flex-col justify-between transition-transform duration-300 ease-[var(--ease-ignara)] ${
          isOpenMobile ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'
        }`}
        style={{ height: '100%' }}
      >
        <div className="flex flex-col h-full overflow-hidden">
          {/* a) Brand Logo + App Name */}
          <div className="flex items-center justify-between pb-4">
            <Link
              to="/dashboard"
              onClick={onCloseMobile}
              className="flex items-center gap-3 group text-left"
            >
              <div
                className="w-[42px] h-[42px] rounded-[12px] flex items-center justify-center text-white shrink-0 shadow-md group-hover:scale-105 transition-transform"
                style={{ background: 'var(--grad-ember)' }}
              >
                <Flame className="w-5 h-5 text-white fill-white/20" strokeWidth={2.2} />
              </div>
              <div className="flex flex-col">
                <span className="text-[20px] font-semibold leading-tight tracking-tight text-[var(--tx)]">
                  Cashflow
                </span>
                <span className="text-[12px] font-normal text-[var(--mu)] leading-none mt-0.5">
                  Autonomous Lifeline
                </span>
              </div>
            </Link>

            {/* Mobile Close Button */}
            {onCloseMobile && (
              <button
                type="button"
                onClick={onCloseMobile}
                className="lg:hidden p-1.5 text-[var(--mu)] hover:text-[var(--tx)] hover:bg-[var(--card)] rounded-lg transition-colors cursor-pointer"
                aria-label="Close menu"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* b) "New" outlined pill button */}
          <div className="py-2.5">
            <button
              type="button"
              onClick={handleNewClick}
              className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-[999px] border border-[var(--line)] bg-[var(--side)] hover:bg-[var(--card)] text-[var(--tx)] transition-all duration-200 group cursor-pointer shadow-2xs"
            >
              <div className="flex items-center gap-2 text-[13.5px] font-medium">
                <Plus className="w-4 h-4 text-[var(--o1)] group-hover:rotate-90 transition-transform duration-200" />
                <span>New Simulation</span>
              </div>
              <kbd className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-[6px] text-[11px] font-mono font-medium text-[var(--dim)] bg-[var(--card)] border border-[var(--line)] group-hover:border-[var(--o1)]/40 group-hover:text-[var(--tx)] transition-colors">
                N
              </kbd>
            </button>
          </div>

          {/* c & d) Nav Groups with Sliding Ember Pill */}
          <div
            ref={navContainerRef}
            className="relative flex-1 overflow-y-auto no-scrollbar py-2 space-y-4"
          >
            {/* Sliding Ember Gradient Pill */}
            <div
              className="absolute left-0 right-0 pointer-events-none rounded-[14px] transition-all duration-500 ease-[cubic-bezier(0.2,0.8,0.2,1)]"
              style={{
                top: `${pillStyle.top}px`,
                height: `${pillStyle.height}px`,
                opacity: pillStyle.opacity,
                background: 'var(--grad-ember)',
                boxShadow: 'var(--shadow-nav-active)',
                transform: pillStyle.stretching ? 'scaleY(1.08)' : 'scaleY(1)',
                zIndex: 0,
              }}
            />

            {navGroups.map((group) => (
              <div key={group.label} className="space-y-1">
                {/* Uppercase group label */}
                <div className="px-3 text-[11px] font-semibold tracking-[0.12em] uppercase text-[var(--dim)] mb-1">
                  {group.label}
                </div>

                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = isPathActive(item);

                  return (
                    <Link
                      key={item.id}
                      to={item.path}
                      ref={(el) => (itemRefs.current[item.id] = el)}
                      onClick={() => {
                        if (onCloseMobile) onCloseMobile();
                      }}
                      className={`relative z-10 w-full flex items-center justify-between px-3 py-2.5 rounded-[14px] text-[13.5px] font-medium transition-colors duration-200 text-left cursor-pointer group ${
                        isActive
                          ? 'text-white'
                          : 'text-[var(--mu)] hover:text-[var(--tx)] hover:bg-[var(--card)]'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon
                          className={`w-[18px] h-[18px] shrink-0 transition-colors ${
                            isActive ? 'text-white' : 'text-[var(--mu)] group-hover:text-[var(--tx)]'
                          }`}
                          strokeWidth={1.7}
                        />
                        <span>{item.label}</span>
                      </div>

                      {item.badge !== undefined && (
                        <span
                          className={`text-[11px] font-semibold px-2 py-0.5 rounded-full transition-colors ${
                            isActive
                              ? 'bg-white/20 text-white'
                              : 'bg-[var(--card)] text-[var(--dim)] group-hover:text-[var(--mu)]'
                          }`}
                        >
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            ))}
          </div>

          {/* e) Bottom Card: "Today so far" */}
          <div className="pt-3">
            <div className="p-3.5 rounded-[18px] bg-[var(--card)] border border-[var(--line)] flex items-center gap-3">
              {/* Conic-gradient 44px progress ring */}
              <div
                className="w-11 h-11 rounded-full shrink-0 flex items-center justify-center p-[3px] relative shadow-inner"
                style={{
                  background: 'conic-gradient(var(--o1) 0% 72%, var(--line) 72% 100%)',
                }}
              >
                <div className="w-full h-full rounded-full bg-[var(--card)] flex items-center justify-center text-[10px] font-bold text-[var(--tx)]">
                  72%
                </div>
              </div>

              <div className="flex flex-col min-w-0">
                <span className="text-[11px] uppercase font-semibold tracking-wider text-[var(--dim)]">
                  Today so far
                </span>
                <span className="text-[14px] font-semibold text-[var(--tx)] truncate">
                  {formatCurrency(1800)}
                </span>
                <span className="text-[10px] text-[var(--mu)] truncate">
                  Goal: {formatCurrency(2500)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
