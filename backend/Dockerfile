FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and database migrations
COPY backend/ ./backend/
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY docs/ ./docs/
COPY .env.example .env

# Make start script executable
RUN chmod +x ./backend/scripts/start.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "backend/scripts/start.py"]
