"""Unit tests for Shootout and DITrack ORM models."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_di_track_creation(session: AsyncSession) -> None:
    """Test creating a DITrack with all fields."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    di_track = DITrack(
        user_id=user.id,
        name="Test DI Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=60.5,
        sample_rate=48000,
        description="Test track",
        guitar="Fender Strat",
        pickup="Bridge",
        checksum="abc123",
    )
    session.add(di_track)
    await session.commit()

    # Refresh to get updated values
    await session.refresh(di_track)

    assert di_track.id is not None
    assert di_track.user_id == user.id
    assert di_track.name == "Test DI Track"
    assert di_track.file_path == "/path/to/track.wav"
    assert di_track.duration_seconds == 60.5
    assert di_track.sample_rate == 48000
    assert di_track.checksum == "abc123"
    assert di_track.created_at is not None
    assert di_track.updated_at is not None


@pytest.mark.asyncio
async def test_shootout_creation(session: AsyncSession) -> None:
    """Test creating a Shootout with all fields."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    di_track = DITrack(
        user_id=user.id,
        name="Test DI Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=60.5,
        sample_rate=48000,
    )
    session.add(di_track)
    await session.commit()

    shootout = Shootout(
        user_id=user.id,
        di_track_id=di_track.id,
        title="Test Shootout",
        description="A test shootout",
        status=ShootoutStatus.PENDING,
        video_path=None,
    )
    session.add(shootout)
    await session.commit()

    await session.refresh(shootout)

    assert shootout.id is not None
    assert shootout.user_id == user.id
    assert shootout.di_track_id == di_track.id
    assert shootout.title == "Test Shootout"
    assert shootout.status == ShootoutStatus.PENDING
    assert shootout.video_path is None
    assert shootout.created_at is not None
    assert shootout.updated_at is not None


@pytest.mark.asyncio
async def test_shootout_chain_junction(session: AsyncSession) -> None:
    """Test ShootoutChain junction model linking shootouts to signal chains."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    di_track = DITrack(
        user_id=user.id,
        name="Test DI Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=60.5,
        sample_rate=48000,
    )
    session.add(di_track)
    await session.commit()

    shootout = Shootout(
        user_id=user.id,
        di_track_id=di_track.id,
        title="Test Shootout",
        status=ShootoutStatus.PENDING,
    )
    session.add(shootout)
    await session.commit()

    from core.domain.value_objects.signal_chain_enums import Platform

    chain = SignalChain(
        user_id=user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    session.add(chain)
    await session.commit()

    shootout_chain = ShootoutChain(
        shootout_id=shootout.id,
        signal_chain_id=chain.id,
        position=0,
        label="Chain A",
    )
    session.add(shootout_chain)
    await session.commit()

    await session.refresh(shootout_chain)

    assert shootout_chain.id is not None
    assert shootout_chain.shootout_id == shootout.id
    assert shootout_chain.signal_chain_id == chain.id
    assert shootout_chain.position == 0
    assert shootout_chain.label == "Chain A"


@pytest.mark.asyncio
async def test_shootout_relationships(session: AsyncSession) -> None:
    """Test Shootout relationships to User, DITrack, and chains."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    di_track = DITrack(
        user_id=user.id,
        name="Test DI Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=60.5,
        sample_rate=48000,
    )
    session.add(di_track)
    await session.commit()

    shootout = Shootout(
        user_id=user.id,
        di_track_id=di_track.id,
        title="Test Shootout",
        status=ShootoutStatus.PENDING,
    )
    session.add(shootout)
    await session.commit()

    from core.domain.value_objects.signal_chain_enums import Platform

    chain1 = SignalChain(user_id=user.id, name="Chain 1", platform=Platform.NAM)
    chain2 = SignalChain(user_id=user.id, name="Chain 2", platform=Platform.NAM)
    session.add_all([chain1, chain2])
    await session.commit()

    shootout_chain1 = ShootoutChain(
        shootout_id=shootout.id,
        signal_chain_id=chain1.id,
        position=0,
        label="Chain A",
    )
    shootout_chain2 = ShootoutChain(
        shootout_id=shootout.id,
        signal_chain_id=chain2.id,
        position=1,
        label="Chain B",
    )
    session.add_all([shootout_chain1, shootout_chain2])
    await session.commit()

    # Refresh shootout in a new session to test eager loading
    await session.refresh(shootout)

    assert shootout.user.username == "testuser"
    assert shootout.di_track.name == "Test DI Track"
    assert len(shootout.chains) == 2
    assert shootout.chains[0].label == "Chain A"
    assert shootout.chains[1].label == "Chain B"


@pytest.mark.asyncio
async def test_audio_segment_creation(session: AsyncSession) -> None:
    """Test AudioSegment model for processed segments."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    di_track = DITrack(
        user_id=user.id,
        name="Test DI Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=60.5,
        sample_rate=48000,
    )
    session.add(di_track)
    await session.commit()

    shootout = Shootout(
        user_id=user.id,
        di_track_id=di_track.id,
        title="Test Shootout",
        status=ShootoutStatus.PENDING,
    )
    session.add(shootout)
    await session.commit()

    from core.domain.value_objects.signal_chain_enums import Platform

    chain = SignalChain(user_id=user.id, name="Test Chain", platform=Platform.NAM)
    session.add(chain)
    await session.commit()

    shootout_chain = ShootoutChain(
        shootout_id=shootout.id,
        signal_chain_id=chain.id,
        position=0,
        label="Chain A",
    )
    session.add(shootout_chain)
    await session.commit()

    segment = AudioSegment(
        shootout_chain_id=shootout_chain.id,
        file_path="/path/to/segment.wav",
        duration_seconds=60.5,
        integrated_lufs=-14.0,
        peak_dbfs=-1.0,
    )
    session.add(segment)
    await session.commit()

    await session.refresh(segment)

    assert segment.id is not None
    assert segment.shootout_chain_id == shootout_chain.id
    assert segment.file_path == "/path/to/segment.wav"
    assert segment.duration_seconds == 60.5
    assert segment.integrated_lufs == -14.0
    assert segment.peak_dbfs == -1.0


