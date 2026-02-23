"""Pydantic schemas for video service API."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from gts.domain.value_objects.composition_spec import CompositionSpec


class RenderRequest(BaseModel):
    """Request schema for POST /render endpoint."""

    composition_type: str = Field(..., description="Type of composition to render")
    data: dict[str, Any] = Field(..., description="Composition-specific data")

    def to_composition_spec(self) -> CompositionSpec:
        """Convert to core domain CompositionSpec.

        Returns:
            CompositionSpec value object
        """
        return CompositionSpec(
            composition_type=self.composition_type,
            data=self.data,
        )


class RenderResponse(BaseModel):
    """Response schema for POST /render endpoint."""

    job_id: str = Field(..., description="Unique job identifier")


class StatusResponse(BaseModel):
    """Response schema for GET /render/{job_id} endpoint."""

    job_id: str = Field(..., description="Job identifier")
    status: Literal["pending", "rendering", "complete", "failed"] = Field(
        ..., description="Current job status"
    )
    output_path: str | None = Field(
        None, description="Path to rendered video (only for complete jobs)"
    )
    error_message: str | None = Field(None, description="Error message (only for failed jobs)")
    progress: float | None = Field(None, description="Render progress percentage (0.0 to 1.0)")


class HealthResponse(BaseModel):
    """Response schema for GET /health endpoint."""

    status: Literal["healthy", "unhealthy"] = Field(..., description="Service health status")
