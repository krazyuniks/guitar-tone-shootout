"""Audit service for logging user actions and security events.

Wraps the SQLAlchemyAuditRepository and provides a clean interface
for logging audit events throughout the application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from webapp.adapters.persistence.repositories.audit_repository import (
        SQLAlchemyAuditRepository,
    )


class AuditService:
    """Service for logging audit events.

    Responsibilities:
    - Wrapping repository calls with business logic
    - Capturing request context (IP, user agent, request ID)
    - Providing consistent audit logging interface
    """

    def __init__(self, repository: SQLAlchemyAuditRepository) -> None:
        """Initialize audit service.

        Args:
            repository: Audit repository for persistence
        """
        self.repository = repository

    async def log_event(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        user_id: UUID | None,
        details: dict[str, object] | None = None,
    ) -> None:
        """Log an audit event.

        Args:
            event_type: Type of event (e.g., 'login', 'logout', 'created')
            entity_type: Type of entity (e.g., 'user', 'shootout', 'signal_chain')
            entity_id: The entity's UUID
            user_id: The acting user's UUID (None for system/anonymous actions)
            details: Optional additional details (IP, user agent, request ID, etc.)
        """
        await self.repository.log_event(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            details=details,
        )
