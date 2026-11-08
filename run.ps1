# PowerShell helper for Cashflow Lifeline (Windows equivalent of Makefile)
param (
    [Parameter(Position=0)]
    [ValidateSet("setup", "seed", "dev", "test", "demo-reset", "frontend", "clean")]
    [string]$Command = "help"
)

$PYTHON = ".\.venv\Scripts\python.exe"

switch ($Command) {
    "setup" {
        Write-Host "==> Setting up Python virtual environment..." -ForegroundColor Cyan
        python -m venv .venv
        & $PYTHON -m pip install --upgrade pip
        & $PYTHON -m pip install -r requirements.txt
        Write-Host "==> Installing frontend dependencies..." -ForegroundColor Cyan
        Set-Location frontend
        npm install
        Set-Location ..
        Write-Host "==> Setup complete!" -ForegroundColor Green
    }
    "seed" {
        Write-Host "==> Seeding database with 12-month client history and contractor obligation..." -ForegroundColor Cyan
        & $PYTHON -m backend.scripts.seed
    }
    "demo-reset" {
        Write-Host "==> Resetting database and preparing clean 3-minute demo scenario..." -ForegroundColor Cyan
        & $PYTHON -m backend.scripts.seed --clean --demo-mode
        Write-Host "==> Ready for demo! Starting balance: $1,800.00, Obligation: $3,200.00 on Friday." -ForegroundColor Green
    }
    "dev" {
        Write-Host "==> Starting Cashflow Lifeline backend on http://localhost:8000..." -ForegroundColor Cyan
        & $PYTHON -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
    }
    "frontend" {
        Write-Host "==> Starting Vite React frontend on http://localhost:5173..." -ForegroundColor Cyan
        Set-Location frontend
        npm run dev
    }
    "test" {
        Write-Host "==> Running backend Pytest suite..." -ForegroundColor Cyan
        & $PYTHON -m pytest backend/tests -v
        Write-Host "`n==> Running frontend Vitest suite..." -ForegroundColor Cyan
        Set-Location frontend
        npm test
        Set-Location ..
    }
    "clean" {
        Write-Host "==> Cleaning cache and database..." -ForegroundColor Yellow
        Remove-Item -Force -Recurse .pytest_cache -ErrorAction SilentlyContinue
        Remove-Item -Force cashflow.db -ErrorAction SilentlyContinue
        Write-Host "==> Clean complete." -ForegroundColor Green
    }
    default {
        Write-Host "Usage: .\run.ps1 [command]" -ForegroundColor Yellow
        Write-Host "Commands:"
        Write-Host "  setup       - Set up virtual environment and install all dependencies"
        Write-Host "  demo-reset  - Reset and seed clean demo scenario"
        Write-Host "  dev         - Start FastAPI backend server on port 8000"
        Write-Host "  frontend    - Start Vite React frontend on port 5173"
        Write-Host "  test        - Run all backend and frontend tests"
        Write-Host "  clean       - Delete cache and local database"
    }
}

