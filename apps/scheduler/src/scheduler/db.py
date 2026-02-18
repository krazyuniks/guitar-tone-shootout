"""Scheduler database session management.

Provides async SQLAlchemy session factory for the scheduler to access the gts_core
database. The scheduler needs to query and update Job records for stale job
monitoring and retry processing.
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
# This is particularly important for SQLite :memory: databases in tests
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


def get_registered_engine() -> AsyncEngine | None:
    """Get the first registered engine from the cache.

    Returns:
        The first registered engine, or None if cache is empty.
    """
    if _engine_cache:
        return next(iter(_engine_cache.values()))
    return None


def async_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the database.

    Args:
        database_url: Database connection string (PostgreSQL with asyncpg or SQLite)

    Returns:
        Session factory that creates AsyncSession instances

    Note:
        Engines are cached by URL to allow sharing connections, particularly
        important for SQLite :memory: databases in tests. For SQLite :memory:
        databases, shared cache mode is automatically enabled to allow multiple
        connections to access the same database.
    """
    # For SQLite :memory: databases, convert to shared cache mode
    # This allows multiple engine instances to share the same in-memory database
    if (
        "sqlite" in database_url
        and ":memory:" in database_url
        and "cache=shared" not in database_url
    ):
        # Replace :memory: with file::memory:?cache=shared&uri=true
        database_url = database_url.replace(":memory:", "file::memory:?cache=shared&uri=true")

    # Check if we already have an engine for this URL
    if database_url not in _engine_cache:
        # SQLite doesn't support pool_size/max_overflow
        if "sqlite" in database_url:
            engine = create_async_engine(
                database_url,
                echo=False,
            )
        else:
            # PostgreSQL with connection pooling
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
    else:
        engine = _engine_cache[database_url]

    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_session(database_url: str | AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session context manager.

    Args:
        database_url: Database connection string (PostgreSQL with asyncpg or SQLite)
                     or an AsyncEngine instance for testing

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
