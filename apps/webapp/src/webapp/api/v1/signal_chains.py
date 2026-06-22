"""SignalChain API endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.entities.signal_chain import SignalChain, SignalChainBlock
from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.user_gear_repository import (
    SQLAlchemyUserGearRepository,
)
from webapp.api.v1.schemas.signal_chain import (
    BlockRequest,
    SignalChainCreateRequest,
    SignalChainResponse,
    SignalChainUpdateRequest,
)
from webapp.auth.dependencies import (
    get_current_user_required as get_current_user,
)
from webapp.auth.dependencies import (
    get_db_session,
)
from webapp.services.signal_chain_service import (
    SignalChainService,
    ValidationException,
)

router = APIRouter(prefix="/api/signal-chains", tags=["signal-chains"])


async def _gear_types_for_blocks(
    db: AsyncSession,
    user_id: UUID,
    blocks: list[BlockRequest],
) -> dict[UUID, GearType]:
    repository = SQLAlchemyUserGearRepository(db)
    requested_ids = [block.user_gear_id for block in blocks]
    gear_types = await repository.gear_types_by_user_gear_ids(user_id, requested_ids)

    if any(user_gear_id not in gear_types for user_gear_id in requested_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User gear item not found",
        )

    return gear_types


def _blocks_from_request(
    chain_id: UUID,
    request_blocks: list[BlockRequest],
    gear_types: dict[UUID, GearType],
) -> list[SignalChainBlock]:
    return [
        SignalChainBlock(
            id=uuid4(),
            signal_chain_id=chain_id,
            position=block.position,
            user_gear_id=block.user_gear_id,
            gear_type=gear_types[block.user_gear_id],
        )
        for block in request_blocks
    ]


@router.get("/", response_model=list[SignalChainResponse])
async def list_signal_chains(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SignalChainResponse]:
    """List current user's signal chains.

    Protected endpoint - requires authentication.
    Returns only the current user's signal chains.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of user's signal chains
    """
    service = SignalChainService(db)
    chains = await service.get_by_user_id(current_user.id)

    return [
        SignalChainResponse(
            id=chain.id,
            user_id=chain.user_id,
            name=chain.name,
            description=chain.description,
            platform=chain.platform.value,
            blocks=[
                {
                    "id": block.id,
                    "user_gear_id": block.user_gear_id,
                    "gear_type": block.gear_type.value,
                    "position": block.position,
                }
                for block in chain.blocks
            ],
            created_at=chain.created_at,
            updated_at=chain.updated_at,
        )
        for chain in chains
    ]


@router.post("/", response_model=SignalChainResponse, status_code=status.HTTP_201_CREATED)
async def create_signal_chain(
    request: SignalChainCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SignalChainResponse:
    """Create a new signal chain.

    Protected endpoint - requires authentication.
    Validates chain before creating.

    Args:
        request: Signal chain creation request
        db: Database session
        current_user: Currently authenticated user

    Returns:
        The created signal chain

    Raises:
        HTTPException: 422 if validation fails
    """
    # Generate ID for new chain
    chain_id = uuid4()

    gear_types = await _gear_types_for_blocks(db, current_user.id, request.blocks)
    blocks = _blocks_from_request(chain_id, request.blocks, gear_types)

    chain = SignalChain(
        id=chain_id,
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        platform=Platform(request.platform),
        blocks=blocks,
    )

    # Create via service (handles validation)
    service = SignalChainService(db)
    try:
        created = await service.create(chain)
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": e.errors},
        ) from e

    return SignalChainResponse(
        id=created.id,
        user_id=created.user_id,
        name=created.name,
        description=created.description,
        platform=created.platform.value,
        blocks=[
            {
                "id": block.id,
                "user_gear_id": block.user_gear_id,
                "gear_type": block.gear_type.value,
                "position": block.position,
            }
            for block in created.blocks
        ],
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.put("/{chain_id}", response_model=SignalChainResponse)
async def update_signal_chain(
    chain_id: UUID,
    request: SignalChainUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SignalChainResponse:
    """Update a signal chain.

    Protected endpoint - requires authentication.
    Validates ownership before updating.

    Args:
        chain_id: ID of chain to update
        request: Signal chain update request
        db: Database session
        current_user: Currently authenticated user

    Returns:
        The updated signal chain

    Raises:
        HTTPException: 404 if chain not found or not owned by user
        HTTPException: 422 if validation fails
    """
    service = SignalChainService(db)

    # Get existing chain
    existing = await service.get_by_id(chain_id)
    if not existing or existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal chain not found",
        )

    gear_types = await _gear_types_for_blocks(db, current_user.id, request.blocks)
    blocks = _blocks_from_request(chain_id, request.blocks, gear_types)

    updated_chain = SignalChain(
        id=chain_id,
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        platform=Platform(request.platform),
        blocks=blocks,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
    )

    # Update via service (handles validation)
    try:
        updated = await service.update(updated_chain)
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": e.errors},
        ) from e

    return SignalChainResponse(
        id=updated.id,
        user_id=updated.user_id,
        name=updated.name,
        description=updated.description,
        platform=updated.platform.value,
        blocks=[
            {
                "id": block.id,
                "user_gear_id": block.user_gear_id,
                "gear_type": block.gear_type.value,
                "position": block.position,
            }
            for block in updated.blocks
        ],
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_signal_chain(
    chain_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a signal chain.

    Protected endpoint - requires authentication.
    Validates ownership before deleting.

    Args:
        chain_id: ID of chain to delete
        db: Database session
        current_user: Currently authenticated user

    Raises:
        HTTPException: 404 if chain not found or not owned by user
    """
    service = SignalChainService(db)

    # Get existing chain
    existing = await service.get_by_id(chain_id)
    if not existing or existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal chain not found",
        )

    # Delete via service
    await service.delete(chain_id)
