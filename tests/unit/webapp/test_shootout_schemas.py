"""Unit tests for Shootout Pydantic schemas."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from webapp.api.v1.schemas.shootout import (
    ShootoutCreateRequest,
    ShootoutResponse,
    ShootoutUpdateRequest,
)


class TestShootoutCreateRequest:
    """Tests for ShootoutCreateRequest schema."""

    def test_valid_create_request(self) -> None:
        """Test creating a valid shootout creation request."""
        data = {
            "name": "Test Shootout",
            "di_track_id": str(uuid4()),
            "description": "Test description",
        }

        request = ShootoutCreateRequest(**data)

        assert request.name == "Test Shootout"
        assert request.description == "Test description"
        assert request.di_track_id is not None

    def test_create_request_requires_name(self) -> None:
        """Test that name is required."""
        data = {
            "di_track_id": str(uuid4()),
        }

        with pytest.raises(ValidationError) as exc_info:
            ShootoutCreateRequest(**data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_create_request_requires_di_track_id(self) -> None:
        """Test that di_track_id is required."""
        data = {
            "name": "Test Shootout",
        }

        with pytest.raises(ValidationError) as exc_info:
            ShootoutCreateRequest(**data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("di_track_id",) for e in errors)

    def test_create_request_description_optional(self) -> None:
        """Test that description is optional."""
        data = {
            "name": "Test Shootout",
            "di_track_id": str(uuid4()),
        }

        request = ShootoutCreateRequest(**data)

        assert request.description is None


class TestShootoutUpdateRequest:
    """Tests for ShootoutUpdateRequest schema."""

    def test_valid_update_request(self) -> None:
        """Test creating a valid shootout update request."""
        data = {
            "name": "Updated Name",
            "description": "Updated description",
        }

        request = ShootoutUpdateRequest(**data)

        assert request.name == "Updated Name"
        assert request.description == "Updated description"

    def test_update_request_all_fields_optional(self) -> None:
        """Test that all fields are optional in update."""
        data = {}

        request = ShootoutUpdateRequest(**data)

        assert request.name is None
        assert request.description is None


class TestShootoutResponse:
    """Tests for ShootoutResponse schema."""

    def test_valid_response(self) -> None:
        """Test creating a valid shootout response."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "name": "Test Shootout",
            "di_track_id": str(uuid4()),
            "description": "Test description",
            "is_processed": False,
            "output_path": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        response = ShootoutResponse(**data)

        assert response.name == "Test Shootout"
        assert response.is_processed is False

    def test_response_requires_id(self) -> None:
        """Test that id is required."""
        data = {
            "user_id": str(uuid4()),
            "name": "Test",
            "di_track_id": str(uuid4()),
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        with pytest.raises(ValidationError) as exc_info:
            ShootoutResponse(**data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("id",) for e in errors)

    def test_response_includes_processed_status(self) -> None:
        """Test that is_processed field is included."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "name": "Test",
            "di_track_id": str(uuid4()),
            "is_processed": True,
            "output_path": "/path/to/video.mp4",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        response = ShootoutResponse(**data)

        assert response.is_processed is True
        assert response.output_path == "/path/to/video.mp4"
