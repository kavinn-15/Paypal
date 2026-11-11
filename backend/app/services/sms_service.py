import logging
import json
import httpx
from typing import Optional, Dict, Any
from backend.app.config import settings

logger = logging.getLogger("sms_service")

# In-memory store for dev/testing inspections: {normalized_phone: last_message_payload}
_DEV_SMS_INBOX: Dict[str, Dict[str, Any]] = {}


def get_last_dev_sms(phone_number: str) -> Optional[Dict[str, Any]]:
    """Helper for automated testing and local debugging in dev mode."""
    return _DEV_SMS_INBOX.get(phone_number)


def clear_dev_sms_inbox():
    """Clears in-memory test SMS records."""
    _DEV_SMS_INBOX.clear()


class SMSProviderBase:
    """Base interface for pluggable SMS providers."""

    def send_sms(self, to_phone: str, message: str, template_id: Optional[str] = None, variables: Optional[Dict[str, str]] = None) -> bool:
        raise NotImplementedError("Subclasses must implement send_sms")


class ConsoleSMSProvider(SMSProviderBase):
    """
    Console SMS provider for local development, demo mode, and automated test suites.
    Cleanly formats and logs SMS messages without making external paid API requests.
    """

    def send_sms(self, to_phone: str, message: str, template_id: Optional[str] = None, variables: Optional[Dict[str, str]] = None) -> bool:
        if not settings.DEV_MODE:
            logger.error("SMS dispatch failure: Console provider is prohibited in production mode. Configure a valid SMS provider (twilio, msg91, exotel).")
            return False
        logger.info(
            f"\n"
            f"========================= [SMS DISPATCH - CONSOLE] =========================\n"
            f"TO:        {to_phone}\n"
            f"SENDER_ID: {settings.SMS_SENDER_ID}\n"
            f"TEMPLATE:  {template_id or 'DEFAULT'}\n"
            f"MESSAGE:   {message}\n"
            f"============================================================================"
        )
        _DEV_SMS_INBOX[to_phone] = {
            "to": to_phone,
            "message": message,
            "template_id": template_id,
            "variables": variables or {},
        }
        return True


class TwilioSMSProvider(SMSProviderBase):
    """
    Production-grade global SMS provider via Twilio REST API.
    """

    def __init__(self):
        self.account_sid = settings.SMS_ACCOUNT_SID or settings.SMS_API_KEY
        self.auth_token = settings.SMS_AUTH_TOKEN
        self.from_sender = settings.SMS_SENDER_ID

    def send_sms(self, to_phone: str, message: str, template_id: Optional[str] = None, variables: Optional[Dict[str, str]] = None) -> bool:
        if not self.account_sid or not self.auth_token:
            logger.error("Twilio credentials missing. Please set SMS_ACCOUNT_SID and SMS_AUTH_TOKEN.")
            return False

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data = {
            "To": to_phone,
            "From": self.from_sender,
            "Body": message,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, data=data, auth=(self.account_sid, self.auth_token))
                if res.status_code in [200, 201]:
                    logger.info(f"Twilio SMS dispatched successfully to {to_phone}")
                    return True
                else:
                    logger.error(f"Twilio SMS API error {res.status_code}: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Twilio SMS delivery exception: {e}")
            return False


