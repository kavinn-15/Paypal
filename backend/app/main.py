from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.db import init_db
from backend.app.events.queue import event_queue

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Safety Checks ---
    if "sandbox.paypal.com" not in settings.PAYPAL_BASE_URL:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Refusing to start Cashflow Lifeline. "
            f"Production PayPal endpoints are strictly prohibited. "
            f"Configured URL: {settings.PAYPAL_BASE_URL}"
        )

    # Initialize database tables
    init_db()

    # Start in-process persisted webhook event queue worker
    await event_queue.start()

    yield

    # --- Shutdown ---
    await event_queue.stop()


app = FastAPI(
    title="Cashflow Lifeline API",
    description="Agentic Financial Early-Warning & Proactive Decision Platform with PayPal Sandbox Integration.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits localhost Vite frontend (ports 5173, 3000, 8000)
    allow_credentials=True,
    allow_methods=["*"],
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


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Cashflow Lifeline",
        "version": "2.0.0",
        "environment": "sandbox",
        "paypal_base_url": settings.PAYPAL_BASE_URL,
        "dev_mode": settings.DEV_MODE
    }


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
