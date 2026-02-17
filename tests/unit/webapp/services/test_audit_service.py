"""Unit tests for AuditService.

All tests use a real SQLite database and real SQLAlchemyAuditRepository.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import AuditLog
from webapp.adapters.persistence.repositories.audit_repository import (
    SQLAlchemyAuditRepository,
)
from webapp.services.audit_service import AuditService


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Real database with transaction rollback."""
    connection = await db_engine.connect()
    transaction = await connection.begin()

    async_session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
def audit_service(db_session: AsyncSession) -> AuditService:
    """Create AuditService with real repository."""
    repository = SQLAlchemyAuditRepository(db_session)
    return AuditService(repository=repository)


class TestAuditService:
    """Test suite for AuditService."""

    async def test_log_event_creates_audit_log(
        self, audit_service: AuditService, db_session: AsyncSession
    ) -> None:
        """Test log_event creates an audit log entry in the database."""
        user_id = uuid4()
        entity_id = uuid4()

        await audit_service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
        )
        await db_session.commit()

        result = await db_session.execute(select(AuditLog))
        logs = result.scalars().all()

        assert len(logs) == 1
        assert logs[0].action == "login"
        assert logs[0].resource_type == "user"
        assert logs[0].resource_id == entity_id
        assert logs[0].user_id == user_id

    async def test_log_event_with_details(
        self, audit_service: AuditService, db_session: AsyncSession
    ) -> None:
        """Test log_event stores details in separate columns."""
        user_id = uuid4()
        entity_id = uuid4()
        details = {"ip_address": "127.0.0.1", "user_agent": "Mozilla/5.0"}

        await audit_service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
            details=details,
        )
        await db_session.commit()

        result = await db_session.execute(select(AuditLog))
        log = result.scalars().first()

        assert log is not None
        assert log.ip_address == "127.0.0.1"
        assert log.user_agent == "Mozilla/5.0"

    async def test_log_event_with_none_user_id(
        self, audit_service: AuditService, db_session: AsyncSession
    ) -> None:
        """Test log_event accepts None for user_id (system actions)."""
        entity_id = uuid4()

        await audit_service.log_event(
            event_type="system_action",
            entity_type="job",
            entity_id=entity_id,
            user_id=None,
        )
        await db_session.commit()

        result = await db_session.execute(select(AuditLog))
        log = result.scalars().first()

        assert log is not None
        assert log.action == "system_action"
        assert log.resource_type == "job"
        assert log.user_id is None

    async def test_log_event_with_request_context(
        self, audit_service: AuditService, db_session: AsyncSession
    ) -> None:
        """Test log_event captures request context (IP, user agent, request ID)."""
        user_id = uuid4()
        entity_id = uuid4()
        details = {
            "ip_address": "192.168.1.1",
            "user_agent": "curl/7.64.1",
            "request_id": "req-123-abc",
        }

        await audit_service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
            details=details,
        )
        await db_session.commit()

        result = await db_session.execute(select(AuditLog))
        log = result.scalars().first()

        assert log is not None
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "curl/7.64.1"
        assert log.request_id == "req-123-abc"

    async def test_multiple_events_are_independent(
        self, audit_service: AuditService, db_session: AsyncSession
    ) -> None:
        """Test multiple log_event calls create independent records."""
        user_id = uuid4()

        await audit_service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=uuid4(),
            user_id=user_id,
        )
        await audit_service.log_event(
            event_type="logout",
            entity_type="user",
            entity_id=uuid4(),
            user_id=user_id,
        )
        await db_session.commit()

        result = await db_session.execute(select(AuditLog))
        logs = result.scalars().all()

        assert len(logs) == 2
        actions = {log.action for log in logs}
        assert actions == {"login", "logout"}
