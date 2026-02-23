"""Unit tests for RenderStatus value object.

Tests the rendering status tracking for video composition jobs.
"""

from dataclasses import FrozenInstanceError

import pytest

from gts.domain.value_objects.render_status import RenderStatus, RenderStatusEnum


class TestRenderStatusEnum:
    """Test RenderStatusEnum values and transitions."""

    def test_has_pending_status(self) -> None:
        """RenderStatusEnum must have PENDING status."""
        assert RenderStatusEnum.PENDING.value == "pending"

    def test_has_rendering_status(self) -> None:
        """RenderStatusEnum must have RENDERING status."""
        assert RenderStatusEnum.RENDERING.value == "rendering"

    def test_has_complete_status(self) -> None:
        """RenderStatusEnum must have COMPLETE status."""
        assert RenderStatusEnum.COMPLETE.value == "complete"

    def test_has_failed_status(self) -> None:
        """RenderStatusEnum must have FAILED status."""
        assert RenderStatusEnum.FAILED.value == "failed"

    def test_all_required_statuses_present(self) -> None:
        """All four required statuses must be present."""
        statuses = {e.value for e in RenderStatusEnum}
        required = {"pending", "rendering", "complete", "failed"}

        assert required.issubset(statuses)

    def test_terminal_states_are_identified(self) -> None:
        """Terminal states should be COMPLETE and FAILED."""
        terminal = RenderStatusEnum.terminal_states()

        assert RenderStatusEnum.COMPLETE in terminal
        assert RenderStatusEnum.FAILED in terminal
        assert RenderStatusEnum.PENDING not in terminal
        assert RenderStatusEnum.RENDERING not in terminal

    def test_active_states_are_identified(self) -> None:
        """Active states should be PENDING and RENDERING."""
        active = RenderStatusEnum.active_states()

        assert RenderStatusEnum.PENDING in active
        assert RenderStatusEnum.RENDERING in active
        assert RenderStatusEnum.COMPLETE not in active
        assert RenderStatusEnum.FAILED not in active

    def test_is_terminal_method(self) -> None:
        """is_terminal() should correctly identify terminal states."""
        assert not RenderStatusEnum.PENDING.is_terminal()
        assert not RenderStatusEnum.RENDERING.is_terminal()
        assert RenderStatusEnum.COMPLETE.is_terminal()
        assert RenderStatusEnum.FAILED.is_terminal()

    def test_is_active_method(self) -> None:
        """is_active() should correctly identify active states."""
        assert RenderStatusEnum.PENDING.is_active()
        assert RenderStatusEnum.RENDERING.is_active()
        assert not RenderStatusEnum.COMPLETE.is_active()
        assert not RenderStatusEnum.FAILED.is_active()

    def test_valid_transition_pending_to_rendering(self) -> None:
        """PENDING can transition to RENDERING."""
        assert RenderStatusEnum.PENDING.can_transition_to(RenderStatusEnum.RENDERING)

    def test_valid_transition_rendering_to_complete(self) -> None:
        """RENDERING can transition to COMPLETE."""
        assert RenderStatusEnum.RENDERING.can_transition_to(RenderStatusEnum.COMPLETE)

    def test_valid_transition_rendering_to_failed(self) -> None:
        """RENDERING can transition to FAILED."""
        assert RenderStatusEnum.RENDERING.can_transition_to(RenderStatusEnum.FAILED)

    def test_invalid_transition_pending_to_complete(self) -> None:
        """PENDING cannot transition directly to COMPLETE."""
        assert not RenderStatusEnum.PENDING.can_transition_to(RenderStatusEnum.COMPLETE)

    def test_invalid_transition_complete_to_rendering(self) -> None:
        """COMPLETE cannot transition back to RENDERING."""
        assert not RenderStatusEnum.COMPLETE.can_transition_to(RenderStatusEnum.RENDERING)

    def test_invalid_transition_failed_to_rendering(self) -> None:
        """FAILED cannot transition to RENDERING."""
        assert not RenderStatusEnum.FAILED.can_transition_to(RenderStatusEnum.RENDERING)


