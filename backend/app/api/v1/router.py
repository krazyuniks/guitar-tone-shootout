"""API v1 main router.

This router aggregates all v1 API endpoints.
"""

from fastapi import APIRouter

from app.api.v1 import auth, tones

api_router = APIRouter()

# Authentication endpoints
api_router.include_router(auth.router)

# Tone 3000 integration endpoints
api_router.include_router(tones.router)

# Future routers will be included here:
# from app.api.v1 import shootouts, jobs
# api_router.include_router(shootouts.router, prefix="/shootouts", tags=["shootouts"])
# api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
