"""Regression test: validates Phase 4 ORM models round-trip correctly.

Tests Phase 4 entities: ShootoutComment, Tag, UserNotification, AuditLog

Run with: just test-regression
Pass = Phase 4 entities work | Fail = ORM or migration issue
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from gts.domain.entities.user import User as UserEntity
from gts.domain.entities.user import UserIdentity
from webapp.adapters.persistence.models.job import AuditLog
from webapp.adapters.persistence.models.notification import UserNotification
from webapp.adapters.persistence.models.shootout import Shootout
from webapp.adapters.persistence.models.shootout_comment import ShootoutComment
from webapp.adapters.persistence.models.tag import Tag
from webapp.adapters.persistence.repositories.audit_repository import (
    SQLAlchemyAuditRepository,
)
from webapp.adapters.persistence.repositories.shootout_comment_repository import (
    ShootoutCommentRepository,
)
from webapp.adapters.persistence.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestPhase4ModelsImport:
    """Verify Phase 4 ORM models can be imported."""

    def test_shootout_comment_import(self) -> None:
        """ShootoutComment model can be imported."""
        assert ShootoutComment is not None
        assert ShootoutComment.__tablename__ == "core_shootout_comments"

    def test_tag_import(self) -> None:
        """Tag model can be imported."""
        assert Tag is not None
        assert Tag.__tablename__ == "core_user_tags"

    def test_notification_import(self) -> None:
        """UserNotification model can be imported."""
        assert UserNotification is not None
        assert UserNotification.__tablename__ == "core_user_notifications"

    def test_audit_log_import(self) -> None:
        """AuditLog model can be imported."""
        assert AuditLog is not None
        assert AuditLog.__tablename__ == "core_audit_logs"


class TestShootoutCommentRoundTrip:
    """Verify ShootoutComment entity can be saved and retrieved."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
        """Create comment via repository, retrieve it - validates full stack."""
        # Create a user first
        identity = UserIdentity(
            provider="t3k", external_id="comment-user-001", username="commenter"
        )
        user = UserEntity.create_with_identity(identity=identity, email="commenter@gts.dev")
        user_repo = SQLAlchemyUserRepository(db_session)
        await user_repo.save(user)
        await db_session.commit()

        # Create a shootout
        shootout = Shootout(
            user_id=user.id,
            name="Test Shootout for Comments",
            description="Testing comment persistence",
        )
        db_session.add(shootout)
        await db_session.commit()

        # Create a comment via repository
        comment_repo = ShootoutCommentRepository(db_session)
        comment = await comment_repo.create(
            shootout_id=shootout.id,
            user_id=user.id,
            content="This is a test comment",
        )
        await db_session.commit()

        # Retrieve and verify
        retrieved = await comment_repo.get_by_id(comment.id, user.id)
        assert retrieved is not None
        assert retrieved.id == comment.id
        assert retrieved.shootout_id == shootout.id
        assert retrieved.user_id == user.id
        assert retrieved.content == "This is a test comment"
        assert retrieved.created_at is not None

    @pytest.mark.asyncio
    async def test_list_by_shootout(self, db_session: AsyncSession) -> None:
        """Comments can be listed by shootout."""
        # Create a user
        identity = UserIdentity(provider="t3k", external_id="list-user-001", username="lister")
        user = UserEntity.create_with_identity(identity=identity, email="lister@gts.dev")
        user_repo = SQLAlchemyUserRepository(db_session)
        await user_repo.save(user)
        await db_session.commit()

        # Create a shootout
        shootout = Shootout(
            user_id=user.id,
            name="Shootout with Comments",
        )
        db_session.add(shootout)
        await db_session.commit()

        # Create multiple comments
        comment_repo = ShootoutCommentRepository(db_session)
        await comment_repo.create(shootout_id=shootout.id, user_id=user.id, content="First comment")
        await comment_repo.create(
            shootout_id=shootout.id, user_id=user.id, content="Second comment"
        )
        await db_session.commit()

        # List comments (scoped to the owning user)
        comments = await comment_repo.list_by_shootout(shootout.id, user.id)
        assert len(comments) == 2
        # Newest first
        assert comments[0].content == "Second comment"
        assert comments[1].content == "First comment"


