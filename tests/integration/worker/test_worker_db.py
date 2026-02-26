"""Integration tests for worker database session factory.

Tests that the worker can create async database sessions and connect to the
gts_core database for reading/writing Job records and other data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest.mark.asyncio
@pytest.mark.integration
class TestWorkerDbModule:
    """Test worker.db module exists and provides required functions."""

    async def test_db_module_exists(self) -> None:
        """db module exists in worker package."""
        from worker import db  # noqa: F401

    async def test_async_session_factory_function_exists(self) -> None:
        """async_session_factory function exists."""
        from worker.db import async_session_factory

        assert callable(async_session_factory)

    async def test_get_session_function_exists(self) -> None:
        """get_session function exists and is an async context manager."""
        from worker.db import get_session

        assert callable(get_session)


@pytest.mark.asyncio
@pytest.mark.integration
class TestAsyncSessionFactory:
    """Test async_session_factory creates valid session factories."""

    async def test_creates_sessionmaker_from_engine(self, core_engine: AsyncEngine) -> None:
        """async_session_factory returns async_sessionmaker when engine is registered."""
        from worker.db import async_session_factory

        factory = async_session_factory(str(core_engine.url))

        assert factory is not None
        assert isinstance(factory, async_sessionmaker)

    async def test_factory_creates_async_sessions(self, core_engine: AsyncEngine) -> None:
        """Session factory creates AsyncSession instances."""
        from worker.db import async_session_factory

        factory = async_session_factory(str(core_engine.url))
        session = factory()

        assert isinstance(session, AsyncSession)
        await session.close()


@pytest.mark.asyncio
@pytest.mark.integration
class TestGetSession:
    """Test get_session context manager."""

    async def test_is_async_context_manager(self, core_engine: AsyncEngine) -> None:
        """get_session is an async context manager."""
        from worker.db import get_session

        cm = get_session(core_engine)
        assert hasattr(cm, "__aenter__")
        assert hasattr(cm, "__aexit__")

    async def test_yields_async_session(self, core_engine: AsyncEngine) -> None:
        """get_session yields an AsyncSession."""
        from worker.db import get_session

        async with get_session(core_engine) as session:
            assert isinstance(session, AsyncSession)

    async def test_session_can_execute_queries(self, core_engine: AsyncEngine) -> None:
        """Session from get_session can execute queries."""
        from worker.db import get_session

        async with get_session(core_engine) as session:
            result = await session.execute(text("SELECT 1 as value"))
            row = result.fetchone()
            assert row is not None
            assert row[0] == 1

    async def test_session_auto_closes_on_exit(self, core_engine: AsyncEngine) -> None:
        """Session closes automatically when exiting context."""
        from worker.db import get_session

        session_ref = None
        async with get_session(core_engine) as session:
            session_ref = session
            assert not session.is_active or session.in_transaction()

        assert session_ref is not None
        assert not session_ref.in_transaction()


@pytest.mark.asyncio
@pytest.mark.integration
class TestDatabaseConnectivity:
    """Test worker can connect to gts_core database and query tables."""

    async def test_can_query_jobs_table(self, core_engine: AsyncEngine) -> None:
        """Worker session can query the jobs table."""
        from worker.db import get_session

        async with get_session(core_engine) as session:
            result = await session.execute(text("SELECT count(*) FROM core_jobs"))
            count = result.scalar()
            assert count == 0

    async def test_can_query_jobs_table_using_orm(self, core_engine: AsyncEngine) -> None:
        """Worker session can query jobs using SQLAlchemy ORM."""
        from webapp.adapters.persistence.models.job import Job
        from worker.db import get_session

        async with get_session(core_engine) as session:
            stmt = select(Job)
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            assert jobs == []

    async def test_session_uses_asyncpg_driver_for_postgresql(self) -> None:
        """Session factory uses asyncpg driver for PostgreSQL URLs."""
        from worker.db import async_session_factory

        pg_url = "postgresql+asyncpg://user:pass@localhost/gts_core"
        factory = async_session_factory(pg_url)

        session = factory()
        engine = session.get_bind()
        assert "asyncpg" in str(engine.url)
        await session.close()

    async def test_session_connects_to_gts_core_database(self) -> None:
        """Session factory connects to gts_core database from WorkerSettings."""
        from worker.config import WorkerSettings
        from worker.db import async_session_factory

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        factory = async_session_factory(settings.database_url)
        session = factory()

        engine = session.get_bind()
        assert "gts_core" in str(engine.url)
        await session.close()
