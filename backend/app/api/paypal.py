from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from backend.app.db import get_db
from backend.app.config import settings
from backend.app.models import PayPalConnection, Owner
from backend.app.auth.deps import get_verified_current_user
from backend.app.paypal.client import paypal_client, PayPalError
from backend.app.schemas import PayPalConnectionStatus, SandboxTestResponse

router = APIRouter(prefix="/paypal", tags=["PayPal Connection"])


@router.get("/connection", response_model=PayPalConnectionStatus)
def get_connection_status(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Retrieves PayPal sandbox connection health for the authenticated user."""
    conn = db.query(PayPalConnection).filter(PayPalConnection.owner_id == current_user.id).first()
    if not conn:
        return PayPalConnectionStatus(
            connected=False,
            environment="sandbox",
            status="disconnected",
            client_id_preview=settings.PAYPAL_CLIENT_ID[:8] + "...",
            message="PayPal sandbox credentials not configured."
        )

    return PayPalConnectionStatus(
        connected=(conn.status == "connected"),
        environment=conn.environment,
        status=conn.status,
        client_id_preview=conn.client_id_preview or (settings.PAYPAL_CLIENT_ID[:8] + "..."),
        last_checked_at=conn.last_checked_at,
        message="Connected to PayPal Sandbox" if conn.status == "connected" else "Connection error"
    )


@router.post("/test-connection", response_model=SandboxTestResponse)
async def test_connection(
    db: Session = Depends(get_db),
    current_user: Owner = Depends(get_verified_current_user)
):
    """Hits the real PayPal Sandbox OAuth2 token endpoint to verify client credentials for user."""
    try:
        token = await paypal_client._get_access_token(force_refresh=True)
        now = datetime.now(timezone.utc)

        conn = db.query(PayPalConnection).filter(PayPalConnection.owner_id == current_user.id).first()
        if not conn:
            conn = PayPalConnection(
                owner_id=current_user.id,
                environment="sandbox",
                status="connected",
                last_checked_at=now,
                client_id_preview=settings.PAYPAL_CLIENT_ID[:8] + "..."
            )
            db.add(conn)
        else:
            conn.status = "connected"
            conn.last_checked_at = now
            conn.client_id_preview = settings.PAYPAL_CLIENT_ID[:8] + "..."
        db.commit()

        return SandboxTestResponse(
            success=True,
            status_code=200,
            environment="sandbox",
            message="Successfully authenticated with PayPal Sandbox API.",
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
    """Registers application webhook URL with PayPal Sandbox API."""
    webhook_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/webhooks/paypal"
    try:
        res = await paypal_client.register_webhook(webhook_url=webhook_url)
        return {
            "success": True,
            "webhook_id": res.get("id"),
            "url": webhook_url,
            "message": "Webhook successfully registered with PayPal Sandbox."
        }
    except PayPalError as e:
        raise HTTPException(status_code=502, detail=f"Webhook registration failed: {str(e)}")
