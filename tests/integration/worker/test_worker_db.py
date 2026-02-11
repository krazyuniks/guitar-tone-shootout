"""Integration tests for worker database session factory.

Tests that the worker can create async database sessions and connect to the
gts_core database for reading/writing Job records and other data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from webapp.adapters.persistence.models.base import Base


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine (SQLite for testing)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


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

    async def test_creates_sessionmaker_from_database_url(self) -> None:
        """async_session_factory returns async_sessionmaker."""
        from worker.db import async_session_factory

        factory = async_session_factory("sqlite+aiosqlite:///:memory:")

        assert factory is not None
        assert isinstance(factory, async_sessionmaker)

    async def test_factory_creates_async_sessions(self) -> None:
        """Session factory creates AsyncSession instances."""
        from worker.db import async_session_factory

        factory = async_session_factory("sqlite+aiosqlite:///:memory:")
        session = factory()

        assert isinstance(session, AsyncSession)
        await session.close()

    async def test_uses_database_url_from_worker_settings(self) -> None:
        """async_session_factory uses DATABASE_URL from WorkerSettings."""
        from worker.config import WorkerSettings
        from worker.db import async_session_factory

        # Create a settings instance with explicit database_url
        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="sqlite+aiosqlite:///:memory:",
            t3k_database_url="postgresql+asyncpg://user:pass@localhost/t3k",
        )

        factory = async_session_factory(settings.database_url)
        session = factory()

        assert isinstance(session, AsyncSession)
        await session.close()


@pytest.mark.asyncio
@pytest.mark.integration
class TestGetSession:
    """Test get_session context manager."""

    async def test_is_async_context_manager(self) -> None:
        """get_session is an async context manager."""
        from worker.db import get_session

        # Check that get_session returns something with __aenter__/__aexit__
        cm = get_session("sqlite+aiosqlite:///:memory:")
        assert hasattr(cm, "__aenter__")
        assert hasattr(cm, "__aexit__")

    async def test_yields_async_session(self) -> None:
        """get_session yields an AsyncSession."""
        from worker.db import get_session

        async with get_session("sqlite+aiosqlite:///:memory:") as session:
            assert isinstance(session, AsyncSession)

    async def test_session_can_execute_queries(self, db_engine: AsyncEngine) -> None:
        """Session from get_session can execute queries."""
        from worker.db import get_session

        # Create a database URL from the test engine
        database_url = str(db_engine.url)

        async with get_session(database_url) as session:
            result = await session.execute(text("SELECT 1 as value"))
            row = result.fetchone()
            assert row is not None
            assert row[0] == 1

    async def test_session_auto_closes_on_exit(self) -> None:
        """Session closes automatically when exiting context."""
        from worker.db import get_session

        session_ref = None
        async with get_session("sqlite+aiosqlite:///:memory:") as session:
            session_ref = session
            assert not session.is_active or session.in_transaction()

        # After exiting context, session should be closed
        assert session_ref is not None
        # Verify session is no longer in an active transaction
        assert not session_ref.in_transaction()


@pytest.mark.asyncio
@pytest.mark.integration
class TestDatabaseConnectivity:
    """Test worker can connect to gts_core database and query tables."""

    async def test_can_query_jobs_table(self, db_engine: AsyncEngine) -> None:
        """Worker session can query the jobs table."""
        from worker.db import get_session

        async with get_session(db_engine) as session:
            # Query jobs table (should be empty in fresh test DB)
            result = await session.execute(text("SELECT count(*) FROM jobs"))
            count = result.scalar()
            assert count == 0

    async def test_can_query_jobs_table_using_orm(self, db_engine: AsyncEngine) -> None:
        """Worker session can query jobs using SQLAlchemy ORM."""
        from webapp.adapters.persistence.models.job import Job
        from worker.db import get_session

        async with get_session(db_engine) as session:
            # Query jobs using ORM
            stmt = select(Job)
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            assert jobs == []

    async def test_session_uses_asyncpg_driver_for_postgresql(self) -> None:
        """Session factory uses asyncpg driver for PostgreSQL URLs."""
        from worker.db import async_session_factory

        # PostgreSQL URL MUST use asyncpg driver
        pg_url = "postgresql+asyncpg://user:pass@localhost/gts_core"
        factory = async_session_factory(pg_url)

        # Verify the engine uses asyncpg
        # The driver is embedded in the URL, so we check the factory's bind
        session = factory()
        engine = session.get_bind()
        assert "asyncpg" in str(engine.url)
        await session.close()

    async def test_session_connects_to_gts_core_database(self) -> None:
        """Session factory connects to gts_core database from WorkerSettings."""
        from worker.config import WorkerSettings
        from worker.db import async_session_factory

        # WorkerSettings.database_url should point to gts_core
        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@db/gts_core",
            t3k_database_url="postgresql+asyncpg://user:pass@db/gts_t3k_source",
        )

        factory = async_session_factory(settings.database_url)
        session = factory()

        # Verify the database URL references gts_core
        engine = session.get_bind()
        assert "gts_core" in str(engine.url)
        await session.close()