class MSG91SMSProvider(SMSProviderBase):
    """
    DLT-compliant SMS provider for India & international routes via MSG91 Flow API.
    """

    def __init__(self):
        self.auth_key = settings.SMS_API_KEY or settings.SMS_AUTH_TOKEN
        self.sender_id = settings.SMS_SENDER_ID
        self.default_template_id = settings.SMS_TEMPLATE_ID

    def send_sms(self, to_phone: str, message: str, template_id: Optional[str] = None, variables: Optional[Dict[str, str]] = None) -> bool:
        if not self.auth_key:
            logger.error("MSG91 API key missing. Please set SMS_API_KEY.")
            return False

        clean_phone = to_phone.lstrip("+")
        flow_template = template_id or self.default_template_id

        url = "https://control.msg91.com/api/v5/flow/"
        headers = {
            "authkey": self.auth_key,
            "content-type": "application/json",
            "accept": "application/json",
        }

        payload: Dict[str, Any] = {
            "template_id": flow_template or "flow_template_default",
            "sender": self.sender_id,
            "short_url": "0",
            "mobiles": clean_phone,
            "message": message,
        }
        if variables:
            payload.update(variables)

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload, headers=headers)
                if res.status_code in [200, 201]:
                    logger.info(f"MSG91 SMS sent to {clean_phone}")
                    return True
                else:
                    logger.error(f"MSG91 SMS API error {res.status_code}: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"MSG91 SMS delivery exception: {e}")
            return False


class ExotelSMSProvider(SMSProviderBase):
    """
    Exotel transactional SMS provider for Indian enterprises.
    """

    def __init__(self):
        self.account_sid = settings.SMS_ACCOUNT_SID
        self.api_key = settings.SMS_API_KEY
        self.api_token = settings.SMS_AUTH_TOKEN
        self.sender_id = settings.SMS_SENDER_ID

    def send_sms(self, to_phone: str, message: str, template_id: Optional[str] = None, variables: Optional[Dict[str, str]] = None) -> bool:
        if not self.account_sid or not self.api_key or not self.api_token:
            logger.error("Exotel credentials missing. Please set SMS_ACCOUNT_SID, SMS_API_KEY, and SMS_AUTH_TOKEN.")
            return False

        clean_phone = to_phone.lstrip("+")
        url = f"https://api.exotel.com/v1/Accounts/{self.account_sid}/Sms/send.json"
        data = {
            "From": self.sender_id,
            "To": clean_phone,
            "Body": message,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, data=data, auth=(self.api_key, self.api_token))
                if res.status_code in [200, 201]:
                    return True
                else:
                    logger.error(f"Exotel SMS error {res.status_code}: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Exotel SMS exception: {e}")
            return False


def get_sms_provider() -> SMSProviderBase:
    """Factory selecting provider based on SMS_PROVIDER setting."""
    provider_name = (settings.SMS_PROVIDER or "console").lower().strip()
    if provider_name == "twilio":
        return TwilioSMSProvider()
    elif provider_name == "msg91":
        return MSG91SMSProvider()
    elif provider_name == "exotel":
        return ExotelSMSProvider()
    return ConsoleSMSProvider()


def render_phone_verification_sms(code: str) -> str:
    """Template for phone number registration / verification OTP."""
    return f"Cashflow Lifeline: Your verification code is {code}. Valid for 5 minutes. Do not share this OTP with anyone."


def render_phone_login_sms(code: str) -> str:
    """Template for passwordless phone OTP sign in."""
    return f"Cashflow Lifeline: Your secure sign-in code is {code}. Valid for 5 minutes. If you did not request this, secure your account."


def render_password_reset_sms(code: str) -> str:
    """Template for phone-based account recovery."""
    return f"Cashflow Lifeline: Your password recovery code is {code}. Valid for 5 minutes. Do not disclose this code."


def render_security_alert_sms(event: str) -> str:
    """Template for critical security change notification."""
    return f"Cashflow Lifeline Security Alert: {event}. If this was not you, please contact support immediately."


def dispatch_sms(
    to_phone: str,
    message: str,
    template_id: Optional[str] = None,
    variables: Optional[Dict[str, str]] = None
) -> bool:
    """
    High-level synchronous entry point to deliver an SMS through the configured provider.
    Fails safely without raising exceptions to API callers.
    """
    if not settings.SMS_ENABLED:
        logger.info(f"SMS disabled via config. Suppressing SMS to {to_phone}")
        return True

    provider = get_sms_provider()
    try:
        return provider.send_sms(to_phone, message, template_id, variables)
    except Exception as e:
        logger.error(f"Failed to dispatch SMS to {to_phone}: {e}")
        return False
