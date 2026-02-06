"""Shared pytest fixtures for webapp integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import FastAPI
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


@pytest.fixture
def app_with_db(db_session: AsyncSession) -> FastAPI:
    """Create FastAPI app with database session configured.

    This fixture provides a FastAPI app with the database dependency
    properly overridden to use the test database session.
    """
    from webapp.api.v1.auth import get_db_session, router as auth_router

    app = FastAPI()
    app.include_router(auth_router)

    # Override database dependency to use test session
    async def override_get_db_session() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    return app
