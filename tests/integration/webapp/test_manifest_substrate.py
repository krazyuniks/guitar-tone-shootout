"""Manifest table and versioned substrate properties (ADR-0004, DOM-manifest-table).

Immutability and exactly-once are database properties here, not policed
behaviour: the unique keys are the invariants the finalise and
idempotent-consume units build on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    Shootout,
    ShootoutChain,
    ShootoutManifest,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.signal_chain_enums import Platform


@pytest.fixture
async def chain_fixture(db_session: AsyncSession, test_user: User) -> ShootoutChain:
    shootout = Shootout(id=uuid4(), user_id=test_user.id, name="Substrate Shootout")
    db_session.add(shootout)
    signal_chain = SignalChain(user_id=test_user.id, name="SC", platform=Platform.NAM)
    db_session.add(signal_chain)
    await db_session.flush()
    chain = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=signal_chain.id,
        position=0,
        label="A",
    )
    db_session.add(chain)
    await db_session.flush()
    return chain


def _segment(chain_id, version: int) -> AudioSegment:
    return AudioSegment(
        shootout_chain_id=chain_id,
        file_path=f"/app/storage/audio/x/v{version}/seg.wav",
        duration_seconds=1.0,
        integrated_lufs=-14.0,
        peak_dbfs=-1.0,
        version=version,
    )


@pytest.mark.asyncio
@pytest.mark.integration
class TestVersionedSubstrate:
    async def test_duplicate_segment_version_is_rejected(
        self, db_session: AsyncSession, chain_fixture: ShootoutChain
    ) -> None:
        """The pre-fix redelivery shape - two segments for one chain+version - is now impossible."""
        db_session.add(_segment(chain_fixture.id, 1))
        await db_session.flush()
        db_session.add(_segment(chain_fixture.id, 1))
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_distinct_versions_coexist(
        self, db_session: AsyncSession, chain_fixture: ShootoutChain
    ) -> None:
        db_session.add(_segment(chain_fixture.id, 1))
        db_session.add(_segment(chain_fixture.id, 2))
        await db_session.flush()

    async def test_shootout_render_version_defaults_to_one(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        shootout = Shootout(id=uuid4(), user_id=test_user.id, name="Fresh")
        db_session.add(shootout)
        await db_session.flush()
        assert shootout.render_version == 1


@pytest.mark.asyncio
@pytest.mark.integration
class TestManifestTable:
    async def test_manifest_unique_per_shootout_version(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """(shootout_id, version) uniqueness is the finalise exactly-once backstop."""
        shootout = Shootout(id=uuid4(), user_id=test_user.id, name="Manifested")
        db_session.add(shootout)
        await db_session.flush()

        db_session.add(ShootoutManifest(shootout_id=shootout.id, version=1, payload={"chains": []}))
        await db_session.flush()
        db_session.add(ShootoutManifest(shootout_id=shootout.id, version=1, payload={"chains": []}))
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_manifest_defaults(self, db_session: AsyncSession, test_user: User) -> None:
        shootout = Shootout(id=uuid4(), user_id=test_user.id, name="Defaulted")
        db_session.add(shootout)
        await db_session.flush()

        manifest = ShootoutManifest(shootout_id=shootout.id, version=1, payload={"chains": []})
        db_session.add(manifest)
        await db_session.flush()
        await db_session.refresh(manifest)

        assert manifest.schema_version == 1
        assert manifest.created_at is not None
