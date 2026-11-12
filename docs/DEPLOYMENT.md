# Production Deployment Guide: 100% Free Tier

Cashflow Lifeline is architected for zero-cost deployment across free-tier services:
- **Backend**: Render Free Web Service
- **Frontend**: Vercel Free Hobby Plan
- **Database**: TiDB Cloud Serverless / Starter
- **Payments**: PayPal Sandbox only

---

## 1. Backend: Render Free Web Service

### Configuration Files
The repository includes [render.yaml](file:///d:/Project/Paypal/render.yaml) preconfigured for Render Blueprints.

### Core Environment Variables

| Variable | Recommended / Default Value | Notes |
| :--- | :--- | :--- |
| `DATABASE_DISABLED` | `true` (temporary) / `false` (with DB) | Set to `true` to run backend without database connection or migrations. |
| `DEV_MODE` | `false` | Enforces production security checks (strong secrets, sandbox safety). |
| `DATABASE_URL` | `mysql://<user>:<password>@gateway01...:4000/<db>` | Your TiDB Cloud connection string (when `DATABASE_DISABLED=false`). |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` | Strictly sandbox endpoints; production endpoints are rejected on startup. |
| `PAYPAL_CLIENT_ID` | Sandbox Client ID | From PayPal Developer Sandbox dashboard. |
| `PAYPAL_CLIENT_SECRET` | Sandbox Secret | From PayPal Developer Sandbox dashboard. |
| `PAYPAL_WEBHOOK_ID` | Sandbox Webhook ID | From registered webhook in PayPal Sandbox dashboard. |
| `APPROVAL_SECRET` | Auto-generated 32+ bytes | Render generates automatically (`generateValue: true`). |
| `JWT_SECRET` | Auto-generated 32+ bytes | Render generates automatically (`generateValue: true`). |
| `OTP_PEPPER` | Auto-generated 32+ bytes | Render generates automatically (`generateValue: true`). |
| `APP_BASE_URL` | `https://cashflow-lifeline.vercel.app` | Vercel production frontend domain. |
| `GOOGLE_REDIRECT_URI` | `https://cashflow-lifeline.vercel.app/auth/callback/google` | Google OAuth production callback URL. |
| `GOOGLE_CLIENT_ID` | `<your-google-client-id>.apps.googleusercontent.com` | Google OAuth 2.0 Web Client ID. |
| `GOOGLE_CLIENT_SECRET` | `<your-google-client-secret>` | Google OAuth 2.0 Web Client Secret. |
| `ALLOWED_ORIGINS` | `https://cashflow-lifeline.vercel.app` | Allowed CORS origins for browser requests. |
| `PUBLIC_BASE_URL` | `https://cashflow-lifeline.onrender.com` | Render public backend URL. |

---

## 2. Temporary Database-Less Deployment Mode

### When to use
Use `DATABASE_DISABLED=true` when:
1. TiDB Cloud database integration is postponed.
2. The database user lacks DDL privileges (`CREATE command denied for table 'alembic_version'`).
3. You need the FastAPI backend live on Render immediately for API health verification and documentation.

### Service Behavior in Temporary Mode
- **Startup**: FastAPI lifespan starts immediately without calling `init_db()` or executing Alembic migrations.
- **Health Checks**:
  - `GET /health` returns `200 OK` (Render health check succeeds and service stays healthy).
  - `GET /health/db` returns `503 Service Unavailable` with diagnostic detail.
- **Independent Endpoints**:
  - `/status`, `/docs`, `/openapi.json`, `/region/countries`, `/region/currencies`, `/region/rates` all return `200 OK`.
- **Database-Dependent Endpoints**:
  - All routes requiring database access (e.g. `/auth/login`, `/clients`, `/forecast/latest`, `/obligations`) return `503 Service Unavailable` with descriptive detail.
  - No dummy/fake data is returned; multi-tenant security is strictly maintained.

---

## 3. Frontend: Vercel

1. Import your GitHub repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Add Environment Variable:
   - `VITE_API_URL`: `https://cashflow-lifeline.onrender.com`
4. Deploy. The included `frontend/vercel.json` ensures client-side SPA routing (`/* -> /index.html`) works out of the box.

---

## 4. Google Cloud Console: OAuth 2.0 Configuration

In the [Google Cloud Console](https://console.cloud.google.com/apis/credentials), configure your Web Application OAuth 2.0 client credentials:

### Authorized JavaScript Origins
Add both local development and production frontend origins:
- `https://cashflow-lifeline.vercel.app`
- `http://localhost:5173`

### Authorized Redirect URIs
Add both local development and production frontend callback routes:
- `https://cashflow-lifeline.vercel.app/auth/callback/google`
- `http://localhost:5173/auth/callback/google`

> **Note**: Google OAuth strictly disallows wildcards in Redirect URIs. The exact URI `https://cashflow-lifeline.vercel.app/auth/callback/google` must be registered.


