"""SignalChainGroup API endpoints."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.entities.signal_chain_group import SignalChainGroup
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.signal_chain_group import (
    SignalChainGroupCreateRequest,
    SignalChainGroupResponse,
    SignalChainGroupUpdateRequest,
)
from webapp.auth.dependencies import (
    get_current_user_required,
    get_db_session,
    set_session_override,
    set_user_override,
)
from webapp.services.signal_chain_group_service import SignalChainGroupService

router = APIRouter(prefix="/api/signal-chain-groups", tags=["signal-chain-groups"])

# Re-export for test compatibility
__all__ = ["router", "set_session_override", "set_user_override"]


@router.get("/", response_model=list[SignalChainGroupResponse])
async def list_signal_chain_groups(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> list[SignalChainGroupResponse]:
    """List current user's signal chain groups.

    Protected endpoint - requires authentication.
    Returns only the current user's groups.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of user's signal chain groups
    """
    service = SignalChainGroupService(db)
    groups = await service.get_by_user_id(current_user.id)

    return [
        SignalChainGroupResponse(
            id=group.id,
            user_id=group.user_id,
            name=group.name,
            description=group.description,
            base_chain_id=group.base_chain_id,
            slot_positions=group.slot_positions,
            gear_options=group.gear_options,
            include_null=group.include_null,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
        for group in groups
    ]


@router.post("/", response_model=SignalChainGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_signal_chain_group(
    request: SignalChainGroupCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> SignalChainGroupResponse:
    """Create a new signal chain group.

    Protected endpoint - requires authentication.

    Args:
        request: Signal chain group creation request
        db: Database session
        current_user: Currently authenticated user

    Returns:
        The created signal chain group
    """
    # Create group entity
    group = SignalChainGroup(
        id=uuid4(),
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        base_chain_id=request.base_chain_id,
        slot_positions=request.slot_positions,
        gear_options=request.gear_options,
        include_null=request.include_null,
    )

    # Create via service
    service = SignalChainGroupService(db)
    async with db.begin():
        created = await service.create(group)

    return SignalChainGroupResponse(
        id=created.id,
        user_id=created.user_id,
        name=created.name,
        description=created.description,
        base_chain_id=created.base_chain_id,
        slot_positions=created.slot_positions,
        gear_options=created.gear_options,
        include_null=created.include_null,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.get("/{group_id}", response_model=SignalChainGroupResponse)
async def get_signal_chain_group(
    group_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> SignalChainGroupResponse:
    """Get a signal chain group by ID.

    Protected endpoint - requires authentication.
    Returns 404 if group not found or not owned by user.

    Args:
        group_id: Group ID to retrieve
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Signal chain group details

    Raises:
        HTTPException: 404 if group not found or not owned by user
    """
    service = SignalChainGroupService(db)
    group = await service.get_by_id(group_id)

    # Return 404 if group not found or not owned by user
    # (Return 404 instead of 403 to avoid leaking existence)
    if not group or group.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal chain group not found",
        )

    return SignalChainGroupResponse(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        base_chain_id=group.base_chain_id,
        slot_positions=group.slot_positions,
        gear_options=group.gear_options,
        include_null=group.include_null,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.put("/{group_id}", response_model=SignalChainGroupResponse)
async def update_signal_chain_group(
    group_id: UUID,
    request: SignalChainGroupUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> SignalChainGroupResponse:
    """Update a signal chain group.

    Protected endpoint - requires authentication.
    Returns 404 if group not found or not owned by user.

    Args:
        group_id: Group ID to update
        request: Update request with fields to modify
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Updated signal chain group

    Raises:
        HTTPException: 404 if group not found or not owned by user
    """
    service = SignalChainGroupService(db)
    group = await service.get_by_id(group_id)

    # Check ownership
    if not group or group.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal chain group not found",
        )

    # Apply updates
    if request.name is not None:
        group.name = request.name
    if request.description is not None:
        group.description = request.description
    if request.slot_positions is not None:
        group.slot_positions = request.slot_positions
    if request.gear_options is not None:
        group.gear_options = request.gear_options
    if request.include_null is not None:
        group.include_null = request.include_null

    # Update via service
    async with db.begin():
        updated = await service.update(group)

    return SignalChainGroupResponse(
        id=updated.id,
        user_id=updated.user_id,
        name=updated.name,
        description=updated.description,
        base_chain_id=updated.base_chain_id,
        slot_positions=updated.slot_positions,
        gear_options=updated.gear_options,
        include_null=updated.include_null,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.post("/{group_id}/generate", response_model=list[str])
async def generate_permutations(
    group_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> list[str]:
    """Generate signal chain permutations from a group.

    Protected endpoint - requires authentication.
    Returns 404 if group not found or not owned by user.
    Returns 400 if permutations exceed the maximum limit.

    Args:
        group_id: Group ID to generate permutations for
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of created chain IDs

    Raises:
        HTTPException: 404 if group not found or not owned by user
        HTTPException: 400 if too many permutations
    """
    service = SignalChainGroupService(db)
    group = await service.get_by_id(group_id)

    if not group or group.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal chain group not found",
        )

    try:
        async with db.begin():
            chain_ids = await service.generate_permutations(group_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return chain_ids


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_signal_chain_group(
    group_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> None:
    """Delete a signal chain group by ID.

    Protected endpoint - requires authentication.
    Returns 404 if group not found or not owned by user.
    """
    service = SignalChainGroupService(db)
    group = await service.get_by_id(group_id)

    if not group or group.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal chain group not found",
        )

    async with db.begin():
        await service.delete(group_id)
