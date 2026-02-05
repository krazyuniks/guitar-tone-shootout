"""GTS Web Application - FastAPI entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from webapp.middleware import RequestIDMiddleware, TimingMiddleware


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Guitar Tone Shootout",
        description="Compare guitar tones with scientific precision",
        version="0.1.0",
    )

    # Middleware order: outermost first (RequestID → Timing → CORS)
    # CORS must be added last so it's innermost (FastAPI reverses order)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:9000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint for container orchestration."""
        return {"status": "healthy"}

    return app


# Application instance for uvicorn/gunicorn
app = create_app()
