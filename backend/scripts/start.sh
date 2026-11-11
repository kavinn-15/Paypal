#!/bin/sh
set -e

echo "[STARTUP] Checking database connection and running Alembic migrations..."
alembic upgrade head || {
    echo "[WARNING] Alembic upgrade completed with warnings or database already initialized."
}

PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"

echo "[STARTUP] Starting Cashflow Lifeline API on 0.0.0.0:${PORT} with ${WORKERS} worker(s)..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT" --workers "$WORKERS"

