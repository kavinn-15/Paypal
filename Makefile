.PHONY: setup seed dev test demo-reset lint clean

PYTHON := $(shell which python3 2>/dev/null || which python 2>/dev/null || echo python)
VENV_PYTHON := .venv/bin/python
ifeq ($(OS),Windows_NT)
	VENV_PYTHON := .venv/Scripts/python.exe
endif

setup:
	@echo "==> Setting up virtual environment and dependencies..."
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	@if [ -d "frontend" ]; then cd frontend && npm install; fi
	@echo "==> Setup complete!"

seed:
	@echo "==> Seeding database with realistic client history and contractor obligation..."
	$(VENV_PYTHON) -m backend.scripts.seed
	@echo "==> Seeding complete!"

dev:
	@echo "==> Starting Cashflow Lifeline development server..."
	$(VENV_PYTHON) -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	@echo "==> Running backend test suite..."
	$(VENV_PYTHON) -m pytest backend/tests -v

demo-reset:
	@echo "==> Resetting database and preparing clean 3-minute demo scenario..."
	$(VENV_PYTHON) -m backend.scripts.seed --clean --demo-mode
	@echo "==> Ready for demo!"

clean:
	@echo "==> Cleaning cache and temporary files..."
	rm -rf .pytest_cache __pycache__ *.pyc cashflow.db

