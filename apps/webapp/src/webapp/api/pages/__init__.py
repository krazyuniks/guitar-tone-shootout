"""Page route modules — combined router for all SSR page and HTMX fragment handlers."""

from fastapi import APIRouter

from webapp.api.pages import chains, di_tracks, gear, jobs, settings, shootouts, sitemap, workflow
from webapp.api.pages.context import (
    format_duration,
    gear_to_browse_context,
    gear_to_detail_context,
)
from webapp.auth.dependencies import (
    get_current_user_optional,
    get_current_user_page,
    get_db_session,
)

router = APIRouter()

router.include_router(gear.router)
router.include_router(shootouts.router)
router.include_router(chains.router)
router.include_router(di_tracks.router)
router.include_router(jobs.router)
router.include_router(settings.router)
router.include_router(sitemap.router)
router.include_router(workflow.router)

# Backward-compat re-exports used by tests for dependency overrides
# and by other modules that imported helpers from the old pages.py
_format_duration = format_duration
_gear_to_pack = gear_to_browse_context
_gear_to_detail_pack = gear_to_detail_context

__all__ = [
    "_format_duration",
    "_gear_to_detail_pack",
    "_gear_to_pack",
    "get_current_user_optional",
    "get_current_user_page",
    "get_db_session",
    "router",
]
