"""Integration tests for admin API database dependency.

Tests that the FastAPI dependency get_db_session in admin.py uses the
get_core_session() factory to connect to gts_core database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from webapp.adapters.persistence.models.base import Base


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine for admin API testing."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
class TestAdminDbDependency:
    """Test that admin.py get_db_session dependency uses get_core_session."""

    async def test_get_db_session_dependency_exists(self) -> None:
        """get_db_session dependency exists in admin module."""
        from worker.admin import get_db_session

        assert callable(get_db_session)

    async def test_get_db_session_is_async_generator(self) -> None:
        """get_db_session is an async generator function."""
        import inspect

        from worker.admin import get_db_session

        # Check that it's an async generator function
        assert inspect.isasyncgenfunction(get_db_session)

    async def test_get_db_session_yields_async_session(self, db_engine: AsyncEngine) -> None:
        """get_db_session yields an AsyncSession."""
        from worker.admin import get_db_session
        from worker.db import register_engine

        # Register the test engine so get_core_session can find it
        register_engine("sqlite+aiosqlite:///:memory:", db_engine)

        # Test the dependency directly
        async for session in get_db_session():
            assert isinstance(session, AsyncSession)
            break

    async def test_get_db_session_uses_core_database(self) -> None:
        """get_db_session uses gts_core database via get_core_session."""
        from worker.admin import get_db_session
        from worker.config import WorkerSettings
        from worker.db import register_engine

        # Create settings with known database URLs
        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        # Create a test engine for gts_core and register it
        from sqlalchemy.ext.asyncio import create_async_engine

        core_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        register_engine(settings.database_url, core_engine)

        # Test the dependency
        async for session in get_db_session():
            # Verify the session uses the core engine
            engine = session.get_bind()
            assert engine == core_engine
            break

        await core_engine.dispose()

    async def test_admin_endpoints_use_core_session(self, db_engine: AsyncEngine) -> None:
        """Admin API endpoints receive sessions from get_core_session."""
        from httpx import ASGITransport, AsyncClient

        from worker.admin import app
        from worker.db import register_engine

        # Register the test engine
        register_engine("sqlite+aiosqlite:///:memory:", db_engine)

        # Create a test client
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Call an endpoint that uses the database
            response = await client.get("/api/admin/jobs")

            # Should succeed (200 OK) with empty list
            assert response.status_code == 200
            assert response.json() == []

    async def test_get_db_session_does_not_use_t3k_database(self) -> None:
        """get_db_session does NOT use gts_t3k_source database."""
        from worker.config import WorkerSettings
        from worker.db import register_engine

        # Create settings with different database URLs
        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        # Create and register engines
        from sqlalchemy.ext.asyncio import create_async_engine

        core_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        t3k_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        register_engine(settings.database_url, core_engine)
        register_engine(settings.t3k_database_url, t3k_engine)

        # Import after registration to ensure settings are loaded
        from worker.admin import get_db_session

        # Test the dependency
        async for session in get_db_session():
            engine = session.get_bind()
            # Should use core engine, NOT t3k engine
            assert engine == core_engine
            assert engine != t3k_engine
            break

        await core_engine.dispose()
        await t3k_engine.dispose()
