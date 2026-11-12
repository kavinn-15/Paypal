import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from backend.app.config import settings
from backend.app.db import init_db, get_db
from backend.app.events.queue import event_queue

logger = logging.getLogger(__name__)

# Import routers
from backend.app.api.auth import router as auth_router
from backend.app.api.paypal import router as paypal_router
from backend.app.api.obligations import router as obligations_router
from backend.app.api.history import router as history_router
from backend.app.api.forecast import router as forecast_router
from backend.app.api.plans import router as plans_router
from backend.app.api.actions import router as actions_router
from backend.app.api.webhooks import router as webhooks_router
from backend.app.api.audit import router as audit_router
from backend.app.api.clients import router as clients_router
from backend.app.api.finance import router as finance_router
from backend.app.api.simulation import router as simulation_router
from backend.app.api.negotiate import router as negotiate_router
from backend.app.api.supervisor import router as supervisor_router
from backend.app.api.resilience import router as resilience_router
from backend.app.api.demo import router as demo_router
from backend.app.api.region import router as region_router


from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Startup Safety Checks in lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Safety Checks ---
    if "sandbox.paypal.com" not in settings.PAYPAL_BASE_URL:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Refusing to start Cashflow Lifeline. "
            f"Production PayPal endpoints are strictly prohibited. "
            f"Configured URL: {settings.PAYPAL_BASE_URL}"
        )

    # Production secrets validation
    if not settings.DEV_MODE:
        if len(settings.JWT_SECRET) < 32 or "change" in settings.JWT_SECRET.lower() or "default" in settings.JWT_SECRET.lower():
            raise RuntimeError("CRITICAL SECURITY VIOLATION: Strong production JWT_SECRET (>=32 chars) required.")
        if len(settings.APPROVAL_SECRET) < 32 or "change" in settings.APPROVAL_SECRET.lower() or "default" in settings.APPROVAL_SECRET.lower():
            raise RuntimeError("CRITICAL SECURITY VIOLATION: Strong production APPROVAL_SECRET (>=32 chars) required.")

    # Initialize database tables and start event queue unless DATABASE_DISABLED is active
    if not settings.DATABASE_DISABLED:
        init_db()
        # Start in-process persisted webhook event queue worker
        await event_queue.start()
    else:
        logger.warning(
            "TEMPORARY DEPLOYMENT MODE: DATABASE_DISABLED=true is active. "
            "Database initialization, Alembic migrations, and persisted event queue worker skipped. "
            "Database-dependent routes will return 503 Service Unavailable."
        )

    yield

    # --- Shutdown ---
    if not settings.DATABASE_DISABLED:
        await event_queue.stop()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app = FastAPI(
    title="Cashflow Lifeline API",
    description="Agentic Financial Early-Warning & Proactive Decision Platform with PayPal Sandbox Integration.",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Unhandled SQLAlchemy database exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database service is temporarily unavailable. Database operations are currently postponed or failed."}
    )

# CORS configured with explicit allowed origins
cors_origins = settings.allowed_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Register all Routers
app.include_router(auth_router)
app.include_router(finance_router)
app.include_router(simulation_router)
app.include_router(supervisor_router)
app.include_router(negotiate_router)
app.include_router(resilience_router)
app.include_router(demo_router)
app.include_router(paypal_router)
app.include_router(obligations_router)
app.include_router(history_router)
app.include_router(forecast_router)
app.include_router(plans_router)
app.include_router(actions_router)
app.include_router(webhooks_router)
app.include_router(audit_router)
app.include_router(clients_router)
app.include_router(region_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Cashflow Lifeline",
        "version": "2.0.0",
        "environment": "sandbox",
        "paypal_base_url": settings.PAYPAL_BASE_URL,
        "dev_mode": settings.DEV_MODE,
        "database_disabled": settings.DATABASE_DISABLED
    }


@app.get("/health/db")
def database_health_check(db: Session = Depends(get_db)):
    """
    Checks database connection pool health and executes a ping query.
    """
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "pool_status": "ok"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database health check failed: {str(e)}")


@app.get("/status")
def system_status():
    return {
        "status": "online",
        "version": "2.0.0",
        "llm_provider": settings.LLM_PROVIDER,
        "max_discount_pct": settings.MAX_DISCOUNT_PCT,
        "max_payout_amount": settings.MAX_PAYOUT_AMOUNT,
        "allowed_currencies": settings.allowed_currencies_list
    }
