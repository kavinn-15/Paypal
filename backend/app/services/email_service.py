import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
import httpx
from backend.app.config import settings

logger = logging.getLogger("email_service")


def render_verification_email(name: str, otp_code: str) -> str:
    """HTML email template for new account email verification."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Verify Your Email — Cashflow Lifeline</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #081026; color: #f1f5f9; margin: 0; padding: 20px; }}
    .container {{ max-width: 540px; margin: 0 auto; background: #0d1a3a; border: 1px solid #1e346b; border-radius: 16px; padding: 32px; }}
    .logo {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; margin-bottom: 24px; }}
    .badge {{ font-size: 11px; font-weight: 700; color: #7ea1f3; background: rgba(75, 91, 252, 0.15); border: 1px solid rgba(75, 91, 252, 0.3); border-radius: 9999px; padding: 3px 8px; margin-left: 6px; text-transform: uppercase; }}
    h1 {{ font-size: 22px; font-weight: 800; color: #ffffff; margin-top: 0; }}
    p {{ font-size: 14px; line-height: 1.6; color: #cbd5e1; }}
    .otp-box {{ background: #081026; border: 1px solid #4b5bfc; border-radius: 12px; padding: 20px; text-align: center; margin: 28px 0; }}
    .otp-code {{ font-family: 'JetBrains Mono', monospace, Courier; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #4b5bfc; }}
    .warning {{ font-size: 12px; color: #94a3b8; border-top: 1px solid #1e346b; padding-top: 16px; margin-top: 24px; }}
    .footer {{ font-size: 11px; color: #64748b; text-align: center; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">CL <span style="font-weight: 300;">| Cashflow Lifeline</span><span class="badge">PayPal AI</span></div>
    <h1>Verify Your Business Email</h1>
    <p>Hello {name or 'Partner'},</p>
    <p>Thank you for registering with Cashflow Lifeline. Please enter the single-use 6-digit verification code below to verify your email and unlock your financial cashflow dashboard.</p>
    
    <div class="otp-box">
      <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #7ea1f3; margin-bottom: 8px;">Verification Code</div>
      <div class="otp-code">{otp_code}</div>
      <div style="font-size: 11px; color: #94a3b8; margin-top: 8px;">Expires in {settings.OTP_EXPIRE_MINUTES} minutes &bull; Single-use only</div>
    </div>

    <p>If you did not request this verification, please disregard this email.</p>
    
    <div class="warning">
      <strong>Security Notice:</strong> Cashflow Lifeline representatives will never ask for your 6-digit code or PayPal credentials.
    </div>
  </div>
  <div class="footer">
    &copy; 2026 Cashflow Lifeline &bull; Built for PayPal AI Hackathon &bull; Sandbox Mode
  </div>
</body>
</html>"""


def render_password_reset_email(name: str, otp_code: str) -> str:
    """HTML email template for password reset OTP."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Reset Your Password — Cashflow Lifeline</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #081026; color: #f1f5f9; margin: 0; padding: 20px; }}
    .container {{ max-width: 540px; margin: 0 auto; background: #0d1a3a; border: 1px solid #1e346b; border-radius: 16px; padding: 32px; }}
    .logo {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; margin-bottom: 24px; }}
    .badge {{ font-size: 11px; font-weight: 700; color: #7ea1f3; background: rgba(75, 91, 252, 0.15); border: 1px solid rgba(75, 91, 252, 0.3); border-radius: 9999px; padding: 3px 8px; margin-left: 6px; text-transform: uppercase; }}
    h1 {{ font-size: 22px; font-weight: 800; color: #ffffff; margin-top: 0; }}
    p {{ font-size: 14px; line-height: 1.6; color: #cbd5e1; }}
    .otp-box {{ background: #081026; border: 1px solid #4b5bfc; border-radius: 12px; padding: 20px; text-align: center; margin: 28px 0; }}
    .otp-code {{ font-family: 'JetBrains Mono', monospace, Courier; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #4b5bfc; }}
    .warning {{ font-size: 12px; color: #94a3b8; border-top: 1px solid #1e346b; padding-top: 16px; margin-top: 24px; }}
    .footer {{ font-size: 11px; color: #64748b; text-align: center; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">CL <span style="font-weight: 300;">| Cashflow Lifeline</span><span class="badge">Security Alert</span></div>
    <h1>Password Recovery Request</h1>
    <p>Hello {name or 'Partner'},</p>
    <p>A password reset request was initiated for your Cashflow Lifeline account. Use the following 6-digit code to complete the verification step:</p>
    
    <div class="otp-box">
      <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #7ea1f3; margin-bottom: 8px;">Password Reset Code</div>
      <div class="otp-code">{otp_code}</div>
      <div style="font-size: 11px; color: #94a3b8; margin-top: 8px;">Expires in {settings.OTP_EXPIRE_MINUTES} minutes &bull; Single-use only</div>
    </div>

    <p>If you did not request a password reset, you can safely disregard this message. Your password will remain unchanged.</p>
    
    <div class="warning">
      <strong>Notice:</strong> This code is single-use and will expire in {settings.OTP_EXPIRE_MINUTES} minutes.
    </div>
  </div>
  <div class="footer">
    &copy; 2026 Cashflow Lifeline &bull; Cryptographic Account Security
  </div>
</body>
</html>"""


