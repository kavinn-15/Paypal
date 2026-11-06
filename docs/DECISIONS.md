# Architecture & Implementation Decisions

This document records architectural, mathematical, and algorithmic decisions made in **Cashflow Lifeline**, along with rationale and compliance with the project specifications.

---

## 1. Database Architecture: SQLite with Multi-RDBMS Compatibility

- **Decision**: Cashflow Lifeline defaults to SQLite 3 (`sqlite:///./cashflow.db`) operating with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and foreign keys enforced (`PRAGMA foreign_keys=ON`).
- **Rationale**:
  - The specification explicitly requires SQLite in the fixed stack section for seamless out-of-the-box local hackathon execution without requiring external database daemons or Docker services.
  - SQLAlchemy 2.0 ORM abstracts all SQL statements. If a production or enterprise MySQL 8.0 instance is provided via `DATABASE_URL=mysql+pymysql://...`, the code seamlessly adapts without modification.
  - JSON columns are supported natively across SQLite (via `json1` extension built-in since SQLite 3.38+) and MySQL.

---

## 2. Sandbox-Only Execution & Refusal Guard

- **Decision**: The backend refuses to start if `PAYPAL_BASE_URL` is set to any production endpoint (such as `https://api-m.paypal.com` or `https://api.paypal.com`).
- **Rationale**:
  - The application is an AI Hackathon prototype designed strictly for sandbox exploration and demonstration.
  - A strict Pydantic and runtime validator ensures `PAYPAL_BASE_URL == "https://api-m.sandbox.paypal.com"`. Any deviation raises a fatal startup error, guaranteeing no real money or live production accounts are ever touched.

---

## 3. Strict 4-State Guardrail State Machine

- **Decision**: Every action transitions strictly through four discrete states:
  $$\text{proposed} \longrightarrow \text{approved} \longrightarrow \text{executed} \longrightarrow \text{confirmed}$$
  (with an auxiliary terminal `failed` state allowed from `executed`).
- **Rationale**:
  - Direct transitions from `proposed` to `executed` or `confirmed` are rejected by `guardrail/state_machine.py`.
  - The LLM or background agents can **never** approve an action. Approval requires an explicit signed HTTP POST from the owner UI containing a valid HMAC approval hash.

---

## 4. Cryptographic HMAC Approval Binding

- **Decision**: Every proposed action generates an `approval_hash` computed as:
  $$\text{HMAC-SHA256}_{K}(\text{recipient} \parallel \text{amount} \parallel \text{currency} \parallel \text{action\_type} \parallel \text{idempotency\_key})$$
- **Rationale**:
  - If a user, malicious actor, or buggy agent attempts to alter the amount (e.g. from \$100 to \$1,000) or change the recipient, the hash validation fails, blocking approval and execution.

---

## 5. Hash-Chained Append-Only Audit Log

- **Decision**: The `AuditLog` table maintains a cryptographic hash chain:
  $$\text{Hash}_n = \text{SHA-256}(\text{Hash}_{n-1} \parallel \text{timestamp} \parallel \text{actor} \parallel \text{event} \parallel \text{payload\_json})$$
  with Genesis block $\text{Hash}_0 = \text{"0" \times 64}$.
- **Rationale**:
  - Any tampering, deletion, or retrofitting of historical audit entries causes all downstream hashes to become invalid.
  - The `/audit/verify` endpoint verifies the integrity of the chain from genesis to head in $O(N)$ time.

---

## 6. LLM Safety & Deterministic Number Validator

- **Decision**: The LLM is restricted to:
  1. Plain-language explanation of calculated drivers.
  2. Trade-off reasoning between Rescue Plans.
  3. Client message drafting (reminders, polite early-pay discount offers).
  The LLM **never** sets amounts, dates, or approval statuses.
- **Number Validator**:
  - All output from the LLM passes through `llm/validator.py`, which parses all dollar amounts and numbers.
  - If any number deviates from computed simulation values or introduces unseen figures, the system discards the LLM text and falls back to a deterministic template.

---

## 7. Statistical & Machine Learning Model

- **Decision**: Two-stage payment delay prediction:
  1. **Late Payment Probability ($p_{\text{late}}$)**: Logistic regression trained on historical invoice features (`amount`, `days_invoiced`, `historical_delay_mean`, `historical_delay_std`, `country`).
  2. **Expected Days Late ($\Delta_{\text{days}}$)**: Empirical quantile distribution (10th, 50th, 90th percentiles).
  3. **Small Sample Shrinkage**: For clients with fewer than 5 historical payments, an Empirical Bayes shrinkage pulls the client's parameters toward the population mean:
     $$\mu_{\text{shrunk}} = \frac{N}{N + K} \mu_{\text{client}} + \frac{K}{N + K} \mu_{\text{population}}$$
     with $K=5$, and expands confidence interval width to reflect uncertainty.
- **Simulation**: Monte Carlo sampling ($N=1,000$) simulates pay dates across open invoices to derive probability of shortfall $p_{\text{shortfall}}$ on the contractor obligation due date.

---

## 8. Webhook Processing & Payment Confirmation

- **Decision**: Webhooks are ingested via an asynchronous queue with an underlying persisted `webhook_events` database table.
- **Verification**: Each webhook is validated against PayPal's `v1/notifications/verify-webhook-signature` API. Unverified webhooks are stored with `verified=false` and ignored.
- **Truth in UI**: An action is marked `confirmed` **only** upon arrival of a verified PayPal sandbox event (`INVOICING.INVOICE.PAID` or `PAYMENT.PAYOUTS-ITEM.SUCCEEDED`). Simulated events in dev mode are stamped with `is_simulated = true` and visibly badged in the UI.

