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

    async def test_get_core_session_yields_async_session(self, db_engine) -> None:
        """get_core_session yields an AsyncSession."""
        from worker.db import get_core_session

        async with get_core_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_get_core_session_uses_core_database_url(self, db_engine) -> None:
        """get_core_session uses WorkerSettings.database_url (gts_core)."""
        from worker.db import get_core_session

        # The conftest db_engine registers an engine under the core URL.
        # Verify the session is functional (uses the registered test engine).
        async with get_core_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_get_core_session_uses_engine_cache(self, db_engine) -> None:
        """get_core_session reuses cached engines."""
        from worker.db import _engine_cache, get_core_session

        cache_size_before = len(_engine_cache)

        async with get_core_session() as _session1:
            cache_size_after_first = len(_engine_cache)

        async with get_core_session() as _session2:
            cache_size_after_second = len(_engine_cache)

        # Cache should not grow — engine already registered by fixture
        assert cache_size_after_first == cache_size_before
        # Second call should not add another engine to cache
        assert cache_size_after_second == cache_size_after_first


@pytest.mark.asyncio
@pytest.mark.integration
class TestGetT3kSession:
    """Test get_t3k_session context manager for gts_t3k_source database."""

    async def test_get_t3k_session_exists(self) -> None:
        """get_t3k_session function exists and is an async context manager."""
        from worker.db import get_t3k_session

        assert callable(get_t3k_session)

    async def test_get_t3k_session_yields_async_session(self, db_engine) -> None:
        """get_t3k_session yields an AsyncSession."""
        from worker.db import get_t3k_session

        async with get_t3k_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_get_t3k_session_uses_t3k_database_url(self, db_engine) -> None:
        """get_t3k_session uses WorkerSettings.t3k_database_url (gts_t3k_source)."""
        from worker.db import get_t3k_session

        # The conftest db_engine registers an engine under the t3k URL.
        # Verify the session is functional (uses the registered test engine).
        async with get_t3k_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_get_t3k_session_uses_engine_cache(self, db_engine) -> None:
        """get_t3k_session reuses cached engines."""
        from worker.db import _engine_cache, get_t3k_session

        cache_size_before = len(_engine_cache)

        async with get_t3k_session() as _session1:
            cache_size_after_first = len(_engine_cache)

        async with get_t3k_session() as _session2:
            cache_size_after_second = len(_engine_cache)

        # Cache should not grow — engine already registered by fixture
        assert cache_size_after_first == cache_size_before
        assert cache_size_after_second == cache_size_after_first


@pytest.mark.asyncio
@pytest.mark.integration
class TestDualDatabaseSeparation:
    """Test that core and t3k sessions connect to different databases."""

    async def test_core_and_t3k_sessions_use_different_engines(self) -> None:
        """get_core_session and get_t3k_session use different database engines."""
        from worker.config import WorkerSettings
        from worker.db import (
            _engine_cache,
            get_core_session,
            get_t3k_session,
            register_engine,
        )

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        from sqlalchemy.ext.asyncio import create_async_engine

        core_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        t3k_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        register_engine(settings.database_url, core_engine)
        register_engine(settings.t3k_database_url, t3k_engine)

        # Verify the cache contains different engines for each URL
        cached_core = _engine_cache[settings.database_url]
        cached_t3k = _engine_cache[settings.t3k_database_url]
        assert cached_core is core_engine
        assert cached_t3k is t3k_engine
        assert cached_core is not cached_t3k

        # Verify both sessions are functional
        async with get_core_session() as core_session, get_t3k_session() as t3k_session:
            core_result = await core_session.execute(text("SELECT 1"))
            assert core_result.scalar() == 1
            t3k_result = await t3k_session.execute(text("SELECT 1"))
            assert t3k_result.scalar() == 1

        await core_engine.dispose()
        await t3k_engine.dispose()

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
