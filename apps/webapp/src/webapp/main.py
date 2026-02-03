"""GTS Web Application - FastAPI entrypoint.

This module provides the FastAPI application factory and configuration.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Guitar Tone Shootout",
        description="Compare guitar tones with scientific precision",
        version="0.1.0",
    )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint for container orchestration."""
        return {"status": "healthy"}

    return app


# Application instance for uvicorn/gunicorn
app = create_app()
