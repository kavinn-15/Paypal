import json
import logging
import ssl
from fastapi import HTTPException, status
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.config import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL
# Automatically normalize mysql:// to mysql+pymysql:// for PyMySQL driver compatibility
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = "mysql+pymysql://" + DATABASE_URL[len("mysql://"):]

connect_args = {}
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,  # Actively tests connections before checkout to safely discard stale ones
    "json_serializer": lambda obj: json.dumps(obj, default=str),
}

if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
elif "mysql" in DATABASE_URL:
    # Optimized connection pooling for TiDB Starter & Cloud Serverless MySQL on Render Free:
    # - pool_size=5: Conservative base pool to stay within free-tier compute/connection limits (Render Free 512MB RAM)
    # - max_overflow=10: Short-lived burst traffic allowance (up to 15 concurrent connections)
    # - pool_recycle=300: Recycles connections every 5 minutes to prevent stale drops by cloud NAT and TiDB idle timeouts
    # - pool_timeout=30: Max wait time for an available connection from the pool
    # - pool_pre_ping=True: Transparently reconnects stale/dropped connections
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_timeout"] = 30

    # Auto-enable TLS context for TiDB Cloud if not explicitly configured in query string
    if ("tidb" in DATABASE_URL.lower() or "tidbcloud.com" in DATABASE_URL.lower()) and "ssl" not in DATABASE_URL.lower():
        connect_args["ssl"] = ssl.create_default_context()

    if connect_args:
        engine_kwargs["connect_args"] = connect_args

try:
    engine = create_engine(DATABASE_URL, **engine_kwargs)
except Exception as e:
    if settings.DATABASE_DISABLED:
        logger.warning(f"Engine creation fallback for DATABASE_DISABLED mode: {e}")
        from sqlalchemy.pool import NullPool
        engine = create_engine("sqlite:///:memory:", poolclass=NullPool)
    else:
        raise

# Enable foreign keys and WAL mode for SQLite
if str(engine.url).startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()
        except Exception:
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    FastAPI database session dependency.
    In DATABASE_DISABLED mode, immediately raises 503 Service Unavailable with a clear message
    rather than attempting a connection and crashing.
    """
    if settings.DATABASE_DISABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is temporarily unavailable (DATABASE_DISABLED mode is active). Database operations are currently postponed."
        )

    try:
        db = SessionLocal()
    except Exception as e:
        logger.error(f"Failed to acquire database session: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database service is temporarily unavailable. Could not connect to database: {e}"
        )

    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """
    Run Alembic migrations programmatically against the configured database.
    Authoritative schema migration mechanism. Fails fast if migration fails.
    Skipped entirely when DATABASE_DISABLED is active.
    """
    if settings.DATABASE_DISABLED:
        logger.warning("run_migrations() skipped: DATABASE_DISABLED mode is active.")
        return

    import os
    from alembic.config import Config
    from alembic import command
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ini_path = os.path.join(base_dir, "alembic.ini")
    if not os.path.exists(ini_path):
        raise FileNotFoundError(f"alembic.ini not found at {ini_path}")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Database schema upgrade successfully verified via Alembic.")
    except Exception as e:
        logger.error(f"Critical: Database migration failed during startup: {e}")
        # Stop startup immediately on migration failure to prevent running with broken or mismatched schema
        raise RuntimeError(f"Database schema migration failed: {e}") from e


def init_db():
    """
    Initialize database schema authoritatively using Alembic migrations.
    Never calls create_all() before migrations to prevent schema state divergence.
    Skipped entirely when DATABASE_DISABLED is active.
    """
    if settings.DATABASE_DISABLED:
        logger.warning("init_db() skipped: DATABASE_DISABLED mode is active.")
        return

    import backend.app.models  # noqa: F401
    run_migrations()
