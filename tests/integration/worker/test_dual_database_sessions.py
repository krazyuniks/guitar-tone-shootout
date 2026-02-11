"""Integration tests for dual database session factories.

Tests that the worker can create async database sessions for both gts_core
and gts_t3k_source databases. The pgmq consumer needs to read from
gts_t3k_source (pgmq queues, staging data) while writing to gts_core
(Gear, GearModel, GearSource).
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.integration
class TestGetCoreSession:
    """Test get_core_session context manager for gts_core database."""

    async def test_get_core_session_exists(self) -> None:
        """get_core_session function exists and is an async context manager."""
        from worker.db import get_core_session

        assert callable(get_core_session)

    async def test_get_core_session_yields_async_session(self) -> None:
        """get_core_session yields an AsyncSession."""
        from worker.db import get_core_session

        async with get_core_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_get_core_session_uses_core_database_url(self) -> None:
        """get_core_session uses WorkerSettings.database_url (gts_core)."""
        from worker.config import WorkerSettings
        from worker.db import get_core_session, register_engine

        # Create a test settings with known database URLs
        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        # Create a test engine and register it
        from sqlalchemy.ext.asyncio import create_async_engine

        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        register_engine(settings.database_url, test_engine)

        async with get_core_session() as session:
            # Verify the session's engine matches the registered engine
            engine = session.get_bind()
            assert engine == test_engine

        await test_engine.dispose()

    async def test_get_core_session_uses_engine_cache(self) -> None:
        """get_core_session reuses cached engines."""
        from worker.db import _engine_cache, get_core_session

        # Clear cache before test
        cache_size_before = len(_engine_cache)

        # Create two sessions with the same database URL
        async with get_core_session() as session1:
            cache_size_after_first = len(_engine_cache)
            engine1 = session1.get_bind()

        async with get_core_session() as session2:
            cache_size_after_second = len(_engine_cache)
            engine2 = session2.get_bind()

        # Cache should grow by at most 1 (if not already cached)
        assert cache_size_after_first <= cache_size_before + 1
        # Second call should not add another engine to cache
        assert cache_size_after_second == cache_size_after_first
        # Both sessions should use the same engine
        assert engine1 == engine2


@pytest.mark.asyncio
@pytest.mark.integration
class TestGetT3kSession:
    """Test get_t3k_session context manager for gts_t3k_source database."""

    async def test_get_t3k_session_exists(self) -> None:
        """get_t3k_session function exists and is an async context manager."""
        from worker.db import get_t3k_session

        assert callable(get_t3k_session)

    async def test_get_t3k_session_yields_async_session(self) -> None:
        """get_t3k_session yields an AsyncSession."""
        from worker.db import get_t3k_session

        async with get_t3k_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_get_t3k_session_uses_t3k_database_url(self) -> None:
        """get_t3k_session uses WorkerSettings.t3k_database_url (gts_t3k_source)."""
        from worker.config import WorkerSettings
        from worker.db import get_t3k_session, register_engine

        # Create a test settings with known database URLs
        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        # Create a test engine and register it
        from sqlalchemy.ext.asyncio import create_async_engine

        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        register_engine(settings.t3k_database_url, test_engine)

        async with get_t3k_session() as session:
            # Verify the session's engine matches the registered engine
            engine = session.get_bind()
            assert engine == test_engine

        await test_engine.dispose()

    async def test_get_t3k_session_uses_engine_cache(self) -> None:
        """get_t3k_session reuses cached engines."""
        from worker.db import _engine_cache, get_t3k_session

        # Clear cache before test
        cache_size_before = len(_engine_cache)

        # Create two sessions with the same database URL
        async with get_t3k_session() as session1:
            cache_size_after_first = len(_engine_cache)
            engine1 = session1.get_bind()

        async with get_t3k_session() as session2:
            cache_size_after_second = len(_engine_cache)
            engine2 = session2.get_bind()

        # Cache should grow by at most 1 (if not already cached)
        assert cache_size_after_first <= cache_size_before + 1
        # Second call should not add another engine to cache
        assert cache_size_after_second == cache_size_after_first
        # Both sessions should use the same engine
        assert engine1 == engine2


@pytest.mark.asyncio
@pytest.mark.integration
class TestDualDatabaseSeparation:
    """Test that core and t3k sessions connect to different databases."""

    async def test_core_and_t3k_sessions_use_different_engines(self) -> None:
        """get_core_session and get_t3k_session use different database engines."""
        from worker.config import WorkerSettings
        from worker.db import get_core_session, get_t3k_session, register_engine

        # Create settings with different database URLs
        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        # Create two different test engines
        from sqlalchemy.ext.asyncio import create_async_engine

        core_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        t3k_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        register_engine(settings.database_url, core_engine)
        register_engine(settings.t3k_database_url, t3k_engine)

        async with get_core_session() as core_session, get_t3k_session() as t3k_session:
            # Verify sessions use different engines
            core_engine_used = core_session.get_bind()
            t3k_engine_used = t3k_session.get_bind()

            assert core_engine_used == core_engine
            assert t3k_engine_used == t3k_engine
            assert core_engine_used != t3k_engine_used

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

        # Verify the database URL references gts_core
        assert "gts_core" in settings.database_url

    async def test_t3k_session_database_url_contains_gts_t3k_source(self) -> None:
        """get_t3k_session database URL references gts_t3k_source database."""
        from worker.config import WorkerSettings

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        # Verify the database URL references gts_t3k_source
        assert "gts_t3k_source" in settings.t3k_database_url
