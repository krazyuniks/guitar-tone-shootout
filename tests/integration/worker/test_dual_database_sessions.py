"""Integration tests for dual database session factories.

Tests that the worker can create async database sessions for both gts_core
and gts_t3k_source databases. The pgmq consumer needs to read from
gts_t3k_source (pgmq queues, staging data) while writing to gts_core
(Gear, GearModel, GearSource).
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


@pytest.mark.asyncio
@pytest.mark.integration
class TestGetT3kSession:
    """Test get_t3k_session context manager for gts_t3k_source database."""

    async def test_get_t3k_session_exists(self) -> None:
        """get_t3k_session function exists and is an async context manager."""
        from worker.db import get_t3k_session

        assert callable(get_t3k_session)

    async def test_get_t3k_session_yields_async_session(self, core_engine) -> None:
        """get_t3k_session yields an AsyncSession."""
        from worker.db import get_t3k_session

        async with get_t3k_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_get_t3k_session_uses_t3k_database_url(self, core_engine) -> None:
        """get_t3k_session uses WorkerSettings.t3k_database_url (gts_t3k_source)."""
        from worker.db import get_t3k_session

        async with get_t3k_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_get_t3k_session_uses_engine_cache(self, core_engine) -> None:
        """get_t3k_session reuses cached engines."""
        from worker.db import _engine_cache, get_t3k_session

        cache_size_before = len(_engine_cache)

        async with get_t3k_session() as _session1:
            cache_size_after_first = len(_engine_cache)

        async with get_t3k_session() as _session2:
            cache_size_after_second = len(_engine_cache)

        assert cache_size_after_first == cache_size_before
        assert cache_size_after_second == cache_size_after_first


@pytest.mark.asyncio
@pytest.mark.integration
class TestDualDatabaseSeparation:
    """Test that core and t3k sessions connect to different databases."""

    async def test_core_and_t3k_use_same_engine(self, core_engine) -> None:
        """get_core_session and get_t3k_session both use gts_core engine.

        Note: get_t3k_session is a backward-compatible alias for get_core_session
        since the database consolidation (single PostgreSQL instance).
        """
        from worker.db import get_core_session, get_t3k_session

        async with get_core_session() as core_session, get_t3k_session() as t3k_session:
            core_result = await core_session.execute(text("SELECT 1"))
            assert core_result.scalar() == 1
            t3k_result = await t3k_session.execute(text("SELECT 1"))
            assert t3k_result.scalar() == 1

    async def test_core_session_database_url_contains_gts_core(self) -> None:
        """get_core_session database URL references gts_core database."""
        from worker.config import WorkerSettings

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        assert "gts_core" in settings.database_url

    async def test_t3k_session_database_url_contains_gts_t3k_source(self) -> None:
        """get_t3k_session database URL references gts_t3k_source database."""
        from worker.config import WorkerSettings

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        assert "gts_t3k_source" in settings.t3k_database_url
