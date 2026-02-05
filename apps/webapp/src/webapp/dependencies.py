"""FastAPI dependency injection utilities."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from webapp.adapters.persistence.models.base import get_async_session

# Global session factory (initialized in create_app)
_session_factory = None


def init_db(database_url: str | None = None) -> None:
    """Initialize database session factory.

    Args:
        database_url: Database connection string. If None, reads from DATABASE_URL env var.
    """
    global _session_factory
    if database_url is None:
        database_url = os.getenv("DATABASE_URL")
        if database_url is None:
            raise ValueError("DATABASE_URL environment variable not set")
    _session_factory = get_async_session(database_url)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session

    Raises:
        RuntimeError: If session factory not initialized
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() before using get_db()."
        )

    async with _session_factory() as session:
        yield session
