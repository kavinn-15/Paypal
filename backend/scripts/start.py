#!/usr/bin/env python3
"""
Production startup wrapper for Cashflow Lifeline backend.
Runs database schema migrations before launching Uvicorn workers.
"""
import os
import subprocess
import sys


def main():
    print("[STARTUP] Checking database connection and running Alembic migrations...")
    try:
        res = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
        if res.returncode == 0:
            print("[STARTUP] Database migrations verified at head revision.")
        else:
            print(f"[STARTUP] Alembic notice: {res.stderr.strip() or res.stdout.strip()}")
    except Exception as e:
        print(f"[STARTUP] Migration notice: {e}")

    host = os.environ.get("HOST", "0.0.0.0")
    port = os.environ.get("PORT", "8000")
    workers = os.environ.get("WORKERS", "2")

    print(f"[STARTUP] Starting Cashflow Lifeline API on {host}:{port} with {workers} worker(s)...")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--workers",
        str(workers),
    ]
    # On POSIX exec replaces process; on Windows run subprocess
    if hasattr(os, "execv"):
        os.execv(sys.executable, cmd)
    else:
        sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()

