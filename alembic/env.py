import os
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.config import settings
from backend.app.db import Base
import backend.app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Authoritatively resolve DATABASE_URL in order of priority:
# 1. Explicit DATABASE_URL environment variable (from Render / hosting platform)
# 2. settings.DATABASE_URL (from Pydantic settings / .env)
# 3. alembic.ini default fallback
env_db_url = os.environ.get("DATABASE_URL")
configured_url = env_db_url or getattr(settings, "DATABASE_URL", None) or config.get_main_option("sqlalchemy.url")

# Normalize mysql:// to mysql+pymysql:// for PyMySQL driver compatibility
if configured_url and configured_url.startswith("mysql://"):
    configured_url = "mysql+pymysql://" + configured_url[len("mysql://"):]

config.set_main_option("sqlalchemy.url", configured_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    if url and url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    target_url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    if target_url and target_url.startswith("mysql://"):
        target_url = "mysql+pymysql://" + target_url[len("mysql://"):]
    configuration["sqlalchemy.url"] = target_url

    connect_args = {}
    if target_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif "mysql" in target_url:
        # Auto-configure TLS context for TiDB Cloud if not already present in connection query string
        if ("tidb" in target_url.lower() or "tidbcloud.com" in target_url.lower()) and "ssl" not in target_url.lower():
            import ssl
            connect_args["ssl"] = ssl.create_default_context()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True if target_url.startswith("sqlite") else False
        )

        with context.begin_transaction():
            context.run_migrations()


is_db_disabled = (
    os.environ.get("DATABASE_DISABLED", "").strip().lower() in ("1", "true", "yes")
    or getattr(settings, "DATABASE_DISABLED", False)
)

if is_db_disabled:
    import logging
    logging.getLogger("alembic.env").warning("DATABASE_DISABLED is active. Alembic migrations skipped.")
elif context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
