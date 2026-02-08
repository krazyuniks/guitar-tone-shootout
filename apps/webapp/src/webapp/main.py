"""GTS Web Application - FastAPI entrypoint."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from webapp.api import pages
from webapp.api.v1 import (
    auth,
    di_tracks,
    gear,
    health,
    html,
    jobs,
    library,
    shootouts,
    signal_chains,
)
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

    # Middleware order: outermost first (RequestID -> Timing -> CORS)
    # CORS must be added last so it's innermost (FastAPI reverses order)
    cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:9000")
    cors_origins = [o.strip() for o in cors_origins_env.split(",")]
    # Always allow local development origins
    for dev_origin in ["http://localhost:3000", "http://localhost:9000"]:
        if dev_origin not in cors_origins:
            cors_origins.append(dev_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Include API routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router)
    app.include_router(gear.router)
    app.include_router(shootouts.router)
    app.include_router(jobs.router)
    app.include_router(html.router)
    app.include_router(library.router)
    app.include_router(signal_chains.router)
    app.include_router(di_tracks.router)

    # Include page routers
    app.include_router(pages.router)

    # Override database dependencies with our initialized one.
    # Only override modules that raise NotImplementedError (no fallback).
    # Modules like pages and html already fall back to get_db internally,
    # and overriding them would break test session injection via _session_override.
    if database_url:
        for module in [health, gear, shootouts, jobs, di_tracks]:
            if hasattr(module, "get_db_session"):
                app.dependency_overrides[module.get_db_session] = get_db

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint for container orchestration (legacy)."""
        return {"status": "healthy"}

    return app


# Application instance for uvicorn/gunicorn
app = create_app()
