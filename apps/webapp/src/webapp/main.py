"""GTS Web Application - FastAPI entrypoint."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from webapp.api import pages
from webapp.api.v1 import health, signal_chains
from webapp.dependencies import get_db, init_db
from webapp.middleware import RequestIDMiddleware, TimingMiddleware


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Guitar Tone Shootout",
        description="Compare guitar tones with scientific precision",
        version="0.1.0",
    )

    # Initialize database (for tests, DATABASE_URL can be set externally)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        init_db(database_url)

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

    # Include API routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(signal_chains.router)

    # Include page routers
    app.include_router(pages.router)

    # Override database dependencies with our initialized one
    if database_url:
        app.dependency_overrides[health.get_db_session] = get_db

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint for container orchestration (legacy)."""
        return {"status": "healthy"}

    return app


# Application instance for uvicorn/gunicorn
app = create_app()