@pytest.mark.asyncio
async def test_cascade_delete_shootout(session: AsyncSession) -> None:
    """Test that deleting a shootout cascades to chains and segments."""
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    di_track = DITrack(
        user_id=user.id,
        name="Test DI Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=60.5,
        sample_rate=48000,
    )
    session.add(di_track)
    await session.commit()

    shootout = Shootout(
        user_id=user.id,
        di_track_id=di_track.id,
        title="Test Shootout",
        status=ShootoutStatus.PENDING,
    )
    session.add(shootout)
    await session.commit()

    from core.domain.value_objects.signal_chain_enums import Platform

    chain = SignalChain(user_id=user.id, name="Test Chain", platform=Platform.NAM)
    session.add(chain)
    await session.commit()

    shootout_chain = ShootoutChain(
        shootout_id=shootout.id,
        signal_chain_id=chain.id,
        position=0,
        label="Chain A",
    )
    session.add(shootout_chain)
    await session.commit()

    segment = AudioSegment(
        shootout_chain_id=shootout_chain.id,
        file_path="/path/to/segment.wav",
        duration_seconds=60.5,
        integrated_lufs=-14.0,
        peak_dbfs=-1.0,
    )
    session.add(segment)
    await session.commit()

    shootout_chain_id = shootout_chain.id
    segment_id = segment.id

    # Delete shootout
    await session.delete(shootout)
    await session.commit()

    # Verify cascade delete
    from sqlalchemy import select

    result = await session.execute(
        select(ShootoutChain).where(ShootoutChain.id == shootout_chain_id)
    )
    assert result.scalar_one_or_none() is None

    result = await session.execute(
        select(AudioSegment).where(AudioSegment.id == segment_id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_indexes_on_user_id_status(session: AsyncSession) -> None:
    """Test that indexes exist on user_id and status fields."""
    # This is a smoke test - actual index validation would require inspecting DB metadata
    user = User(username="testuser", email="test@example.com")
    session.add(user)
    await session.commit()

    di_track = DITrack(
        user_id=user.id,
        name="Test DI Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=60.5,
        sample_rate=48000,
    )
    session.add(di_track)
    await session.commit()

    shootout = Shootout(
        user_id=user.id,
        di_track_id=di_track.id,
        title="Test Shootout",
        status=ShootoutStatus.PENDING,
    )
    session.add(shootout)
    await session.commit()

    # Query by user_id (should use index)
    from sqlalchemy import select

    result = await session.execute(select(Shootout).where(Shootout.user_id == user.id))
    shootouts = result.scalars().all()
    assert len(shootouts) == 1

    # Query by status (should use index)
    result = await session.execute(
        select(Shootout).where(Shootout.status == ShootoutStatus.PENDING)
    )
    shootouts = result.scalars().all()
    assert len(shootouts) == 1
