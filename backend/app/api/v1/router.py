"""API v1 main router.

This router aggregates all v1 API endpoints.
"""

from fastapi import APIRouter

api_router = APIRouter()

# Future routers will be included here:
# from app.api.v1 import auth, shootouts, jobs
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(shootouts.router, prefix="/shootouts", tags=["shootouts"])
# api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
