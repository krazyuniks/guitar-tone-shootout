"""Integration tests for remaining repository implementations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.domain.entities.di_track import DITrack as DITrackEntity
from core.domain.entities.job import Job as JobEntity
from core.domain.entities.shootout import Shootout as ShootoutEntity
from core.domain.entities.shootout import ShootoutChain as ShootoutChainVO
from core.domain.entities.signal_chain import SignalChain as SignalChainEntity
from core.domain.entities.signal_chain_group import SignalChainGroup as SignalChainGroupEntity
from core.domain.entities.user import User as UserEntity
from core.domain.entities.user import UserIdentity
from core.domain.value_objects.audio_checksum import AudioChecksum
from core.domain.value_objects.job_status import JobStatus, JobType
from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.repositories.audit_repository import (
    SQLAlchemyAuditRepository,
)
from webapp.adapters.persistence.repositories.di_track_repository import (
    SQLAlchemyDITrackRepository,
)
from webapp.adapters.persistence.repositories.job_repository import SQLAlchemyJobRepository
from webapp.adapters.persistence.repositories.shootout_repository import (
    SQLAlchemyShootoutRepository,
)
from webapp.adapters.persistence.repositories.signal_chain_group_repository import (
    SQLAlchemySignalChainGroupRepository,
)
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)
from webapp.adapters.persistence.repositories.user_repository import (
    SQLAlchemyUserRepository,
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Use in-memory SQLite for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Clean up
    await engine.dispose()


@pytest.fixture
async def user(
    db_session: AsyncSession,
) -> UserEntity:
    """Create a test user."""
    identity = UserIdentity(
        provider="t3k",
        external_id="ext123",
        username="testuser",
        avatar_url="https://example.com/avatar.jpg",
    )
    user = UserEntity.create_with_identity(
        identity=identity,
        email="test@example.com",
    )

    user_repo = SQLAlchemyUserRepository(db_session)
    await user_repo.save(user)
    await db_session.commit()

    return user


# DITrackRepository Tests


@pytest.mark.asyncio
async def test_di_track_save_and_get_by_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test saving and retrieving a DI track."""
    repo = SQLAlchemyDITrackRepository(db_session)

    # Create DI track
    track = DITrackEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Test Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=30.5,
        sample_rate=48000,
        description="Test description",
        guitar="Fender Strat",
        pickup="Bridge",
        checksum=AudioChecksum("a" * 64),  # Valid SHA256 checksum
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Save track
    await repo.save(track)
    await db_session.commit()

    # Retrieve track
    retrieved = await repo.get_by_id(track.id)

    # Verify
    assert retrieved is not None
    assert retrieved.id == track.id
    assert retrieved.name == track.name
    assert retrieved.file_path == track.file_path
    assert retrieved.checksum is not None
    assert retrieved.checksum.value == "a" * 64


@pytest.mark.asyncio
async def test_di_track_get_by_user_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test getting DI tracks for a user."""
    repo = SQLAlchemyDITrackRepository(db_session)

    # Create multiple tracks
    for i in range(3):
        track = DITrackEntity(
            id=uuid.uuid4(),
            user_id=user.id,
            name=f"Track {i}",
            file_path=f"/path/to/track{i}.wav",
            original_filename=f"track{i}.wav",
            duration_seconds=30.0,
            sample_rate=44100,
        )
        await repo.save(track)
    await db_session.commit()

    # Get tracks
    tracks = await repo.get_by_user_id(user.id)

    # Verify
    assert len(tracks) == 3
    assert all(t.user_id == user.id for t in tracks)


@pytest.mark.asyncio
async def test_di_track_count_by_user_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test counting DI tracks for a user."""
    repo = SQLAlchemyDITrackRepository(db_session)

    # Create tracks
    for i in range(5):
        track = DITrackEntity(
            id=uuid.uuid4(),
            user_id=user.id,
            name=f"Track {i}",
            file_path=f"/path/to/track{i}.wav",
            original_filename=f"track{i}.wav",
            duration_seconds=30.0,
            sample_rate=44100,
        )
        await repo.save(track)
    await db_session.commit()

    # Count tracks
    count = await repo.count_by_user_id(user.id)

    # Verify
    assert count == 5


