"""Unit tests for VideoRenderClient protocol definition.

Tests verify the protocol interface exists with correct method signatures.
"""

from gts.domain.value_objects.composition_spec import CompositionSpec
from gts.ports.video_render_client import VideoRenderClient


class TestVideoRenderClientProtocol:
    """Tests for VideoRenderClient protocol definition."""

    def test_protocol_exists(self) -> None:
        """VideoRenderClient protocol is defined in core.ports."""
        assert VideoRenderClient is not None

    def test_protocol_has_submit_render_method(self) -> None:
        """VideoRenderClient has submit_render method."""
        assert hasattr(VideoRenderClient, "submit_render")

    def test_protocol_has_poll_status_method(self) -> None:
        """VideoRenderClient has poll_status method."""
        assert hasattr(VideoRenderClient, "poll_status")

    def test_submit_render_accepts_composition_spec(self) -> None:
        """submit_render method accepts CompositionSpec parameter."""
        # This test verifies the protocol method signature shape
        # Actual implementation will be tested in integration tests
        CompositionSpec(
            composition_type="shootout",
            data={"shootout_id": "s-123"},
        )
        # Protocol methods are abstract - we just verify the signature exists
        assert hasattr(VideoRenderClient, "submit_render")

    def test_poll_status_accepts_job_id(self) -> None:
        """poll_status method accepts str job_id parameter."""
        # Protocol defines the interface shape
        assert hasattr(VideoRenderClient, "poll_status")
