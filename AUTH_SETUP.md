# Cashflow Lifeline — Authentication & Identity Security Guide

This document describes the production-minded authentication, verification, and recovery architecture for **Cashflow Lifeline**, built for the PayPal AI Hackathon 2026.

---

## 1. Architecture Overview

```
                      +------------------------------------------+
                      |         Frontend Authentication          |
                      |  (React 18 + Vite + Tailwind + Context)  |
                      +--------------------+---------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
         [Email + Password Flow]                           [Google OAuth 2.0]
                   |                                               |
                   v                                               v
        FastAPI /auth/register                          FastAPI /auth/google/start
        - Argon2id Password Hashing                     - PKCE code_challenge / state
        - Issues 6-digit OTP                            - Google consent redirect
                   |                                               |
                   v                                               v
        FastAPI /auth/email/verify                      FastAPI /auth/google/callback
        - Keyed HMAC-SHA256 (OTP_PEPPER)                - Exchanges code & validates ID token
        - Attempt limiting (max 5)                      - Links to OAuthIdentity model
        - Marks email_verified=True                                |
                   |                                               |
                   +-----------------------+-----------------------+
                                           |
                                           v
                             +---------------------------+
                             |   Protected Workspaces    |
                             |   - JWT Bearer Tokens     |
                             |   - Verified Email Check  |
                             |   - Multi-Tenant Owner ID |
                             |     Query Isolation       |
                             +---------------------------+
```

### Key Security Properties

1. **Argon2id Password Hashing**:
   - Modern RFC 9106 Argon2id password hashing via `argon2-cffi`.
   - Backward-compatible verification for legacy bcrypt password hashes.
   - Dual-mode verification: automatically transparent.

2. **Cryptographically Secure Email OTP Verification**:
   - 6-digit codes generated via Python `secrets.choice("0123456789")`.
   - Stored **only as keyed HMAC-SHA256 hashes** with server-side `OTP_PEPPER` over `{email}:{purpose}:{otp}`. Plaintext OTPs are never stored in the database, returned in API responses, or exposed in logs.
   - Expire after 10 minutes (`OTP_EXPIRE_MINUTES`).
   - Single-use consumption (marked with `consumed_at`).
   - Maximum 5 attempts per OTP (`OTP_MAX_ATTEMPTS`).
   - Resend cooldown enforcement (60 seconds) to prevent SMS/email flooding.
   - Purpose binding: OTPs for `email_verification` cannot be submitted for `password_reset`.

3. **3-Step Password Recovery with Anti-Enumeration**:
   - **Step 1 (`POST /auth/password-reset/request`)**: Always returns `200 OK` with generic success message regardless of whether the email exists, preventing timing and existence enumeration. Dispatches OTP via email.
   - **Step 2 (`POST /auth/password-reset/verify-otp`)**: Verifies 6-digit code against keyed hash. Upon success, issues a short-lived single-use JWT reset authorization token (`purpose="password_reset_auth"`).
   - **Step 3 (`POST /auth/password-reset/confirm`)**: Verifies reset token, hashes new password with Argon2id, revokes all active refresh tokens for the user, and sends a security confirmation email.

4. **Multi-Provider OAuth 2.0 / OpenID Connect**:
   - Supports Google Sign-In with PKCE and state protection (`/auth/google/start`, `/auth/google/callback`).
   - Supports client-side Google ID Token credential verification (`/auth/google/token`).
   - Extensible `OAuthIdentity` table associating `(provider, provider_user_id)` to internal `Owner`.
   - Safe account linking: Existing email accounts are linked without account takeover vulnerability.

5. **Strict Financial Dashboard Protection**:
   - `get_verified_current_user` FastAPI dependency enforces `email_verified=True` on protected financial endpoints for registered users.
   - Frontend `ProtectedRoute` intercepts unverified accounts and routes them to `/verify-email`.

---

## 2. Environment Variables & Configuration

Add the following variables to your `.env` file (see `.env.example`):

```bash
# -------------------------------------------------------------
# Security & Token Cryptography
# -------------------------------------------------------------
APPROVAL_SECRET=change-this-to-a-secure-random-32-byte-secret-key-1234
JWT_SECRET=change-this-to-a-secure-jwt-signing-secret-key-5678
PUBLIC_BASE_URL=http://localhost:8000
APP_BASE_URL=http://localhost:5173

# -------------------------------------------------------------
# Email Verification & Password Reset OTP System
# -------------------------------------------------------------
OTP_PEPPER=change-this-to-a-cryptographically-secure-otp-pepper-9012
OTP_EXPIRE_MINUTES=10
OTP_RESEND_COOLDOWN_SECONDS=60
OTP_MAX_ATTEMPTS=5
RESET_TOKEN_EXPIRE_MINUTES=15

# -------------------------------------------------------------
# Email Provider (console | smtp | resend | sendgrid)
# -------------------------------------------------------------
EMAIL_PROVIDER=console
EMAIL_FROM="Cashflow Lifeline <no-reply@cashflowlifeline.com>"
EMAIL_API_KEY=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_TLS=true
SMTP_SSL=false

# -------------------------------------------------------------
# Google OAuth 2.0 / OpenID Connect
# -------------------------------------------------------------
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5173/auth/callback/google
```

