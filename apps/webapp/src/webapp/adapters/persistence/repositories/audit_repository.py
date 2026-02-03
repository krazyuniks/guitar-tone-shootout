"""SQLAlchemy implementation of AuditRepository protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from webapp.adapters.persistence.models.job import AuditLog

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyAuditRepository:
    """SQLAlchemy implementation of AuditRepository protocol.

    Logs audit events to the database.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

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
            event_type: Type of event (e.g., 'created', 'updated', 'deleted')
            entity_type: Type of entity (e.g., 'shootout', 'signal_chain')
            entity_id: The entity's UUID
            user_id: The acting user's UUID (None for system actions)
            details: Optional additional details
        """
        audit_log = AuditLog(
            action=event_type,
            resource_type=entity_type,
            resource_id=entity_id,
            user_id=user_id,
            extra_data=details or {},
        )
        self.session.add(audit_log)
        await self.session.flush()
