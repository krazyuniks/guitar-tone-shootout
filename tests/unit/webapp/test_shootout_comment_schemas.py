"""Unit tests for ShootoutComment Pydantic schemas."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from webapp.api.v1.schemas.shootout_comment import (
    CommentCreateRequest,
    CommentResponse,
)


class TestCommentCreateRequest:
    """Tests for the CommentCreateRequest schema."""

    def test_valid_content(self) -> None:
        """CommentCreateRequest accepts valid content."""
        req = CommentCreateRequest(content="Great shootout!")
        assert req.content == "Great shootout!"

    def test_rejects_empty_content(self) -> None:
        """CommentCreateRequest rejects empty string content."""
        with pytest.raises(ValidationError):
            CommentCreateRequest(content="")

    def test_rejects_whitespace_only_content(self) -> None:
        """CommentCreateRequest rejects whitespace-only content."""
        with pytest.raises(ValidationError):
            CommentCreateRequest(content="   ")

    def test_rejects_content_over_2000_chars(self) -> None:
        """CommentCreateRequest rejects content longer than 2000 characters."""
        with pytest.raises(ValidationError):
            CommentCreateRequest(content="x" * 2001)

    def test_accepts_content_at_max_length(self) -> None:
        """CommentCreateRequest accepts content of exactly 2000 characters."""
        req = CommentCreateRequest(content="x" * 2000)
        assert len(req.content) == 2000

    def test_strips_leading_trailing_whitespace(self) -> None:
        """CommentCreateRequest strips leading/trailing whitespace from content."""
        req = CommentCreateRequest(content="  Hello world  ")
        assert req.content == "Hello world"


class TestCommentResponse:
    """Tests for the CommentResponse schema."""

    def test_serialises_all_fields(self) -> None:
        """CommentResponse includes all expected fields."""
        now = datetime.now(UTC)
        resp = CommentResponse(
            id=uuid4(),
            shootout_id=uuid4(),
            user_id=uuid4(),
            content="Test comment",
            author_username="testuser",
            author_avatar_url=None,
            created_at=now,
        )

        assert resp.content == "Test comment"
        assert resp.author_username == "testuser"
        assert resp.author_avatar_url is None
        assert resp.created_at == now

    def test_serialises_with_avatar_url(self) -> None:
        """CommentResponse includes avatar URL when present."""
        resp = CommentResponse(
            id=uuid4(),
            shootout_id=uuid4(),
            user_id=uuid4(),
            content="Test",
            author_username="testuser",
            author_avatar_url="https://example.com/avatar.png",
            created_at=datetime.now(UTC),
        )

        assert resp.author_avatar_url == "https://example.com/avatar.png"

    def test_from_attributes_mode(self) -> None:
        """CommentResponse supports from_attributes mode for ORM compatibility."""
        # Verify ConfigDict(from_attributes=True) is set
        assert CommentResponse.model_config.get("from_attributes") is True
