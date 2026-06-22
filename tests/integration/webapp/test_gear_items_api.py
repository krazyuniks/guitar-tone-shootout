"""Integration tests for the gear items API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.gear_source import GearSource
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.main import app

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession

    from webapp.adapters.persistence.models.gear import Gear
    from webapp.adapters.persistence.models.gear_model import GearModel
    from webapp.adapters.persistence.models.user import User


@dataclass(frozen=True, slots=True)
class SeededGearItem:
    user_gear: UserGear
    gear: Gear
    model: GearModel
    tag_name: str
    tag_id: str


async def _make_source(
    db_session: AsyncSession,
    *,
    source_name: str,
    source_record_id: str,
) -> GearSource:
    source = GearSource(
        id=uuid4(),
        source_name=source_name,
        source_record_id=source_record_id,
        source_updated_at=datetime.now(UTC),
    )
    db_session.add(source)
    await db_session.flush()
    return source


async def _save_user_gear(
    db_session: AsyncSession,
    user: User,
    gear: Gear,
    *,
    model_index: int = 0,
    nickname: str | None = None,
    is_favourite: bool = False,
) -> SeededGearItem:
    await db_session.refresh(gear, ["models", "tags"])
    model = gear.models[model_index]
    user_gear = UserGear(
        id=uuid4(),
        user_id=user.id,
        gear_model_id=model.id,
        nickname=nickname,
        is_favourite=is_favourite,
    )
    db_session.add(user_gear)
    await db_session.flush()
    await db_session.refresh(user_gear)
    return SeededGearItem(
        user_gear=user_gear,
        gear=gear,
        model=model,
        tag_name=gear.tags[0].name,
        tag_id=str(gear.tags[0].id),
    )


async def _seed_library(
    db_session: AsyncSession,
    make_gear: Callable[..., Coroutine[Any, Any, Gear]],
    make_user: Callable[..., Coroutine[Any, Any, User]],
    test_user: User,
) -> dict[str, SeededGearItem]:
    marker = uuid4().hex[:8]
    numeric_source = await _make_source(
        db_session,
        source_name="t3k",
        source_record_id="123456",
    )
    non_t3k_source = await _make_source(
        db_session,
        source_name="user_upload",
        source_record_id="999999",
    )

    amp = await make_gear(
        GearType.AMP,
        Platform.NAM,
        models=2,
        name=f"{marker} Studio Amp",
        slug=f"{marker}-studio-amp",
        source_id=numeric_source.id,
    )
    pedal = await make_gear(
        GearType.PEDAL,
        Platform.NAM,
        models=1,
        name=f"{marker} Drive Pedal",
        slug=f"{marker}-drive-pedal",
    )
    ir = await make_gear(
        GearType.IR,
        Platform.IR,
        models=1,
        name=f"{marker} Cabinet IR",
        slug=f"{marker}-cabinet-ir",
        source_id=non_t3k_source.id,
    )

    other_user = await make_user()
    other_gear = await make_gear(
        GearType.FULL_RIG,
        Platform.NAM,
        models=1,
        name=f"{marker} Other Rig",
        slug=f"{marker}-other-rig",
    )

    seeded = {
        "numeric": await _save_user_gear(
            db_session,
            test_user,
            amp,
            nickname="Studio Favourite",
            is_favourite=True,
        ),
        "nonnumeric": await _save_user_gear(db_session, test_user, pedal),
        "non_t3k": await _save_user_gear(db_session, test_user, ir),
        "other": await _save_user_gear(db_session, other_user, other_gear),
    }
    await db_session.flush()
    return seeded


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearItemsApi:
    async def test_authenticated_request_returns_user_gear_projection(
        self,
        db_session: AsyncSession,
        make_gear: Callable[..., Coroutine[Any, Any, Gear]],
        make_user: Callable[..., Coroutine[Any, Any, User]],
        test_user: User,
    ) -> None:
        seeded = await _seed_library(db_session, make_gear, make_user, test_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/gear-items")

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"gear_items", "total", "page", "page_size"}
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 100

        items_by_id = {item["id"]: item for item in body["gear_items"]}
        assert set(items_by_id) == {
            str(seeded["numeric"].user_gear.id),
            str(seeded["nonnumeric"].user_gear.id),
            str(seeded["non_t3k"].user_gear.id),
        }
        assert str(seeded["other"].user_gear.id) not in items_by_id

        numeric = items_by_id[str(seeded["numeric"].user_gear.id)]
        assert numeric["gear_type"] == "amp"
        assert numeric["model_id"] == str(seeded["numeric"].model.id)
        assert numeric["display_name"] == "Studio Favourite"
        assert numeric["is_favorite"] is True
        assert numeric["tone3000_tone_id"] == 123456
        assert numeric["tone3000_model_id"] is None
        assert numeric["pack_title"] == seeded["numeric"].gear.name
        # model_name has no current-model counterpart (GearModel has no name); honest null,
        # consistent with tone3000_model_id.
        assert numeric["model_name"] is None
        assert numeric["model_size"] == seeded["numeric"].model.size.value
        assert numeric["pack_models_count"] == 2
        assert numeric["created_at"] is not None
        # Tag id is the real GearTag UUID, not a positional index.
        assert numeric["tags"] == [
            {"id": seeded["numeric"].tag_id, "name": seeded["numeric"].tag_name, "category": None}
        ]

        nonnumeric = items_by_id[str(seeded["nonnumeric"].user_gear.id)]
        assert nonnumeric["gear_type"] == "pedal"
        assert nonnumeric["display_name"] == seeded["nonnumeric"].gear.name
        assert nonnumeric["is_favorite"] is False
        assert nonnumeric["tone3000_tone_id"] is None

        non_t3k = items_by_id[str(seeded["non_t3k"].user_gear.id)]
        assert non_t3k["gear_type"] == "ir"
        assert non_t3k["tone3000_tone_id"] is None

    async def test_unauthenticated_request_returns_401(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/gear-items")

        assert response.status_code == 401

    async def test_pagination_bounds_page_and_preserves_total(
        self,
        db_session: AsyncSession,
        make_gear: Callable[..., Coroutine[Any, Any, Gear]],
        make_user: Callable[..., Coroutine[Any, Any, User]],
        test_user: User,
    ) -> None:
        await _seed_library(db_session, make_gear, make_user, test_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first_page = await client.get("/api/gear-items", params={"page_size": 2})
            second_page = await client.get(
                "/api/gear-items",
                params={"page": 2, "page_size": 2},
            )

        assert first_page.status_code == 200
        first_body = first_page.json()
        assert len(first_body["gear_items"]) == 2
        assert first_body["total"] == 3
        assert first_body["page"] == 1
        assert first_body["page_size"] == 2

        assert second_page.status_code == 200
        second_body = second_page.json()
        assert len(second_body["gear_items"]) == 1
        assert second_body["total"] == 3
        assert second_body["page"] == 2
        assert second_body["page_size"] == 2

    async def test_page_size_above_limit_returns_422(
        self,
        test_user: User,
    ) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/gear-items", params={"page_size": 101})

        assert response.status_code == 422

    async def test_outboard_gear_folds_to_pedal(
        self,
        db_session: AsyncSession,
        make_gear: Callable[..., Coroutine[Any, Any, Gear]],
        test_user: User,
    ) -> None:
        # GearType.OUTBOARD has no GearItemType member; the projection must fold it to
        # "pedal" (matching the frontend) so the caller still gets one item per row
        # rather than a response-validation 500.
        marker = uuid4().hex[:8]
        outboard = await make_gear(
            GearType.OUTBOARD,
            Platform.NAM,
            models=1,
            name=f"{marker} Rack Preamp",
            slug=f"{marker}-rack-preamp",
        )
        seeded = await _save_user_gear(db_session, test_user, outboard)
        await db_session.flush()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/gear-items")

        assert response.status_code == 200
        items_by_id = {item["id"]: item for item in response.json()["gear_items"]}
        assert items_by_id[str(seeded.user_gear.id)]["gear_type"] == "pedal"
