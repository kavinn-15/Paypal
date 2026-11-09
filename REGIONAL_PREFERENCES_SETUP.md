# Cashflow Lifeline — Automatic Country Detection, Currency Localization & Regional Preferences

This document provides a comprehensive operational and architectural reference for the automatic country detection, multi-currency localization, and regional preference system implemented across the Cashflow Lifeline platform.

---

## 1. Overview & Architectural Principles

Cashflow Lifeline is designed for global freelancers, agencies, and small businesses operating across international borders. The platform implements an end-to-end regional localization engine with strict adherence to the following fintech security and usability principles:

1. **Zero-Permission Approximate Geolocation**:
   - Geolocation is derived solely from reverse proxy/CDN headers (`CF-IPCountry`, `CloudFront-Viewer-Country`, `X-Country-Code`) and cached IP lookup fallbacks with strict timeouts ($\le 1.5$s).
   - The platform **never** requests device GPS or high-precision geolocation permissions from visitors.

2. **Strict Financial Currency Safety (Triple-Layer Separation)**:
   - **Base Accounting Ledger Currency (`Owner.currency`)**: The canonical currency in which double-entry entries, risk thresholds, and financial models are settled. This cannot be overwritten silently.
   - **Preferred Display Currency (`Owner.preferred_currency`)**: The presentation currency in which dashboards, forecasts, and visual summaries are rendered.
   - **Individual Transaction Currency (`Invoice.currency`, `Obligation.currency`)**: The native settlement currency of each invoice or obligation. Invoices issued in EUR or GBP preserve their original currency regardless of user display preference.

3. **Multi-Platform Consistency**:
   - Both anonymous visitors and authenticated users enjoy localized country and currency defaults.
   - Preferences chosen on public pages persist to `localStorage` (`cashflow_regional_preference`) and automatically pre-fill user registration and onboarding.

---

## 2. API Endpoints Reference

### Public Regional Endpoints

#### `GET /api/region/detect` (or `/region/detect`)
Detects visitor country and suggests default currency.
- **Query Parameters**:
  - `client_hint` *(optional, string)*: ISO 3166-1 alpha-2 country code hint from client cache.
- **Detection Precedence**:
  1. Explicit client hint (e.g. `?client_hint=IN`)
  2. CDN / Proxy country headers (`CF-IPCountry`, `CloudFront-Viewer-Country`, `X-Country-Code`, `X-Geo-Country`)
  3. Public IP geolocation lookup (`ipapi.co` with 1.5s timeout and in-memory TTL caching)
  4. Browser `Accept-Language` header
  5. Default fallback (`US` / `USD`)
- **Sample Response**:
  ```json
  {
    "country": "IN",
    "country_name": "India",
    "flag": "🇮🇳",
    "suggested_currency": "INR",
    "currency_name": "Indian Rupee",
    "currency_symbol": "₹",
    "decimals": 2,
    "dial_code": "+91",
    "locale": "en-IN",
    "detection_method": "header",
    "confidence": 0.95
  }
  ```

#### `GET /api/region/countries` (or `/region/countries`)
Returns list of all supported countries with flags, ISO codes, phone dial codes, default currencies, and popular badges.
- **Sample Item**:
  ```json
  {
    "code": "IN",
    "name": "India",
    "flag": "🇮🇳",
    "currency": "INR",
    "dial_code": "+91",
    "locale": "en-IN",
    "popular": true
  }
  ```

#### `GET /api/region/currencies` (or `/region/currencies`)
Returns list of supported currencies with symbols and decimal fraction specifications (including zero-decimal currencies like JPY, KRW and 3-decimal currencies like KWD, BHD).
- **Sample Items**:
  ```json
  [
    { "code": "USD", "name": "US Dollar", "symbol": "$", "decimals": 2 },
    { "code": "INR", "name": "Indian Rupee", "symbol": "₹", "decimals": 2 },
    { "code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimals": 0 },
    { "code": "KWD", "name": "Kuwaiti Dinar", "symbol": "KD", "decimals": 3 }
  ]
  ```

---

### Authenticated Profile Endpoints

#### `GET /api/profile/regional-preferences` (or `/profile/regional-preferences`)
- **Headers**: `Authorization: Bearer <access_token>`
- **Response**:
  ```json
  {
    "country": "IN",
    "country_name": "India",
    "flag": "🇮🇳",
    "currency": "USD",
    "preferred_currency": "INR",
    "currency_symbol": "₹",
    "locale": "en-IN",
    "region_detection_enabled": true,
    "region_preference_source": "manual",
    "updated_at": "2026-11-10T00:15:00.000000"
  }
  ```

