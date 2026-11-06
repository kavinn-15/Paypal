from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from backend.app.db import get_db
from backend.app.config import settings
from backend.app.models import PayPalConnection
from backend.app.paypal.client import paypal_client, PayPalError
from backend.app.schemas import PayPalConnectionStatus, SandboxTestResponse

router = APIRouter(prefix="/paypal", tags=["PayPal Connection"])


@router.get("/connection", response_model=PayPalConnectionStatus)
def get_connection_status(db: Session = Depends(get_db)):
    conn = db.query(PayPalConnection).first()
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
async def test_connection(db: Session = Depends(get_db)):
    """Hits the real PayPal Sandbox OAuth2 token endpoint to verify client credentials."""
    try:
        token = await paypal_client._get_access_token(force_refresh=True)
        now = datetime.now(timezone.utc)

        conn = db.query(PayPalConnection).first()
        if conn:
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
        conn = db.query(PayPalConnection).first()
        if conn:
            conn.status = "error"
            conn.last_checked_at = datetime.now(timezone.utc)
            db.commit()

        return SandboxTestResponse(
            success=False,
            status_code=e.status_code or 401,
            environment="sandbox",
            message=f"PayPal Sandbox Authentication Failed: {str(e)}",
            token_preview=None
        )


@router.post("/register-webhook")
async def register_webhook():
    """Helper to register public webhook URL with PayPal Sandbox."""
    public_url = settings.PUBLIC_BASE_URL.rstrip("/")
    target_url = f"{public_url}/webhooks/paypal"
    try:
        res = await paypal_client.register_webhook(target_url)
        return {"success": True, "webhook_id": res.get("id"), "url": target_url}
    except PayPalError as e:
        raise HTTPException(status_code=400, detail=str(e))

