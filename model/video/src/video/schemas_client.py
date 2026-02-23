"""Client-side Pydantic schemas for VideoRenderClient HTTP implementation.

These schemas define the request/response contracts for the HTTP client
that communicates with the video BC worker service.
"""

from typing import Any

from pydantic import BaseModel, Field

from gts.domain.value_objects.composition_spec import CompositionSpec
from gts.domain.value_objects.render_status import RenderStatus


class SubmitRenderRequest(BaseModel):
    """Request schema for submitting a video composition render job.

    Maps CompositionSpec domain value object to HTTP request payload.
    """

    composition_type: str = Field(
        ...,
        description="Type of composition to render (e.g., 'shootout')",
    )
    data: dict[str, Any] = Field(
        ...,
        description="Composition-specific data payload",
    )

    @classmethod
    def from_composition_spec(cls, spec: CompositionSpec) -> "SubmitRenderRequest":
        """Create request from CompositionSpec domain value object.

        Args:
            spec: Domain composition specification

        Returns:
            HTTP request schema instance
        """
        return cls(
            composition_type=spec.composition_type,
            data=spec.data,
        )


class SubmitRenderResponse(BaseModel):
    """Response schema for render job submission.

    Contains the job ID that can be used to poll render status.
    """

    job_id: str = Field(
        ...,
        description="Unique identifier for the submitted render job",
    )


class PollStatusResponse(BaseModel):
    """Response schema for polling render job status.

    Maps HTTP response to RenderStatus domain value object.
    """

    job_id: str = Field(
        ...,
        description="Job ID being polled",
    )
    status: str = Field(
        ...,
        description="Current render status (pending, rendering, complete, failed)",
    )
    output_path: str | None = Field(
        default=None,
        description="Path to rendered output file (when complete)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error description (when failed)",
    )
    progress: float | None = Field(
        default=None,
        description="Render progress percentage (0.0 to 1.0)",
    )

    def to_render_status(self) -> RenderStatus:
        """Convert HTTP response to RenderStatus domain value object.

        Returns:
            Domain render status value object
        """
        return RenderStatus(
            job_id=self.job_id,
            status=self.status,
            output_path=self.output_path,
            error_message=self.error_message,
            progress=self.progress,
        )
