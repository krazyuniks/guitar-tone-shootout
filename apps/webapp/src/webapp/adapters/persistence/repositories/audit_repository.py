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
            details: Optional additional details (may include ip_address, user_agent, request_id)
        """
        # Extract known fields from details
        ip_address = None
        user_agent = None
        request_id = None
        extra_data = {}

        if details:
            ip_address = details.get("ip_address")
            user_agent = details.get("user_agent")
            request_id = details.get("request_id")
            # Store remaining details in extra_data
            extra_data = {
                k: v
                for k, v in details.items()
                if k not in ("ip_address", "user_agent", "request_id")
            }

        audit_log = AuditLog(
            action=event_type,
            resource_type=entity_type,
            resource_id=entity_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            extra_data=extra_data if extra_data else None,
        )
        self.session.add(audit_log)
        await self.session.flush()
