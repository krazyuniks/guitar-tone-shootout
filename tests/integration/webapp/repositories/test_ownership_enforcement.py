"""Cross-user isolation tests for repository ownership enforcement.

Verifies that get_by_id methods on user-owned resource repositories enforce
ownership at the query level: a query with the wrong user_id returns None,
not another user's data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.di_track_repository import (
    SQLAlchemyDITrackRepository,
)
from webapp.adapters.persistence.repositories.job_repository import (
    SQLAlchemyJobRepository,
)
from webapp.adapters.persistence.repositories.shootout_comment_repository import (
    ShootoutCommentRepository,
)
from webapp.adapters.persistence.repositories.shootout_repository import (
    SQLAlchemyShootoutRepository,
)
from webapp.adapters.persistence.repositories.signal_chain_group_repository import (
    SQLAlchemySignalChainGroupRepository,
)
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _create_user(db_session: AsyncSession, suffix: str) -> User:
    user = User(
        id=uuid4(),
        username=f"owner_{suffix}",
        email=f"owner_{suffix}@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_get_by_id_rejects_wrong_user(db_session: AsyncSession) -> None:
    """get_by_id returns None when user_id does not match the record owner."""
    from gts.domain.entities.shootout import Shootout as ShootoutEntity
    from gts.domain.value_objects.signal_chain_enums import Platform
    from webapp.adapters.persistence.models.shootout import DITrack
    from webapp.adapters.persistence.models.signal_chain import SignalChain

    suffix = uuid4().hex[:8]
    owner = await _create_user(db_session, f"owner_{suffix}")
    other = await _create_user(db_session, f"other_{suffix}")

    di_track = DITrack(
        id=uuid4(),
        user_id=owner.id,
        name="DI Track",
        file_path="/audio/di.wav",
        original_filename="di.wav",
        duration_seconds=30.0,
        sample_rate=44100,
    )
    db_session.add(di_track)

    chain = SignalChain(id=uuid4(), user_id=owner.id, name="Chain", platform=Platform.NAM)
    db_session.add(chain)

    await db_session.flush()

    entity = ShootoutEntity(
        id=uuid4(),
        user_id=owner.id,
        name="Owned Shootout",
        di_track_id=di_track.id,
    )
    repo = SQLAlchemyShootoutRepository(db_session)
    await repo.save(entity)
    await db_session.flush()

    # Owner can fetch it
    found = await repo.get_by_id(entity.id, owner.id)
    assert found is not None
    assert found.id == entity.id

    # Different user gets None — cross-user isolation enforced at query level
    not_found = await repo.get_by_id(entity.id, other.id)
    assert not_found is None

    # Non-existent ID also returns None
    assert await repo.get_by_id(uuid4(), owner.id) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_chain_get_by_id_rejects_wrong_user(db_session: AsyncSession) -> None:
    """get_by_id returns None when user_id does not match the record owner."""
    from gts.domain.entities.signal_chain import SignalChain as SignalChainEntity
    from gts.domain.value_objects.signal_chain_enums import Platform

    suffix = uuid4().hex[:8]
    owner = await _create_user(db_session, f"owner_{suffix}")
    other = await _create_user(db_session, f"other_{suffix}")

    entity = SignalChainEntity(
        id=uuid4(),
        user_id=owner.id,
        name="Owned Chain",
        platform=Platform.NAM,
    )
    repo = SQLAlchemySignalChainRepository(db_session)
    await repo.save(entity)
    await db_session.flush()

    found = await repo.get_by_id(entity.id, owner.id)
    assert found is not None
    assert found.id == entity.id

    not_found = await repo.get_by_id(entity.id, other.id)
    assert not_found is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signal_chain_group_get_by_id_rejects_wrong_user(db_session: AsyncSession) -> None:
    """get_by_id returns None when user_id does not match the record owner."""
    from gts.domain.entities.signal_chain_group import SignalChainGroup

    suffix = uuid4().hex[:8]
    owner = await _create_user(db_session, f"owner_{suffix}")
    other = await _create_user(db_session, f"other_{suffix}")

    entity = SignalChainGroup(
        id=uuid4(),
        user_id=owner.id,
        name="Owned Group",
        slot_positions=[0, 1],
        gear_options={},
    )
    repo = SQLAlchemySignalChainGroupRepository(db_session)
    await repo.save(entity)
    await db_session.flush()

    found = await repo.get_by_id(entity.id, owner.id)
    assert found is not None
    assert found.id == entity.id

    not_found = await repo.get_by_id(entity.id, other.id)
    assert not_found is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_di_track_get_by_id_rejects_wrong_user(db_session: AsyncSession) -> None:
    """get_by_id returns None when user_id does not match the record owner."""
    from gts.domain.entities.di_track import DITrack as DITrackEntity

    suffix = uuid4().hex[:8]
    owner = await _create_user(db_session, f"owner_{suffix}")
    other = await _create_user(db_session, f"other_{suffix}")

    entity = DITrackEntity(
        id=uuid4(),
        user_id=owner.id,
        name="Owned DI Track",
        file_path="/audio/owned.wav",
        original_filename="owned.wav",
        duration_seconds=30.0,
        sample_rate=44100,
        checksum=None,
    )
    repo = SQLAlchemyDITrackRepository(db_session)
    await repo.save(entity)
    await db_session.flush()

    found = await repo.get_by_id(entity.id, owner.id)
    assert found is not None
    assert found.id == entity.id

    not_found = await repo.get_by_id(entity.id, other.id)
    assert not_found is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_job_get_by_id_rejects_wrong_user(db_session: AsyncSession) -> None:
    """get_by_id returns None when user_id does not match the record owner."""
    from gts.domain.entities.job import Job as JobEntity
    from gts.domain.value_objects.job_status import JobType

    suffix = uuid4().hex[:8]
    owner = await _create_user(db_session, f"owner_{suffix}")
    other = await _create_user(db_session, f"other_{suffix}")

    entity = JobEntity(
        id=uuid4(),
        user_id=owner.id,
        job_type=JobType.AUDIO_PROCESSING,
    )
    repo = SQLAlchemyJobRepository(db_session)
    await repo.save(entity)
    await db_session.flush()

    found = await repo.get_by_id(entity.id, owner.id)
    assert found is not None
    assert found.id == entity.id

    not_found = await repo.get_by_id(entity.id, other.id)
    assert not_found is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_shootout_comment_get_by_id_rejects_wrong_user(db_session: AsyncSession) -> None:
    """get_by_id returns None when user_id does not match the comment author."""
    from webapp.adapters.persistence.models.shootout import DITrack, Shootout
    from webapp.adapters.persistence.models.shootout_comment import ShootoutComment

    suffix = uuid4().hex[:8]
    owner = await _create_user(db_session, f"owner_{suffix}")
    other = await _create_user(db_session, f"other_{suffix}")

    di_track = DITrack(
        id=uuid4(),
        user_id=owner.id,
        name="DI",
        file_path="/audio/di.wav",
        original_filename="di.wav",
        duration_seconds=30.0,
        sample_rate=44100,
    )
    db_session.add(di_track)
    shootout = Shootout(
        id=uuid4(),
        user_id=owner.id,
        name="Shootout",
        di_track_id=di_track.id,
    )
    db_session.add(shootout)
    await db_session.flush()

    comment = ShootoutComment(
        id=uuid4(),
        shootout_id=shootout.id,
        user_id=owner.id,
        content="Owner's comment",
    )
    db_session.add(comment)
    await db_session.flush()
    comment_id = comment.id

    repo = ShootoutCommentRepository(db_session)

    found = await repo.get_by_id(comment_id, owner.id)
    assert found is not None
    assert found.id == comment_id

    not_found = await repo.get_by_id(comment_id, other.id)
    assert not_found is None
