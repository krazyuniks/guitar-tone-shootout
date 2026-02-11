"""Notifications API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.notification import (
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationResponse,
)
from webapp.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

# Session and user overrides for testing
_session_override: AsyncSession | None = None
_user_override: User | None = None


def set_session_override(session: AsyncSession | None) -> None:
    """Override the database session for testing."""
    global _session_override
    _session_override = session


def set_user_override(user: User | None) -> None:
    """Override the current user for testing."""
    global _user_override
    _user_override = user


async def get_db_session() -> AsyncSession:
    """Get database session dependency."""
    if _session_override:
        return _session_override
    raise NotImplementedError("Database session dependency not configured")


async def get_current_user() -> User:
    """Get current authenticated user dependency."""
    if _user_override:
        return _user_override
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[NotificationResponse]:
    """List current user's notifications."""
    service = NotificationService(db)
    notifications = await service.get_all(current_user.id)

    return [
        NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )
        for notification in notifications
    ]


@router.put("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_notification_read(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarkReadResponse:
    """Mark a notification as read."""
    service = NotificationService(db)
    success = await service.mark_read(notification_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return MarkReadResponse(success=True)


@router.put("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarkAllReadResponse:
    """Mark all unread notifications as read."""
    service = NotificationService(db)
    count = await service.mark_all_read(current_user.id)

    return MarkAllReadResponse(marked_count=count)
