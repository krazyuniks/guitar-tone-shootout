"""Fixtures for worker integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncEngine

from webapp.adapters.persistence.models.base import Base
from worker.db import async_session_factory, register_engine


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine using worker's async_session_factory.

    This fixture uses the worker's session factory to ensure that sessions
    created via get_session() can access the same database and tables.
    """
    # Use shared memory SQLite database so multiple connections can access it
    database_url = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

    # Create session factory and get the engine
    factory = async_session_factory(database_url)
    engine = factory.kw["bind"]

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Register the engine so get_session() will use it
    register_engine("sqlite+aiosqlite:///:memory:", engine)

    yield engine

    await engine.dispose()
