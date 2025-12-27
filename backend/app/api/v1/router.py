"""API v1 main router.

This router aggregates all v1 API endpoints.
"""

from fastapi import APIRouter

from app.api.v1 import auth, files, jobs, tones, ws

api_router = APIRouter()

# Authentication endpoints
api_router.include_router(auth.router)

# Tone 3000 integration endpoints
api_router.include_router(tones.router)

# Job management endpoints
api_router.include_router(jobs.router)

# File upload endpoints
api_router.include_router(files.router)

# WebSocket endpoints
api_router.include_router(ws.router)
