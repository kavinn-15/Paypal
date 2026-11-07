import os
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
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
    JWT_EXPIRE_MINUTES: int = Field(default=1440)  # 24 hours
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
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None)
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(default=None)
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:5173/auth/callback/google")

    # Policy Limits
    MAX_DISCOUNT_PCT: float = Field(default=5.0)  # maximum 5% early payment discount
    MAX_PAYOUT_AMOUNT: float = Field(default=10000.0)  # max single payout
    ALLOWED_CURRENCIES: str = Field(default="USD,EUR,GBP,CAD,INR")
    DEV_MODE: bool = Field(default=True)
    ALLOW_DEMO_ENDPOINTS: bool = Field(default=True)
    PORT: int = Field(default=8000)

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
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

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
