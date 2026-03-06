"""Integration tests for ShootoutService CRUD and lifecycle operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from gts.domain.entities.shootout import (
    Shootout,
    ShootoutChain,
)
from webapp.adapters.persistence.models.di_track import DITrack
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.services.shootout_service import ShootoutService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_signal_chain(
    db_session: AsyncSession,
    test_user: User,
) -> SignalChain:
    """Create a test signal chain."""
    from gts.domain.value_objects.signal_chain_enums import Platform

    chain = SignalChain(
        user_id=test_user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.flush()
    await db_session.refresh(chain)
    return chain


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_shootout_persists_to_database(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test creating a shootout via service persists to database."""
    service = ShootoutService(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
        description="Test description",
    )

    async with db_session.begin():
        created = await service.create(shootout)

    # Verify created shootout has ID
    assert created.id is not None
    assert created.name == "Test Shootout"
    assert created.user_id == test_user.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_shootout_by_id_returns_entity(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test retrieving a shootout by ID returns complete entity."""
    service = ShootoutService(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
    )

    async with db_session.begin():
        await service.create(shootout)

    # Retrieve shootout
    retrieved = await service.get_by_id(shootout.id)

    assert retrieved is not None
    assert retrieved.id == shootout.id
    assert retrieved.name == "Test Shootout"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_shootout_by_id_returns_none_for_missing(
    db_session: AsyncSession,
) -> None:
    """Test retrieving a non-existent shootout returns None."""
    service = ShootoutService(db_session)

    result = await service.get_by_id(uuid4())

    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_shootouts_by_user_id_filters_by_owner(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test retrieving shootouts for a specific user."""
    service = ShootoutService(db_session)

    # Create two shootouts for test_user
    shootout1 = Shootout(
        user_id=test_user.id,
        name="Shootout 1",
        di_track_id=test_di_track.id,
    )
    shootout2 = Shootout(
        user_id=test_user.id,
        name="Shootout 2",
        di_track_id=test_di_track.id,
    )

    async with db_session.begin():
        await service.create(shootout1)
        await service.create(shootout2)

    # Create another user's shootout (should not appear)
    other_user = User(username="other", email="other@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_di_track = DITrack(
        user_id=other_user.id,
        name="Other DI",
        file_path="/path/other.wav",
        original_filename="other.wav",
        duration_seconds=60.0,
        sample_rate=48000,
    )
    db_session.add(other_di_track)
    await db_session.flush()

    other_shootout = Shootout(
        user_id=other_user.id,
        name="Other Shootout",
        di_track_id=other_di_track.id,
    )
    async with db_session.begin():
        await service.create(other_shootout)

    # Retrieve test_user's shootouts
    results = await service.get_by_user_id(test_user.id)

    assert len(results) == 2
    assert all(s.user_id == test_user.id for s in results)
    assert {s.name for s in results} == {"Shootout 1", "Shootout 2"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_shootout_persists_changes(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test updating a shootout persists changes."""
    service = ShootoutService(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Original Name",
        di_track_id=test_di_track.id,
    )

    async with db_session.begin():
        await service.create(shootout)

    # Update shootout
    shootout.name = "Updated Name"
    shootout.description = "New description"

    async with db_session.begin():
        updated = await service.update(shootout)

    # Verify update
    assert updated.name == "Updated Name"
    assert updated.description == "New description"

    # Verify persisted
    retrieved = await service.get_by_id(shootout.id)
    assert retrieved is not None
    assert retrieved.name == "Updated Name"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_shootout_removes_from_database(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test deleting a shootout removes it from database."""
    service = ShootoutService(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="To Delete",
        di_track_id=test_di_track.id,
    )

    async with db_session.begin():
        await service.create(shootout)

    shootout_id = shootout.id

    # Delete shootout
    async with db_session.begin():
        await service.delete(shootout_id)

    # Verify deletion
    result = await service.get_by_id(shootout_id)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_chain_to_shootout_persists_association(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
    test_signal_chain: SignalChain,
) -> None:
    """Test adding a chain to shootout persists the association."""
    service = ShootoutService(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
    )

    async with db_session.begin():
        await service.create(shootout)

    # Add chain
    chain_ref = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=test_signal_chain.id,
        position=0,
        label="Chain A",
    )
    shootout.add_chain(chain_ref)

    async with db_session.begin():
        await service.update(shootout)

    # Verify chain persisted
    retrieved = await service.get_by_id(shootout.id)
    assert retrieved is not None
    assert len(retrieved.chains) == 1
    assert retrieved.chains[0].signal_chain_id == test_signal_chain.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mark_processed_updates_status(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test marking shootout as processed updates status."""
    service = ShootoutService(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
    )

    async with db_session.begin():
        await service.create(shootout)

    # Mark as processed
    shootout.mark_processed("/path/to/video.mp4")

    async with db_session.begin():
        await service.update(shootout)

    # Verify processed status
    retrieved = await service.get_by_id(shootout.id)
    assert retrieved is not None
    assert retrieved.is_processed is True
    assert retrieved.output_path == "/path/to/video.mp4"
