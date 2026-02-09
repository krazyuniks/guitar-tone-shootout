"""Unit tests for video service Pydantic schemas."""

import pytest
from pydantic import ValidationError

from core.domain.value_objects.composition_spec import CompositionSpec
from video.schemas import (
    RenderRequest,
    RenderResponse,
    StatusResponse,
    HealthResponse,
)


class TestRenderRequest:
    """Tests for RenderRequest schema."""

    def test_validates_composition_spec_fields(self) -> None:
        """RenderRequest accepts composition_type and data."""
        request = RenderRequest(
            composition_type="shootout",
            data={"shootout_id": "test-123", "gear_ids": ["g1", "g2"]},
        )
        assert request.composition_type == "shootout"
        assert request.data["shootout_id"] == "test-123"

    def test_rejects_missing_composition_type(self) -> None:
        """RenderRequest requires composition_type field."""
        with pytest.raises(ValidationError) as exc_info:
            RenderRequest(data={"test": "data"})  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("composition_type",) for e in errors)

    def test_rejects_missing_data(self) -> None:
        """RenderRequest requires data field."""
        with pytest.raises(ValidationError) as exc_info:
            RenderRequest(composition_type="shootout")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("data",) for e in errors)

    def test_converts_to_composition_spec(self) -> None:
        """RenderRequest can convert to core CompositionSpec."""
        request = RenderRequest(
            composition_type="shootout",
            data={"shootout_id": "123"},
        )
        spec = request.to_composition_spec()

        assert isinstance(spec, CompositionSpec)
        assert spec.composition_type == "shootout"
        assert spec.data == {"shootout_id": "123"}


class TestRenderResponse:
    """Tests for RenderResponse schema."""

    def test_contains_job_id(self) -> None:
        """RenderResponse returns job_id."""
        response = RenderResponse(job_id="job-abc-123")
        assert response.job_id == "job-abc-123"

    def test_rejects_missing_job_id(self) -> None:
        """RenderResponse requires job_id."""
        with pytest.raises(ValidationError) as exc_info:
            RenderResponse()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("job_id",) for e in errors)


class TestStatusResponse:
    """Tests for StatusResponse schema."""

    def test_contains_required_fields(self) -> None:
        """StatusResponse has job_id and status."""
        response = StatusResponse(job_id="job-123", status="pending")
        assert response.job_id == "job-123"
        assert response.status == "pending"

    def test_accepts_valid_status_values(self) -> None:
        """StatusResponse accepts standard RenderStatus enum values."""
        for status in ["pending", "rendering", "complete", "failed"]:
            response = StatusResponse(job_id="job-123", status=status)
            assert response.status == status

    def test_includes_optional_output_path(self) -> None:
        """StatusResponse can include output_path when complete."""
        response = StatusResponse(
            job_id="job-123",
            status="complete",
            output_path="/output/video.mp4",
        )
        assert response.output_path == "/output/video.mp4"

    def test_includes_optional_error_message(self) -> None:
        """StatusResponse can include error_message when failed."""
        response = StatusResponse(
            job_id="job-123",
            status="failed",
            error_message="Render timeout",
        )
        assert response.error_message == "Render timeout"

    def test_includes_optional_progress(self) -> None:
        """StatusResponse can include progress percentage."""
        response = StatusResponse(
            job_id="job-123",
            status="rendering",
            progress=0.45,
        )
        assert response.progress == 0.45


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_contains_healthy_status(self) -> None:
        """HealthResponse reports service health."""
        response = HealthResponse(status="healthy")
        assert response.status == "healthy"

    def test_accepts_unhealthy_status(self) -> None:
        """HealthResponse can report unhealthy state."""
        response = HealthResponse(status="unhealthy")
        assert response.status == "unhealthy"
