"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from taskiq_fastapi import init as taskiq_init

from app.api import health
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import get_logger, setup_logging
from app.tasks import broker

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan context manager.

    Handles startup and shutdown events for the application.
    """
    # Startup
    setup_logging()
    logger.info(
        "Starting %s in %s mode",
        settings.app_name,
        "debug" if settings.debug else "production",
    )

    # Initialize TaskIQ broker (for non-worker processes)
    if not broker.is_worker_process:
        await broker.startup()
        logger.info("TaskIQ broker started")

    yield

    # Shutdown
    logger.info("Shutting down %s", settings.app_name)

    # Shutdown TaskIQ broker
    if not broker.is_worker_process:
        await broker.shutdown()
        logger.debug("TaskIQ broker shutdown")

    await engine.dispose()
    logger.debug("Database engine disposed")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Initialize TaskIQ-FastAPI integration
taskiq_init(broker, app)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoints at root level
app.include_router(health.router, tags=["health"])

# API v1 endpoints
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Guitar Tone Shootout API", "version": "0.1.0"}
