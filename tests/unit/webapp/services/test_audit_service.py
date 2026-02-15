"""Unit tests for AuditService."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
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
def mock_repository() -> Mock:
    """Create a mock repository."""
    repo = Mock()
    repo.log_event = AsyncMock()
    return repo


class TestAuditService:
    """Test suite for AuditService."""

    async def test_log_event_calls_repository(self, mock_repository: Mock) -> None:
        """Test log_event delegates to repository with correct parameters."""
        service = AuditService(repository=mock_repository)

        user_id = uuid4()
        entity_id = uuid4()

        await service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
        )

        mock_repository.log_event.assert_called_once_with(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
            details=None,
        )

    async def test_log_event_with_details(self, mock_repository: Mock) -> None:
        """Test log_event passes details dict to repository."""
        service = AuditService(repository=mock_repository)

        user_id = uuid4()
        entity_id = uuid4()
        details = {"ip_address": "127.0.0.1", "user_agent": "Mozilla/5.0"}

        await service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
            details=details,
        )

        mock_repository.log_event.assert_called_once_with(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
            details=details,
        )

    async def test_log_event_with_none_user_id(self, mock_repository: Mock) -> None:
        """Test log_event accepts None for user_id (system actions)."""
        service = AuditService(repository=mock_repository)

        entity_id = uuid4()

        await service.log_event(
            event_type="system_action",
            entity_type="job",
            entity_id=entity_id,
            user_id=None,
        )

        mock_repository.log_event.assert_called_once_with(
            event_type="system_action",
            entity_type="job",
            entity_id=entity_id,
            user_id=None,
            details=None,
        )

    async def test_log_event_with_request_context(self, mock_repository: Mock) -> None:
        """Test log_event captures request context (IP, user agent, request ID)."""
        service = AuditService(repository=mock_repository)

        user_id = uuid4()
        entity_id = uuid4()
        details = {
            "ip_address": "192.168.1.1",
            "user_agent": "curl/7.64.1",
            "request_id": "req-123-abc",
        }

        await service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
            details=details,
        )

        call_args = mock_repository.log_event.call_args
        assert call_args[1]["details"]["ip_address"] == "192.168.1.1"
        assert call_args[1]["details"]["user_agent"] == "curl/7.64.1"
        assert call_args[1]["details"]["request_id"] == "req-123-abc"

    async def test_log_event_integration_with_real_repository(
        self, db_session: AsyncSession
    ) -> None:
        """Test AuditService with real repository creates audit log entry."""
        from sqlalchemy import select

        from webapp.adapters.persistence.models.job import AuditLog
        from webapp.adapters.persistence.repositories.audit_repository import (
            SQLAlchemyAuditRepository,
        )

        repository = SQLAlchemyAuditRepository(db_session)
        service = AuditService(repository=repository)

        user_id = uuid4()
        entity_id = uuid4()

        await service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=entity_id,
            user_id=user_id,
        )

        await db_session.commit()

        # Verify audit log was created
        result = await db_session.execute(select(AuditLog))
        logs = result.scalars().all()

        assert len(logs) == 1
        assert logs[0].action == "login"
        assert logs[0].resource_type == "user"
        assert logs[0].resource_id == entity_id
        assert logs[0].user_id == user_id
