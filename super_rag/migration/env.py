from logging.config import fileConfig

from sqlalchemy import pool, text
from alembic import context
from super_rag.config import settings as app_config

# Special handling for SQLAlchemy async migration support
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
import asyncio

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from super_rag.db.models import Base

target_metadata = Base.metadata

# Set the main database URL value for Alembic config
config.set_main_option("sqlalchemy.url", app_config.database_url)


def _get_server_url():
    """Build a MySQL/PostgreSQL server-level URL (no database) for creating the database."""
    url = app_config.database_url
    if url.startswith("mysql+aiomysql://"):
        return url.replace("mysql+aiomysql://", "mysql+pymysql://").rsplit("/", 1)[0]
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://").rsplit("/", 1)[0]
    return None


def _ensure_database_exists():
    """Create the target database if it does not exist."""
    server_url = _get_server_url()
    if not server_url:
        return

    db_name = app_config.mysql_db
    from sqlalchemy import create_engine

    engine = create_engine(server_url)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
        print(f"Database '{db_name}' is ready.")
    except Exception as e:
        print(f"Warning: could not auto-create database '{db_name}': {e}")
    finally:
        engine.dispose()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (non-async).

    This configures the context with just a URL and not an Engine,
    suitable for emitting SQL as text.
    """
    _ensure_database_exists()
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection, target_metadata=target_metadata
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations_online():
    """Run migrations in 'online' mode using SQLAlchemy async engine."""
    _ensure_database_exists()
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    """Fallback to sync migrations if not async URL."""

    from sqlalchemy.engine import engine_from_config

    _ensure_database_exists()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    # Detect if the configured database URL is async.
    db_url = config.get_main_option("sqlalchemy.url")
    if db_url.startswith("postgresql+asyncpg") or db_url.startswith("mysql+aiomysql"):
        asyncio.run(run_async_migrations_online())
    else:
        run_migrations_online()
