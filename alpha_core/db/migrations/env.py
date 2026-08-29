"""
Alembic environment configuration for Alpha Brain database migrations.
Imports models to ensure all tables are registered with Base.metadata.
Enables render_as_batch=True for SQLite copy-and-move schema alterations.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import Base and all models so metadata is populated
from alpha_core.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    if not url or url == "sqlite:///alpha_brain.db":
        import os
        url = os.environ.get("DATABASE_URL")
    if url:
        url = url.replace("+asyncpg", "+psycopg").replace("+aiosqlite", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the database."""
    section = config.get_section(config.config_ini_section, {})
    url = config.get_main_option("sqlalchemy.url")
    if not url or url == "sqlite:///alpha_brain.db":
        import os
        url = os.environ.get("DATABASE_URL")
    if url:
        url = url.replace("+asyncpg", "+psycopg").replace("+aiosqlite", "")
        section["sqlalchemy.url"] = url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