class TestRenderStatusCreation:
    """Test RenderStatus value object creation."""

    def test_can_create_with_minimal_fields(self) -> None:
        """RenderStatus requires job_id and status."""
        status = RenderStatus(
            job_id="job-123",
            status="pending",
        )

        assert status.job_id == "job-123"
        assert status.status == "pending"

    def test_job_id_is_required(self) -> None:
        """job_id field must be provided."""
        with pytest.raises(TypeError, match="job_id"):
            RenderStatus(status="pending")  # type: ignore

    def test_status_is_required(self) -> None:
        """status field must be provided."""
        with pytest.raises(TypeError, match="status"):
            RenderStatus(job_id="job-123")  # type: ignore

    def test_is_frozen_dataclass(self) -> None:
        """RenderStatus must be immutable (frozen dataclass)."""
        status = RenderStatus(
            job_id="job-123",
            status="pending",
        )

        with pytest.raises(FrozenInstanceError):
            status.job_id = "other"  # type: ignore

    def test_can_create_with_optional_output_path(self) -> None:
        """RenderStatus can include optional output_path."""
        status = RenderStatus(
            job_id="job-123",
            status="complete",
            output_path="/path/to/video.mp4",
        )

        assert status.output_path == "/path/to/video.mp4"

    def test_can_create_with_optional_error_message(self) -> None:
        """RenderStatus can include optional error_message for failures."""
        status = RenderStatus(
            job_id="job-123",
            status="failed",
            error_message="Rendering crashed",
        )

        assert status.error_message == "Rendering crashed"

    def test_can_create_with_optional_progress(self) -> None:
        """RenderStatus can include optional progress percentage."""
        status = RenderStatus(
            job_id="job-123",
            status="rendering",
            progress=0.45,
        )

        assert status.progress == 0.45


class TestRenderStatusEquality:
    """Test RenderStatus equality."""

    def test_equal_statuses_are_equal(self) -> None:
        """Two RenderStatus with same values should be equal."""
        status1 = RenderStatus(job_id="job-123", status="pending")
        status2 = RenderStatus(job_id="job-123", status="pending")

        assert status1 == status2

    def test_different_job_id_not_equal(self) -> None:
        """RenderStatus with different job_id should not be equal."""
        status1 = RenderStatus(job_id="job-123", status="pending")
        status2 = RenderStatus(job_id="job-456", status="pending")

        assert status1 != status2

    def test_different_status_not_equal(self) -> None:
        """RenderStatus with different status should not be equal."""
        status1 = RenderStatus(job_id="job-123", status="pending")
        status2 = RenderStatus(job_id="job-123", status="rendering")

        assert status1 != status2


class TestRenderStatusUseCases:
    """Test RenderStatus for different use cases."""

    def test_pending_render(self) -> None:
        """RenderStatus for a newly submitted job."""
        status = RenderStatus(
            job_id="job-123",
            status="pending",
        )

        assert status.status == "pending"
        assert status.output_path is None
        assert status.error_message is None

    def test_rendering_with_progress(self) -> None:
        """RenderStatus for an in-progress job."""
        status = RenderStatus(
            job_id="job-123",
            status="rendering",
            progress=0.67,
        )

        assert status.status == "rendering"
        assert status.progress == 0.67

    def test_complete_with_output(self) -> None:
        """RenderStatus for a completed job."""
        status = RenderStatus(
            job_id="job-123",
            status="complete",
            output_path="/output/video.mp4",
        )

        assert status.status == "complete"
        assert status.output_path == "/output/video.mp4"

    def test_failed_with_error(self) -> None:
        """RenderStatus for a failed job."""
        status = RenderStatus(
            job_id="job-123",
            status="failed",
            error_message="Codec not supported",
        )

        assert status.status == "failed"
        assert status.error_message == "Codec not supported"
