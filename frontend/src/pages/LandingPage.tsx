import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Lock,
  ChevronDown,
  Layers,
  Bot,
  Zap,
  Sliders,
  FileText,
  DollarSign,
  Menu,
  X,
  Play,
  LogOut,
  UserCheck,
  Flame
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useRegionalPreferences } from '../context/RegionalPreferencesContext';
import { RegionalFooterSelector } from '../components/RegionalFooterSelector';

export const LandingPage: React.FC = () => {
  const { formatCurrency } = useRegionalPreferences();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);
  const [demoLoading, setDemoLoading] = useState(false);
  const { currentUser, logout, demoLogin } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore
    } finally {
      window.location.reload();
    }
  };

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

  const handleLaunchDemo = async () => {
    try {
      setDemoLoading(true);
      await demoLogin();
      navigate('/dashboard');
    } catch {
      // ignore
    } finally {
      setDemoLoading(false);
    }
  };

  const toggleFaq = (index: number) => {
    setOpenFaqIndex(openFaqIndex === index ? null : index);
  };

  const faqItems = [
    {
      q: 'What is Cashflow Lifeline?',
      a: 'Cashflow Lifeline is an intelligent cashflow forecasting and financial rescue platform. It finds the specific upcoming payment a PayPal-paid freelancer or business is about to miss, compares the cheapest ways to protect it, and prepares verified rescue actions that only execute with your explicit approval.'
    },
    {
      q: 'Who should use it?',
      a: 'Freelancers, independent contractors, creative agencies, and small businesses who receive client payments via PayPal and face fixed recurring expenses such as contractor payouts, payroll, rent, and software subscriptions.'
    },
    {
      q: 'How does cashflow forecasting work?',
      a: 'Cashflow Lifeline analyzes historical client invoice settlement latency using a statistical hazard rate model. Instead of naively assuming clients pay on their due date, it projects empirical delay probabilities to simulate 14-day cash trajectories and identify shortfall cliffs days in advance.'
    },
    {
      q: 'Does it guarantee payments?',
      a: 'No platform can guarantee third-party client settlements. Cashflow Lifeline provides probabilistic forecasting, empirical delay modeling, and actionable contingency plans (such as automated early-payment discount incentives or contractor split payouts) so you never discover a shortfall at the last minute.'
    },
    {
      q: 'How does PayPal integration work?',
      a: 'The application integrates directly with the PayPal REST API to inspect invoice statuses, generate invoice pay links with early-payment discounts, and stage contractor payouts via PayPal Payouts. All actions remain in a draft state until you approve them.'
    },
    {
      q: 'Can I approve or reject recommendations?',
      a: 'Yes. Cashflow Lifeline enforces strict deterministic human-in-the-loop safeguards. No money is ever moved, and no invoices or discounts are dispatched without your cryptographic approval in the Approval Inbox.'
    },
    {
      q: 'Is my financial information private?',
      a: 'Yes. Each user account operates with an isolated database tenant. User passwords are encrypted with bcrypt, sessions are signed with ephemeral JWTs, and your client and obligation records are strictly query-filtered by your authenticated owner ID.'
    },
    {
      q: 'Is the current application using PayPal Sandbox or Live?',
      a: 'Cashflow Lifeline currently operates strictly in the PayPal Sandbox environment. This allows complete end-to-end testing of live webhooks, invoice generation, discount incentives, and payout executions without real financial risk.'
    }
  ];

  return (
    <div className="min-h-screen bg-ink-950 text-white font-sans selection:bg-electric selection:text-white">
      {/* 1. Navigation Bar */}
      <nav className="border-b border-ink-800/80 bg-ink-950/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 sm:h-20">
            {/* Logo */}
            <div className="flex items-center space-x-3">
              <Link to="/" className="flex items-center space-x-2.5">
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center text-white shadow-md shrink-0"
                  style={{ background: 'linear-gradient(135deg, var(--o1), var(--o2))' }}
                >
                  <Flame className="w-5 h-5 fill-white/20 text-white" />
                </div>
                <div className="flex flex-col">
                  <span className="font-extrabold text-base tracking-tight text-white flex items-center gap-1.5">
                    Cashflow Lifeline
                    <span
                      className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border"
                      style={{
                        backgroundColor: 'rgba(251, 124, 60, 0.15)',
                        color: 'var(--o1)',
                        borderColor: 'rgba(251, 124, 60, 0.3)'
                      }}
                    >
                      PayPal AI
                    </span>
                  </span>
                  <span className="text-[10px] text-sardine-muted hidden sm:block">
                    Fintech Early-Warning & Rescue Platform
                  </span>
                </div>
              </Link>
            </div>

            {/* Desktop Nav Items */}
            <div className="hidden md:flex items-center space-x-8 text-sm font-medium text-slate-300">
              <a href="#features" className="hover:text-white transition-colors">Features</a>
              <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
              <a href="#preview" className="hover:text-white transition-colors">Product Demo</a>
              <a href="#security" className="hover:text-white transition-colors">Security</a>
              <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
            </div>

            {/* Right Action Buttons */}
            <div className="hidden md:flex items-center space-x-3">
              {currentUser ? (
                <>
                  <div className="flex items-center space-x-1.5 px-3 py-1.5 bg-ink-900 border border-slate-700 rounded-lg text-xs font-semibold">
                    <UserCheck className="w-3.5 h-3.5 text-electric shrink-0" />
                    <span className="text-white truncate max-w-[120px]">{currentUser.name || currentUser.email}</span>
                    {currentUser.is_demo && (
                      <span className="text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold px-1 rounded-sm">
                        DEMO
                      </span>
                    )}
                  </div>
                  <Link
                    to="/dashboard"
                    className="px-3.5 py-2 rounded-lg text-xs font-semibold ignara-btn-primary text-white shadow-glow-electric transition-all flex items-center space-x-1"
                  >
                    <span>Dashboard</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="px-3 py-2 rounded-lg text-xs font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30 hover:bg-rose-500/25 transition-all flex items-center space-x-1 cursor-pointer"
                    title={currentUser.is_demo ? 'Exit Demo Account' : 'Sign Out Account'}
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>{currentUser.is_demo ? 'Exit Demo' : 'Sign Out'}</span>
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={handleLaunchDemo}
                    disabled={demoLoading}
                    className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-ink-800 text-electric-300 border border-electric/30 hover:bg-ink-700 hover:border-electric transition-all flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
                  >
                    <Play className="w-3 h-3 fill-electric-300" />
                    <span>{demoLoading ? 'Starting...' : 'Explore Demo'}</span>
                  </button>
                  <Link
                    to="/login"
                    className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-200 hover:text-white hover:bg-ink-800 transition-colors"
                  >
                    Sign In
                  </Link>
                  <Link
                    to="/register"
                    className="px-4 py-2 rounded-lg text-xs font-semibold ignara-btn-primary text-white shadow-glow-electric transition-all flex items-center space-x-1"
                  >
                    <span>Get Started Free</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </>
              )}
            </div>

            {/* Mobile Menu Toggle */}
            <div className="flex md:hidden items-center space-x-2">
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="w-10 h-10 flex items-center justify-center rounded-lg text-slate-400 hover:text-white hover:bg-ink-900 focus:outline-none transition-colors"
                aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-b border-ink-800 bg-ink-900/98 backdrop-blur-xl px-4 pt-3 pb-6 space-y-4 animate-fadeIn">
            <div className="flex flex-col space-y-1 text-sm font-medium text-slate-300">
              <a href="#features" onClick={() => setMobileMenuOpen(false)} className="py-2.5 px-3 rounded-lg hover:bg-ink-800/80 hover:text-white transition-colors">Features</a>
              <a href="#how-it-works" onClick={() => setMobileMenuOpen(false)} className="py-2.5 px-3 rounded-lg hover:bg-ink-800/80 hover:text-white transition-colors">How It Works</a>
              <a href="#preview" onClick={() => setMobileMenuOpen(false)} className="py-2.5 px-3 rounded-lg hover:bg-ink-800/80 hover:text-white transition-colors">Product Demo</a>
              <a href="#security" onClick={() => setMobileMenuOpen(false)} className="py-2.5 px-3 rounded-lg hover:bg-ink-800/80 hover:text-white transition-colors">Security</a>
              <a href="#faq" onClick={() => setMobileMenuOpen(false)} className="py-2.5 px-3 rounded-lg hover:bg-ink-800/80 hover:text-white transition-colors">FAQ</a>
            </div>
            <div className="pt-3 border-t border-ink-800 flex flex-col space-y-2.5">
              {currentUser ? (
                <>
                  <div className="flex items-center space-x-2 px-3 py-2 bg-ink-950 rounded-xl text-xs border border-slate-800">
                    <UserCheck className="w-4 h-4 text-electric shrink-0" />
                    <span className="text-white font-semibold truncate flex-1">{currentUser.name || currentUser.email}</span>
                    {currentUser.is_demo && (
                      <span className="text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold px-1.5 py-0.5 rounded">
                        DEMO
                      </span>
                    )}
                  </div>
                  <Link
                    to="/dashboard"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full py-3 rounded-xl text-xs font-semibold ignara-btn-primary text-white text-center shadow-glow-electric min-h-[44px] flex items-center justify-center space-x-2"
                  >
                    <span>Go to Dashboard</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                  <button
                    onClick={() => {
                      setMobileMenuOpen(false);
                      handleLogout();
                    }}
                    className="w-full py-3 rounded-xl text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 text-center min-h-[44px] flex items-center justify-center space-x-2"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>{currentUser.is_demo ? 'Exit Demo Sandbox' : 'Sign Out Account'}</span>
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => { setMobileMenuOpen(false); handleLaunchDemo(); }}
                    disabled={demoLoading}
                    className="w-full py-3 rounded-xl text-xs font-semibold bg-ink-800 text-electric-300 border border-electric/30 text-center min-h-[44px] flex items-center justify-center"
                  >
                    {demoLoading ? 'Launching Demo...' : 'Explore Demo (Alex Morgan Persona)'}
                  </button>
                  <div className="grid grid-cols-2 gap-2">
                    <Link
                      to="/login"
                      onClick={() => setMobileMenuOpen(false)}
                      className="py-3 rounded-xl text-xs font-semibold bg-ink-800 text-white text-center border border-slate-700 min-h-[44px] flex items-center justify-center"
                    >
                      Sign In
                    </Link>
                    <Link
                      to="/register"
                      onClick={() => setMobileMenuOpen(false)}
                      className="py-3 rounded-xl text-xs font-semibold ignara-btn-primary text-white text-center shadow-glow-electric min-h-[44px] flex items-center justify-center"
                    >
                      Get Started
                    </Link>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </nav>

      {/* 2. Hero Section */}
      <section className="relative overflow-hidden pt-8 pb-16 sm:pt-12 sm:pb-20 lg:pt-20 lg:pb-28">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(251,124,60,0.15),rgba(255,255,255,0))]" />
        
        <div className="max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8 relative z-10">
          <div className="max-w-3xl mx-auto text-center space-y-5 sm:space-y-6">
            <div
              className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full border text-xs font-medium"
              style={{
                backgroundColor: 'rgba(251, 124, 60, 0.1)',
                borderColor: 'rgba(251, 124, 60, 0.3)',
                color: 'var(--o1)'
              }}
            >
              <Sparkles className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">PayPal AI Hackathon 2026 &bull; Build What&rsquo;s Next</span>
            </div>

            <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-[1.15] sm:leading-[1.1]">
              Stay Ahead of Cashflow. <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 via-amber-300 to-rose-400">
                Never Be Surprised by a Shortfall.
              </span>
            </h1>

            <p className="text-sm sm:text-base lg:text-lg text-slate-300 leading-relaxed max-w-2xl mx-auto font-normal">
              Cashflow Lifeline helps freelancers and small businesses predict payment delays, identify upcoming cash shortages and explore intelligent financial rescue strategies before problems become emergencies.
            </p>

            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
              <Link
                to="/register"
                className="w-full sm:w-auto px-7 py-3.5 rounded-xl font-bold text-sm ignara-btn-primary text-white shadow-glow-electric transition-all flex items-center justify-center space-x-2 min-h-[44px]"
              >
                <span>Get Started Free</span>
                <ArrowRight className="w-4 h-4 shrink-0" />
              </Link>
              <button
                onClick={handleLaunchDemo}
                disabled={demoLoading}
                className="w-full sm:w-auto px-6 py-3.5 rounded-xl font-semibold text-sm bg-ink-900 text-white border border-slate-700 hover:border-electric hover:bg-ink-800 transition-all flex items-center justify-center space-x-2 min-h-[44px]"
              >
                <Play className="w-3.5 h-3.5 fill-electric-300 text-electric-300 shrink-0" />
                <span>{demoLoading ? 'Starting Demo...' : 'Explore Demo Sandbox'}</span>
              </button>
              <a
                href="#how-it-works"
                className="w-full sm:w-auto px-5 py-3.5 rounded-xl font-semibold text-sm text-slate-300 hover:text-white transition-colors flex items-center justify-center min-h-[44px]"
              >
                Explore How It Works &darr;
              </a>
            </div>

            <p className="text-xs text-sardine-muted pt-1">
              No credit card required &bull; Works with PayPal Sandbox &bull; Strict multi-tenant isolation
            </p>
          </div>

          {/* Hero Dashboard Preview (Clearly Labeled Sample Data) */}
          <div id="preview" className="scroll-mt-24 sm:scroll-mt-28 mt-10 sm:mt-14 lg:mt-20 relative max-w-5xl mx-auto">
            {/* Sample Data Disclaimer Badge */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 px-1 sm:px-2">
              <div className="flex items-center space-x-2">
                <span className="flex h-2 w-2 relative shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-[11px] font-mono uppercase tracking-wider text-sardine-muted">
                  Interactive Platform Preview
                </span>
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md bg-amber-500/15 text-amber-300 border border-amber-500/30 self-start sm:self-auto">
                Sample Data &mdash; Demonstration Only
              </span>
            </div>

            {/* Dashboard Card Container */}
            <div className="rounded-2xl border border-ink-700 bg-ink-900/95 backdrop-blur-xl shadow-2xl p-3.5 sm:p-6 lg:p-8 space-y-4 sm:space-y-6">
              {/* Header metrics row */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
                <div className="bg-ink-950 p-4 rounded-xl border border-ink-800">
                  <div className="text-[11px] font-mono text-sardine-muted uppercase tracking-wider">
                    Available Balance
                  </div>
                  <div className="text-2xl font-black text-white mt-1">{formatCurrency(1800)}</div>
                  <div className="text-[10px] text-emerald-400 mt-1 flex items-center space-x-1">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>PayPal Sandbox Confirmed</span>
                  </div>
                </div>

                <div className="bg-ink-950 p-4 rounded-xl border border-ink-800">
                  <div className="text-[11px] font-mono text-sardine-muted uppercase tracking-wider">
                    Target Obligation
                  </div>
                  <div className="text-2xl font-black text-slate-100 mt-1">{formatCurrency(2200)}</div>
                  <div className="text-[10px] text-amber-400 mt-1 flex items-center space-x-1">
                    <Clock className="w-3 h-3" />
                    <span>Contractor due Friday Nov 14</span>
                  </div>
                </div>

                <div className="bg-red-950/40 p-4 rounded-xl border border-red-500/40">
                  <div className="text-[11px] font-mono text-red-300 uppercase tracking-wider flex items-center space-x-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>Projected Shortfall</span>
                  </div>
                  <div className="text-2xl font-black text-red-400 mt-1">-{formatCurrency(400)}</div>
                  <div className="text-[10px] text-red-300 mt-1">
                    Apex Labs invoice likely 5 days late
                  </div>
                </div>

                <div className="bg-electric-950/40 p-4 rounded-xl border border-electric-500/40">
                  <div className="text-[11px] font-mono text-electric-300 uppercase tracking-wider flex items-center space-x-1">
                    <TrendingUp className="w-3 h-3" />
                    <span>Financial Resilience</span>
                  </div>
                  <div className="text-2xl font-black text-electric-300 mt-1">72 / 100</div>
                  <div className="text-[10px] text-slate-300 mt-1">
                    Moderate &bull; 8 days runway
                  </div>
                </div>
              </div>

              {/* At-risk banner & AI plan preview */}
              <div className="bg-ink-950 rounded-xl p-5 border border-ink-800 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-ink-800">
                  <div>
                    <span className="text-xs font-bold text-electric uppercase tracking-wider">
                      Forecaster Agent Alert
                    </span>
                    <h3 className="text-base font-bold text-white mt-0.5">
                      Shortfall Alert: {formatCurrency(2200)} Contractor Payout at Risk on Friday
                    </h3>
                  </div>
                  <span className="inline-flex items-center text-xs px-2.5 py-1 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-mono">
                    84% probability of shortfall
                  </span>
                </div>

                {/* Rescue Plans Comparison Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                  {/* Plan A */}
                  <div className="rounded-xl border border-electric/40 bg-ink-900/80 p-4 relative">
                    <div className="absolute -top-2.5 right-3 bg-electric text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
                      Recommended &bull; Cheapest
                    </div>
                    <div className="font-bold text-sm text-white">Plan A: 3% Client Early-Payment Discount</div>
                    <p className="text-xs text-sardine-muted mt-1">
                      Offer Apex Labs a 3% discount ({formatCurrency(90)} savings) to settle their {formatCurrency(3000)} invoice 5 days early via PayPal.
                    </p>
                    <div className="mt-3 pt-3 border-t border-ink-800 flex items-center justify-between text-xs">
                      <span className="text-slate-400">Total Net Cost:</span>
                      <span className="font-mono font-bold text-emerald-400">{formatCurrency(90)} (vs {formatCurrency(180)} interest)</span>
                    </div>
                  </div>

                  {/* Plan B */}
                  <div className="rounded-xl border border-ink-800 bg-ink-900/50 p-4">
                    <div className="font-bold text-sm text-white">Plan B: Contractor Payout Split</div>
                    <p className="text-xs text-sardine-muted mt-1">
                      Pay {formatCurrency(1500)} on Friday Nov 14 and stage the remaining {formatCurrency(700)} for Tuesday Nov 18 upon client receipt.
                    </p>
                    <div className="mt-3 pt-3 border-t border-ink-800 flex items-center justify-between text-xs">
                      <span className="text-slate-400">Total Net Cost:</span>
                      <span className="font-mono font-bold text-slate-200">{formatCurrency(0)} (Preserves cash buffer)</span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 flex items-center justify-between text-xs text-sardine-muted">
                  <div className="flex items-center space-x-1.5">
                    <ShieldCheck className="w-4 h-4 text-electric" />
                    <span>Deterministic Guardrails: Execution requires your explicit signature in the Approval Inbox.</span>
                  </div>
                  <Link to="/register" className="text-electric hover:underline font-semibold hidden sm:inline">
                    Simulate your business &rarr;
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Problem Section */}
      <section className="py-20 bg-ink-900/60 border-y border-ink-800">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl mx-auto text-center space-y-4 mb-16">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-electric-400">
              The Reality of Freelance Cashflow
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white">
              Profitable on Paper. Empty in the Account.
            </h2>
            <p className="text-sm sm:text-base text-slate-300">
              Why traditional accounting dashboards fail independent businesses when timing mismatches occur.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800/80 space-y-3">
              <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 font-bold">
                01
              </div>
              <h3 className="font-bold text-base text-white">Clients Pay 5&ndash;14 Days Late</h3>
              <p className="text-xs text-sardine-muted leading-relaxed">
                Even reliable enterprise clients frequently settle invoices after their due dates due to internal approval loops and international wire processing.
              </p>
            </div>

            <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800/80 space-y-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 font-bold">
                02
              </div>
              <h3 className="font-bold text-base text-white">Obligations Have Fixed Dates</h3>
              <p className="text-xs text-sardine-muted leading-relaxed">
                Contractors, payroll, SaaS tools, and taxes cannot wait for overdue receivables. Missing a contractor payout damages critical partnerships.
              </p>
            </div>

            <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800/80 space-y-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 font-bold">
                03
              </div>
              <h3 className="font-bold text-base text-white">Balances Look Deceptively Healthy</h3>
              <p className="text-xs text-sardine-muted leading-relaxed">
                Your PayPal balance looks adequate right up until multiple payouts collide, leaving no time to arrange contingency bridge capital.
              </p>
            </div>

            <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800/80 space-y-3">
              <div className="w-10 h-10 rounded-xl bg-electric/10 border border-electric/20 flex items-center justify-center text-electric-300 font-bold">
                04
              </div>
              <h3 className="font-bold text-base text-white">Decisions Are Made in Panic</h3>
              <p className="text-xs text-sardine-muted leading-relaxed">
                Discovering a deficit on payout morning forces emergency high-cost credit cards or awkward client emails. Cashflow Lifeline predicts this days ahead.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Features Section (10 Verified Capabilities) */}
      <section id="features" className="scroll-mt-24 sm:scroll-mt-28 py-20 lg:py-28 max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mx-auto text-center space-y-4 mb-16">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-electric-400">
            Platform Capabilities
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white">
            10 Verifiable Fintech Innovations
          </h2>
          <p className="text-sm sm:text-base text-slate-300">
            Built from scratch for the PayPal AI Hackathon with zero mockups, live database persistence, and deterministic execution.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Feature 1 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <TrendingUp className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">1. AI Cashflow Forecasting</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Multi-horizon Monte Carlo and hazard-rate cash projections modeling 7, 14, and 30-day balance trajectories under real delay conditions.
            </p>
          </div>

          {/* Feature 2 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">2. Payment Delay Prediction</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Empirical Bayesian hazard modeling per client estimating settlement probabilities, variance intervals, and cold-start fallback profiles.
            </p>
          </div>

          {/* Feature 3 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">3. Early Shortfall Detection</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Identifies the exact upcoming obligation about to fail, calculates the deficit, and pinpoints the specific late invoice causing the cliff.
            </p>
          </div>

          {/* Feature 4 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <Zap className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">4. Intelligent Rescue Planning</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Compares fee-optimized solutions: early client payment discounts, contractor split payouts, and emergency lines with cost-benefit analysis.
            </p>
          </div>

          {/* Feature 5 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <Bot className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">5. Client Payment Behaviour Analysis</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Calculates payment regularity, relationship scores, and historical payment latency to prevent awkward friction with VIP clients.
            </p>
          </div>

          {/* Feature 6 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">6. Contractor Obligation Management</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Tracks mandatory contractor payouts, due dates, split eligibility, and payout priority with partial-payment ledger support.
            </p>
          </div>

          {/* Feature 7 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <DollarSign className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">7. PayPal Invoices & Payouts</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Direct REST API integration with PayPal Sandbox for invoice generation, pay links, and single-click staged contractor disbursements.
            </p>
          </div>

          {/* Feature 8 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <Lock className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">8. Approval-Based Guardrails</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Deterministic state machine with human-in-the-loop approvals. No action executes without cryptographic payload hash confirmation.
            </p>
          </div>

          {/* Feature 9 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all">
            <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">9. Financial Audit Trail</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Tamper-evident Merkle hash chain linking all system events, AI predictions, owner approvals, and PayPal webhook execution receipts.
            </p>
          </div>

          {/* Feature 10 */}
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3 hover:border-electric/50 transition-all md:col-span-2 lg:col-span-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-electric/15 text-electric flex items-center justify-center shrink-0">
                  <Sliders className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">10. What-If Financial Simulation Engine</h3>
                  <p className="text-xs text-sardine-muted mt-0.5">
                    Test complex scenarios before committing: simulated 10-day client delays, unexpected emergencies, and partial settlements.
                  </p>
                </div>
              </div>
              <Link
                to="/register"
                className="px-4 py-2 rounded-lg bg-ink-800 hover:bg-ink-700 text-xs font-semibold text-white border border-slate-700 shrink-0 self-start sm:self-auto"
              >
                Try In App &rarr;
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 5. How It Works (5-Step Workflow) */}
      <section id="how-it-works" className="scroll-mt-24 sm:scroll-mt-28 py-20 bg-ink-900/60 border-y border-ink-800">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl mx-auto text-center space-y-4 mb-16">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-electric-400">
              The Rescue Workflow
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white">
              From Prediction to Protection in 5 Steps
            </h2>
            <p className="text-sm sm:text-base text-slate-300">
              How Cashflow Lifeline safeguards your obligations without taking autonomy away from the owner.
            </p>
          </div>

          <div className="relative">
            {/* Connecting line */}
            <div className="hidden lg:block absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-electric/10 via-electric to-electric/10 -translate-y-8" />

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 relative z-10">
              <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800 space-y-3">
                <div className="w-8 h-8 rounded-full bg-electric text-white text-xs font-bold flex items-center justify-center font-mono">
                  1
                </div>
                <h4 className="font-bold text-sm text-white">Connect &amp; Ingest</h4>
                <p className="text-xs text-sardine-muted leading-relaxed">
                  Connect your PayPal Sandbox account or enter clients and obligations via the guided dashboard.
                </p>
              </div>

              <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800 space-y-3">
                <div className="w-8 h-8 rounded-full bg-electric text-white text-xs font-bold flex items-center justify-center font-mono">
                  2
                </div>
                <h4 className="font-bold text-sm text-white">Analyze History</h4>
                <p className="text-xs text-sardine-muted leading-relaxed">
                  The model analyzes settlement patterns to establish each client&rsquo;s empirical payment hazard curve.
                </p>
              </div>

              <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800 space-y-3">
                <div className="w-8 h-8 rounded-full bg-electric text-white text-xs font-bold flex items-center justify-center font-mono">
                  3
                </div>
                <h4 className="font-bold text-sm text-white">Predict Shortfalls</h4>
                <p className="text-xs text-sardine-muted leading-relaxed">
                  Simulates daily cash balance and flags any upcoming obligation that drops into deficit territory.
                </p>
              </div>

              <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800 space-y-3">
                <div className="w-8 h-8 rounded-full bg-electric text-white text-xs font-bold flex items-center justify-center font-mono">
                  4
                </div>
                <h4 className="font-bold text-sm text-white">Compare Plans</h4>
                <p className="text-xs text-sardine-muted leading-relaxed">
                  The Planner Agent synthesizes fee-optimized rescue plans comparing discount costs vs split payouts.
                </p>
              </div>

              <div className="bg-ink-950 p-6 rounded-2xl border border-ink-800 space-y-3">
                <div className="w-8 h-8 rounded-full bg-electric text-white text-xs font-bold flex items-center justify-center font-mono">
                  5
                </div>
                <h4 className="font-bold text-sm text-white">Approve &amp; Track</h4>
                <p className="text-xs text-sardine-muted leading-relaxed">
                  Review and cryptographically approve actions. PayPal executes them, and the Merkle log verifies the ledger.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-12 text-center">
            <span className="text-xs text-sardine-muted font-mono bg-ink-950 px-4 py-2 rounded-full border border-ink-800 inline-block">
              &bull; Strict Distinction: Probabilistic forecasts are clearly differentiated from confirmed ledger settlements &bull;
            </span>
          </div>
        </div>
      </section>

      {/* 6. Security Section */}
      <section id="security" className="scroll-mt-24 sm:scroll-mt-28 py-20 lg:py-28 max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mx-auto text-center space-y-4 mb-16">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-400">
            Safety &amp; Compliance Standards
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white">
            Fintech Architecture Safeguards
          </h2>
          <p className="text-sm sm:text-base text-slate-300">
            We state our technical safeguards truthfully without exaggerated claims or fake certifications.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3">
            <ShieldCheck className="w-6 h-6 text-emerald-400" />
            <h3 className="font-bold text-white text-base">Individual User Accounts</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Strict multi-tenant database separation. Every query is filtered by authenticated owner ID. Registered accounts never see demo or peer data.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3">
            <Lock className="w-6 h-6 text-emerald-400" />
            <h3 className="font-bold text-white text-base">Approval-First Safeguards</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              No financial action or payout is dispatched autonomously. AI recommends; human approves with cryptographic payload verification.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3">
            <FileText className="w-6 h-6 text-emerald-400" />
            <h3 className="font-bold text-white text-base">Merkle-Chained Audit Trail</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Every state transition and approval is hashed into a SHA-256 forward-linked chain that detects any unauthorized ledger tampering.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3">
            <Zap className="w-6 h-6 text-emerald-400" />
            <h3 className="font-bold text-white text-base">Verified PayPal Webhooks</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Webhook events undergo HMAC and API verification before recording incoming settlements to prevent balance spoofing.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3">
            <Lock className="w-6 h-6 text-emerald-400" />
            <h3 className="font-bold text-white text-base">Credential Security &amp; Rate Limiting</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              Passwords hashed with bcrypt, access tokens enforce short TTLs with rotating refresh tokens, and authentication enforces brute-force lockout.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-ink-900 border border-ink-800 space-y-3">
            <AlertTriangle className="w-6 h-6 text-amber-400" />
            <h3 className="font-bold text-white text-base">PayPal Sandbox Environment</h3>
            <p className="text-xs text-sardine-muted leading-relaxed">
              For security during evaluation, Cashflow Lifeline strictly connects to official PayPal Sandbox developer endpoints to ensure zero real capital loss.
            </p>
          </div>
        </div>
      </section>

      {/* 7. FAQ Section */}
      <section id="faq" className="scroll-mt-24 sm:scroll-mt-28 py-20 bg-ink-900/60 border-y border-ink-800">
        <div className="max-w-[1000px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center space-y-4 mb-14">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-electric-400">
              Frequently Asked Questions
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white">
              Questions &amp; Answers
            </h2>
            <p className="text-sm text-slate-300">
              Clear, honest explanations of how Cashflow Lifeline operates.
            </p>
          </div>

          <div className="space-y-3">
            {faqItems.map((item, index) => {
              const isOpen = openFaqIndex === index;
              return (
                <div
                  key={index}
                  className="rounded-xl border border-ink-800 bg-ink-950 overflow-hidden transition-all"
                >
                  <button
                    onClick={() => toggleFaq(index)}
                    className="w-full text-left px-5 py-4 flex items-center justify-between text-sm sm:text-base font-semibold text-white hover:text-electric transition-colors"
                  >
                    <span>{item.q}</span>
                    <ChevronDown
                      className={`w-4 h-4 text-sardine-muted shrink-0 transition-transform duration-200 ${
                        isOpen ? 'transform rotate-180 text-electric' : ''
                      }`}
                    />
                  </button>
                  {isOpen && (
                    <div className="px-5 pb-5 text-xs sm:text-sm text-sardine-muted leading-relaxed border-t border-ink-800/60 pt-3">
                      {item.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* 8. Bottom CTA Banner */}
      <section className="py-12 sm:py-20 max-w-[1440px] mx-auto px-3 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-electric/30 bg-gradient-to-b from-electric/15 to-ink-900 p-6 sm:p-12 text-center space-y-5 sm:space-y-6 relative overflow-hidden">
          <div className="max-w-2xl mx-auto space-y-4">
            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-white">
              Ready to Protect Next Friday&rsquo;s Payout?
            </h2>
            <p className="text-xs sm:text-sm lg:text-base text-slate-300">
              Create your account in under 60 seconds, connect PayPal Sandbox, and forecast your cashflow risk before it becomes an emergency.
            </p>
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                to="/register"
                className="w-full sm:w-auto px-7 py-3.5 rounded-xl font-bold text-sm ignara-btn-primary text-white shadow-glow-electric transition-all min-h-[44px] flex items-center justify-center"
              >
                Create Free Account
              </Link>
              <button
                onClick={handleLaunchDemo}
                disabled={demoLoading}
                className="w-full sm:w-auto px-6 py-3.5 rounded-xl font-semibold text-sm bg-ink-950 text-white border border-slate-700 hover:border-orange-500 transition-all min-h-[44px] flex items-center justify-center"
              >
                {demoLoading ? 'Starting...' : 'Explore Demo Persona'}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 9. Public Footer */}
      <footer className="border-t border-ink-800 bg-ink-950 py-8 sm:py-12 text-xs text-sardine-muted">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6 sm:gap-8 pb-8 sm:pb-10 border-b border-ink-800">
            {/* Col 1 */}
            <div className="space-y-3 sm:col-span-2 md:col-span-1">
              <div className="flex items-center space-x-2">
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs shrink-0"
                  style={{ background: 'linear-gradient(135deg, var(--o1), var(--o2))' }}
                >
                  <Flame className="w-4 h-4 fill-white/20 text-white" />
                </div>
                <span className="font-extrabold text-sm text-white">Cashflow Lifeline</span>
              </div>
              <p className="text-[11px] text-sardine-muted leading-relaxed">
                Autonomous financial early-warning and rescue platform built for PayPal AI Hackathon 2026.
              </p>
            </div>

            {/* Col 2 */}
            <div className="space-y-2.5">
              <div className="font-bold text-white text-xs uppercase tracking-wider">Product</div>
              <ul className="space-y-1">
                <li><a href="#features" className="hover:text-white transition-colors py-1 inline-block">Features</a></li>
                <li><a href="#how-it-works" className="hover:text-white transition-colors py-1 inline-block">How It Works</a></li>
                <li><a href="#preview" className="hover:text-white transition-colors py-1 inline-block">Platform Demo</a></li>
                <li><a href="#security" className="hover:text-white transition-colors py-1 inline-block">Security Architecture</a></li>
              </ul>
            </div>

            {/* Col 3 */}
            <div className="space-y-2.5">
              <div className="font-bold text-white text-xs uppercase tracking-wider">Authentication</div>
              <ul className="space-y-1">
                <li><Link to="/login" className="hover:text-white transition-colors py-1 inline-block">Sign In</Link></li>
                <li><Link to="/register" className="hover:text-white transition-colors py-1 inline-block">Register Account</Link></li>
                <li><Link to="/forgot-password" className="hover:text-white transition-colors py-1 inline-block">Forgot Password</Link></li>
                <li><button onClick={handleLaunchDemo} className="hover:text-white transition-colors text-left py-1 inline-block">Demo Persona</button></li>
              </ul>
            </div>

            {/* Col 4 */}
            <div className="space-y-2.5">
              <div className="font-bold text-white text-xs uppercase tracking-wider">Legal &amp; Privacy</div>
              <ul className="space-y-1">
                <li className="py-1"><span className="text-slate-400">PayPal AI Hackathon 2026</span></li>
                <li className="py-1"><span className="text-slate-400">Strict Multi-Tenant Isolation</span></li>
                <li className="py-1"><span className="text-slate-400">Deterministic Guardrails</span></li>
                <li className="py-1"><span className="text-slate-400">PayPal Sandbox Environment</span></li>
              </ul>
            </div>
          </div>

          <div className="pt-6 sm:pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 border-b border-ink-800 pb-6 text-xs">
            <div className="flex items-center gap-2 text-slate-400">
              <span>Region &amp; Currency:</span>
              <RegionalFooterSelector />
            </div>
            <div className="text-slate-400 text-xs">
              Autonomous IP &amp; country detection with zero precision tracking.
            </div>
          </div>

          <div className="pt-6 sm:pt-8 flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-4 text-[11px] text-center sm:text-left">
            <div>
              &copy; 2026 Cashflow Lifeline. Built for PayPal AI Hackathon (&ldquo;Build What&rsquo;s Next with PayPal and AI&rdquo;).
            </div>
            <div className="flex flex-wrap items-center justify-center sm:justify-end gap-2 sm:gap-4">
              <span>PayPal Sandbox Verified</span>
              <span className="hidden sm:inline">&bull;</span>
              <span>SHA-256 Merkle Chain Audit</span>
              <span className="hidden sm:inline">&bull;</span>
              <span>Human-in-the-Loop Safeguards</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

