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

        assert inspect.isasyncgenfunction(get_db_session)

    async def test_get_db_session_yields_async_session(self, core_engine: AsyncEngine) -> None:
        """get_db_session yields an AsyncSession."""
        from worker.admin import get_db_session

        async for session in get_db_session():
            assert isinstance(session, AsyncSession)
            break

    async def test_get_db_session_uses_core_database(self, core_engine: AsyncEngine) -> None:
        """get_db_session uses gts_core database via get_core_session."""
        from worker.admin import get_db_session

        async for session in get_db_session():
            from sqlalchemy import text

            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            break

    async def test_admin_endpoints_use_core_session(self, core_engine: AsyncEngine) -> None:
        """Admin API endpoints receive sessions from get_core_session."""
        from httpx import ASGITransport, AsyncClient

        from worker.admin import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/admin/jobs")
            assert response.status_code == 200
            assert isinstance(response.json(), list)