#### `PUT /api/profile/regional-preferences` (or `/profile/regional-preferences`)
- **Headers**: `Authorization: Bearer <access_token>`
- **Request Body**:
  ```json
  {
    "country": "IN",
    "preferred_currency": "INR",
    "locale": "en-IN",
    "region_detection_enabled": true
  }
  ```
- **Auditing**: Every update generates a tamper-evident entry in `audit_log` with event `REGIONAL_PREFERENCES_UPDATED`.

---

## 3. Database Schema & Migration

### Alembic Migration
- **Revision ID**: `6f7a8b9c0d1e`
- **Revises**: `5e6f7a8b9c0d`
- **File**: `alembic/versions/6f7a8b9c0d1e_add_regional_preferences.py`

### Owner Table Columns Added / Verified
| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `country` | `String(50)` | Nullable | `'US'` | ISO 3166-1 alpha-2 country code |
| `currency` | `String(10)` | Non-null | `'USD'` | Base accounting ledger currency |
| `preferred_currency` | `String(10)` | Nullable | `'USD'` | User preferred display currency |
| `locale` | `String(10)` | Non-null | `'en-US'` | Regional locale for number and date formatting |
| `region_detection_enabled` | `Boolean` | Non-null | `True` | Whether auto-detection is enabled for future visits |
| `region_preference_source` | `String(30)` | Non-null | `'detected'` | Source of preference (`'detected'` or `'manual'`) |
| `region_preferences_updated_at` | `DateTime` | Nullable | `None` | UTC timestamp of last preference change |

---

## 4. Frontend Components & Localization

### 1. `RegionalFooterSelector` (`frontend/src/components/RegionalFooterSelector.tsx`)
- Displayed in the public footer of:
  - Landing Page (`/`)
  - Login Page (`/login`)
  - Register Page (`/register`)
  - Forgot Password Page (`/forgot-password`)
- Renders `🌐 [Flag] [Country Name] | [Currency Code] [Symbol]`.
- Clicking opens a dual-tab modal with search filtering across ~250 countries and 49 major global currencies.
- Features a one-click **"Auto-detect"** button to detect location on demand.
- Updates are dispatched via `regional-preference-changed` DOM custom event for immediate multi-component synchronization.

### 2. User Registration Experience (`frontend/src/pages/RegisterPage.tsx`)
- Automatically initializes country and currency dropdowns using detected region or stored anonymous preference.
- Displays an **Auto-localized** badge indicating country and suggested currency with override capability.
- Full dynamic catalogs populated via backend APIs.

### 3. Guided Onboarding Experience (`frontend/src/components/OnboardingModal.tsx`)
- Confirms detected country and suggested base operating currency.
- Provides immediate selection chips with major global currencies (USD, INR, EUR, GBP, CAD, AUD, JPY, SGD).
- Automatically persists preferences to database via `api.updateRegionalPreferences()`.

### 4. Authenticated Settings (`frontend/src/pages/SettingsPage.tsx`)
- Dedicated **Regional Preferences & Currency Localization** bento-card.
- Direct management of Country, Display Currency, and Auto-detection toggle.
- Clear distinction between **Display Currency** and **Base Accounting Ledger Currency (Audited Fixed)**.

### 5. Currency Formatter Utility (`frontend/src/utils/currency.ts`)
- Utilizes standard `Intl.NumberFormat` with custom fallback handling.
- Accurately formats zero-decimal currencies (JPY, KRW, VND, CLP, etc.) without false `.00` trailing cents.
- Formats 3-decimal currencies (KWD, BHD, OMR) with 3 fractional digits.

---

## 5. Verification & Testing

- **Backend Pytest Suite**:
  - `backend/tests/test_regional_preferences.py` (8/8 tests passing)
  - Tests covering client hints, proxy headers, language fallback, catalog endpoints, authenticated updates, and validation failure cases.
- **Frontend Vitest Suite**:
  - `frontend/src/RegionalPreferences.test.ts` (8/8 tests passing)
  - Tests covering zero-decimal fraction digits, `formatCurrency`, `getCurrencySymbol`, and localStorage persistence.
- **Production TypeScript Build**:
  - `npm --prefix frontend run build` completes with 0 errors.

