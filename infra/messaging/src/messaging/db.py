"""Database session management for worker containers.

Provides async SQLAlchemy session factory for worker containers to access
the gts_core database. Reads DATABASE_URL directly from the environment.
"""

from __future__ import annotations

import os
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

    Useful for tests that create their own engines and want
    get_session() to reuse them.
    """
    _engine_cache[database_url] = engine


def async_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the database."""
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
    """Get an async database session context manager with an active transaction."""
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
    """Get an async database session without an implicit transaction.

    Use for long-running workers/consumers that manage explicit commit/rollback
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
    """Get an async database session for the gts_core database."""
    database_url = os.environ["DATABASE_URL"]
    async with get_session(database_url) as session:
        yield session


@asynccontextmanager
async def get_core_session_no_tx() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session for gts_core without an implicit transaction."""
    database_url = os.environ["DATABASE_URL"]
    async with get_session_no_tx(database_url) as session:
        yield session
