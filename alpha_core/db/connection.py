import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alpha_core.config import settings

from .models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def async_database_url(url: str) -> str:
    """Map provider-neutral Postgres URLs to SQLAlchemy's async psycopg dialect."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def sync_database_url(url: str) -> str:
    """Map async SQLAlchemy URLs to standard sync URLs for Alembic migrations."""
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    if url.startswith("sqlite+aiosqlite:///"):
        return "sqlite:///" + url.removeprefix("sqlite+aiosqlite:///")
    return url


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            async_database_url(settings.DATABASE_URL),
            echo=settings.DEBUG,
            future=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


def run_alembic_migrations_sync(database_url: str | None = None) -> None:
    """Synchronous runner for Alembic database migrations."""
    target_url = database_url or settings.DATABASE_URL
    sync_url = sync_database_url(target_url)

    root_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = root_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url.replace("%", "%%"))
    command.upgrade(alembic_cfg, "head")


async def run_alembic_migrations(database_url: str | None = None) -> None:
    """Asynchronous wrapper to execute Alembic upgrade head."""
    await asyncio.to_thread(run_alembic_migrations_sync, database_url)


async def init_db() -> None:
    """
    Initialize database schema.
    In production and staging, must never run Alembic migrations.
    In development and test environments, uses schema creation.
    """
    if settings.is_production or settings.is_staging:
        try:
            await run_alembic_migrations()
        except Exception as exc:
            import logging

            logging.getLogger("alphabrain.db").warning(
                "Alembic auto-migration during init_db encountered an exception: %s", exc
            )
    elif settings.DATABASE_URL.startswith("sqlite+aiosqlite:///:memory:"):
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        # Default local / development
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency / context provider for async database sessions."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