# ShootoutRepository Tests


@pytest.mark.asyncio
async def test_shootout_save_and_get_by_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test saving and retrieving a shootout."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Create DI track first
    di_track_repo = SQLAlchemyDITrackRepository(db_session)
    di_track = DITrackEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Test Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=30.0,
        sample_rate=44100,
    )
    await di_track_repo.save(di_track)

    # Create signal chains
    chain_repo = SQLAlchemySignalChainRepository(db_session)
    chain1 = SignalChainEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Chain 1",
        platform=Platform.NAM,
        blocks=[],
    )
    chain2 = SignalChainEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Chain 2",
        platform=Platform.NAM,
        blocks=[],
    )
    await chain_repo.save(chain1)
    await chain_repo.save(chain2)
    await db_session.commit()

    # Create shootout
    shootout = ShootoutEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Test Shootout",
        di_track_id=di_track.id,
        description="Test description",
        is_processed=False,
    )

    # Add chains
    chain_vo1 = ShootoutChainVO(
        id=uuid.uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=chain1.id,
        position=0,
        label="Chain A",
    )
    chain_vo2 = ShootoutChainVO(
        id=uuid.uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=chain2.id,
        position=1,
        label="Chain B",
    )
    shootout.chains = [chain_vo1, chain_vo2]

    # Save shootout
    await repo.save(shootout)
    await db_session.commit()

    # Retrieve shootout
    retrieved = await repo.get_by_id(shootout.id)

    # Verify
    assert retrieved is not None
    assert retrieved.id == shootout.id
    assert retrieved.name == shootout.name
    assert len(retrieved.chains) == 2
    assert retrieved.chains[0].label == "Chain A"


@pytest.mark.asyncio
async def test_shootout_get_public(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test getting public (completed) shootouts."""
    repo = SQLAlchemyShootoutRepository(db_session)

    # Create DI track
    di_track_repo = SQLAlchemyDITrackRepository(db_session)
    di_track = DITrackEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Test Track",
        file_path="/path/to/track.wav",
        original_filename="track.wav",
        duration_seconds=30.0,
        sample_rate=44100,
    )
    await di_track_repo.save(di_track)
    await db_session.commit()

    # Create pending shootout
    pending_shootout = ShootoutEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Pending Shootout",
        di_track_id=di_track.id,
        is_processed=False,
    )
    await repo.save(pending_shootout)

    # Create completed shootout
    completed_shootout = ShootoutEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Completed Shootout",
        di_track_id=di_track.id,
        is_processed=True,
        output_path="/path/to/video.mp4",
    )
    await repo.save(completed_shootout)
    await db_session.commit()

    # Get public shootouts
    public = await repo.get_public()

    # Verify
    assert len(public) == 1
    assert public[0].id == completed_shootout.id


# JobRepository Tests


@pytest.mark.asyncio
async def test_job_save_and_get_by_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test saving and retrieving a job."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create job
    job = JobEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.PENDING,
        progress=0,
        message="Waiting to start",
        attempt=1,
        max_attempts=3,
        entity_id=uuid.uuid4(),
        task_id="task123",
    )

    # Save job
    await repo.save(job)
    await db_session.commit()

    # Retrieve job
    retrieved = await repo.get_by_id(job.id)

    # Verify
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.job_type == JobType.AUDIO_PROCESSING
    assert retrieved.status == JobStatus.PENDING


@pytest.mark.asyncio
async def test_job_get_by_task_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test getting a job by task ID."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create job
    job = JobEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.PENDING,
        task_id="task456",
    )
    await repo.save(job)
    await db_session.commit()

    # Get by task ID
    retrieved = await repo.get_by_task_id("task456")

    # Verify
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.task_id == "task456"


@pytest.mark.asyncio
async def test_job_get_active_by_user_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test getting active jobs for a user."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create jobs with different statuses
    pending_job = JobEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.PENDING,
    )
    running_job = JobEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.RUNNING,
    )
    completed_job = JobEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.COMPLETED,
    )

    await repo.save(pending_job)
    await repo.save(running_job)
    await repo.save(completed_job)
    await db_session.commit()

    # Get active jobs
    active = await repo.get_active_by_user_id(user.id)

    # Verify
    assert len(active) == 2
    assert all(j.status in [JobStatus.PENDING, JobStatus.RUNNING] for j in active)


@pytest.mark.asyncio
async def test_job_get_children(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test getting child jobs."""
    repo = SQLAlchemyJobRepository(db_session)

    # Create parent job
    parent_job = JobEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        status=JobStatus.RUNNING,
    )
    await repo.save(parent_job)

    # Create child jobs
    child1 = JobEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        parent_job_id=parent_job.id,
        status=JobStatus.PENDING,
    )
    child2 = JobEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type=JobType.AUDIO_PROCESSING,
        parent_job_id=parent_job.id,
        status=JobStatus.COMPLETED,
    )
    await repo.save(child1)
    await repo.save(child2)
    await db_session.commit()

    # Get children
    children = await repo.get_children(parent_job.id)

    # Verify
    assert len(children) == 2
    assert all(j.parent_job_id == parent_job.id for j in children)


