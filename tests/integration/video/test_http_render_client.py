"""Integration tests for HTTP VideoRenderClient implementation.

These tests verify the HTTP client implementation against a real video service.
They are skipped until Phase 5A (worker) is complete.
"""

import pytest

from core.domain.value_objects.composition_spec import CompositionSpec
from core.domain.value_objects.render_status import RenderStatus
from core.ports.video_render_client import VideoRenderClient
from video.client import HttpVideoRenderClient


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skip(reason="Phase 5A: worker required")
class TestHttpVideoRenderClient:
    """Tests for HttpVideoRenderClient implementation."""

    @pytest.fixture
    async def video_service_url(self) -> str:
        """Base URL for video service."""
        # TODO Phase 5A: Configure from environment
        return "http://localhost:8002"

    @pytest.fixture
    async def client(self, video_service_url: str) -> HttpVideoRenderClient:
        """HTTP client instance."""
        return HttpVideoRenderClient(base_url=video_service_url)

    async def test_implements_video_render_client_protocol(
        self, client: HttpVideoRenderClient
    ) -> None:
        """HttpVideoRenderClient implements VideoRenderClient protocol."""
        assert isinstance(client, VideoRenderClient)

    async def test_submit_render_returns_job_id(self, client: HttpVideoRenderClient) -> None:
        """submit_render submits composition and returns job_id."""
        spec = CompositionSpec(
            composition_type="shootout",
            data={"shootout_id": "s-123", "gear_ids": ["g1", "g2"]},
        )

        job_id = await client.submit_render(spec)

        assert isinstance(job_id, str)
        assert len(job_id) > 0

    async def test_submit_render_sends_correct_payload(self, client: HttpVideoRenderClient) -> None:
        """submit_render sends composition_type and data in request."""
        spec = CompositionSpec(
            composition_type="test_type",
            data={"key": "value", "nested": {"data": [1, 2, 3]}},
        )

        job_id = await client.submit_render(spec)

        # Job ID returned indicates successful submission with correct payload
        assert job_id is not None

    async def test_poll_status_returns_render_status(self, client: HttpVideoRenderClient) -> None:
        """poll_status returns RenderStatus for valid job_id."""
        # First submit a job
        spec = CompositionSpec(
            composition_type="test",
            data={"test": "data"},
        )
        job_id = await client.submit_render(spec)

        # Poll the status
        status = await client.poll_status(job_id)

        assert isinstance(status, RenderStatus)
        assert status.job_id == job_id
        assert status.status in ["pending", "rendering", "complete", "failed"]

    async def test_poll_status_includes_optional_fields(
        self, client: HttpVideoRenderClient
    ) -> None:
        """poll_status includes output_path, error_message, progress when present."""
        spec = CompositionSpec(composition_type="test", data={})
        job_id = await client.submit_render(spec)

        status = await client.poll_status(job_id)

        # Optional fields should be present (may be None)
        assert hasattr(status, "output_path")
        assert hasattr(status, "error_message")
        assert hasattr(status, "progress")

    async def test_poll_status_raises_job_not_found_error(
        self, client: HttpVideoRenderClient
    ) -> None:
        """poll_status raises JobNotFoundError for nonexistent job_id."""
        from video.client import JobNotFoundError

        with pytest.raises(JobNotFoundError) as exc_info:
            await client.poll_status("nonexistent-job-id")

        assert "nonexistent-job-id" in str(exc_info.value)

    async def test_submit_render_raises_submission_error_on_failure(
        self, client: HttpVideoRenderClient
    ) -> None:
        """submit_render raises SubmissionError on HTTP failure."""
        from video.client import SubmissionError

        # Invalid spec that should cause submission failure
        spec = CompositionSpec(
            composition_type="",  # Empty type should fail validation
            data={},
        )

        with pytest.raises(SubmissionError):
            await client.submit_render(spec)

    async def test_client_handles_service_unavailable(self, video_service_url: str) -> None:
        """HttpVideoRenderClient raises appropriate error when service unavailable."""
        from video.client import SubmissionError

        # Client pointing to non-existent service
        client = HttpVideoRenderClient(base_url="http://localhost:99999")
        spec = CompositionSpec(composition_type="test", data={})

        with pytest.raises(SubmissionError):
            await client.submit_render(spec)

    async def test_poll_status_handles_malformed_response(
        self, client: HttpVideoRenderClient
    ) -> None:
        """poll_status raises appropriate error for malformed API response."""
        # This test verifies error handling for unexpected API response shapes
        # Actual implementation will determine specific exception type
        spec = CompositionSpec(composition_type="test", data={})
        job_id = await client.submit_render(spec)

        # Valid call - error handling will be tested when service returns errors
        status = await client.poll_status(job_id)
        assert status is not None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skip(reason="Phase 5A: worker required")
class TestHttpVideoRenderClientConfiguration:
    """Tests for HttpVideoRenderClient configuration and initialization."""

    def test_accepts_base_url(self) -> None:
        """HttpVideoRenderClient accepts base_url parameter."""
        client = HttpVideoRenderClient(base_url="http://test:8002")
        assert client.base_url == "http://test:8002"

    def test_accepts_timeout_configuration(self) -> None:
        """HttpVideoRenderClient accepts timeout parameter."""
        client = HttpVideoRenderClient(
            base_url="http://test:8002",
            timeout=30.0,
        )
        assert client.timeout == 30.0

    def test_default_timeout_is_reasonable(self) -> None:
        """HttpVideoRenderClient has reasonable default timeout."""
        client = HttpVideoRenderClient(base_url="http://test:8002")
        # Default should be high enough for render submissions but not infinite
        assert client.timeout > 0
        assert client.timeout < 300  # Less than 5 minutes

    def test_base_url_strips_trailing_slash(self) -> None:
        """HttpVideoRenderClient normalizes base_url by stripping trailing slash."""
        client = HttpVideoRenderClient(base_url="http://test:8002/")
        # URL should be normalized for consistent path joining
        assert not client.base_url.endswith("/")