---

## 3. Google OAuth 2.0 Setup Guide

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create a new project (e.g. `cashflow-lifeline`).
3. Configure the **OAuth Consent Screen**:
   - User Type: **External**
   - App Name: `Cashflow Lifeline`
   - Scopes: `openid`, `.../auth/userinfo.email`, `.../auth/userinfo.profile`
4. Under **Credentials**, click **Create Credentials** &rarr; **OAuth Client ID**:
   - Application Type: **Web application**
   - Name: `Cashflow Lifeline Web`
   - Authorized JavaScript origins:
     - https://cashflow-lifeline.vercel.app
     - http://localhost:5173
   - Authorized redirect URIs:
     - https://cashflow-lifeline.vercel.app/auth/callback/google
     - http://localhost:5173/auth/callback/google
5. Copy your **Client ID** and **Client Secret** into `.env`.

> **Note for Local/Mock Testing**: In `DEV_MODE=true`, Google verification accepts `mock_google:<sub>:<email>` tokens without making external network calls, allowing full automated test coverage offline.

---

## 4. Email Providers Setup

Cashflow Lifeline includes a unified multi-provider email service (`backend/app/services/email_service.py`):

| Provider | Setting | Configuration |
|---|---|---|
| **Console Logger** *(Default for local dev)* | `EMAIL_PROVIDER=console` | Prints branded HTML emails directly to stdout / server logs. Zero external dependencies. |
| **Resend** | `EMAIL_PROVIDER=resend` | Set `EMAIL_API_KEY=re_...` and `EMAIL_FROM=onboarding@resend.dev` |
| **SendGrid** | `EMAIL_PROVIDER=sendgrid` | Set `EMAIL_API_KEY=SG....` and `EMAIL_FROM=verified@yourdomain.com` |
| **SMTP (Gmail / AWS SES)** | `EMAIL_PROVIDER=smtp` | Set `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USERNAME`, `SMTP_PASSWORD` |

---

## 5. Database Schema & Migrations

The database models are located in `backend/app/models.py`:

- `Owner`:
  - `email_verified`: Boolean flag
  - `email_verified_at`: Timestamp of successful OTP verification
  - Relationships: `otps`, `oauth_identities`
- `EmailOTP`:
  - `id`: Integer Primary Key
  - `owner_id`: Optional FK to `owners.id`
  - `email`: String (indexed)
  - `otp_hash`: Keyed HMAC-SHA256 hex digest
  - `purpose`: `"email_verification"` | `"password_reset"`
  - `expires_at`: Datetime
  - `attempts_count`: Integer
  - `max_attempts`: Integer (default 5)
  - `consumed_at`: Datetime
- `OAuthIdentity`:
  - `id`: Integer Primary Key
  - `owner_id`: FK to `owners.id`
  - `provider`: `"google"` | `"microsoft"`
  - `provider_user_id`: Provider subject ID
  - `email`: String
  - Unique Constraint: `(provider, provider_user_id)`

### Running Migrations

```bash
# Alembic Migration
alembic upgrade head
```

*(For SQLite dev setups, `init_db()` in `backend/app/db.py` automatically detects and adds missing columns without data loss).*

---

## 6. API Reference

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/auth/register` | Register new user, hash password with Argon2id, dispatch 6-digit verification OTP. | No |
| `POST` | `/auth/login` | Email/password login with 5-attempt rate limiter. Returns JWT & `email_verified` status. | No |
| `POST` | `/auth/email/verify` | Validates 6-digit OTP code and marks `email_verified=True`. | No |
| `POST` | `/auth/email/verification/resend` | Dispatches new 6-digit OTP enforcing 60s cooldown. | No |
| `POST` | `/auth/password-reset/request` | Generic anti-enumeration password recovery request; dispatches 6-digit OTP. | No |
| `POST` | `/auth/password-reset/verify-otp` | Validates reset OTP and issues single-use reset JWT token. | No |
| `POST` | `/auth/password-reset/confirm` | Consumes reset JWT, updates password hash with Argon2id, revokes old sessions. | No |
| `GET` | `/auth/google/start` | Returns Google OAuth 2.0 authorization URL and state. | No |
| `GET` | `/auth/google/callback` | OAuth redirect callback; exchanges code, links or creates user. | No |
| `POST` | `/auth/google/token` | Direct Google ID token verification and login. | No |
| `POST` | `/auth/refresh` | Exchange refresh token for fresh short-lived access token. | No |
| `POST` | `/auth/logout` | Revokes refresh token in database. | No |
| `GET` | `/auth/me` | Returns authenticated user profile including verification status. | Yes |

---

## 7. Running Verification Tests

### Backend Test Suite (Pytest)

```bash
# Run all 59 backend tests (100% pass rate)
cmd /c "set PYTHONPATH=. && .venv\Scripts\pytest.exe backend/tests"

# Run dedicated authentication test suite
cmd /c "set PYTHONPATH=. && .venv\Scripts\pytest.exe backend/tests/test_secure_authentication.py"
```

### Frontend Test Suite (Vitest) & Build

```bash
# Run vitest unit tests
npm --prefix frontend test -- --run

# Run TypeScript compilation and production build
npm --prefix frontend run build
```

