"""Unit tests for client-side Pydantic schemas.

Tests verify the client request/response schemas for the VideoRenderClient
HTTP implementation.
"""

import pytest
from pydantic import ValidationError

from core.domain.value_objects.composition_spec import CompositionSpec
from core.domain.value_objects.render_status import RenderStatus
from video.schemas_client import (
    PollStatusResponse,
    SubmitRenderRequest,
    SubmitRenderResponse,
)


class TestSubmitRenderRequest:
    """Tests for SubmitRenderRequest schema."""

    def test_creates_from_composition_spec(self) -> None:
        """SubmitRenderRequest can be created from CompositionSpec."""
        spec = CompositionSpec(
            composition_type="shootout",
            data={"shootout_id": "s-123", "gear_ids": ["g1", "g2"]},
        )
        request = SubmitRenderRequest.from_composition_spec(spec)

        assert request.composition_type == "shootout"
        assert request.data == {"shootout_id": "s-123", "gear_ids": ["g1", "g2"]}

    def test_validates_composition_type_required(self) -> None:
        """SubmitRenderRequest requires composition_type."""
        with pytest.raises(ValidationError) as exc_info:
            SubmitRenderRequest(data={"test": "value"})  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("composition_type",) for e in errors)

    def test_validates_data_required(self) -> None:
        """SubmitRenderRequest requires data field."""
        with pytest.raises(ValidationError) as exc_info:
            SubmitRenderRequest(composition_type="test")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("data",) for e in errors)

    def test_accepts_arbitrary_data_dict(self) -> None:
        """SubmitRenderRequest accepts any dict structure in data field."""
        request = SubmitRenderRequest(
            composition_type="custom",
            data={
                "nested": {"key": "value"},
                "list": [1, 2, 3],
                "string": "test",
            },
        )
        assert request.data["nested"]["key"] == "value"
        assert request.data["list"] == [1, 2, 3]


class TestSubmitRenderResponse:
    """Tests for SubmitRenderResponse schema."""

    def test_contains_job_id(self) -> None:
        """SubmitRenderResponse has job_id field."""
        response = SubmitRenderResponse(job_id="job-abc-123")
        assert response.job_id == "job-abc-123"

    def test_validates_job_id_required(self) -> None:
        """SubmitRenderResponse requires job_id."""
        with pytest.raises(ValidationError) as exc_info:
            SubmitRenderResponse()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("job_id",) for e in errors)

    def test_job_id_must_be_string(self) -> None:
        """SubmitRenderResponse job_id must be string type."""
        response = SubmitRenderResponse(job_id="test-123")
        assert isinstance(response.job_id, str)


class TestPollStatusResponse:
    """Tests for PollStatusResponse schema."""

    def test_contains_required_fields(self) -> None:
        """PollStatusResponse has job_id and status fields."""
        response = PollStatusResponse(job_id="job-123", status="pending")
        assert response.job_id == "job-123"
        assert response.status == "pending"

    def test_validates_job_id_required(self) -> None:
        """PollStatusResponse requires job_id."""
        with pytest.raises(ValidationError) as exc_info:
            PollStatusResponse(status="pending")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("job_id",) for e in errors)

    def test_validates_status_required(self) -> None:
        """PollStatusResponse requires status."""
        with pytest.raises(ValidationError) as exc_info:
            PollStatusResponse(job_id="job-123")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("status",) for e in errors)

    def test_accepts_valid_status_values(self) -> None:
        """PollStatusResponse accepts standard render status values."""
        for status in ["pending", "rendering", "complete", "failed"]:
            response = PollStatusResponse(job_id="job-123", status=status)
            assert response.status == status

    def test_includes_optional_output_path(self) -> None:
        """PollStatusResponse can include output_path when complete."""
        response = PollStatusResponse(
            job_id="job-123",
            status="complete",
            output_path="/output/video.mp4",
        )
        assert response.output_path == "/output/video.mp4"

    def test_includes_optional_error_message(self) -> None:
        """PollStatusResponse can include error_message when failed."""
        response = PollStatusResponse(
            job_id="job-123",
            status="failed",
            error_message="Render timeout exceeded",
        )
        assert response.error_message == "Render timeout exceeded"

    def test_includes_optional_progress(self) -> None:
        """PollStatusResponse can include progress percentage."""
        response = PollStatusResponse(
            job_id="job-123",
            status="rendering",
            progress=0.67,
        )
        assert response.progress == 0.67

    def test_converts_to_render_status(self) -> None:
        """PollStatusResponse can convert to core RenderStatus."""
        response = PollStatusResponse(
            job_id="job-123",
            status="complete",
            output_path="/output/test.mp4",
            progress=1.0,
        )
        status = response.to_render_status()

        assert isinstance(status, RenderStatus)
        assert status.job_id == "job-123"
        assert status.status == "complete"
        assert status.output_path == "/output/test.mp4"
        assert status.progress == 1.0

    def test_converts_failed_status_with_error(self) -> None:
        """PollStatusResponse converts failed status with error_message."""
        response = PollStatusResponse(
            job_id="job-123",
            status="failed",
            error_message="Render crashed",
        )
        status = response.to_render_status()

        assert status.status == "failed"
        assert status.error_message == "Render crashed"
        assert status.output_path is None
