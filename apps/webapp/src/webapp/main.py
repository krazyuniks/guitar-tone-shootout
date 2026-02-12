"""GTS Web Application - FastAPI entrypoint."""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from webapp.api import pages
from webapp.api.v1 import (
    auth,
    di_tracks,
    gear,
    health,
    html,
    irs,
    jobs,
    library,
    notifications,
    shootouts,
    signal_chain_groups,
    signal_chains,
    test,
)
from webapp.auth.dependencies import RedirectToLogin
from webapp.dependencies import get_db, init_db
from webapp.exception_handlers import (
    app_exception_handler,
    http_exception_handler,
    request_validation_error_handler,
    sqlalchemy_error_handler,
    unhandled_exception_handler,
)
from webapp.exceptions import AppException
from webapp.middleware import RequestIDMiddleware, TimingMiddleware
from webapp.shutdown import ShutdownMiddleware, create_lifespan


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Guitar Tone Shootout",
        description="Compare guitar tones with scientific precision",
        version="0.1.0",
        lifespan=create_lifespan(),
    )

    # Initialize database (for tests, DATABASE_URL can be set externally)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        init_db(database_url)

    # Middleware order: outermost first (RequestID -> Timing -> Shutdown -> CORS)
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
    # Shutdown middleware accesses shutdown_manager from request.app.state,
    # which is set during lifespan startup. This is safe because lifespan
    # startup runs before any requests are handled.
    app.add_middleware(ShutdownMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Mount exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    # Register RuntimeError explicitly so it's handled by ExceptionMiddleware
    # (which does NOT re-raise). FastAPI routes the generic Exception handler to
    # ServerErrorMiddleware, which always re-raises after responding — this
    # breaks ASGITransport tests and wraps in ExceptionGroup with BaseHTTPMiddleware.
    app.add_exception_handler(RuntimeError, unhandled_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Include API routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router)
    app.include_router(gear.router)
    app.include_router(shootouts.router)
    app.include_router(jobs.router)
    app.include_router(html.router)
    app.include_router(library.router)
    app.include_router(signal_chains.router)
    app.include_router(signal_chain_groups.router)
    app.include_router(di_tracks.router)
    app.include_router(irs.router)
    app.include_router(notifications.router)

    # Include page routers
    app.include_router(pages.router)

    # Mount test/debug router only in development mode
    env = os.getenv("ENV", "production")
    if env == "development":
        app.include_router(test.router, tags=["test"])

    # Override database dependencies with our initialized one.
    # Only override modules that raise NotImplementedError (no fallback).
    # Modules like pages and html already fall back to get_db internally,
    # and overriding them would break test session injection via _session_override.
    if database_url:
        # Override only modules with their OWN local get_db_session.
        # Modules using webapp.auth.dependencies.get_db_session (library,
        # signal_chains, di_tracks) must NOT be overridden — the centralised
        # function already falls back to get_db and supports test overrides.
        for module in [health, gear, shootouts, jobs]:
            if hasattr(module, "get_db_session"):
                app.dependency_overrides[module.get_db_session] = get_db

    @app.exception_handler(RedirectToLogin)
    async def redirect_to_login(_request: Request, _exc: RedirectToLogin) -> RedirectResponse:
        """Redirect unauthenticated page requests to /login."""
        return RedirectResponse(url="/login", status_code=302)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint for container orchestration (legacy)."""
        return {"status": "healthy"}

    return app


# Application instance for uvicorn/gunicorn
app = create_app()
