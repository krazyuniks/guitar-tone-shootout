"""Video renderer port definition for domain layer.

Defines the generic interface for video rendering operations using a
submit/poll pattern, decoupled from specific composition types.
"""

from typing import Protocol

from core.domain.value_objects.composition_spec import CompositionSpec
from core.domain.value_objects.render_status import RenderStatus


class VideoRenderer(Protocol):
    """Protocol for asynchronous video rendering operations.

    This port defines a generic interface for submitting video compositions
    and polling their status. Unlike the legacy VideoComposer, this interface
    is not coupled to shootout-specific operations.
    """

    async def submit(self, spec: CompositionSpec) -> str:
        """Submit a composition for rendering.

        Args:
            spec: Composition specification with type and data

        Returns:
            Job ID string for polling status

        Raises:
            SubmissionError: If submission fails
        """
        ...

    async def poll(self, job_id: str) -> RenderStatus:
        """Poll the status of a rendering job.

        Args:
            job_id: Job ID returned from submit()

        Returns:
            Current render status with optional output path or error

        Raises:
            JobNotFoundError: If job_id doesn't exist
        """
        ...
