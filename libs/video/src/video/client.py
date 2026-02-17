"""HTTP client implementation for VideoRenderClient protocol.

Provides HTTP/REST communication with the video BC worker service for
submitting render jobs and polling status.
"""

from httpx import AsyncClient, HTTPStatusError, RequestError

from core.domain.value_objects.composition_spec import CompositionSpec
from core.domain.value_objects.render_status import RenderStatus
from video.schemas_client import (
    PollStatusResponse,
    SubmitRenderRequest,
    SubmitRenderResponse,
)


class SubmissionError(Exception):
    """Raised when render job submission fails."""

    pass


class JobNotFoundError(Exception):
    """Raised when polling a non-existent job ID."""

    pass


class HttpVideoRenderClient:
    """HTTP client for video rendering service.

    Implements VideoRenderClient protocol using httpx for async HTTP requests.
    """

    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        """Initialize HTTP client.

        Args:
            base_url: Base URL of video service (e.g., "http://localhost:8002")
            timeout: Request timeout in seconds (default: 60.0)
        """
        # Normalize URL by stripping trailing slash
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def submit_render(self, spec: CompositionSpec) -> str:
        """Submit a composition for rendering via HTTP.

        Args:
            spec: Composition specification with type and data

        Returns:
            Job ID string for polling status

        Raises:
            SubmissionError: If HTTP submission fails
        """
        request = SubmitRenderRequest.from_composition_spec(spec)

        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/render",
                    json=request.model_dump(),
                )
                response.raise_for_status()

                response_data = SubmitRenderResponse.model_validate(response.json())
                return response_data.job_id

        except (HTTPStatusError, RequestError) as e:
            raise SubmissionError(f"Failed to submit render job: {e}") from e
        except Exception as e:
            raise SubmissionError(f"Unexpected error during submission: {e}") from e

    async def poll_status(self, job_id: str) -> RenderStatus:
        """Poll the status of a rendering job via HTTP.

        Args:
            job_id: Job ID returned from submit_render()

        Returns:
            Current render status with optional output path or error

        Raises:
            JobNotFoundError: If job_id doesn't exist
        """
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/render/{job_id}",
                )

                if response.status_code == 404:
                    raise JobNotFoundError(f"Job not found: {job_id}")

                response.raise_for_status()

                response_data = PollStatusResponse.model_validate(response.json())
                return response_data.to_render_status()

        except JobNotFoundError:
            raise
        except (HTTPStatusError, RequestError) as e:
            raise RuntimeError(f"Failed to poll job status: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error during status poll: {e}") from e
