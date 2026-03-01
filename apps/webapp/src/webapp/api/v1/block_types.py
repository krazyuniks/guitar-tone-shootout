"""Block Types API endpoints."""

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.api.v1.schemas.block_type import BlockTypeResponse
from webapp.auth.dependencies import get_db_session
from webapp.services.block_type_registry import BlockTypeRegistry

if TYPE_CHECKING:
    from webapp.adapters.persistence.models.block_type import BlockType

router = APIRouter(prefix="/api/block-types", tags=["block-types"])


@router.get("", response_model=list[BlockTypeResponse])
async def list_block_types(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    response: Response,
) -> "list[BlockType]":
    """List all built-in block types.

    Returns all registered block types with their parameter definitions.
    This is a public endpoint (no authentication required) with caching enabled.
    Block types are static reference data.
    """
    # Set Cache-Control header — block types are immutable
    response.headers["Cache-Control"] = "public, max-age=3600"

    registry = BlockTypeRegistry(db)
    block_types = await registry.get_all_builtin_types()
    return block_types
