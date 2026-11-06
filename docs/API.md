# Cashflow Lifeline: REST API Reference

Base URL: `http://localhost:8000` (or configured `PORT`)
All timestamps in ISO 8601 UTC format. All currency values in 2 decimal places.

---

## 1. PayPal Sandbox & Connection

### `GET /paypal/connection`
Returns current PayPal Sandbox connection status and client preview.

**Response (200 OK):**
```json
{
  "connected": true,
  "environment": "sandbox",
  "status": "connected",
  "client_id_preview": "sb-client...",
  "last_checked_at": "2026-11-06T08:30:00Z",
  "message": "Connected to PayPal Sandbox"
}
```

### `POST /paypal/test-connection`
Hits the live PayPal Sandbox OAuth2 token endpoint to verify client credentials.

**Response (200 OK):**
```json
{
  "success": true,
  "status_code": 200,
  "environment": "sandbox",
  "message": "Successfully authenticated with PayPal Sandbox API.",
  "token_preview": "A21AAI_xyz... (valid 3600s)"
}
```

---

## 2. Contractor Obligations

### `GET /obligations`
Lists active contractor obligations.

### `POST /obligations`
Registers an upcoming contractor obligation to protect.

**Request Body:**
```json
{
  "payee_name": "Marcus Sterling",
  "payee_email": "marcus.contractor@example.com",
  "amount": 3200.0,
  "currency": "USD",
  "due_date": "2026-11-13T17:00:00Z",
  "split_allowed": true
}
```

---

## 3. Forecast & Rescue Plans

### `POST /forecast/run`
Executes forecasting pipeline: fits ML payment delay model on historical data, runs 1,000 Monte Carlo trajectories, detects shortfall, ranks client drivers, and generates Rescue Plans A, B, and C.

**Query Parameters:**
- `starting_balance` (float, default: `1800.0`)
- `discount_pct` (float, default: `3.0`)

**Response (200 OK):**
```json
{
  "run_id": "fc_8b417c91fa02",
  "obligation": {
    "payee_name": "Marcus Sterling",
    "amount": 3200.0,
    "due_date": "2026-11-13T17:00:00Z",
    "split_allowed": true
  },
  "shortfall_amount": 1400.0,
  "first_shortfall_date": "2026-11-13",
  "tradeoff_summary": "Plan A incurs $0.00 cost but relies on prompt response. Plan B accelerates cash flow at an early discount cost of $60.00. Plan C splits the payout with $0.00 cash cost.",
  "plans": [
    {
      "id": 1,
      "plan_type": "A",
      "name": "Plan A: Collect Without Concessions",
      "cost": 0.0,
      "incoming_needed": 1400.0,
      "rationale": "Sends an official PayPal payment reminder with a direct pay link...",
      "remaining_risk": "Plausibly protects contractor payment if client settles promptly. Timing is not guaranteed.",
      "primary_action": {
        "id": 10,
        "action_type": "SEND_REMINDER",
        "recipient": "Apex Design Studio",
        "amount": 2000.0,
        "currency": "USD",
        "state": "proposed",
        "approval_hash": "4a7b...",
        "idempotency_key": "act_remind_1_..."
      }
    }
  ]
}
```

---

## 4. Guardrail Actions & Approvals

### `POST /actions/{id}/approve`
Owner UI Approval endpoint. Requires exact HMAC approval hash computed over recipient, amount, currency, action type, and idempotency key.

**Request Body:**
```json
{
  "approval_hash": "4a7b6c..."
}
```

### `POST /actions/{id}/execute`
Dispatches an approved action to the PayPal Sandbox (Invoicing reminder, discount update, or payout).

**Request Body:**
```json
{
  "idempotency_key": "act_remind_1_..."
}
```

---

## 5. PayPal Webhooks & Dev Simulator

### `POST /webhooks/paypal`
Public endpoint receiving verified PayPal Sandbox events.
Headers required:
- `PAYPAL-TRANSMISSION-ID`
- `PAYPAL-TRANSMISSION-TIME`
- `PAYPAL-CERT-URL`
- `PAYPAL-AUTH-ALGO`
- `PAYPAL-TRANSMISSION-SIG`

### `POST /dev/simulate-webhook`
Fast-track simulation endpoint (DEV_MODE only). Simulates confirmed client invoice payment event.

**Request Body:**
```json
{
  "paypal_invoice_id": "INV2-DEMO-APEX-001"
}
```

---

## 6. Audit Trail & Integrity

### `GET /audit`
Returns chronological audit ledger.

### `GET /audit/verify`
Traverses cryptographic SHA-256 hash chain from Genesis block and returns integrity status.

**Response (200 OK):**
```json
{
  "chain_valid": true,
  "total_blocks": 7,
  "genesis_valid": true,
  "message": "Audit chain verified successfully (7 blocks). 100% intact.",
  "corrupted_block_id": null
}
```
