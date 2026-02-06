"""Shared pytest fixtures for webapp integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    # Use in-memory SQLite for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create session factory
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.fixture(autouse=True)
async def _wire_auth_session(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Auto-wire test DB session into auth module.

    The auth endpoints use a module-level session override so tests that
    create their own FastAPI() app (without dependency_overrides) still
    get the test session.
    """
    from webapp.api.v1.auth import set_session_override

    set_session_override(db_session)
    yield
    set_session_override(None)
