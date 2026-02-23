"""Video render client port definition for domain layer.

Defines the client interface for submitting video composition jobs to the
video BC (bounded context) and polling their status.
"""

from typing import Protocol

from gts.domain.value_objects.composition_spec import CompositionSpec
from gts.domain.value_objects.render_status import RenderStatus


class VideoRenderClient(Protocol):
    """Protocol for HTTP client to video rendering service.

    This port defines the interface for the HTTP client that communicates
    with the video BC worker service. Unlike VideoRenderer (the generic port),
    this protocol is specific to HTTP/REST communication patterns.
    """

    async def submit_render(self, spec: CompositionSpec) -> str:
        """Submit a composition for rendering via HTTP.

        Args:
            spec: Composition specification with type and data

        Returns:
            Job ID string for polling status

        Raises:
            SubmissionError: If HTTP submission fails
        """
        ...

    async def poll_status(self, job_id: str) -> RenderStatus:
        """Poll the status of a rendering job via HTTP.

        Args:
            job_id: Job ID returned from submit_render()

        Returns:
            Current render status with optional output path or error

        Raises:
            JobNotFoundError: If job_id doesn't exist
        """
        ...
