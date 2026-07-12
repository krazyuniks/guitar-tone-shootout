"""Public shootout media resolution and security gate."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from webapp.adapters.persistence.models.shootout import (
    Shootout,
    ShootoutManifest,
    ShootoutStatus,
    ShootoutVisibility,
)
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.shootouts import router, set_session_override
from webapp.auth.dependencies import set_user_override

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    from fastapi import FastAPI

    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
async def client(app: FastAPI, db_session: AsyncSession) -> AsyncClient:
    set_session_override(db_session)
    set_user_override(None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    set_user_override(None)
    set_session_override(None)


async def _shootout_with_media(
    db_session: AsyncSession,
    owner: User,
    storage_root: Path,
    *,
    visibility: ShootoutVisibility = ShootoutVisibility.PUBLIC,
    shootout_status: ShootoutStatus = ShootoutStatus.COMPLETED,
    with_manifest: bool = True,
    media_path: str | None = None,
) -> tuple[Shootout, str]:
    shootout = Shootout(
        user_id=owner.id,
        name="Public media",
        visibility=visibility,
        status=shootout_status,
        render_version=2,
    )
    db_session.add(shootout)
    await db_session.flush()

    media_id = uuid4()
    relative_path = media_path or f"v2/{uuid4()}.wav"
    if with_manifest:
        db_session.add(
            ShootoutManifest(
                shootout_id=shootout.id,
                version=2,
                payload={
                    "chains": [
                        {
                            "segment_id": str(media_id),
                            "media_path": relative_path,
                        }
                    ]
                },
            )
        )

    if media_path is None:
        file_path = storage_root / "audio" / str(shootout.id) / relative_path
        file_path.parent.mkdir(parents=True)
        file_path.write_bytes(b"RIFF-manifest-pinned")

    await db_session.commit()
    return shootout, str(media_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_public_media_resolves_the_manifest_pinned_path(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
    shootout, media_id = await _shootout_with_media(db_session, test_user, tmp_path)

    response = await client.get(f"/api/shootouts/{shootout.id}/media/{media_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF-manifest-pinned"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    ("visibility", "shootout_status", "with_manifest"),
    [
        (ShootoutVisibility.PRIVATE, ShootoutStatus.COMPLETED, True),
        (ShootoutVisibility.PUBLIC, ShootoutStatus.PROCESSING, True),
        (ShootoutVisibility.PUBLIC, ShootoutStatus.COMPLETED, False),
    ],
)
async def test_public_media_gate_failures_are_uniform_404(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    visibility: ShootoutVisibility,
    shootout_status: ShootoutStatus,
    with_manifest: bool,
) -> None:
    monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
    shootout, media_id = await _shootout_with_media(
        db_session,
        test_user,
        tmp_path,
        visibility=visibility,
        shootout_status=shootout_status,
        with_manifest=with_manifest,
    )

    response = await client.get(f"/api/shootouts/{shootout.id}/media/{media_id}")
    missing = await client.get(f"/api/shootouts/{uuid4()}/media/{uuid4()}")

    assert response.status_code == missing.status_code == 404
    assert response.json() == missing.json() == {"detail": "Media not found"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_public_media_rejects_paths_outside_the_shootout_storage_root(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
    outside = tmp_path / "private.wav"
    outside.write_bytes(b"private")
    shootout, media_id = await _shootout_with_media(
        db_session,
        test_user,
        tmp_path,
        media_path="../../../private.wav",
    )

    response = await client.get(f"/api/shootouts/{shootout.id}/media/{media_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Media not found"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_public_montage_uses_the_manifest_version_scoped_pointer(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
    shootout, _ = await _shootout_with_media(db_session, test_user, tmp_path)
    montage_path = tmp_path / "audio" / str(shootout.id) / "v2" / "master.wav"
    montage_path.write_bytes(b"RIFF-version-two-montage")
    shootout.output_path = str(montage_path)
    await db_session.commit()
    manifest_id = (
        await db_session.execute(
            select(ShootoutManifest.id).where(
                ShootoutManifest.shootout_id == shootout.id,
                ShootoutManifest.version == 2,
            )
        )
    ).scalar_one()

    response = await client.get(f"/api/shootouts/{shootout.id}/media/montage/{manifest_id}")

    assert response.status_code == 200
    assert response.content == b"RIFF-version-two-montage"
