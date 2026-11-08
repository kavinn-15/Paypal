# Cashflow Lifeline 🛡️💸
**Built for the PayPal AI Hackathon ("Build What's Next with PayPal and AI")**

> *Cashflow Lifeline finds the one upcoming payment a PayPal-paid freelancer is about to miss, compares the cheapest ways to protect it, and executes the plan the owner approves through PayPal.*

---

## 💡 The Core Problem & Product Philosophy

Freelancers, independent contractors, agencies, and small businesses are frequently profitable on paper and still run out of cash. Overseas clients pay days or weeks late, while contractor payouts, rent, software licenses, and taxes fall on strict, immovable deadlines. A single 5-day client delay can trigger a missed contractor payout.

The account balance looks healthy right up to the day it does not. The missing piece is **not** another passive balance forecast graph; it is an active, costed plan that protects **ONE** specific upcoming obligation and that the owner can approve in a single step with deterministic guardrails.

### Core Philosophy
> **"Don't just tell users where their money went. Predict what financial problem will happen next, explain why it may happen, recommend the best solution, and help them execute it safely."**

---

## ⚡ 10-Minute Quickstart

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- (Optional) Docker & Docker Compose (for production MySQL 8.0 stack)
- (Optional) PayPal Developer Sandbox Account ([developer.paypal.com](https://developer.paypal.com))

### 2. Clone and Setup
```bash
git clone https://github.com/your-username/cashflow-lifeline.git
cd cashflow-lifeline

# Setup Python virtual environment & dependencies
make setup
```

### 3. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default configuration works immediately with the deterministic template fallback and SQLite.
To connect to your live sandbox app, update in `.env`:
```env
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
PAYPAL_WEBHOOK_ID=your_registered_webhook_id
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
```
*(Note: Cashflow Lifeline strictly refuses to start if `PAYPAL_BASE_URL` is set to any production endpoint).*

### 4. Seed Database & Start Application
```bash
# Seed 12-month client behavioral profiles & the demo Friday contractor obligation
make demo-reset

# Start Backend (FastAPI on port 8000)
make dev
```

In a separate terminal, start the React frontend:
```bash
cd frontend
npm run dev
```
Open your browser to `http://localhost:5173`.

---

## 🏗️ Architectural Highlights & Autonomous Agents

Cashflow Lifeline features a coordinated multi-agent financial intelligence architecture:

```
                               ┌────────────────────────┐
                               │ Autonomous Supervisor  │
                               │ Agent Orchestrator     │
                               └───────────┬────────────┘
                                           │
         ┌───────────────────┬─────────────┴─────────────┬────────────────────┐
         ▼                   ▼                           ▼                    ▼
┌─────────────────┐ ┌─────────────────┐         ┌─────────────────┐  ┌──────────────────┐
│ Forecaster Agent│ │ Collector Agent │         │ Treasurer Agent │  │ Negotiator Agent │
│ scikit-learn +  │ │ Behavioral      │         │ Split Solver &  │  │ 3-Tone Dynamic   │
│ Monte Carlo     │ │ Risk Analysis   │         │ Timing Engine   │  │ Drafting Engine  │
└────────┬────────┘ └────────┬────────┘         └────────┬────────┘  └────────┬─────────┘
         │                   │                           │                    │
         └───────────────────┴─────────────┬─────────────┴────────────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │ Rescue Planner Agent   │
                               │ Plan A, Plan B, Plan C │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │ Deterministic Security │
                               │ Guardrail Layer        │
                               │ HMAC • Policy • State  │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │ PayPal Sandbox REST    │
                               │ Invoicing • Payouts    │
                               └────────────────────────┘
```

1. **Autonomous Supervisor Agent**: Orchestrates the analysis pipeline across Forecaster, Collector, Treasurer, and Planner with persistent, auditable workflow execution traces (`AgentWorkflowRun`).
2. **Forecaster Agent**: Analyzes 7, 30, 60, and 90-day cashflow horizons using scikit-learn logistic regression, empirical Bayes delay modeling, and Monte Carlo probability simulations.
3. **Collector Agent**: Evaluates client payment reliability, late payment probability, and crafts targeted invoice payment reminders.
4. **Treasurer Agent**: Computes optimal split ratios and settlement timing to avoid negative balances without incurring credit fees.
5. **Financial Negotiation Agent**: Generates tailored communication drafts across 3 distinct tone styles:
   - **Professional**: Formal, corporate, terms-focused.
   - **Friendly**: Collaborative, relationship-preserving.
   - **Urgent & Respectful**: Critical-path timing with bounded incentives.
6. **What-If Simulation Studio**: In-memory, non-destructive sandbox allowing users to simulate scenarios (e.g. 5-day client delay, emergency expense shock, contractor split agreement) with zero side effects on live records.
7. **Financial Resilience Score (0–100)**: Transparent 6-dimensional gauge measuring Runway, Cash Buffer, Client Diversification, Invoice Delay Risk, Payment Predictability, and Obligation Pressure.

---

## 🛠️ Complete Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2 | High-performance async REST API and schema validation |
| **Database** | MySQL 8.0 (Docker) + SQLite 3 (WAL fallback) | Enterprise RDBMS with Alembic migrations + zero-config local dev |
| **Precision** | SQLAlchemy `Numeric(12, 2)` & Python `Decimal` | Exact financial math with zero floating-point rounding errors |
| **Security & Auth** | JWT (PyJWT RFC 7519), bcrypt, HMAC-SHA256 | Multi-tenant user data isolation & tamper-proof cryptographic approvals |
| **Statistical Model** | scikit-learn + NumPy | Logistic regression for $p_{\text{late}}$ + empirical Bayes shrinkage |
| **Simulation** | Monte Carlo (1,000 runs) + What-If Engine | 90-day trajectory confidence bands & in-memory scenario comparisons |
| **LLM Layer** | Anthropic Claude / Google Gemini / Template | Natural language summaries with strict regex number validation |
| **PayPal Sandbox** | Invoicing v2, Payouts, Webhooks, Search | Token caching, automated reminders, early discounts, payout batches |
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS, Recharts | Sardine.ai Bento Grid design system, 10 views, zero top slide bar |

---

## 🔒 Safety Architecture & Guardrails

Cashflow Lifeline enforces strict safety guarantees:
1. **No LLM Financial Control**: The LLM is **never** permitted to approve, execute, or alter amounts. Approvals require an explicit signed owner action from the UI.
2. **Deterministic Number Validation**: Any number produced by the LLM is scanned by `backend/app/llm/validator.py`. If a figure deviates from computed facts, the response is discarded in favor of a deterministic template.
3. **Cryptographic HMAC Approval Binding**: Every action generates an HMAC signature:
   $$\text{HMAC}(\text{recipient} \parallel \text{amount} \parallel \text{currency} \parallel \text{action\_type} \parallel \text{idempotency\_key})$$
   Any modification to amount or recipient immediately invalidates approval.
4. **Strict 4-State Machine**: Transitions strictly follow `proposed -> approved -> executed -> confirmed`. Illegal jumps are rejected.
5. **Cryptographic Audit Trail**: Append-only SHA-256 hash chain from Genesis. Real-time `/audit/verify` verification detects any tampering.
6. **Verified Sandbox Webhooks Only**: Confirmation is claimed **only** upon arrival of a verified PayPal webhook signature.

*For detailed code mappings, see [docs/SAFETY.md](docs/SAFETY.md).*

---

## 📊 Three Rescue Plans: Cheaper Ways to Protect Friday

| Feature | Plan A: Collect Without Concessions | Plan B: Limited Early-Pay Discount | Plan C: Collect + Agreed Split |
|---|---|---|---|
| **Action** | PayPal invoice payment reminder with pay link | 3% early settlement discount on PayPal invoice | Reminder to client + split contractor payout into 2 dates |
| **Cost** | **$0.00** | **$60.00** concession | **$0.00** cash cost (goodwill proxy) |
| **Incoming Needed** | $1,400.00 | $1,400.00 | $0.00 for Friday ($1,800 covers installment 1) |
| **Execution** | `POST /v2/invoicing/invoices/{id}/remind` | `PUT /v2/invoicing/invoices/{id}` | `POST /v1/payments/payouts` batch installment |
| **Remaining Risk** | Clients may still pay late; timing unconfirmed | Client may decline discount offer | Requires written contractor consent |
| **Wording Rule** | Plausibly protects (never guarantees) | Plausibly protects (never guarantees) | Plausibly protects (never guarantees) |

---

## 🖥️ Modern Bento Grid Interface (10 Core Views)

Crafted following the Sardine.ai fintech design tokens (`#081026` ink, `#4b5bfc` electric blue, clean Swiss typography, 1440px max width):

1. **Forecast & Rescue Plans**: Real-time balance status, 14-day projection chart with Monte Carlo band, and side-by-side Plan A/B/C comparison cards.
2. **Autonomous Supervisor**: Multi-agent orchestration visualizer with step-by-step progress, agent outputs, and persistent run traces.
3. **What-If Studio**: Interactive scenario tester comparing baseline vs simulated trajectories with instant delta metrics.
4. **Negotiation Studio**: AI-assisted communications generator drafting client reminders, discount incentives, and contractor split proposals in 3 distinct tones.
5. **Resilience Score**: 0–100 health gauge with a breakdown of 6 transparent dimensions and actionable optimization tips.
6. **Financial Timeline**: Chronological inflow/outflow ledger classifying transactions into confirmed, expected, estimated, and simulated.
7. **Approval Inbox**: Pending cryptographic approvals requiring explicit owner signature.
8. **Clients & Invoices**: Historical payment reliability patterns, empirical delay distributions, and invoice statuses.
9. **Audit Trail**: Cryptographic SHA-256 block-chained ledger with one-click full chain mathematical verification.
10. **Settings & Sandbox Status**: PayPal API credentials, webhook status, token cache health, and demo reset controls.

---

## 🧪 Testing

Run the automated test suite (100% pass rate):
```bash
# Backend unit & integration tests (32 tests covering auth, state, policy, agents, math, webhooks)
make test

# Frontend unit tests
cd frontend && npm test
```

### Live Sandbox Smoke Test
When valid sandbox credentials are added to `.env`:
```bash
python -m backend.scripts.sandbox_smoke
```

---

## 🏆 Devpost Submission Summary

- **Title**: Cashflow Lifeline &mdash; Autonomous AI Cashflow Guardian for Freelancers
- **Elevator Pitch**: Predicts the upcoming payment a PayPal-paid freelancer is about to miss, computes the three cheapest ways to protect it, and executes the approved plan through PayPal Sandbox with cryptographic guardrails.
- **Built With**: Python 3.11, FastAPI, MySQL 8 / SQLite, SQLAlchemy, Alembic, React 18, Vite, TypeScript, Tailwind CSS, Recharts, scikit-learn, PayPal Sandbox REST APIs (Invoicing v2, Payouts, Webhooks).
