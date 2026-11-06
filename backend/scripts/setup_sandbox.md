# PayPal Sandbox Setup Guide (10 Minutes)

This guide walks you through setting up a PayPal Developer sandbox app, generating test credentials, setting up an ngrok or Cloudflare tunnel, and registering webhooks for **Cashflow Lifeline**.

---

## 1. Access the PayPal Developer Dashboard

1. Navigate to [developer.paypal.com](https://developer.paypal.com/) and sign in with your PayPal credentials.
2. Under **Apps & Credentials**, toggle to the **Sandbox** tab.
3. Click **Create App**:
   - **App Name**: `Cashflow Lifeline Sandbox`
   - **App Type**: `Merchant`
   - **Sandbox Business Account**: Select the default business account or create one.
4. Once created, copy:
   - **Client ID** $\rightarrow$ set as `PAYPAL_CLIENT_ID` in your `.env`
   - **Secret** $\rightarrow$ set as `PAYPAL_CLIENT_SECRET` in your `.env`
   - Ensure `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`

---

## 2. Sandbox Accounts

Under **Testing Tools** $\rightarrow$ **Sandbox Accounts**, PayPal provides default accounts:
1. **Business Account (Freelancer/Owner)**:
   - Used for receiving client payments and scheduling contractor payouts.
   - Example: `sb-freelancer@business.example.com`
2. **Personal Account (Client)**:
   - Used for paying invoices through sandbox invoice payment links.
   - Example: `sb-client@personal.example.com`

---

## 3. Webhook Tunnel Setup (ngrok or cloudflared)

PayPal Webhook events must be delivered to a publicly accessible HTTPS endpoint.

### Option A: ngrok
```bash
# Start your local backend on port 8000
uvicorn backend.app.main:app --port 8000

# In a separate terminal, start ngrok
ngrok http 8000
```
Copy the forwarding HTTPS URL (e.g., `https://abc-123.ngrok-free.app`).

### Option B: Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

---

## 4. Register the Webhook

Set `PUBLIC_BASE_URL` in `.env`:
```env
PUBLIC_BASE_URL=https://abc-123.ngrok-free.app
```

Then run the webhook registration script:
```bash
python -m backend.scripts.register_webhook
```
The script will register the webhook endpoint:
`https://abc-123.ngrok-free.app/webhooks/paypal`

Subscribed events:
- `INVOICING.INVOICE.PAID`
- `INVOICING.INVOICE.REFUNDED`
- `PAYMENT.PAYOUTS-ITEM.SUCCEEDED`
- `PAYMENT.PAYOUTS-ITEM.FAILED`

Save the returned `WEBHOOK_ID` to `PAYPAL_WEBHOOK_ID` in `.env`.

---

## 5. Test Live Connection

Run the sandbox smoke test script:
```bash
python -m backend.scripts.sandbox_smoke
```
Or click the **"Test Connection"** button on the Settings screen in the web UI.

