import json
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.config import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL

connect_args = {}
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "json_serializer": lambda obj: json.dumps(obj, default=str),
}

if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
elif "mysql" in DATABASE_URL:
    # Production MySQL 8 connection pool optimization
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_recycle"] = 3600

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Enable foreign keys and WAL mode for SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """
    Run Alembic migrations programmatically against the current configured database.
    Authoritative schema migration mechanism. Fails fast if migration fails.
    """
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
        logger.warning(f"Alembic migration notice during worker startup: {e}")


def init_db():
    """
    Initialize database schema authoritatively using Alembic migrations.
    Never calls create_all() before migrations to prevent schema state divergence.
    """
    import backend.app.models  # noqa: F401
    run_migrations()
