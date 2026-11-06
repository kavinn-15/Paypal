# Cashflow Lifeline: System Architecture

**PayPal AI Hackathon ("Build What's Next with PayPal and AI")**

Cashflow Lifeline finds the one upcoming payment a PayPal-paid freelancer is about to miss, compares the cheapest ways to protect it, and executes the plan the owner approves through PayPal.

---

## 1. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Frontend["Frontend Client (React + Vite + TypeScript + Tailwind)"]
        UI_Dash["Dashboard & At-Risk Banner"]
        UI_Chart["Interactive Recharts Timeline (CI Band + Plan Overlay)"]
        UI_Cards["Rescue Plan Cards (Plan A / B / C)"]
        UI_Modal["HMAC Approval Modal"]
        UI_Timeline["4-State Action Timeline"]
        UI_Audit["Audit Log & Integrity Verifier"]
        UI_Clients["Client Behavioral Pattern Viewer"]
    end

    subgraph API["FastAPI Application Layer (backend/app/api)"]
        Router_PayPal["/paypal (Token Check, Webhook Reg)"]
        Router_Obligations["/obligations (Contractor Payouts)"]
        Router_Forecast["/forecast (Run Engine, Latest State)"]
        Router_Plans["/plans (Plan Retrieval)"]
        Router_Actions["/actions (Approve, Execute)"]
        Router_Webhooks["/webhooks/paypal (Verified Ingress)"]
        Router_DevSim["/dev/simulate-webhook (Dev Only)"]
        Router_Audit["/audit (Ledger, Verify Chain)"]
        Router_Clients["/clients (Behavioral Patterns)"]
    end

    subgraph Guardrail["Deterministic Guardrail Security Layer (No LLM Decisions)"]
        SM["4-State Machine (proposed -> approved -> executed -> confirmed)"]
        HMAC["HMAC-SHA256 Signature Binding (Recipient, Amount, Currency, Action)"]
        Policy["Policy Bounds (5% Max Discount, $10k Cap, Whitelist)"]
        AuditLog["Hash-Chained Audit Trail (SHA-256 Chaining)"]
    end

    subgraph Agents["Intelligent & Deterministic Agents"]
        Agent_Forecaster["Forecaster Agent (scikit-learn + Monte Carlo)"]
        Agent_Collector["Collector Agent (Target Scoring & Pay Links)"]
        Agent_Treasurer["Treasurer Agent (Timing & Split Solver)"]
        Agent_Planner["Rescue Plan Engine (Plan A, B, C Generation)"]
        Layer_LLM["LLM Layer (Gemini / Claude / Template)"]
        Validator_Num["Strict Number & Metric Validator"]
    end

    subgraph Storage["Storage & Event Queue"]
        SQLite_DB[("SQLite Database (WAL Mode / MySQL Compatible)")]
        Persisted_Queue[("In-Process Queue + webhook_events table")]
    end

    subgraph PayPal_Sandbox["PayPal REST API Sandbox (Sandbox Only)"]
        PP_Auth["OAuth2 Client Credentials Cache"]
        PP_Invoice["Invoicing v2 API (Remind, Discount, Send)"]
        PP_Payouts["Payouts API (Idempotent Batch)"]
        PP_Reporting["Transaction Search / Reporting"]
        PP_WebhookVerify["verify-webhook-signature API"]
    end

    UI_Dash --> API
    UI_Chart --> API
    UI_Cards --> API
    UI_Modal --> API
    UI_Audit --> API

    API --> Guardrail
    API --> Agents
    Agents --> Layer_LLM
    Layer_LLM --> Validator_Num
    Agents --> Storage
    Guardrail --> Storage

    API --> PayPal_Sandbox
    PayPal_Sandbox --> Router_Webhooks
    Router_Webhooks --> Persisted_Queue
    Persisted_Queue --> Storage
```

---

## 2. Agent Responsibilities & Boundaries

| Component | Responsibility | Boundary & Constraints |
|---|---|---|
| **Forecaster Agent** | Fits statistical payment delay models, runs 1,000 Monte Carlo trajectories, detects first shortfall date and amount, ranks driver clients. | Strictly mathematical and statistical. Cannot approve plans. |
| **Collector Agent** | Scores and ranks clients using: $\text{Score} = (\text{Amount}/\text{Shortfall}) \times (1 - p_{\text{late}}) \times W_{\text{rel}}$. Selects optimal targets for reminders vs discount concessions. | Computes candidate rankings and explanations. Never approves or executes. |
| **Treasurer Agent** | Ranks upcoming obligations by urgency; calculates feasible 2-stage installment schedules within available balance and future inflow timings. | Evaluates split timing. Direct cash cost is \$0.00. |
| **Rescue Plan Engine** | Generates exactly three plans per shortfall: Plan A (Reminders), Plan B (Early-Pay Discount), Plan C (Contractor Split). Attaches with/without projections and late scenarios. | Never presents any plan as guaranteed. Must state "plausibly protects". |
| **Guardrail Agent** | Enforces 4-state state machine, validates HMAC approval hashes, checks policy bounds, appends hash-chained audit blocks. | Deterministic Python code only. Zero LLM involvement. Rejects illegal transitions. |
| **LLM Service** | Generates natural language driver summaries, plan trade-off reasoning, and polite message drafts. | Strictly restricted to prose. All numbers pass through `validate_llm_numbers()`. Any discrepancy falls back to deterministic templates. |

---

## 3. Data Flow: The End-to-End Lifeline Cycle

1. **Baseline Assessment**:
   - The user opens the dashboard. Current balance is healthy (\$1,800.00).
   - Contractor obligation: Marcus Sterling, \$3,200.00 due on Friday.
2. **Shortfall Detection**:
   - Forecaster Agent computes open invoices:
     - Apex Design Studio (\$2,000.00 due in 2 days) typically pays 14 days late $\rightarrow$ cash arrives after Friday!
     - Nordic Data Labs (\$1,500.00) arrives with 6-day lag.
   - Projected balance on Friday drops to **-\$1,400.00** (Shortfall Amount: \$1,400.00).
   - Monte Carlo simulation reveals an **85% probability of shortfall**.
3. **Rescue Plan Generation**:
   - Engine creates Plan A (\$0.00 cost), Plan B (\$60.00 discount cost), and Plan C (\$0.00 cash cost split).
   - Each plan includes an exact `Action` in `proposed` state with a pre-computed HMAC signature.
4. **Owner Review & Signed Approval**:
   - Owner reviews the side-by-side cards. Owner selects Plan A and clicks **"Approve Exact Action"**.
   - Guardrail verifies HMAC signature against `(recipient, amount, currency, action_type, idempotency_key)`.
   - Action moves from `proposed` $\rightarrow$ `approved`. Audit block appended.
5. **Sandbox Execution**:
   - Owner clicks **"Execute in PayPal Sandbox"**.
   - ActionExecutionService dispatches PayPal Invoicing reminder API with live payment link.
   - Action moves from `approved` $\rightarrow$ `executed`.
6. **Payment Confirmation & Recalculation**:
   - Client pays invoice in PayPal sandbox (or fast-tracked via "Simulate Client Payment" button).
   - Webhook arrives at `/webhooks/paypal`. Cryptographic signature verified against PayPal sandbox API.
   - Event queued and processed. Action moves from `executed` $\rightarrow$ `confirmed`.
   - Forecaster recalculates: cash balance rises to \$3,800.00.
   - At-Risk banner updates to: **"Obligation Protected — \$3,200.00 Covered"**.

