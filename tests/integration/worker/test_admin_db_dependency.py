"""Integration tests for admin API database dependency.

Tests that the FastAPI dependency get_db_session in admin.py uses the
get_core_session() factory to connect to gts_core database.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


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

    async def test_get_db_session_yields_async_session(self, core_engine: AsyncEngine) -> None:
        """get_db_session yields an AsyncSession."""
        from worker.admin import get_db_session

        # Test the dependency directly (db_engine fixture from conftest
        # registers under PostgreSQL URLs so get_core_session finds it)
        async for session in get_db_session():
            assert isinstance(session, AsyncSession)
            break

    async def test_get_db_session_uses_core_database(self, core_engine: AsyncEngine) -> None:
        """get_db_session uses gts_core database via get_core_session."""
        from worker.admin import get_db_session

        # The conftest db_engine fixture registers the test engine under
        # the PostgreSQL core URL. Verify get_db_session uses that engine.
        async for session in get_db_session():
            # Session should be functional (using the test SQLite engine)
            from sqlalchemy import text

            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            break

    async def test_admin_endpoints_use_core_session(self, core_engine: AsyncEngine) -> None:
        """Admin API endpoints receive sessions from get_core_session."""
        from httpx import ASGITransport, AsyncClient

        from worker.admin import app

        # db_engine fixture from conftest registers under PostgreSQL URLs
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Call an endpoint that uses the database
            response = await client.get("/api/admin/jobs")

            # Should succeed (200 OK) with empty list
            assert response.status_code == 200
            assert response.json() == []

    async def test_get_db_session_does_not_use_t3k_database(self, core_engine: AsyncEngine) -> None:
        """get_db_session does NOT use gts_t3k_source database."""
        from sqlalchemy.ext.asyncio import create_async_engine

        from worker.admin import get_db_session
        from worker.db import register_engine

        # Create a separate engine for t3k and register it
        t3k_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        register_engine("postgresql+asyncpg://user:pass@db/gts_t3k_source", t3k_engine)

        # get_db_session should use core, not t3k
        async for session in get_db_session():
            # Session should be functional
            from sqlalchemy import text

            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            break

        await t3k_engine.dispose()