def render_password_changed_email(name: str) -> str:
    """HTML email template confirming successful password change."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Password Changed Successfully — Cashflow Lifeline</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #081026; color: #f1f5f9; margin: 0; padding: 20px; }}
    .container {{ max-width: 540px; margin: 0 auto; background: #0d1a3a; border: 1px solid #1e346b; border-radius: 16px; padding: 32px; }}
    .logo {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; margin-bottom: 24px; }}
    h1 {{ font-size: 22px; font-weight: 800; color: #ffffff; margin-top: 0; }}
    p {{ font-size: 14px; line-height: 1.6; color: #cbd5e1; }}
    .success-badge {{ display: inline-block; background: rgba(52, 211, 153, 0.15); border: 1px solid rgba(52, 211, 153, 0.4); color: #34d399; font-weight: 700; font-size: 13px; border-radius: 8px; padding: 8px 16px; margin: 16px 0; }}
    .footer {{ font-size: 11px; color: #64748b; text-align: center; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">CL <span style="font-weight: 300;">| Cashflow Lifeline</span></div>
    <h1>Security Confirmation</h1>
    <div class="success-badge">&check; Password Successfully Updated</div>
    <p>Hello {name or 'Partner'},</p>
    <p>The password for your Cashflow Lifeline account has been successfully updated. All existing sessions and active refresh tokens have been revoked as a security safeguard.</p>
    <p>If you made this change, no further action is required.</p>
    <p style="color: #f87171; font-weight: 600;">If you did NOT make this change, please contact your security administrator immediately.</p>
  </div>
  <div class="footer">
    &copy; 2026 Cashflow Lifeline &bull; Identity & Access Governance
  </div>
</body>
</html>"""


def render_oauth_login_alert_email(name: str, provider: str) -> str:
    """HTML email template notifying user of a newly linked OAuth identity."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>New Login Method Linked — Cashflow Lifeline</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #081026; color: #f1f5f9; margin: 0; padding: 20px; }}
    .container {{ max-width: 540px; margin: 0 auto; background: #0d1a3a; border: 1px solid #1e346b; border-radius: 16px; padding: 32px; }}
    .logo {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; margin-bottom: 24px; }}
    h1 {{ font-size: 22px; font-weight: 800; color: #ffffff; margin-top: 0; }}
    p {{ font-size: 14px; line-height: 1.6; color: #cbd5e1; }}
    .footer {{ font-size: 11px; color: #64748b; text-align: center; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">CL <span style="font-weight: 300;">| Cashflow Lifeline</span></div>
    <h1>New Sign-In Method Linked</h1>
    <p>Hello {name or 'Partner'},</p>
    <p>Your Cashflow Lifeline account was recently connected to a <strong>{provider.title()}</strong> identity for single-sign-on access.</p>
    <p>If you authorized this connection, no action is needed.</p>
  </div>
  <div class="footer">
    &copy; 2026 Cashflow Lifeline &bull; Account Security
  </div>
</body>
</html>"""


def send_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """
    Sends an email using the configured provider (smtp, resend, sendgrid, or console logger).
    Never throws unhandled exceptions to avoid breaking user workflows.
    """
    provider = settings.EMAIL_PROVIDER.lower().strip()
    from_email = settings.EMAIL_FROM

    # 1. SMTP Provider
    if provider == "smtp" and settings.SMTP_HOST:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = to_email

            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"Email successfully dispatched via SMTP to {to_email}")
            return True
        except Exception as e:
            logger.error(f"SMTP dispatch failure to {to_email}: {e}")
            return False

    # 2. Resend Provider
    elif provider == "resend" and settings.EMAIL_API_KEY:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {settings.EMAIL_API_KEY}"},
                    json={
                        "from": from_email,
                        "to": [to_email],
                        "subject": subject,
                        "html": html_content,
                    }
                )
                if res.is_success:
                    logger.info(f"Email successfully dispatched via Resend to {to_email}")
                    return True
                else:
                    logger.error(f"Resend API error: {res.status_code} - {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Resend dispatch failure to {to_email}: {e}")
            return False

    # 3. SendGrid Provider
    elif provider == "sendgrid" and settings.EMAIL_API_KEY:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {settings.EMAIL_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "personalizations": [{"to": [{"email": to_email}]}],
                        "from": {"email": from_email},
                        "subject": subject,
                        "content": [{"type": "text/html", "value": html_content}]
                    }
                )
                if res.is_success:
                    logger.info(f"Email successfully dispatched via SendGrid to {to_email}")
                    return True
                else:
                    logger.error(f"SendGrid API error: {res.status_code} - {res.text}")
                    return False
        except Exception as e:
            logger.error(f"SendGrid dispatch failure to {to_email}: {e}")
            return False

    # 4. Console Logger / Development Sandbox Mode (Default)
    else:
        logger.info(
            f"\n"
            f"========================= [DEVELOPMENT EMAIL DISPATCH] =========================\n"
            f"To: {to_email}\n"
            f"From: {from_email}\n"
            f"Subject: {subject}\n"
            f"Provider: Console / Sandbox Simulation\n"
            f"================================================================================\n"
        )
        return True

