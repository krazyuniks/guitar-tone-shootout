"""Preset API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.preset import Preset
from webapp.adapters.persistence.models.signal_chain import SignalChain, SignalChainBlock
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.preset import (
    PresetCreateRequest,
    PresetResponse,
    PresetUpdateRequest,
)
from webapp.auth.dependencies import (
    get_current_user_required as get_current_user,
)
from webapp.auth.dependencies import (
    get_db_session,
)
from webapp.exceptions import AppException
from webapp.services.preset_processor import PresetProcessor
from webapp.services.preset_service import PresetService

router = APIRouter(prefix="/api/v1/presets", tags=["presets"])


async def _get_block_with_ownership_check(
    block_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> SignalChainBlock:
    """Get block and verify ownership through chain → user.

    Args:
        block_id: ID of the signal chain block
        user_id: ID of the current user
        db: Database session

    Returns:
        SignalChainBlock if found and owned by user

    Raises:
        HTTPException: 404 if block not found or not owned by user
    """
    stmt = (
        select(SignalChainBlock)
        .join(SignalChain, SignalChainBlock.signal_chain_id == SignalChain.id)
        .where(SignalChainBlock.id == block_id)
        .where(SignalChain.user_id == user_id)
        .options(joinedload(SignalChainBlock.signal_chain))
    )
    result = await db.execute(stmt)
    block = result.unique().scalar_one_or_none()

    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found",
        )

    return block


async def _get_preset_with_ownership_check(
    preset_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Preset:
    """Get preset and verify ownership through block → chain → user.

    Args:
        preset_id: ID of the preset
        user_id: ID of the current user
        db: Database session

    Returns:
        Preset if found and owned by user

    Raises:
        HTTPException: 404 if preset not found or not owned by user
    """
    stmt = (
        select(Preset)
        .join(SignalChainBlock, Preset.signal_chain_block_id == SignalChainBlock.id)
        .join(SignalChain, SignalChainBlock.signal_chain_id == SignalChain.id)
        .where(Preset.id == preset_id)
        .where(SignalChain.user_id == user_id)
        .options(joinedload(Preset.signal_chain_block).joinedload(SignalChainBlock.signal_chain))
    )
    result = await db.execute(stmt)
    preset = result.unique().scalar_one_or_none()

    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found",
        )

    return preset


@router.get("", response_model=list[PresetResponse])
async def list_presets(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Preset]:
    """List current user's presets.

    Returns all presets owned by the authenticated user through their
    signal chain blocks.
    """
    stmt = (
        select(Preset)
        .join(SignalChainBlock, Preset.signal_chain_block_id == SignalChainBlock.id)
        .join(SignalChain, SignalChainBlock.signal_chain_id == SignalChain.id)
        .where(SignalChain.user_id == current_user.id)
        .options(joinedload(Preset.signal_chain_block).joinedload(SignalChainBlock.signal_chain))
    )
    result = await db.execute(stmt)
    presets = list(result.unique().scalars().all())

    return [PresetResponse.from_orm_preset(preset) for preset in presets]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PresetResponse)
async def create_preset(
    request: PresetCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresetResponse:
    """Create a new preset.

    Validates that the signal chain block exists and is owned by the user.
    Validates chain parameters against block type definitions using PresetProcessor.

    Returns:
        201 with PresetResponse on success
        404 if block not found or not owned by user
        422 if chain parameters are invalid
    """
    # Verify ownership of the block
    await _get_block_with_ownership_check(
        request.signal_chain_block_id,
        current_user.id,
        db,
    )

    # Validate chain parameters using PresetProcessor
    processor = PresetProcessor(db)
    try:
        await processor.validate_params(
            request.signal_chain_block_id,
            request.chain_parameters,
        )
    except AppException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    # Create preset using service
    service = PresetService(db)
    async with db.begin():
        preset = await service.save_preset(
            signal_chain_block_id=request.signal_chain_block_id,
            name=request.name,
            description=request.description,
            params=request.chain_parameters,
        )

    return PresetResponse.from_orm_preset(preset)


@router.get("/{preset_id}", response_model=PresetResponse)
async def get_preset(
    preset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresetResponse:
    """Get preset detail.

    Returns:
        200 with preset detail
        404 if preset not found or not owned by user
    """
    preset = await _get_preset_with_ownership_check(preset_id, current_user.id, db)
    return PresetResponse.from_orm_preset(preset)


@router.put("/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: UUID,
    request: PresetUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresetResponse:
    """Update preset.

    Validates chain parameters against block type definitions using PresetProcessor.

    Returns:
        200 with updated preset
        404 if preset not found or not owned by user
        422 if chain parameters are invalid
    """
    # Verify ownership
    preset = await _get_preset_with_ownership_check(preset_id, current_user.id, db)

    # Validate chain parameters using PresetProcessor
    processor = PresetProcessor(db)
    try:
        await processor.validate_params(
            preset.signal_chain_block_id,
            request.chain_parameters,
        )
    except AppException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    # Update preset using service
    service = PresetService(db)
    async with db.begin():
        updated_preset = await service.update_preset(
            preset_id=preset_id,
            name=request.name,
            description=request.description,
            params=request.chain_parameters,
        )

    if not updated_preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found",
        )

    return PresetResponse.from_orm_preset(updated_preset)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    preset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete preset.

    Returns:
        204 on success
        404 if preset not found or not owned by user
    """
    # Verify ownership
    await _get_preset_with_ownership_check(preset_id, current_user.id, db)

    # Delete using service
    service = PresetService(db)
    async with db.begin():
        await service.delete_preset(preset_id)
