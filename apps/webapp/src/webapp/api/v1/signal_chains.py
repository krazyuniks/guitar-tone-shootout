"""SignalChain API endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.entities.signal_chain import SignalChain, SignalChainBlock
from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.signal_chain import (
    SignalChainCreateRequest,
    SignalChainResponse,
    SignalChainUpdateRequest,
)
from webapp.services.signal_chain_service import (
    SignalChainService,
    ValidationException,
)

router = APIRouter(prefix="/api/v1/signal-chains", tags=["signal-chains"])

# Session and user overrides for testing
_session_override: AsyncSession | None = None
_user_override: User | None = None


def set_session_override(session: AsyncSession | None) -> None:
    """Override the database session for testing.

    Args:
        session: Test database session or None to clear
    """
    global _session_override
    _session_override = session


def set_user_override(user: User | None) -> None:
    """Override the current user for testing.

    Args:
        user: Test user to use as CurrentUser or None to clear
    """
    global _user_override
    _user_override = user


async def get_db_session() -> AsyncSession:
    """Get database session dependency.

    Checks for test session override first, then falls back to the
    global database session factory.
    """
    if _session_override:
        return _session_override
    raise NotImplementedError("Database session dependency not configured")


async def get_current_user() -> User:
    """Get current authenticated user dependency.

    In production this would validate session/token.
    For testing, uses override if set.
    """
    if _user_override:
        return _user_override
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


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

    # Convert request to domain entity
    blocks = [
        SignalChainBlock(
            id=uuid4(),
            signal_chain_id=chain_id,
            position=block.position,
            user_gear_id=block.user_gear_id,
            gear_type=GearType(block.gear_type),
        )
        for block in request.blocks
    ]

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

    # Convert request to domain entity
    blocks = [
        SignalChainBlock(
            id=uuid4(),
            signal_chain_id=chain_id,
            position=block.position,
            user_gear_id=block.user_gear_id,
            gear_type=GearType(block.gear_type),
        )
        for block in request.blocks
    ]

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
