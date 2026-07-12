"""Contract tests for the shootout artefact read projection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
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
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


FORBIDDEN_RESPONSE_FIELDS = {
    "file_path",
    "output_path",
    "result_path",
    "video_path",
    "media_path",
    "segment_id",
    "job_id",
    "video_job_id",
    "task_id",
    "error",
    "attempt",
    "retry_count",
    "video_status",
}


def _manifest_payload(shootout: Shootout, *, label: str, segment_id: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "shootout": {
            "id": str(shootout.id),
            "title": "Published comparison",
            "description": "Two amps",
            "creator": {
                "username": "tone-owner",
                "avatar_url": "https://example.test/avatar.png",
                "user_id": str(shootout.user_id),
                "email": "private@example.test",
            },
            "created_at": "2026-07-12T12:00:00+00:00",
            "output_path": "/private/master.wav",
        },
        "di": {
            "name": "Dry guitar",
            "guitar": "Telecaster",
            "pickup": "bridge",
            "tuning": "E standard",
            "duration_seconds": 2.0,
            "file_path": "/private/di.wav",
        },
        "timeline": {"aligned": "start", "duration_seconds": 2.0, "task_id": "internal"},
        "chains": [
            {
                "label": label,
                "media_path": f"v2/{uuid4()}.wav",
                "segment_id": segment_id,
                "duration_seconds": 2.0,
                "waveform": {"peaks": [0.1, 0.5], "sample_rate": 48000},
                "integrated_lufs": -14.0,
                "peak_dbfs": -1.5,
                "provenance": [
                    {
                        "position": 0,
                        "gear_type": "amp",
                        "display_name": "Clean amp",
                        "platform": "nam",
                        "icon_asset_id": str(uuid4()),
                        "parameters": {"gain": 0.5},
                    }
                ],
                "job_id": str(uuid4()),
                "error": "private failure detail",
            }
        ],
        "video_status": "ready",
    }


def _assert_no_forbidden_fields(value: Any) -> None:
    if isinstance(value, dict):
        assert FORBIDDEN_RESPONSE_FIELDS.isdisjoint(value)
        for child in value.values():
            _assert_no_forbidden_fields(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_forbidden_fields(child)


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


async def _published_shootout(
    db_session: AsyncSession,
    owner: User,
    *,
    visibility: ShootoutVisibility = ShootoutVisibility.PUBLIC,
    status: ShootoutStatus = ShootoutStatus.COMPLETED,
    with_manifest: bool = True,
) -> Shootout:
    shootout = Shootout(
        user_id=owner.id,
        name="Published comparison",
        visibility=visibility,
        status=status,
        render_version=2,
    )
    db_session.add(shootout)
    await db_session.flush()
    if with_manifest:
        db_session.add_all(
            [
                ShootoutManifest(
                    shootout_id=shootout.id,
                    version=1,
                    payload=_manifest_payload(
                        shootout, label="Old manifest", segment_id=str(uuid4())
                    ),
                ),
                ShootoutManifest(
                    shootout_id=shootout.id,
                    version=2,
                    payload=_manifest_payload(
                        shootout, label="Latest manifest", segment_id=str(uuid4())
                    ),
                ),
            ]
        )
    await db_session.commit()
    return shootout


@pytest.mark.asyncio
@pytest.mark.integration
async def test_artefact_returns_highest_manifest_allow_list_for_anonymous_reader(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    shootout = await _published_shootout(db_session, test_user)
    set_user_override(None)

    response = await client.get(f"/api/shootouts/{shootout.id}/artefact")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(shootout.id)
    assert payload["title"] == "Published comparison"
    assert payload["creator"] == {
        "username": "tone-owner",
        "avatar_url": "https://example.test/avatar.png",
    }
    assert payload["chains"][0]["label"] == "Latest manifest"
    assert payload["chains"][0]["media_url"].startswith(f"/api/shootouts/{shootout.id}/media/")
    assert ".wav" not in payload["chains"][0]["media_url"]
    assert payload["chains"][0]["provenance"] == [
        {
            "position": 0,
            "gear_type": "amp",
            "display_name": "Clean amp",
            "platform": "nam",
            "icon_asset_id": payload["chains"][0]["provenance"][0]["icon_asset_id"],
        }
    ]
    _assert_no_forbidden_fields(payload)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_artefact_exposes_only_an_opaque_montage_url(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    shootout = await _published_shootout(db_session, test_user)
    shootout.output_path = f"/app/storage/audio/{shootout.id}/v2/master.wav"
    await db_session.commit()
    manifest_id = (
        await db_session.execute(
            select(ShootoutManifest.id).where(
                ShootoutManifest.shootout_id == shootout.id,
                ShootoutManifest.version == 2,
            )
        )
    ).scalar_one()

    response = await client.get(f"/api/shootouts/{shootout.id}/artefact")

    assert response.status_code == 200
    assert response.json()["montage_url"] == (
        f"/api/shootouts/{shootout.id}/media/montage/{manifest_id}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_artefact_allows_unlisted_direct_link_and_private_owner_preview(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    unlisted = await _published_shootout(
        db_session, test_user, visibility=ShootoutVisibility.UNLISTED
    )
    private = await _published_shootout(
        db_session,
        test_user,
        visibility=ShootoutVisibility.PRIVATE,
        status=ShootoutStatus.PROCESSING,
    )
    set_user_override(None)

    assert (await client.get(f"/api/shootouts/{unlisted.id}/artefact")).status_code == 200
    assert (await client.get(f"/api/shootouts/{private.id}/artefact")).status_code == 404

    set_user_override(test_user)
    assert (await client.get(f"/api/shootouts/{private.id}/artefact")).status_code == 200


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
async def test_artefact_gate_failures_are_uniform_404(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    visibility: ShootoutVisibility,
    shootout_status: ShootoutStatus,
    with_manifest: bool,
) -> None:
    shootout = await _published_shootout(
        db_session,
        test_user,
        visibility=visibility,
        status=shootout_status,
        with_manifest=with_manifest,
    )
    set_user_override(None)

    response = await client.get(f"/api/shootouts/{shootout.id}/artefact")
    missing = await client.get(f"/api/shootouts/{uuid4()}/artefact")

    assert response.status_code == missing.status_code == 404
    assert response.json() == missing.json() == {"detail": "Shootout not found"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_artefact_private_shootout_is_hidden_from_non_owner(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    private = await _published_shootout(
        db_session, test_user, visibility=ShootoutVisibility.PRIVATE
    )
    other_user = User(username="artefact-other", email="artefact-other@example.test")
    db_session.add(other_user)
    await db_session.commit()

    set_user_override(other_user)
    response = await client.get(f"/api/shootouts/{private.id}/artefact")

    assert response.status_code == 404
    assert response.json() == {"detail": "Shootout not found"}
