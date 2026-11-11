from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from backend.app.db import get_db
from backend.app.config import settings
from backend.app.models import PayPalConnection, PayPalWebhookRegistration, Owner
from backend.app.auth.deps import get_verified_current_user
from backend.app.paypal.client import paypal_client, PayPalError
from backend.app.schemas import PayPalConnectionStatus, SandboxTestResponse

router = APIRouter(prefix="/paypal", tags=["PayPal Connection"])


@router.get("/connection", response_model=PayPalConnectionStatus)
def get_connection_status(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Retrieves PayPal sandbox connection health for the authenticated user.
    Honestly labels shared developer sandbox credentials vs individual merchant account.
    """
    active_wh = db.query(PayPalWebhookRegistration).filter(
        PayPalWebhookRegistration.status == "active"
    ).order_by(PayPalWebhookRegistration.created_at.desc()).first()
    wh_id = active_wh.webhook_id if active_wh else (
        settings.PAYPAL_WEBHOOK_ID if settings.PAYPAL_WEBHOOK_ID and settings.PAYPAL_WEBHOOK_ID != "sandbox_wh_id" else None
    )

    conn = db.query(PayPalConnection).filter(PayPalConnection.owner_id == current_user.id).first()
    if not conn:
        return PayPalConnectionStatus(
            connected=False,
            environment="sandbox",
            status="disconnected",
            client_id_preview=settings.PAYPAL_CLIENT_ID[:8] + "...",
            message="PayPal sandbox credentials not configured.",
            connection_type="shared_sandbox",
            is_shared_sandbox=True,
            account_label="Shared Application Sandbox (Developer Test Account)",
            merchant_id=None,
            merchant_email=None,
            webhook_id=wh_id
        )

    resolved_wh_id = conn.webhook_id or wh_id

    return PayPalConnectionStatus(
        connected=(conn.status == "connected"),
        environment=conn.environment,
        status=conn.status,
        client_id_preview=conn.client_id_preview or (settings.PAYPAL_CLIENT_ID[:8] + "..."),
        last_checked_at=conn.last_checked_at,
        message="Connected to Shared PayPal Developer Sandbox" if conn.status == "connected" else "Connection error",
        connection_type=conn.connection_type or "shared_sandbox",
        is_shared_sandbox=conn.is_shared_sandbox if conn.is_shared_sandbox is not None else True,
        account_label="Shared Application Sandbox (Developer Test Account)",
        merchant_id=conn.merchant_id,
        merchant_email=conn.merchant_email,
        webhook_id=resolved_wh_id
    )


@router.post("/test-connection", response_model=SandboxTestResponse)
async def test_connection(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Hits the real PayPal Sandbox OAuth2 token endpoint to verify client credentials.
    Explicitly labels the connection as shared developer sandbox.
    """
    try:
        token = await paypal_client._get_access_token(force_refresh=True)
        now = datetime.now(timezone.utc)

        active_wh = db.query(PayPalWebhookRegistration).filter(
            PayPalWebhookRegistration.status == "active"
        ).order_by(PayPalWebhookRegistration.created_at.desc()).first()
        wh_id = active_wh.webhook_id if active_wh else (
            settings.PAYPAL_WEBHOOK_ID if settings.PAYPAL_WEBHOOK_ID and settings.PAYPAL_WEBHOOK_ID != "sandbox_wh_id" else None
        )

        conn = db.query(PayPalConnection).filter(PayPalConnection.owner_id == current_user.id).first()
        if not conn:
            conn = PayPalConnection(
                owner_id=current_user.id,
                environment="sandbox",
                status="connected",
                connection_type="shared_sandbox",
                is_shared_sandbox=True,
                last_checked_at=now,
                client_id_preview=settings.PAYPAL_CLIENT_ID[:8] + "...",
                webhook_id=wh_id
            )
            db.add(conn)
        else:
            conn.status = "connected"
            conn.connection_type = "shared_sandbox"
            conn.is_shared_sandbox = True
            conn.last_checked_at = now
            conn.client_id_preview = settings.PAYPAL_CLIENT_ID[:8] + "..."
            if wh_id:
                conn.webhook_id = wh_id
        db.commit()

        return SandboxTestResponse(
            success=True,
            status_code=200,
            environment="sandbox",
            message="Successfully authenticated shared application credentials with PayPal Sandbox API. This sandbox integration facilitates developer testing and simulated flows.",
            token_preview=f"{token[:12]}... (valid 3600s)"
        )
    except PayPalError as e:
        conn = db.query(PayPalConnection).filter(PayPalConnection.owner_id == current_user.id).first()
        if conn:
            conn.status = "error"
            conn.last_checked_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(status_code=502, detail=f"PayPal Sandbox OAuth2 failed: {str(e)}")


@router.post("/webhook/register")
async def register_webhook(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """
    Registers application webhook URL with PayPal Sandbox API and persists
    the returned webhook_id in the database for cryptographic verification.
    """
    webhook_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/webhooks/paypal"
    webhook_id = None

    try:
        # 1. Check if the webhook URL is already registered in PayPal to avoid duplicate error
        try:
            existing_wh_list = await paypal_client.list_webhooks()
            for wh in existing_wh_list.get("webhooks", []):
                if wh.get("url") == webhook_url:
                    webhook_id = wh.get("id")
                    break
        except Exception:
            webhook_id = None

        # 2. If not already registered, register it
        if not webhook_id:
            res = await paypal_client.register_webhook(webhook_url=webhook_url)
            webhook_id = res.get("id")

        if not webhook_id:
            raise HTTPException(status_code=502, detail="PayPal API did not return a valid webhook ID.")

        # 3. Persist registration in database
        now = datetime.now(timezone.utc)
        reg = db.query(PayPalWebhookRegistration).filter(
            (PayPalWebhookRegistration.webhook_id == webhook_id) | (PayPalWebhookRegistration.url == webhook_url)
        ).first()

        if not reg:
            reg = PayPalWebhookRegistration(
                webhook_id=webhook_id,
                url=webhook_url,
                environment="sandbox",
                status="active",
                created_at=now,
                last_verified_at=now
            )
            db.add(reg)
        else:
            reg.webhook_id = webhook_id
            reg.url = webhook_url
            reg.status = "active"
            reg.last_verified_at = now

        # Update user's PayPalConnection if present
        conn = db.query(PayPalConnection).filter(PayPalConnection.owner_id == current_user.id).first()
        if conn:
            conn.webhook_id = webhook_id

        db.commit()

        return {
            "success": True,
            "webhook_id": webhook_id,
            "url": webhook_url,
            "message": "Webhook successfully registered and persisted with PayPal Sandbox."
        }
    except PayPalError as e:
        raise HTTPException(status_code=502, detail=f"Webhook registration failed: {str(e)}")
