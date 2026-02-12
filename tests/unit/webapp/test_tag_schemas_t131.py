"""Unit tests for Tag Pydantic schemas (T131)."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from webapp.api.v1.schemas.tag import TagCreateRequest, TagResponse


class TestTagCreateRequest:
    """Test TagCreateRequest schema validation."""

    def test_valid_tag_name(self) -> None:
        """Test creating a valid tag request."""
        req = TagCreateRequest(name="blues")
        assert req.name == "blues"

    def test_empty_name_rejected(self) -> None:
        """Test that empty string name is rejected."""
        with pytest.raises(ValidationError):
            TagCreateRequest(name="")

    def test_whitespace_only_name_rejected(self) -> None:
        """Test that whitespace-only name is rejected."""
        with pytest.raises(ValidationError):
            TagCreateRequest(name="   ")


class TestTagResponse:
    """Test TagResponse schema."""

    def test_response_fields(self) -> None:
        """Test TagResponse has expected fields."""
        tag_id = uuid4()
        user_id = uuid4()
        response = TagResponse(
            id=tag_id,
            name="blues",
            user_id=user_id,
            created_at="2026-01-01T00:00:00",
        )
        assert response.id == tag_id
        assert response.name == "blues"
        assert response.user_id == user_id

    def test_response_from_attributes(self) -> None:
        """Test TagResponse supports from_attributes (ORM mode)."""
        assert TagResponse.model_config.get("from_attributes") is True
