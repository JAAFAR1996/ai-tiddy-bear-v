import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# --- Production: Read DATABASE_URL from environment and inject into config ---
# Use MIGRATIONS_DATABASE_URL if available (sync driver), otherwise fallback to DATABASE_URL
db_url = os.getenv("MIGRATIONS_DATABASE_URL") or os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL not set in environment")

# Convert to sync driver for migrations (asyncpg → psycopg2)
if db_url.startswith("postgresql+asyncpg://"):
    sync_db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://"):
    sync_db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgres://"):
    sync_db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
else:
    sync_db_url = db_url

config = context.config
config.set_main_option("sqlalchemy.url", sync_db_url)

# Mask password in logs for security
masked_url = sync_db_url
if '@' in sync_db_url and ':' in sync_db_url:
    parts = sync_db_url.split('@')
    if len(parts) == 2:
        auth_part = parts[0]
        if '://' in auth_part and ':' in auth_part.split('://')[-1]:
            scheme_user = auth_part.rsplit(':', 1)[0]
            masked_url = f"{scheme_user}:***@{parts[1]}"
print(f"[alembic] Using SQLAlchemy URL: {masked_url}")

# Ensure src is in sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import your Base metadata
from src.infrastructure.database.models import Base

# Alembic Config object, provides access to values within the .ini file
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    # Mask password in logs for security
    masked_url = url
    if '@' in url and ':' in url:
        parts = url.split('@')
        if len(parts) == 2:
            auth_part = parts[0]
            if '://' in auth_part and ':' in auth_part.split('://')[-1]:
                scheme_user = auth_part.rsplit(':', 1)[0]
                masked_url = f"{scheme_user}:***@{parts[1]}"
    print(f"[alembic] Using SQLAlchemy URL (offline): {masked_url}")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""

    # Print the URL for production diagnostics (mask password for security)
    url = config.get_main_option("sqlalchemy.url")
    # Mask password in logs for security
    masked_url = url
    if '@' in url and ':' in url:
        parts = url.split('@')
        if len(parts) == 2:
            auth_part = parts[0]
            if '://' in auth_part and ':' in auth_part.split('://')[-1]:
                scheme_user = auth_part.rsplit(':', 1)[0]
                masked_url = f"{scheme_user}:***@{parts[1]}"
    print(f"[alembic] Using SQLAlchemy URL (online): {masked_url}")

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