class TestTagRoundTrip:
    """Verify Tag entity can be saved and retrieved."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
        """Create tag, retrieve it - validates Tag ORM."""
        # Create a user
        identity = UserIdentity(provider="t3k", external_id="tag-user-001", username="tagger")
        user = UserEntity.create_with_identity(identity=identity, email="tagger@gts.dev")
        user_repo = SQLAlchemyUserRepository(db_session)
        await user_repo.save(user)
        await db_session.commit()

        # Create a tag
        tag = Tag(user_id=user.id, name="rock")
        db_session.add(tag)
        await db_session.commit()

        # Retrieve and verify
        from sqlalchemy import select

        stmt = select(Tag).where(Tag.id == tag.id)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.id == tag.id
        assert retrieved.user_id == user.id
        assert retrieved.name == "rock"
        assert retrieved.created_at is not None

    @pytest.mark.asyncio
    async def test_unique_constraint(self, db_session: AsyncSession) -> None:
        """Tag names are unique per user."""
        # Create a user
        identity = UserIdentity(provider="t3k", external_id="unique-user-001", username="unique")
        user = UserEntity.create_with_identity(identity=identity, email="unique@gts.dev")
        user_repo = SQLAlchemyUserRepository(db_session)
        await user_repo.save(user)
        await db_session.commit()

        # Create first tag
        tag1 = Tag(user_id=user.id, name="metal")
        db_session.add(tag1)
        await db_session.commit()

        # Attempt to create duplicate tag name for same user
        tag2 = Tag(user_id=user.id, name="metal")
        db_session.add(tag2)

        with pytest.raises(Exception):  # IntegrityError or similar
            await db_session.commit()


class TestUserNotificationRoundTrip:
    """Verify UserNotification entity can be saved and retrieved."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
        """Create notification, retrieve it - validates UserNotification ORM."""
        # Create a user
        identity = UserIdentity(provider="t3k", external_id="notif-user-001", username="notified")
        user = UserEntity.create_with_identity(identity=identity, email="notified@gts.dev")
        user_repo = SQLAlchemyUserRepository(db_session)
        await user_repo.save(user)
        await db_session.commit()

        # Create a notification
        notification = UserNotification(
            user_id=user.id,
            type="info",
            title="Welcome",
            message="Welcome to GTS!",
        )
        db_session.add(notification)
        await db_session.commit()

        # Retrieve and verify
        from sqlalchemy import select

        stmt = select(UserNotification).where(UserNotification.id == notification.id)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.id == notification.id
        assert retrieved.user_id == user.id
        assert retrieved.type == "info"
        assert retrieved.title == "Welcome"
        assert retrieved.message == "Welcome to GTS!"
        assert retrieved.read_at is None
        assert retrieved.created_at is not None

    @pytest.mark.asyncio
    async def test_mark_as_read(self, db_session: AsyncSession) -> None:
        """Notification can be marked as read."""
        # Create a user
        identity = UserIdentity(provider="t3k", external_id="read-user-001", username="reader")
        user = UserEntity.create_with_identity(identity=identity, email="reader@gts.dev")
        user_repo = SQLAlchemyUserRepository(db_session)
        await user_repo.save(user)
        await db_session.commit()

        # Create a notification
        notification = UserNotification(
            user_id=user.id,
            type="info",
            title="Test",
            message="Test message",
        )
        db_session.add(notification)
        await db_session.commit()

        # Mark as read
        notification.read_at = datetime.now(UTC)
        await db_session.commit()

        # Retrieve and verify
        from sqlalchemy import select

        stmt = select(UserNotification).where(UserNotification.id == notification.id)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.read_at is not None


class TestAuditLogRoundTrip:
    """Verify AuditLog entity can be saved and retrieved."""

    @pytest.mark.asyncio
    async def test_create_via_repository(self, db_session: AsyncSession) -> None:
        """Create audit log via repository - validates AuditLog ORM."""
        # Create a user
        identity = UserIdentity(provider="t3k", external_id="audit-user-001", username="auditor")
        user = UserEntity.create_with_identity(identity=identity, email="auditor@gts.dev")
        user_repo = SQLAlchemyUserRepository(db_session)
        await user_repo.save(user)
        await db_session.commit()

        # Create an audit log via repository
        audit_repo = SQLAlchemyAuditRepository(db_session)
        resource_id = uuid4()
        await audit_repo.log_event(
            event_type="created",
            entity_type="shootout",
            entity_id=resource_id,
            user_id=user.id,
            details={
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
                "request_id": "test-req-001",
                "extra_field": "extra_value",
            },
        )
        await db_session.commit()

        # Retrieve and verify
        from sqlalchemy import select

        stmt = select(AuditLog).where(AuditLog.resource_id == resource_id)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.user_id == user.id
        assert retrieved.action == "created"
        assert retrieved.resource_type == "shootout"
        assert retrieved.resource_id == resource_id
        assert retrieved.ip_address == "192.168.1.1"
        assert retrieved.user_agent == "Mozilla/5.0"
        assert retrieved.request_id == "test-req-001"
        assert retrieved.extra_data == {"extra_field": "extra_value"}
        assert retrieved.timestamp is not None

    @pytest.mark.asyncio
    async def test_system_action_without_user(self, db_session: AsyncSession) -> None:
        """Audit log supports system actions without a user."""
        audit_repo = SQLAlchemyAuditRepository(db_session)
        resource_id = uuid4()
        await audit_repo.log_event(
            event_type="system_cleanup",
            entity_type="job",
            entity_id=resource_id,
            user_id=None,  # System action
            details={"reason": "expired"},
        )
        await db_session.commit()

        # Retrieve and verify
        from sqlalchemy import select

        stmt = select(AuditLog).where(AuditLog.resource_id == resource_id)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.user_id is None
        assert retrieved.action == "system_cleanup"
        assert retrieved.extra_data == {"reason": "expired"}
