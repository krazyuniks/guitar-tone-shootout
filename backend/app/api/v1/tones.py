"""Tone 3000 tones API endpoints.

Provides endpoints for fetching user tones, favorites, and searching
the Tone 3000 library.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.tone3000 import PaginatedResponse, Tone
from app.services.tone3000 import (
    AuthenticationExpired,
    RateLimitExceeded,
    Tone3000Client,
    Tone3000Error,
)

router = APIRouter(prefix="/tones", tags=["tones"])


@router.get("/mine", response_model=PaginatedResponse)
async def get_my_tones(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    """Get the current user's created tones from Tone 3000.

    Args:
        user: The authenticated user
        db: Database session
        page: Page number (1-indexed)
        per_page: Results per page (max 100)

    Returns:
        Paginated list of user's tones
    """
    try:
        async with Tone3000Client(user, db) as client:
            return await client.get_user_tones(page=page, per_page=per_page)
    except AuthenticationExpired as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        ) from e
    except Tone3000Error as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.get("/favorites", response_model=PaginatedResponse)
async def get_favorite_tones(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    """Get the current user's favorited tones from Tone 3000.

    Args:
        user: The authenticated user
        db: Database session
        page: Page number (1-indexed)
        per_page: Results per page (max 100)

    Returns:
        Paginated list of user's favorited tones
    """
    try:
        async with Tone3000Client(user, db) as client:
            return await client.get_favorited_tones(page=page, per_page=per_page)
    except AuthenticationExpired as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        ) from e
    except Tone3000Error as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.get("/search", response_model=PaginatedResponse)
async def search_tones(
    user: CurrentUser,
    db: DbSession,
    query: str | None = Query(default=None),
    gear: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    """Search public tones on Tone 3000.

    Args:
        user: The authenticated user
        db: Database session
        query: Search query string
        gear: Filter by gear type (amp, pedal, ir, etc.)
        platform: Filter by platform (nam, ir, aida-x)
        page: Page number (1-indexed)
        per_page: Results per page (max 100)

    Returns:
        Paginated list of matching tones
    """
    try:
        async with Tone3000Client(user, db) as client:
            return await client.search_tones(
                query=query,
                gear=gear,
                platform=platform,
                page=page,
                per_page=per_page,
            )
    except AuthenticationExpired as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        ) from e
    except Tone3000Error as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.get("/{tone_id}", response_model=Tone)
async def get_tone(
    tone_id: int,
    user: CurrentUser,
    db: DbSession,
) -> Tone:
    """Get a specific tone by ID.

    Args:
        tone_id: The tone's ID on Tone 3000
        user: The authenticated user
        db: Database session

    Returns:
        The tone details
    """
    try:
        async with Tone3000Client(user, db) as client:
            return await client.get_tone(tone_id)
    except AuthenticationExpired as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        ) from e
    except Tone3000Error as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