# AuditRepository Tests


@pytest.mark.asyncio
async def test_audit_log_event(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test logging an audit event."""
    repo = SQLAlchemyAuditRepository(db_session)

    entity_id = uuid.uuid4()

    # Log event
    await repo.log_event(
        event_type="created",
        entity_type="shootout",
        entity_id=entity_id,
        user_id=user.id,
        details={"title": "Test Shootout"},
    )
    await db_session.commit()

    # Verify (check that no exception was raised)
    assert True


# SignalChainGroupRepository Tests


@pytest.mark.asyncio
async def test_signal_chain_group_save_and_get_by_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test saving and retrieving a signal chain group."""
    repo = SQLAlchemySignalChainGroupRepository(db_session)

    # Create base chain
    chain_repo = SQLAlchemySignalChainRepository(db_session)
    base_chain = SignalChainEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Base Chain",
        platform=Platform.NAM,
        blocks=[],
    )
    await chain_repo.save(base_chain)
    await db_session.commit()

    # Create group
    group = SignalChainGroupEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Test Group",
        description="Test description",
        base_chain_id=base_chain.id,
        slot_positions=[1, 3],
        gear_options={
            1: [uuid.uuid4(), uuid.uuid4()],
            3: [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()],
        },
        include_null=True,
    )

    # Save group
    await repo.save(group)
    await db_session.commit()

    # Retrieve group
    retrieved = await repo.get_by_id(group.id)

    # Verify
    assert retrieved is not None
    assert retrieved.id == group.id
    assert retrieved.name == group.name
    assert retrieved.slot_positions == [1, 3]
    assert len(retrieved.gear_options[1]) == 2
    assert len(retrieved.gear_options[3]) == 3
    assert retrieved.include_null is True


@pytest.mark.asyncio
async def test_signal_chain_group_get_by_user_id(
    db_session: AsyncSession,
    user: UserEntity,
) -> None:
    """Test getting signal chain groups for a user."""
    repo = SQLAlchemySignalChainGroupRepository(db_session)

    # Create multiple groups
    for i in range(3):
        group = SignalChainGroupEntity(
            id=uuid.uuid4(),
            user_id=user.id,
            name=f"Group {i}",
            slot_positions=[],
            gear_options={},
        )
        await repo.save(group)
    await db_session.commit()

    # Get groups
    groups = await repo.get_by_user_id(user.id)

    # Verify
    assert len(groups) == 3
    assert all(g.user_id == user.id for g in groups)
