"""FastAPI application for video rendering service."""

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException

from video.schemas import (
    HealthResponse,
    RenderRequest,
    RenderResponse,
    StatusResponse,
)


# In-memory job storage for MVP
# TODO: Replace with persistent storage (Redis, database)
_jobs: dict[str, dict[str, Any]] = {}


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="GTS Video Rendering Service",
        description="Remotion-based video composition API",
        version="1.0.0",
    )

    @app.post("/render", response_model=RenderResponse, status_code=202)
    async def render(request: RenderRequest) -> RenderResponse:
        """Submit a video render job.

        Accepts a composition specification and returns a job ID for polling.
        """
        job_id = str(uuid.uuid4())

        # Store job in memory
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "composition_type": request.composition_type,
            "data": request.data,
            "output_path": None,
            "error_message": None,
        }

        return RenderResponse(job_id=job_id)

    @app.get("/render/{job_id}", response_model=StatusResponse)
    async def get_status(job_id: str) -> StatusResponse:
        """Poll render job status.

        Returns current status, output path (if complete), and error message (if failed).
        """
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job = _jobs[job_id]
        return StatusResponse(
            job_id=job["job_id"],
            status=job["status"],
            output_path=job["output_path"],
            error_message=job["error_message"],
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Health check endpoint.

        Returns service health status. Public endpoint (no auth required).
        """
        return HealthResponse(status="healthy")

    return app
