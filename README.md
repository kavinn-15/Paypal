# Cashflow Lifeline 🛡️💸

**Built for the PayPal AI Hackathon ("Build What's Next with PayPal and AI")**

> *Cashflow Lifeline finds the one upcoming payment a PayPal-paid freelancer is about to miss, compares the cheapest ways to protect it, and executes the plan the owner approves through PayPal.*

---

## 💡 The Core Problem

Freelancers are profitable on paper and still run out of cash. Overseas clients often pay days or weeks late, while contractor payouts, rent, and software licenses fall on strict, immovable deadlines. A single 5-day client delay can mean a missed contractor payout.

The account balance looks healthy right up to the day it does not. The missing piece is **not** another passive balance forecast graph; it is an active, costed plan that protects **ONE** specific upcoming obligation and that the owner can approve in a single step with deterministic guardrails.

### Question the App Answers
> **"Will I be able to pay Friday's contractor invoice, and if not, what is the cheapest safe fix?"**

---

## ⚡ 10-Minute Quickstart

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- (Optional) A PayPal Developer Sandbox Account ([developer.paypal.com](https://developer.paypal.com))

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
Default configuration works immediately with the deterministic template fallback.
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

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2 | High-performance async REST API and validation |
| **Database** | SQLAlchemy 2.0 + SQLite (WAL mode) / MySQL | Zero-config local execution; multi-RDBMS compatible |
| **Statistical Model** | scikit-learn + NumPy | Logistic regression for $p_{\text{late}}$ + empirical Bayes shrinkage |
| **LLM Layer** | Anthropic Claude / Google Gemini / Template | Natural language summaries with strict number validation |
| **Security & Guardrail**| HMAC-SHA256, Hash-Chained Audit Log | Deterministic policy bounds and cryptographic approval binding |
| **PayPal Sandbox** | Invoicing v2, Payouts, Webhooks, Search | Token caching, automated reminders, early discounts, payout batches |
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS, Recharts | Interactive cashflow forecast, confidence bands, plan comparison |

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

## 🧪 Testing

Run the automated test suite (100% pass rate):
```bash
# Backend unit & integration tests
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

## 🔍 Honest Limitations & Competitor Comparison

### Current Limitations
1. **Sandbox Only**: Cashflow Lifeline is strictly restricted to PayPal Sandbox accounts. Production execution is intentionally blocked at the configuration level.
2. **Seeded Baseline Data**: 12-month client history is pre-seeded with 6 behavioral personas to ensure demo reproducibility. Live sandbox accounts with transaction history will feed the statistical model directly via Transaction Search.
3. **Statistical Model Scope**: The delay model uses logistic regression and empirical Bayes shrinkage. It does not model macro-economic currency volatility or multi-obligation combinatorial knapsack optimizations.

### Public Competitor Comparison
*(Based on publicly available product descriptions)*:
- **QuickBooks / Xero**: Provide static accounting reports and retroactive reconciliation, but do not provide autonomous rescue plan generation to protect one specific date.
- **Float / Agicap**: Provide passive balance projection charts, but do not propose or execute costed actions via payment networks.
- **Owed / PayPilot**: Send basic payment dunning emails, but do not integrate payout split scheduling or cryptographic guardrails.

---

## 🏆 Devpost Submission Summary

**Title**: Cashflow Lifeline &mdash; AI Cashflow Guardian for Freelancers
**Elevator Pitch**: Finds the one upcoming payment a PayPal-paid freelancer is about to miss, compares the cheapest ways to protect it, and executes the approved plan through PayPal with cryptographic guardrails.
**Built With**: Python, FastAPI, React, TypeScript, Tailwind CSS, Recharts, scikit-learn, PayPal Sandbox REST APIs (Invoicing v2, Payouts, Webhooks).

