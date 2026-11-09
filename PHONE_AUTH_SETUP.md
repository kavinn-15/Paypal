# Cashflow Lifeline – Phone Authentication & SMS OTP Setup Guide

This document describes the multi-channel phone number authentication and SMS OTP architecture for Cashflow Lifeline, built for the PayPal AI Hackathon 2026.

---

## 1. Architecture Overview

Cashflow Lifeline offers a unified authentication architecture where a single `Owner` entity can authenticate via:
1. **Work / Business Email + Password**
2. **Mobile Phone Number + Password**
3. **Mobile Phone Number + SMS OTP** (passwordless login for verified phones)
4. **Google Sign-In / OAuth 2.0**

### Security & Privacy Highlights:
- **E.164 Standardization**: Every mobile number is parsed, validated, and canonicalized into E.164 format (e.g. `+919876543210`) using Google's `phonenumbers` library.
- **Default Region**: India (`+91`), with full support for international dial codes (`+1`, `+44`, `+61`, `+65`, `+971`, `+49`, etc.).
- **Zero Plain-Text OTPs**: All 6-digit OTP codes are hashed with HMAC-SHA256 keyed by `OTP_PEPPER` before database storage.
- **Single-Use Consumption**: Once verified, OTPs are instantly stamped with `consumed_at = utcnow()` and cannot be replayed.
- **Purpose Binding**: OTPs are cryptographically constrained to specific purposes (`phone_verification`, `phone_login`, `password_reset`, `phone_change`).
- **Brute-Force & Flood Throttling**: Strict limit of 5 failed attempts per OTP code, with a 60-second cooldown on resends.
- **Session Revocation**: Password reset via phone OTP invalidates all active sessions and refresh tokens.

---

## 2. Environment Configuration

Add the following variables to your `.env` file:

```ini
# ==============================================================================
# SMS OTP & Multi-Channel Phone Authentication
# ==============================================================================
SMS_PROVIDER=console             # Options: console | twilio | msg91 | exotel
SMS_ENABLED=true
SMS_OTP_EXPIRE_MINUTES=5
SMS_RESEND_COOLDOWN_SECONDS=60
DEFAULT_COUNTRY_DIAL_CODE=+91

# Provider Credentials
SMS_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
SMS_AUTH_TOKEN=your_twilio_auth_token_here
SMS_API_KEY=your_msg91_or_exotel_api_key_here
SMS_SENDER_ID=CSHLIF             # 6-character registered DLT Header / Sender ID
SMS_TEMPLATE_ID=11071XXXXXXXXX   # DLT approved template identifier
```

---

## 3. SMS Provider Setup

### Option A: Development & Testing (`console`)
Default for local development and CI testing. OTP codes and SMS payloads are rendered to the application logs without incurring SMS carrier charges:
```
[SMS-CONSOLE] Dispatching SMS to +919876543210:
  Cashflow Lifeline: Your mobile verification code is 482910. Valid for 5 minutes. Do not share this code.
```

### Option B: Twilio
To use Twilio for global SMS delivery:
1. Sign up at [twilio.com](https://www.twilio.com).
2. Retrieve your **Account SID**, **Auth Token**, and registered phone number or alphanumeric Sender ID.
3. Set in `.env`:
   ```ini
   SMS_PROVIDER=twilio
   SMS_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   SMS_AUTH_TOKEN=your_twilio_auth_token
   SMS_SENDER_ID=+12025550199
   ```

### Option C: MSG91 (India DLT Compliant)
For SMS routing in India complying with TRAI DLT regulations:
1. Register on the DLT portal (Jio, Airtel, or Vilpower) with your Principal Entity (PE ID).
2. Register sender header `CSHLIF` and SMS OTP template:
   - Template: `Cashflow Lifeline: Your mobile verification code is {#var#}. Valid for 5 minutes. Do not share this code.`
3. Obtain your AuthKey from MSG91 dashboard.
4. Set in `.env`:
   ```ini
   SMS_PROVIDER=msg91
   SMS_API_KEY=your_msg91_authkey
   SMS_SENDER_ID=CSHLIF
   SMS_TEMPLATE_ID=1107160000000000000
   ```

### Option D: Exotel (India Enterprise)
For Exotel enterprise telephony & SMS:
1. Set in `.env`:
   ```ini
   SMS_PROVIDER=exotel
   SMS_ACCOUNT_SID=your_exotel_sid
   SMS_API_KEY=your_exotel_api_key
   SMS_AUTH_TOKEN=your_exotel_api_token
   SMS_SENDER_ID=CSHLIF
   ```

---

## 4. API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register with optional `phone_number` and `phone_country_code`. Dispatches SMS OTP. |
| `POST` | `/auth/phone/verification/request` | Request an SMS verification code for an unverified phone number. |
| `POST` | `/auth/phone/verification/verify` | Verify 6-digit OTP code and mark `phone_verified = true`. |
| `POST` | `/auth/phone/verification/resend` | Resend verification SMS OTP (enforces 60-second cooldown). |
| `POST` | `/auth/phone/login/request-otp` | Initiate passwordless phone login by dispatching a 6-digit SMS OTP. |
| `POST` | `/auth/phone/login/verify-otp` | Verify login OTP and issue access + refresh JWT tokens. |
| `POST` | `/auth/phone/login/password` | Authenticate directly using registered phone number + password. |
| `POST` | `/auth/phone/password-reset/request` | Request password recovery OTP via SMS (anti-enumeration response). |
| `POST` | `/auth/phone/password-reset/verify-otp` | Validate reset OTP and receive single-use reset JWT token. |
| `POST` | `/auth/phone/password-reset/confirm` | Set new password and revoke all active refresh tokens. |
| `POST` | `/auth/phone/change/request` | Re-authenticate with current password and dispatch OTP to new phone number. |
| `POST` | `/auth/phone/change/verify` | Verify OTP on new phone number, update profile, and send security alert to prior number. |

---

## 5. Frontend User Experience

- **Register Page (`/register`)**: Includes international `PhoneInput` dropdown with India `+91` preselected.
- **Login Page (`/login`)**: 3-in-1 segmented navigation tabs:
  - **Email & Password**
  - **Phone & Password**
  - **Phone OTP** (2-step inline verification)
  - **Continue with Google**
  - **Sandbox Evaluation (Alex Morgan)**
- **Dedicated Phone Verification (`/verify-phone`)**: 6-digit OTP input with resend countdown and progress forwarding.
- **Forgot Password (`/forgot-password`)**: Seamless toggle between email recovery and mobile SMS OTP recovery.
- **Settings Page (`/settings`)**: "Security & Contact Information" dashboard displaying verification badges and self-service phone change with password reauthentication.

---

## 6. Verification and Testing

Run backend tests:
```bash
cmd /c "set PYTHONPATH=. && .venv\Scripts\pytest.exe backend/tests/test_phone_authentication.py"
```

Run frontend test suite:
```bash
npm --prefix frontend test -- --run
```

Run frontend production build:
```bash
npm --prefix frontend run build
```

