"""Scheduler database session management."""

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

_engine_cache: dict[str, AsyncEngine] = {}


def register_engine(database_url: str, engine: AsyncEngine) -> None:
    """Register an existing engine in the cache."""
    _engine_cache[database_url] = engine


def get_registered_engine() -> AsyncEngine | None:
    """Get the first registered engine from the cache."""
    if _engine_cache:
        return next(iter(_engine_cache.values()))
    return None


def async_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the database."""
    if (
        "sqlite" in database_url
        and ":memory:" in database_url
        and "cache=shared" not in database_url
    ):
        database_url = database_url.replace(":memory:", "file::memory:?cache=shared&uri=true")

    if database_url not in _engine_cache:
        if "sqlite" in database_url:
            engine = create_async_engine(database_url, echo=False)
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
    else:
        engine = _engine_cache[database_url]

    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_session(database_url: str | AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session context manager."""
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
