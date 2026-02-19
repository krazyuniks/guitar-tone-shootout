"""Unit tests for AuditService.

All tests use the shared PostgreSQL database from the root conftest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

from webapp.adapters.persistence.models.job import AuditLog
from webapp.adapters.persistence.repositories.audit_repository import (
    SQLAlchemyAuditRepository,
)
from webapp.services.audit_service import AuditService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def audit_service(session: AsyncSession) -> AuditService:
    """Create AuditService with real repository."""
    repository = SQLAlchemyAuditRepository(session)
    return AuditService(repository=repository)


class TestAuditService:
    """Test suite for AuditService."""

    async def test_log_event_creates_audit_log(
        self, audit_service: AuditService, session: AsyncSession
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
        await session.commit()

        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == entity_id))
        log = result.scalar_one()

        assert log.action == "login"
        assert log.resource_type == "user"
        assert log.resource_id == entity_id
        assert log.user_id == user_id

    async def test_log_event_with_details(
        self, audit_service: AuditService, session: AsyncSession
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
        await session.commit()

        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == entity_id))
        log = result.scalar_one()

        assert log is not None
        assert log.ip_address == "127.0.0.1"
        assert log.user_agent == "Mozilla/5.0"

    async def test_log_event_with_none_user_id(
        self, audit_service: AuditService, session: AsyncSession
    ) -> None:
        """Test log_event accepts None for user_id (system actions)."""
        entity_id = uuid4()

        await audit_service.log_event(
            event_type="system_action",
            entity_type="job",
            entity_id=entity_id,
            user_id=None,
        )
        await session.commit()

        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == entity_id))
        log = result.scalar_one()

        assert log is not None
        assert log.action == "system_action"
        assert log.resource_type == "job"
        assert log.user_id is None

    async def test_log_event_with_request_context(
        self, audit_service: AuditService, session: AsyncSession
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
        await session.commit()

        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == entity_id))
        log = result.scalar_one()

        assert log is not None
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "curl/7.64.1"
        assert log.request_id == "req-123-abc"

    async def test_multiple_events_are_independent(
        self, audit_service: AuditService, session: AsyncSession
    ) -> None:
        """Test multiple log_event calls create independent records."""
        user_id = uuid4()
        entity_id_1 = uuid4()
        entity_id_2 = uuid4()

        await audit_service.log_event(
            event_type="login",
            entity_type="user",
            entity_id=entity_id_1,
            user_id=user_id,
        )
        await audit_service.log_event(
            event_type="logout",
            entity_type="user",
            entity_id=entity_id_2,
            user_id=user_id,
        )
        await session.commit()

        result = await session.execute(select(AuditLog).where(AuditLog.user_id == user_id))
        logs = result.scalars().all()

        assert len(logs) == 2
        actions = {log.action for log in logs}
        assert actions == {"login", "logout"}
