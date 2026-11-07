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


def init_db():
    # Import models so all tables are registered before creating
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Seamless SQLite column migration if table already existed
    if DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                from sqlalchemy import text
                res = conn.execute(text("PRAGMA table_info(owners);")).fetchall()
                existing_cols = {row[1] for row in res}
                cols_to_add = [
                    ("country", "VARCHAR(50) DEFAULT 'US'"),
                    ("business_type", "VARCHAR(50) DEFAULT 'Freelancer'"),
                    ("preferred_currency", "VARCHAR(10) DEFAULT 'USD'"),
                    ("email_verified", "BOOLEAN DEFAULT 1"),
                    ("account_status", "VARCHAR(20) DEFAULT 'active'"),
                    ("password_reset_token", "VARCHAR(255)"),
                    ("reset_token_expires_at", "DATETIME"),
                    ("email_verification_token", "VARCHAR(255)"),
                    ("updated_at", "DATETIME")
                ]
                for col_name, col_def in cols_to_add:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE owners ADD COLUMN {col_name} {col_def};"))
                conn.commit()
        except Exception as e:
            logger.warning(f"SQLite owners schema update warning: {e}")
