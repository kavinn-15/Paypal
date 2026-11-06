# Cashflow Lifeline: Safety Architecture & Verification Matrix

This document provides a comprehensive audit of all safety safeguards, access boundaries, deterministic guardrails, and cryptographic protections enforced in **Cashflow Lifeline**.

---

## 1. Safety Safeguards Matrix

| Safeguard | Risk Mitigated | Enforcement Mechanism | File Reference | Verified In Test |
|---|---|---|---|---|
| **Sandbox Host Refusal Guard** | Accidental live PayPal execution; real money movement | Hard startup validator checks `PAYPAL_BASE_URL`. Refuses to start if production host is detected. | `backend/app/config.py`<br>`backend/app/paypal/client.py`<br>`backend/app/main.py` | `test_paypal_client_refuses_production_url` |
| **Strict 4-State Machine** | Bypassing approvals; unconfirmed payouts; illegal jumps | State transitions strictly follow `proposed -> approved -> executed -> confirmed`. Illegal transitions raise `InvalidStateTransitionError`. | `backend/app/guardrail/state_machine.py` | `test_guardrail_rejects_illegal_transition` |
| **HMAC-SHA256 Approval Binding** | Tampering with payment amounts or recipients | Approval hash binds `(recipient, amount, currency, action_type, idempotency_key)`. Any alteration by 1 cent invalidates approval. | `backend/app/guardrail/approval.py` | `test_guardrail_rejects_tampered_approval_hash` |
| **LLM Approval Isolation** | Agent autonomously authorizing financial transactions | No code path permits an agent or LLM to set state to `approved`. Approval requires explicit signed POST with owner signature. | `backend/app/api/actions.py`<br>`backend/app/guardrail/state_machine.py` | `test_guardrail_rejects_illegal_transition` |
| **Deterministic Number Validator** | LLM hallucinating financial metrics, costs, or dates | All LLM output parsed for numbers; validated against computed facts. Mismatch triggers immediate fallback to deterministic template. | `backend/app/llm/validator.py`<br>`backend/app/llm/client.py` | `test_validate_llm_numbers_detects_hallucination` |
| **Cryptographic Audit Hash Chain** | Undetected tampering, deletion, or retrofitting of ledger | Each row stores `prev_hash` and SHA-256 block hash. `/audit/verify` traverses and verifies chain from Genesis block. | `backend/app/guardrail/audit.py` | `test_audit_log_detects_payload_tampering`<br>`test_audit_log_detects_hash_tampering` |
| **Policy Limits Enforcement** | Runaway discounts, excessive payouts, or foreign currency leakage | Validates max discount (5% cap), max payout amount ($10,000 ceiling), allowed currencies (USD, EUR, GBP, CAD), and recipient whitelist. | `backend/app/guardrail/policy.py` | `test_policy_currency_validation`<br>`test_policy_max_payout_limit`<br>`test_policy_unrecognized_recipient` |
| **PayPal Webhook Verification** | Spoofed payment confirmations | Webhooks validated against PayPal's `verify-webhook-signature` API. Unverified webhooks are stored with `verified=false` and ignored. | `backend/app/paypal/client.py`<br>`backend/app/api/webhooks.py` | `test_unverified_webhook_does_not_modify_cashflow` |
| **Idempotency & Double-Click Guard** | Duplicate payouts or repeated reminder dispatches | Unique constraints on `actions.idempotency_key` and `webhook_events.paypal_event_id`. Duplicate execute calls return existing action without re-calling PayPal. | `backend/app/models.py`<br>`backend/app/api/actions.py`<br>`backend/app/api/webhooks.py` | `test_create_payout_with_idempotency`<br>`test_duplicate_webhook_deduplication` |
| **Truth in Advertising Wording** | Misleading users into believing future payments are guaranteed | All UI cards and plan rationale use the required phrasing **"plausibly protects"**, and strictly prohibit the term **"guarantees"**. | `backend/app/agents/planner.py`<br>`frontend/src/components/RescuePlanCard.tsx` | `test_plans_generation_and_formulas`<br>`frontend/src/RescuePlanCard.test.ts` |
| **Seeded & Simulated Badging** | Presenting test or simulated data as live money confirmations | Database marks `source="seeded"` or `is_simulated=true`. UI renders high-contrast badges for "Seeded History" and "Simulated Event". | `backend/scripts/seed.py`<br>`backend/app/api/webhooks.py`<br>`frontend/src/components/AtRiskBanner.tsx` | `test_end_to_end_api_lifecycle` |

---

## 2. Guardrail Enforcement Details

### A. HMAC Approval Signature
```python
# Defined in backend/app/guardrail/approval.py
def generate_approval_hash(recipient, amount, currency, action_type, idempotency_key, secret):
    payload = f"{recipient.strip().lower()}|{amount:.2f}|{currency.strip().upper()}|{action_type.strip().upper()}|{idempotency_key.strip()}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
```
When an owner clicks "Approve Exact Action" in the UI, this exact hash is submitted. If a malicious agent or frontend script changed `amount` from `60.00` to `600.00`, the constant-time comparison `hmac.compare_digest()` returns `False` and the transition is rejected with `InvalidStateTransitionError`.

### B. LLM Confinement Boundary
The LLM is invoked **only** through three functions in `backend/app/llm/client.py`:
1. `generate_driver_explanation()`
2. `generate_tradeoff_summary()`
3. `draft_reminder_message()` / `draft_discount_message()` / `draft_contractor_split_message()`

The LLM is given prompt instructions to draft text, but **all financial parameters** (amounts, dates, client names) are computed upstream by deterministic algorithms. Furthermore, `backend/app/llm/validator.py` scans the output text: if any unapproved number appears, the LLM response is discarded and the deterministic template is used.

### C. Append-Only Hash Chain
The audit log table (`audit_log`) maintains a continuous cryptographic hash chain:
$$\text{Hash}_n = \text{SHA-256}(\text{Hash}_{n-1} \parallel \text{timestamp} \parallel \text{actor} \parallel \text{event} \parallel \text{payload})$$
The Genesis block is hardcoded with $64$ zeros (`0` $\times 64$).
The `/audit/verify` endpoint verifies the mathematical linkage of every row in $O(N)$ time.
