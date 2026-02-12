"""Tag API endpoints."""

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.tag import TagCreateRequest, TagResponse
from webapp.auth.dependencies import (
    get_current_user_required as get_current_user,
)
from webapp.auth.dependencies import (
    get_db_session,
)
from webapp.services.tag_service import TagService

if TYPE_CHECKING:
    from webapp.adapters.persistence.models.tag import Tag

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


@router.get("", response_model=list[TagResponse])
async def list_tags(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> "list[Tag]":
    """List current user's tags.

    Returns all tags owned by the authenticated user.
    """
    service = TagService(db)
    tags = await service.get_by_user(user_id=current_user.id)
    return tags


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TagResponse)
async def create_tag(
    request: TagCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> "Tag":
    """Create a new tag.

    Tag names are normalized to lowercase and must be unique per user.
    Returns 201 with TagResponse on success.
    Returns 409 for duplicate tag names.
    """
    service = TagService(db)
    async with db.begin():
        tag = await service.create(user_id=current_user.id, name=request.name)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a tag.

    Ownership check is enforced: returns 404 if tag not found or not owned by user.
    """
    service = TagService(db)
    async with db.begin():
        await service.delete(tag_id=tag_id, user_id=current_user.id)
