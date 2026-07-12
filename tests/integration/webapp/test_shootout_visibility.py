"""Shootout visibility and publication-gate invariants."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

from webapp.adapters.persistence.models.shootout import (
    Shootout,
    ShootoutManifest,
    ShootoutStatus,
    ShootoutVisibility,
)
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.shootout_repository import (
    SQLAlchemyShootoutRepository,
    readable_shootout_gate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _shootout(
    user_id,
    name: str,
    *,
    visibility: ShootoutVisibility = ShootoutVisibility.PUBLIC,
    status: ShootoutStatus = ShootoutStatus.COMPLETED,
) -> Shootout:
    return Shootout(
        id=uuid4(),
        user_id=user_id,
        name=name,
        visibility=visibility,
        status=status,
    )


def _manifest(shootout: Shootout) -> ShootoutManifest:
    return ShootoutManifest(
        shootout_id=shootout.id,
        version=shootout.render_version,
        payload={"chains": []},
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_public_browse_applies_visibility_status_and_manifest_gate(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    eligible = _shootout(test_user.id, "eligible")
    unlisted = _shootout(
        test_user.id,
        "unlisted",
        visibility=ShootoutVisibility.UNLISTED,
    )
    private = _shootout(
        test_user.id,
        "private",
        visibility=ShootoutVisibility.PRIVATE,
    )
    incomplete = _shootout(test_user.id, "incomplete", status=ShootoutStatus.PROCESSING)
    manifestless = _shootout(test_user.id, "manifestless")
    db_session.add_all([eligible, unlisted, private, incomplete, manifestless])
    await db_session.flush()
    db_session.add_all(
        [_manifest(eligible), _manifest(unlisted), _manifest(private), _manifest(incomplete)]
    )
    await db_session.commit()

    repository = SQLAlchemyShootoutRepository(db_session)

    assert [item.name for item in await repository.get_public()] == ["eligible"]
    assert await repository.count_public() == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_direct_link_allows_unlisted_but_hides_private_and_unpublished(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    unlisted = _shootout(
        test_user.id,
        "unlisted direct link",
        visibility=ShootoutVisibility.UNLISTED,
    )
    private = _shootout(
        test_user.id,
        "private direct link",
        visibility=ShootoutVisibility.PRIVATE,
    )
    incomplete = _shootout(test_user.id, "incomplete", status=ShootoutStatus.PROCESSING)
    manifestless = _shootout(test_user.id, "manifestless")
    db_session.add_all([unlisted, private, incomplete, manifestless])
    await db_session.flush()
    db_session.add_all([_manifest(unlisted), _manifest(private), _manifest(incomplete)])
    await db_session.commit()

    async def visible_to(viewer_id, shootout_id):
        return await db_session.scalar(
            select(Shootout).where(
                Shootout.id == shootout_id,
                readable_shootout_gate(viewer_id),
            )
        )

    assert await visible_to(None, unlisted.id) is unlisted
    assert await visible_to(None, private.id) is None
    assert await visible_to(None, incomplete.id) is None
    assert await visible_to(None, manifestless.id) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_direct_link_never_leaks_private_shootout_to_non_owner(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    private = _shootout(
        test_user.id,
        "private direct link",
        visibility=ShootoutVisibility.PRIVATE,
    )
    other_user = User(username="visibility-other", email="visibility-other@example.com")
    db_session.add_all([private, other_user])
    await db_session.flush()
    db_session.add(_manifest(private))
    await db_session.commit()

    hidden = await db_session.scalar(
        select(Shootout).where(
            Shootout.id == private.id,
            readable_shootout_gate(other_user.id),
        )
    )
    assert hidden is None
