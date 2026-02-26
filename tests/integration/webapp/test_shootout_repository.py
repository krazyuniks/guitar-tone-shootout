"""Integration tests for ShootoutRepository CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from gts.domain.entities.shootout import (
    Shootout,
    ShootoutChain,
)
from webapp.adapters.persistence.models.di_track import DITrack
from webapp.adapters.persistence.models.shootout import (
    Shootout as ShootoutModel,
)
from webapp.adapters.persistence.models.shootout import (
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.shootout_repository import (
    SQLAlchemyShootoutRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_di_track(db_session: AsyncSession, test_user: User) -> DITrack:
    """Create a test DI track."""
    di_track = DITrack(
        user_id=test_user.id,
        name="Test DI",
        file_path="/path/to/di.wav",
        original_filename="di.wav",
        duration_seconds=60.0,
        sample_rate=48000,
    )
    db_session.add(di_track)
    await db_session.flush()
    await db_session.refresh(di_track)
    return di_track


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
async def test_save_creates_new_shootout(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test saving a new shootout entity persists to database."""
    repo = SQLAlchemyShootoutRepository(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
        description="Test description",
    )

    await repo.save(shootout)
    await db_session.commit()

    # Verify in database
    stmt = select(ShootoutModel).where(ShootoutModel.id == shootout.id)
    result = await db_session.execute(stmt)
    db_shootout = result.scalar_one()

    assert db_shootout.title == "Test Shootout"
    assert db_shootout.user_id == test_user.id
    assert db_shootout.di_track_id == test_di_track.id
    assert db_shootout.status == ShootoutStatus.DRAFT


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_updates_existing_shootout(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test saving an existing shootout updates the record."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Create shootout
    shootout = Shootout(
        user_id=test_user.id,
        name="Original Name",
        di_track_id=test_di_track.id,
    )
    await repo.save(shootout)
    await db_session.commit()

    # Update shootout
    shootout.name = "Updated Name"
    shootout.description = "New description"
    await repo.save(shootout)
    await db_session.commit()

    # Verify update
    stmt = select(ShootoutModel).where(ShootoutModel.id == shootout.id)
    result = await db_session.execute(stmt)
    db_shootout = result.scalar_one()

    assert db_shootout.title == "Updated Name"
    assert db_shootout.description == "New description"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_persists_chains(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
    test_signal_chain: SignalChain,
) -> None:
    """Test saving a shootout with chains persists chain links."""
    repo = SQLAlchemyShootoutRepository(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
    )

    chain = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=test_signal_chain.id,
        position=0,
        label="Chain A",
    )
    shootout.add_chain(chain)

    await repo.save(shootout)
    await db_session.commit()

    # Verify chains in database
    stmt = (
        select(ShootoutModel)
        .where(ShootoutModel.id == shootout.id)
        .options(joinedload(ShootoutModel.chains))
    )
    result = await db_session.execute(stmt)
    db_shootout = result.unique().scalar_one()

    assert len(db_shootout.chains) == 1
    assert db_shootout.chains[0].signal_chain_id == test_signal_chain.id
    assert db_shootout.chains[0].label == "Chain A"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_id_returns_entity_with_chains(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
    test_signal_chain: SignalChain,
) -> None:
    """Test retrieving a shootout by ID returns complete entity."""
    repo = SQLAlchemyShootoutRepository(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
    )

    chain = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=test_signal_chain.id,
        position=0,
        label="Chain A",
    )
    shootout.add_chain(chain)

    await repo.save(shootout)
    await db_session.commit()

    # Retrieve entity
    retrieved = await repo.get_by_id(shootout.id)

    assert retrieved is not None
    assert retrieved.id == shootout.id
    assert retrieved.name == "Test Shootout"
    assert len(retrieved.chains) == 1
    assert retrieved.chains[0].label == "Chain A"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_id_returns_none_for_missing(
    db_session: AsyncSession,
) -> None:
    """Test retrieving a non-existent shootout returns None."""
    repo = SQLAlchemyShootoutRepository(db_session)

    result = await repo.get_by_id(uuid4())

    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_user_id_filters_by_owner(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test retrieving shootouts for a specific user."""
    repo = SQLAlchemyShootoutRepository(db_session)

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

    await repo.save(shootout1)
    await repo.save(shootout2)
    await db_session.commit()

    # Create another user and shootout (should not appear)
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
    await repo.save(other_shootout)
    await db_session.commit()

    # Retrieve test_user's shootouts
    results = await repo.get_by_user_id(test_user.id)

    assert len(results) == 2
    assert all(s.user_id == test_user.id for s in results)
    assert {s.name for s in results} == {"Shootout 1", "Shootout 2"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_user_id_orders_by_created_desc(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test shootouts are ordered by created_at descending."""
    repo = SQLAlchemyShootoutRepository(db_session)

    shootout1 = Shootout(
        user_id=test_user.id,
        name="First",
        di_track_id=test_di_track.id,
    )
    shootout2 = Shootout(
        user_id=test_user.id,
        name="Second",
        di_track_id=test_di_track.id,
    )

    await repo.save(shootout1)
    await db_session.flush()
    # Ensure different timestamps
    import asyncio

    await asyncio.sleep(0.01)
    await repo.save(shootout2)
    await db_session.commit()

    results = await repo.get_by_user_id(test_user.id)

    # Most recent first
    assert results[0].name == "Second"
    assert results[1].name == "First"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_count_by_user_id_returns_count(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test counting shootouts for a user."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Create three shootouts
    for i in range(3):
        shootout = Shootout(
            user_id=test_user.id,
            name=f"Shootout {i}",
            di_track_id=test_di_track.id,
        )
        await repo.save(shootout)

    await db_session.commit()

    count = await repo.count_by_user_id(test_user.id)

    assert count == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_public_filters_by_completed_status(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test get_public only returns completed shootouts."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Create pending shootout (should not appear)
    pending = Shootout(
        user_id=test_user.id,
        name="Pending",
        di_track_id=test_di_track.id,
        is_processed=False,
    )
    await repo.save(pending)

    # Create completed shootout (should appear)
    completed = Shootout(
        user_id=test_user.id,
        name="Completed",
        di_track_id=test_di_track.id,
    )
    completed.mark_processed("/path/to/video.mp4")
    await repo.save(completed)

    await db_session.commit()

    results = await repo.get_public()

    assert len(results) == 1
    assert results[0].name == "Completed"
    assert results[0].is_processed is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_count_public_counts_completed_only(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test count_public only counts completed shootouts."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Create 2 pending + 3 completed
    for i in range(2):
        pending = Shootout(
            user_id=test_user.id,
            name=f"Pending {i}",
            di_track_id=test_di_track.id,
            is_processed=False,
        )
        await repo.save(pending)

    for i in range(3):
        completed = Shootout(
            user_id=test_user.id,
            name=f"Completed {i}",
            di_track_id=test_di_track.id,
        )
        completed.mark_processed(f"/path/to/video{i}.mp4")
        await repo.save(completed)

    await db_session.commit()

    count = await repo.count_public()

    assert count == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_removes_shootout(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test deleting a shootout removes it from database."""
    repo = SQLAlchemyShootoutRepository(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="To Delete",
        di_track_id=test_di_track.id,
    )
    await repo.save(shootout)
    await db_session.commit()

    shootout_id = shootout.id

    # Delete shootout
    await repo.delete(shootout_id)
    await db_session.commit()

    # Verify deletion
    result = await repo.get_by_id(shootout_id)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_cascades_to_chains(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
    test_signal_chain: SignalChain,
) -> None:
    """Test deleting a shootout cascades to shootout_chains."""
    repo = SQLAlchemyShootoutRepository(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
    )

    chain = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=test_signal_chain.id,
        position=0,
        label="Chain A",
    )
    shootout.add_chain(chain)

    await repo.save(shootout)
    await db_session.commit()

    chain_id = shootout.chains[0].id

    # Delete shootout
    await repo.delete(shootout.id)
    await db_session.commit()

    # Verify chain was cascade deleted
    from webapp.adapters.persistence.models.shootout import ShootoutChain as ShootoutChainModel

    stmt = select(ShootoutChainModel).where(ShootoutChainModel.id == chain_id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_nonexistent_is_noop(
    db_session: AsyncSession,
) -> None:
    """Test deleting a non-existent shootout does not raise error."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Should not raise
    await repo.delete(uuid4())
    await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_removes_deleted_chains(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
    test_signal_chain: SignalChain,
) -> None:
    """Test updating a shootout removes chains that are no longer in entity."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Create shootout with chains
    shootout = Shootout(
        user_id=test_user.id,
        name="Test Shootout",
        di_track_id=test_di_track.id,
    )

    chain1 = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=test_signal_chain.id,
        position=0,
        label="Chain A",
    )
    shootout.add_chain(chain1)

    # Create second chain
    from gts.domain.value_objects.signal_chain_enums import Platform

    chain2_model = SignalChain(
        user_id=test_user.id,
        name="Chain 2",
        platform=Platform.NAM,
    )
    db_session.add(chain2_model)
    await db_session.flush()

    chain2 = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=chain2_model.id,
        position=1,
        label="Chain B",
    )
    shootout.add_chain(chain2)

    await repo.save(shootout)
    await db_session.commit()

    # Remove chain1 from entity
    shootout.remove_chain(test_signal_chain.id)

    # Save again
    await repo.save(shootout)
    await db_session.commit()

    # Verify only chain2 remains
    stmt = select(ShootoutModel).where(ShootoutModel.id == shootout.id)
    result = await db_session.execute(stmt)
    db_shootout = result.scalar_one()

    assert len(db_shootout.chains) == 1
    assert db_shootout.chains[0].signal_chain_id == chain2_model.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_entity_mapping_preserves_processed_status(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test _to_entity maps status correctly to is_processed."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Create processed shootout
    shootout = Shootout(
        user_id=test_user.id,
        name="Processed",
        di_track_id=test_di_track.id,
    )
    shootout.mark_processed("/path/to/video.mp4")

    await repo.save(shootout)
    await db_session.commit()

    # Retrieve and verify
    retrieved = await repo.get_by_id(shootout.id)

    assert retrieved is not None
    assert retrieved.is_processed is True
    assert retrieved.output_path == "/path/to/video.mp4"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_entity_mapping_sets_default_output_format(
    db_session: AsyncSession,
    test_user: User,
    test_di_track: DITrack,
) -> None:
    """Test _to_entity sets default output_format when not stored."""
    repo = SQLAlchemyShootoutRepository(db_session)

    shootout = Shootout(
        user_id=test_user.id,
        name="Test",
        di_track_id=test_di_track.id,
    )

    await repo.save(shootout)
    await db_session.commit()

    retrieved = await repo.get_by_id(shootout.id)

    assert retrieved is not None
    assert retrieved.output_format == "mp4"
    assert retrieved.sample_rate == 44100
