import os
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator, model_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Locate root directory and load .env
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
    # PayPal Sandbox Configuration
    PAYPAL_CLIENT_ID: str = Field(default="sandbox_client_id_placeholder")
    PAYPAL_CLIENT_SECRET: str = Field(default="sandbox_client_secret_placeholder")
    PAYPAL_WEBHOOK_ID: Optional[str] = Field(default=None)
    PAYPAL_BASE_URL: str = Field(default="https://api-m.sandbox.paypal.com")

    # LLM Settings
    LLM_PROVIDER: str = Field(default="template")  # "template", "anthropic", "gemini"
    LLM_API_KEY: Optional[str] = Field(default=None)
    LLM_MODEL: Optional[str] = Field(default=None)

    # Security & Guardrail
    APPROVAL_SECRET: str = Field(default="cashflow-lifeline-sandbox-hmac-secret-key-32bytes")
    JWT_SECRET: str = Field(default="cashflow-lifeline-jwt-super-secure-token-secret-2026")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=30)  # 30 minutes access token
    JWT_REFRESH_EXPIRE_DAYS: int = Field(default=7)  # 7 days
    PUBLIC_BASE_URL: str = Field(default="http://localhost:8000")
    APP_BASE_URL: str = Field(default="http://localhost:5173")
    DATABASE_URL: str = Field(default="sqlite:///./cashflow.db")
    DATABASE_DISABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices("DATABASE_DISABLED", "DISABLE_DATABASE", "SKIP_DB_INIT"),
        description="When true, enables temporary deployment mode: skips init_db(), migrations, and database connections. Database-dependent endpoints return 503."
    )
    ALLOWED_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            clean = v.strip()
            if clean.startswith("mysql://"):
                return "mysql+pymysql://" + clean[len("mysql://"):]
            return clean
        return v

    @field_validator("PUBLIC_BASE_URL", "APP_BASE_URL", mode="before")
    @classmethod
    def clean_base_urls(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().rstrip("/")
        return v

    # OTP & Verification Security
    OTP_PEPPER: str = Field(default="cashflow-lifeline-otp-pepper-secret-key-32b")
    OTP_EXPIRE_MINUTES: int = Field(default=10)
    OTP_RESEND_COOLDOWN_SECONDS: int = Field(default=60)
    OTP_MAX_ATTEMPTS: int = Field(default=5)
    RESET_TOKEN_EXPIRE_MINUTES: int = Field(default=15)

    # Email Service Configuration
    EMAIL_PROVIDER: str = Field(default="console")  # "console", "smtp", "resend", "sendgrid"
    EMAIL_FROM: str = Field(default="security@cashflowlifeline.com")
    EMAIL_API_KEY: Optional[str] = Field(default=None)
    SMTP_HOST: Optional[str] = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SMTP_USE_TLS: bool = Field(default=True)

    # SMS Service Configuration
    SMS_PROVIDER: str = Field(default="console")  # "console", "twilio", "msg91", "sns", "exotel"
    SMS_ENABLED: bool = Field(default=True)
    SMS_API_KEY: Optional[str] = Field(default=None)
    SMS_AUTH_TOKEN: Optional[str] = Field(default=None)
    SMS_ACCOUNT_SID: Optional[str] = Field(default=None)
    SMS_SENDER_ID: str = Field(default="CFLIFE")
    SMS_TEMPLATE_ID: Optional[str] = Field(default=None)
    SMS_OTP_EXPIRE_MINUTES: int = Field(default=5)  # 5 minutes required
    SMS_RESEND_COOLDOWN_SECONDS: int = Field(default=60)
    DEFAULT_COUNTRY_DIAL_CODE: str = Field(default="+91")
    DEFAULT_COUNTRY_REGION: str = Field(default="IN")

    # Google OAuth 2.0 / OpenID Connect
    GOOGLE_CLIENT_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_CLIENT_ID", "VITE_GOOGLE_CLIENT_ID")
    )
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(default=None)
    GOOGLE_REDIRECT_URI: Optional[str] = Field(default=None)

    @field_validator("GOOGLE_CLIENT_ID", mode="before")
    @classmethod
    def clean_google_client_id(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("GOOGLE_CLIENT_SECRET", mode="before")
    @classmethod
    def clean_google_client_secret(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("GOOGLE_REDIRECT_URI", mode="before")
    @classmethod
    def clean_google_redirect_uri(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            v = v.strip().rstrip("/")
            return v if v else None
        return v

    # Policy Limits
    MAX_DISCOUNT_PCT: float = Field(default=5.0)  # maximum 5% early payment discount
    MAX_PAYOUT_AMOUNT: float = Field(default=10000.0)  # max single payout
    ALLOWED_CURRENCIES: str = Field(default="USD,EUR,GBP,CAD,INR")
    DEV_MODE: bool = Field(default=False)
    ALLOW_DEMO_ENDPOINTS: bool = Field(default=True)
    CANONICAL_DEMO_EMAIL: str = Field(default="alex.morgan.freelance@example.com")
    PORT: int = Field(default=8000)

    # Regional Detection & Geolocation Configuration
    TRUSTED_PROXIES: str = Field(default="127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16")
    DEV_COUNTRY_OVERRIDE: Optional[str] = Field(default=None)  # Active ONLY when DEV_MODE=True
    IP_GEOLOCATION_PROVIDER: str = Field(default="ipapi")  # "ipapi" | "ip_api"

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def allowed_currencies_list(self) -> List[str]:
        return [c.strip().upper() for c in self.ALLOWED_CURRENCIES.split(",") if c.strip()]

    @property
    def allowed_origins_list(self) -> List[str]:
        origins = [o.strip().rstrip("/") for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        if hasattr(self, "APP_BASE_URL") and self.APP_BASE_URL:
            clean_app = self.APP_BASE_URL.strip().rstrip("/")
            if clean_app and clean_app not in origins:
                origins.append(clean_app)
        return origins

    @property
    def trusted_proxies_list(self) -> List[str]:
        return [p.strip() for p in self.TRUSTED_PROXIES.split(",") if p.strip()]

    @model_validator(mode="after")
    def resolve_google_redirect_uri(self) -> 'Settings':
        clean_app = (self.APP_BASE_URL or "").strip().rstrip("/")
        if not clean_app:
            clean_app = "http://localhost:5173" if self.DEV_MODE else "https://cashflow-lifeline.vercel.app"
            object.__setattr__(self, "APP_BASE_URL", clean_app)

        raw_redirect = (self.GOOGLE_REDIRECT_URI or "").strip()

        # If GOOGLE_REDIRECT_URI is not set, derive dynamically from APP_BASE_URL
        if not raw_redirect:
            object.__setattr__(self, "GOOGLE_REDIRECT_URI", f"{clean_app}/auth/callback/google")
        else:
            clean_redirect = raw_redirect.rstrip("/")
            # If APP_BASE_URL is a production non-localhost domain but GOOGLE_REDIRECT_URI was left as localhost
            is_app_production = "localhost" not in clean_app and "127.0.0.1" not in clean_app
            is_redirect_localhost = "localhost" in clean_redirect or "127.0.0.1" in clean_redirect
            if is_app_production and is_redirect_localhost:
                logger.warning(
                    f"GOOGLE_REDIRECT_URI was configured with localhost ({clean_redirect}), "
                    f"but APP_BASE_URL is production ({clean_app}). Automatically resolving to match APP_BASE_URL."
                )
                clean_redirect = f"{clean_app}/auth/callback/google"
            object.__setattr__(self, "GOOGLE_REDIRECT_URI", clean_redirect)

        # In production mode (DEV_MODE=False), strictly prevent redirecting to localhost
        if not self.DEV_MODE:
            final_redirect = self.GOOGLE_REDIRECT_URI or ""
            if "localhost" in final_redirect or "127.0.0.1" in final_redirect:
                prod_default = "https://cashflow-lifeline.vercel.app/auth/callback/google"
                logger.warning(
                    f"Production mode active but GOOGLE_REDIRECT_URI points to localhost ({final_redirect}). "
                    f"Defaulting to production frontend callback: {prod_default}"
                )
                object.__setattr__(self, "GOOGLE_REDIRECT_URI", prod_default)
                if "localhost" in self.APP_BASE_URL or "127.0.0.1" in self.APP_BASE_URL:
                    object.__setattr__(self, "APP_BASE_URL", "https://cashflow-lifeline.vercel.app")
        return self

    @model_validator(mode="after")
    def validate_production_security(self) -> 'Settings':
        if not self.DEV_MODE:
            # 1. Enforce that demo/simulation endpoints are strictly disabled in production
            object.__setattr__(self, "ALLOW_DEMO_ENDPOINTS", False)

            # 2. Reject known default secrets in production
            known_insecure = {
                "cashflow-lifeline-sandbox-hmac-secret-key-32bytes",
                "cashflow-lifeline-jwt-super-secure-token-secret-2026",
                "change-this-to-a-secure-random-32-byte-secret-key-1234",
                "change-this-to-a-secure-jwt-signing-secret-key-5678",
                "cashflow-lifeline-otp-pepper-secret-key-32b",
                "change-this-to-a-cryptographically-secure-otp-pepper-9012"
            }
            if self.APPROVAL_SECRET in known_insecure or len(self.APPROVAL_SECRET) < 32:
                raise ValueError("CRITICAL SECURITY VIOLATION: Production mode requires a unique, high-entropy APPROVAL_SECRET (>= 32 chars). Default secrets rejected.")
            if self.JWT_SECRET in known_insecure or len(self.JWT_SECRET) < 32:
                raise ValueError("CRITICAL SECURITY VIOLATION: Production mode requires a unique, high-entropy JWT_SECRET (>= 32 chars). Default secrets rejected.")
            if self.OTP_PEPPER in known_insecure or len(self.OTP_PEPPER) < 32:
                raise ValueError("CRITICAL SECURITY VIOLATION: Production mode requires a unique, high-entropy OTP_PEPPER (>= 32 chars). Default secrets rejected.")

            # 3. Require valid registered PayPal webhook ID in production
            if not self.PAYPAL_WEBHOOK_ID or "placeholder" in self.PAYPAL_WEBHOOK_ID.lower():
                raise ValueError("CRITICAL: Production mode requires a valid registered PAYPAL_WEBHOOK_ID.")

            # 4. Require valid PayPal Sandbox API credentials in production (reject placeholders)
            insecure_paypal_ids = {
                "sandbox_client_id_placeholder",
                "your_paypal_sandbox_client_id",
                "placeholder",
                ""
            }
            if not self.PAYPAL_CLIENT_ID or self.PAYPAL_CLIENT_ID.lower() in insecure_paypal_ids or "placeholder" in self.PAYPAL_CLIENT_ID.lower():
                raise ValueError("CRITICAL SECURITY VIOLATION: Production mode requires valid PayPal credentials. Placeholder PAYPAL_CLIENT_ID is rejected.")
            if not self.PAYPAL_CLIENT_SECRET or "placeholder" in self.PAYPAL_CLIENT_SECRET.lower() or len(self.PAYPAL_CLIENT_SECRET) < 8:
                raise ValueError("CRITICAL SECURITY VIOLATION: Production mode requires valid PayPal credentials. Placeholder PAYPAL_CLIENT_SECRET is rejected.")
        return self

    def get_safe_log_summary(self) -> dict:
        """Returns non-sensitive configuration parameters with all keys and secrets redacted."""
        return {
            "DEV_MODE": self.DEV_MODE,
            "DATABASE_DISABLED": self.DATABASE_DISABLED,
            "ALLOW_DEMO_ENDPOINTS": self.ALLOW_DEMO_ENDPOINTS,
            "APP_BASE_URL": self.APP_BASE_URL,
            "GOOGLE_REDIRECT_URI": self.GOOGLE_REDIRECT_URI,
            "PAYPAL_BASE_URL": self.PAYPAL_BASE_URL,
            "PAYPAL_CLIENT_ID_PREVIEW": (self.PAYPAL_CLIENT_ID[:6] + "...") if self.PAYPAL_CLIENT_ID else None,
            "LLM_PROVIDER": self.LLM_PROVIDER,
            "EMAIL_PROVIDER": self.EMAIL_PROVIDER,
            "SMS_PROVIDER": self.SMS_PROVIDER,
            "PORT": self.PORT
        }

    @field_validator("PAYPAL_BASE_URL")
    @classmethod
    def validate_sandbox_only(cls, v: str) -> str:
        clean = v.strip().rstrip("/")
        # Strictly verify sandbox host
        if "sandbox.paypal.com" not in clean:
            raise ValueError(
                f"SAFETY VIOLATION: Refusing to start. PAYPAL_BASE_URL must be the sandbox endpoint "
                f"(https://api-m.sandbox.paypal.com). Received: '{v}'"
            )
        if "api-m.paypal.com" in clean and "sandbox" not in clean:
            raise ValueError("CRITICAL: Production PayPal base URL detected! Refusing to start.")
        return clean


settings = Settings()
