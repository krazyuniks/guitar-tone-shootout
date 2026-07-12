"""Unit tests for Job Pydantic schemas."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from gts.domain.value_objects.job_status import JobType
from webapp.api.v1.schemas.job import JobResponse


class TestJobResponse:
    """Tests for JobResponse schema."""

    def test_valid_job_response(self) -> None:
        """Test creating a valid job response."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "job_type": "audio_processing",
            "status": "running",
            "progress": 50,
            "message": "Processing audio...",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        response = JobResponse(**data)

        assert response.job_type == "audio_processing"
        assert response.status == "running"
        assert response.progress == 50
        assert response.message == "Processing audio..."

    def test_response_requires_id(self) -> None:
        """Test that id is required."""
        data = {
            "user_id": str(uuid4()),
            "job_type": "audio_processing",
            "status": "pending",
            "progress": 0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        with pytest.raises(ValidationError) as exc_info:
            JobResponse(**data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("id",) for e in errors)

    def test_response_requires_status(self) -> None:
        """Test that status is required."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "job_type": "audio_processing",
            "progress": 0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        with pytest.raises(ValidationError) as exc_info:
            JobResponse(**data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("status",) for e in errors)

    def test_response_requires_job_type(self) -> None:
        """Test that job_type is required."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "status": "pending",
            "progress": 0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        with pytest.raises(ValidationError) as exc_info:
            JobResponse(**data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("job_type",) for e in errors)

    def test_response_message_optional(self) -> None:
        """Test that message is optional."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "job_type": "audio_processing",
            "status": "pending",
            "progress": 0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        response = JobResponse(**data)

        assert response.message is None

    def test_response_includes_timestamps(self) -> None:
        """Test that response includes created_at and updated_at."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "job_type": "audio_processing",
            "status": "completed",
            "progress": 100,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z",
        }

        response = JobResponse(**data)

        assert response.created_at is not None
        assert response.updated_at is not None

    def test_response_includes_operational_fields_but_excludes_internal_paths(self) -> None:
        """The owner can see errors and entity links, but not worker internals."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "job_type": "audio_processing",
            "status": "failed",
            "progress": 75,
            "error": "Processing failed",
            "parent_job_id": str(uuid4()),
            "entity_id": str(uuid4()),
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        response = JobResponse(**data)

        assert response.error == "Processing failed"
        assert response.parent_job_id is not None
        assert response.entity_id is not None
        assert "result_path" not in JobResponse.model_fields
        assert "task_id" not in JobResponse.model_fields

    @pytest.mark.parametrize(
        "job_type",
        [
            "audio_processing",
            "video_compose",
            "gear_sync",
            "model_download",
            "ir_download",
            "notification",
            "shootout",
            "shootout_audio",
            "shootout_master",
            "shootout_finalise",
            "source_sync",
        ],
    )
    def test_response_accepts_every_job_type(self, job_type: str) -> None:
        """The response schema stays aligned with the domain job type set."""
        response = JobResponse(
            id=uuid4(),
            user_id=uuid4(),
            job_type=job_type,
            status="pending",
            progress=0,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        assert response.job_type == JobType(job_type)

    def test_response_progress_must_be_integer(self) -> None:
        """Test that progress must be an integer."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "job_type": "audio_processing",
            "status": "running",
            "progress": "50",  # String instead of int
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        # Pydantic will coerce string to int, so this should work
        response = JobResponse(**data)
        assert response.progress == 50
        assert isinstance(response.progress, int)

    def test_response_validates_status_enum(self) -> None:
        """Test that status must be a valid JobStatus value."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "job_type": "audio_processing",
            "status": "invalid_status",
            "progress": 0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        with pytest.raises(ValidationError) as exc_info:
            JobResponse(**data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("status",) for e in errors)

    def test_response_validates_job_type_enum(self) -> None:
        """Test that job_type must be a valid JobType value."""
        data = {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "job_type": "invalid_type",
            "status": "pending",
            "progress": 0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        with pytest.raises(ValidationError) as exc_info:
            JobResponse(**data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("job_type",) for e in errors)
