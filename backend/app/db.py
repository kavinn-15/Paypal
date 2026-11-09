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
                    ("updated_at", "DATETIME"),
                    ("email_verified_at", "DATETIME"),
                    ("phone_number", "VARCHAR(32)"),
                    ("phone_country_code", "VARCHAR(8) DEFAULT '+91'"),
                    ("phone_verified", "BOOLEAN DEFAULT 0"),
                    ("phone_verified_at", "DATETIME")
                ]
                for col_name, col_def in cols_to_add:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE owners ADD COLUMN {col_name} {col_def};"))

                # Invoices migration
                res_inv = conn.execute(text("PRAGMA table_info(invoices);")).fetchall()
                inv_cols = {row[1] for row in res_inv}
                if "is_simulated_paid" not in inv_cols:
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN is_simulated_paid BOOLEAN DEFAULT 0;"))

                # Actions migration
                res_act = conn.execute(text("PRAGMA table_info(actions);")).fetchall()
                act_cols = {row[1] for row in res_act}
                if "approved_payload_hash" not in act_cols:
                    conn.execute(text("ALTER TABLE actions ADD COLUMN approved_payload_hash VARCHAR(64);"))
                if "is_simulated" not in act_cols:
                    conn.execute(text("ALTER TABLE actions ADD COLUMN is_simulated BOOLEAN DEFAULT 0;"))

                # Obligations migration
                res_obl = conn.execute(text("PRAGMA table_info(obligations);")).fetchall()
                obl_cols = {row[1] for row in res_obl}
                for c_name, c_def in [
                    ("split_consent_recorded", "BOOLEAN DEFAULT 0"),
                    ("split_consent_source", "VARCHAR(100)"),
                    ("split_consent_timestamp", "DATETIME"),
                    ("split_consent_is_simulated", "BOOLEAN DEFAULT 0"),
                ]:
                    if c_name not in obl_cols:
                        conn.execute(text(f"ALTER TABLE obligations ADD COLUMN {c_name} {c_def};"))

                # Payment History migration
                res_ph = conn.execute(text("PRAGMA table_info(payment_history);")).fetchall()
                ph_cols = {row[1] for row in res_ph}
                if "transaction_reference" not in ph_cols:
                    conn.execute(text("ALTER TABLE payment_history ADD COLUMN transaction_reference VARCHAR(255);"))

                conn.commit()
        except Exception as e:
            logger.warning(f"SQLite schema update warning: {e}")
