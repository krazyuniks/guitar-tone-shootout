"""Unit tests for VideoRenderer protocol.

Tests the generic video rendering port interface for composition submissions.
"""

from gts.domain.value_objects.composition_spec import CompositionSpec
from gts.domain.value_objects.render_status import RenderStatus
from gts.ports.video_renderer import VideoRenderer


class TestVideoRendererProtocol:
    """Test the VideoRenderer protocol interface."""

    def test_protocol_has_submit_method(self) -> None:
        """VideoRenderer protocol must define submit method."""
        assert hasattr(VideoRenderer, "submit")

    def test_protocol_has_poll_method(self) -> None:
        """VideoRenderer protocol must define poll method."""
        assert hasattr(VideoRenderer, "poll")

    def test_submit_signature_accepts_composition_spec(self) -> None:
        """submit() method signature must accept CompositionSpec."""
        # This test verifies the protocol signature at import time
        from inspect import signature

        # Get the method from the protocol
        submit_method = getattr(VideoRenderer, "submit", None)
        assert submit_method is not None

        # Check signature
        sig = signature(submit_method)
        params = list(sig.parameters.keys())

        # Should have 'self' and 'spec' parameters
        assert "spec" in params
        assert sig.parameters["spec"].annotation.__name__ == "CompositionSpec"

    def test_submit_returns_string_job_id(self) -> None:
        """submit() must return a string job_id."""
        from inspect import signature

        submit_method = getattr(VideoRenderer, "submit", None)
        sig = signature(submit_method)

        # Return type should be str
        assert sig.return_annotation is str

    def test_poll_signature_accepts_job_id(self) -> None:
        """poll() method signature must accept job_id string."""
        from inspect import signature

        poll_method = getattr(VideoRenderer, "poll", None)
        assert poll_method is not None

        sig = signature(poll_method)
        params = list(sig.parameters.keys())

        # Should have 'self' and 'job_id' parameters
        assert "job_id" in params
        assert sig.parameters["job_id"].annotation is str

    def test_poll_returns_render_status(self) -> None:
        """poll() must return RenderStatus value object."""
        from inspect import signature

        poll_method = getattr(VideoRenderer, "poll", None)
        sig = signature(poll_method)

        # Return type should be RenderStatus
        assert sig.return_annotation.__name__ == "RenderStatus"


class MockVideoRenderer:
    """Mock implementation to test protocol compliance."""

    async def submit(self, spec: CompositionSpec) -> str:
        """Submit a composition for rendering."""
        return "mock-job-id-123"

    async def poll(self, job_id: str) -> RenderStatus:
        """Poll rendering status."""
        return RenderStatus(
            job_id=job_id,
            status="pending",
        )


class TestProtocolCompliance:
    """Test that mock implementation satisfies the protocol."""

    def test_mock_satisfies_protocol(self) -> None:
        """MockVideoRenderer should satisfy VideoRenderer protocol."""
        mock = MockVideoRenderer()

        # Check protocol compliance
        assert hasattr(mock, "submit")
        assert hasattr(mock, "poll")
        assert callable(mock.submit)
        assert callable(mock.poll)

    async def test_submit_call_works(self) -> None:
        """submit() call should work with CompositionSpec."""
        mock = MockVideoRenderer()

        spec = CompositionSpec(
            composition_type="shootout",
            data={"test": "data"},
        )

        job_id = await mock.submit(spec)

        assert isinstance(job_id, str)
        assert len(job_id) > 0

    async def test_poll_call_works(self) -> None:
        """poll() call should work with job_id string."""
        mock = MockVideoRenderer()

        status = await mock.poll("test-job-id")

        assert isinstance(status, RenderStatus)
        assert status.job_id == "test-job-id"
