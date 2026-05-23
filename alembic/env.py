"""
NexusForge AI — Alembic Environment (sync version)
Alembic runs synchronously — uses psycopg2, NOT asyncpg.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

config = context.config

# Use the SYNC URL (postgresql:// with psycopg2) — NOT asyncpg
db_url = os.environ.get(
    "DATABASE_SYNC_URL",
    "postgresql://nexusforge:nexusforge_secret@localhost:5432/nexusforge",
)
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models for autogenerate support
target_metadata = None
try:
    from backend.core.database import Base
    target_metadata = Base.metadata

    # Import model files individually
    import importlib
    import pkgutil
    import backend.models as _models_pkg
    for _finder, _name, _ispkg in pkgutil.iter_modules(_models_pkg.__path__):
        try:
            importlib.import_module(f"backend.models.{_name}")
        except Exception as e:
            print(f"  [warn] Skipping model {_name}: {e}")
except Exception as e:
    print(f"[warn] Could not load models: {e}. Running without autogenerate.")


def run_migrations_offline() -> None:
    """Run in offline mode (no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run in online mode with a real sync connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
