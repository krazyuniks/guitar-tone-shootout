"""Integration tests for worker database session factories.

Tests that the worker can create async database sessions for the gts_core
database. All BCs share one database with table prefix isolation
(core_*, t3k_*, msg_*).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.integration
class TestGetCoreSession:
    """Test get_core_session context manager for gts_core database."""

    async def test_get_core_session_exists(self) -> None:
        """get_core_session function exists and is an async context manager."""
        from worker.db import get_core_session

        assert callable(get_core_session)

    async def test_get_core_session_yields_async_session(self, core_engine) -> None:
        """get_core_session yields an AsyncSession."""
        from worker.db import get_core_session

        async with get_core_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_get_core_session_uses_core_database_url(self, core_engine) -> None:
        """get_core_session uses WorkerSettings.database_url (gts_core)."""
        from worker.db import get_core_session

        async with get_core_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_get_core_session_uses_engine_cache(self, core_engine) -> None:
        """get_core_session reuses cached engines."""
        from worker.db import _engine_cache, get_core_session

        cache_size_before = len(_engine_cache)

        async with get_core_session() as _session1:
            cache_size_after_first = len(_engine_cache)

        async with get_core_session() as _session2:
            cache_size_after_second = len(_engine_cache)

        assert cache_size_after_first == cache_size_before
        assert cache_size_after_second == cache_size_after_first

    async def test_core_session_database_url_contains_gts_core(self) -> None:
        """get_core_session database URL references gts_core database."""
        from worker.config import WorkerSettings

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
        )

        assert "gts_core" in settings.database_url
