"""Worker database session management.

Provides async SQLAlchemy session factory for the worker to access the gts_core
database. The worker needs to read/write Job records, Shootout status, and
AudioSegment data.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Module-level engine cache for sharing database connections
_engine_cache: dict[str, AsyncEngine] = {}


def register_engine(database_url: str, engine: AsyncEngine) -> None:
    """Register an existing engine in the cache.

    This is useful for tests that create their own engines and want
    get_session() to reuse them.

    Args:
        database_url: The database URL string
        engine: The AsyncEngine instance to register
    """
    _engine_cache[database_url] = engine


def async_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the database.

    Args:
        database_url: PostgreSQL connection string (asyncpg driver).

    Returns:
        Session factory that creates AsyncSession instances.

    Note:
        Engines are cached by URL to allow sharing connections. Tests can
        pre-register engines using register_engine().
    """
    if database_url in _engine_cache:
        engine = _engine_cache[database_url]
    else:
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
        )
        _engine_cache[database_url] = engine

    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_session(database_url: str | AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session context manager.

    Args:
        database_url: PostgreSQL connection string or an AsyncEngine instance for testing

    Yields:
        AsyncSession: Database session with an active transaction

    Example:
        async with get_session(settings.database_url) as session:
            result = await session.execute(select(Job))
            jobs = result.scalars().all()
            # Transaction auto-commits on successful exit, rolls back on exception
    """
    # If an engine is provided directly, use it; otherwise create from URL
    if isinstance(database_url, AsyncEngine):
        factory = async_sessionmaker(
            database_url,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    else:
        factory = async_session_factory(database_url)

    session = factory()
    try:
        async with session.begin():
            yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_session_no_tx(database_url: str | AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session without wrapping it in an implicit transaction.

    Use this for long-running workers/consumers that manage explicit commit/rollback
    boundaries per message or batch.
    """
    if isinstance(database_url, AsyncEngine):
        factory = async_sessionmaker(
            database_url,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    else:
        factory = async_session_factory(database_url)

    session = factory()
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_core_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session for the gts_core database.

    Yields:
        AsyncSession: Database session connected to gts_core with active transaction

    Example:
        async with get_core_session() as session:
            result = await session.execute(select(Job))
            jobs = result.scalars().all()

    Note:
        Uses WorkerSettings.database_url which is loaded from the DATABASE_URL
        environment variable. In tests, this can be overridden by pre-registering
        an engine under the desired URL using register_engine().
    """
    from worker.config import WorkerSettings

    settings = WorkerSettings()  # type: ignore[call-arg]
    async with get_session(settings.database_url) as session:
        yield session


@asynccontextmanager
async def get_core_session_no_tx() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session for gts_core without implicit transaction."""
    from worker.config import WorkerSettings

    settings = WorkerSettings()  # type: ignore[call-arg]
    async with get_session_no_tx(settings.database_url) as session:
        yield session
