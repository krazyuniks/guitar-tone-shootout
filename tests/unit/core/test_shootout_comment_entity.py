"""Unit tests for ShootoutComment domain entity."""

from uuid import uuid4

from core.domain.entities.shootout_comment import ShootoutComment


class TestShootoutCommentEntity:
    """Tests for ShootoutComment domain entity fields and behaviour."""

    def test_shootout_comment_has_required_fields(self) -> None:
        """ShootoutComment entity has id, shootout_id, user_id, content, created_at, updated_at."""
        shootout_id = uuid4()
        user_id = uuid4()

        comment = ShootoutComment(
            shootout_id=shootout_id,
            user_id=user_id,
            content="Great shootout!",
        )

        assert comment.id is not None
        assert comment.shootout_id == shootout_id
        assert comment.user_id == user_id
        assert comment.content == "Great shootout!"
        assert comment.created_at is not None
        assert comment.updated_at is not None

    def test_shootout_comment_inherits_entity(self) -> None:
        """ShootoutComment should inherit from Entity base class."""
        from core.domain.entities.base import Entity

        comment = ShootoutComment(
            shootout_id=uuid4(),
            user_id=uuid4(),
            content="Test",
        )
        assert isinstance(comment, Entity)

    def test_shootout_comment_equality_by_id(self) -> None:
        """Two ShootoutComment entities with the same ID should be equal."""
        comment_id = uuid4()
        shootout_id = uuid4()
        user_id = uuid4()

        comment1 = ShootoutComment(
            id=comment_id,
            shootout_id=shootout_id,
            user_id=user_id,
            content="First",
        )
        comment2 = ShootoutComment(
            id=comment_id,
            shootout_id=shootout_id,
            user_id=user_id,
            content="Second",
        )
        assert comment1 == comment2

    def test_shootout_comment_different_ids_not_equal(self) -> None:
        """Two ShootoutComment entities with different IDs should not be equal."""
        shootout_id = uuid4()
        user_id = uuid4()

        comment1 = ShootoutComment(
            shootout_id=shootout_id,
            user_id=user_id,
            content="Same content",
        )
        comment2 = ShootoutComment(
            shootout_id=shootout_id,
            user_id=user_id,
            content="Same content",
        )
        assert comment1 != comment2


class TestShootoutCommentExport:
    """Tests for ShootoutComment being exported from entities __init__."""

    def test_shootout_comment_exported_from_entities(self) -> None:
        """ShootoutComment should be importable from core.domain.entities."""
        from core.domain.entities import ShootoutComment as ExportedComment

        assert ExportedComment is ShootoutComment
