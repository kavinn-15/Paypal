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
    ALLOWED_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")

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
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:5173/auth/callback/google")

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
        origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        if hasattr(self, "APP_BASE_URL") and self.APP_BASE_URL:
            clean_app = self.APP_BASE_URL.strip().rstrip("/")
            if clean_app and clean_app not in origins:
                origins.append(clean_app)
        return origins

    @property
    def trusted_proxies_list(self) -> List[str]:
        return [p.strip() for p in self.TRUSTED_PROXIES.split(",") if p.strip()]

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
            "ALLOW_DEMO_ENDPOINTS": self.ALLOW_DEMO_ENDPOINTS,
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
