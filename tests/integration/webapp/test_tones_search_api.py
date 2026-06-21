"""Integration tests for the tone search API."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.main import app


async def _make_search_gear(make_gear, marker: str) -> None:
    await make_gear(
        GearType.AMP,
        Platform.NAM,
        models=1,
        name=f"{marker} Alpha Amp",
        slug=f"{marker}-alpha-amp",
        description="Alpha clean amp",
        thumbnail_url="https://example.test/alpha.jpg",
        downloads_count=7,
        favorites_count=3,
    )
    await make_gear(
        GearType.PEDAL,
        Platform.AIDA_X,
        models=1,
        name=f"{marker} Beta Pedal",
        slug=f"{marker}-beta-pedal",
        description="Beta drive pedal",
    )
    await make_gear(
        GearType.IR,
        Platform.IR,
        models=1,
        name=f"{marker} Gamma IR",
        slug=f"{marker}-gamma-ir",
        description="Gamma cabinet IR",
    )


@pytest.mark.asyncio
@pytest.mark.integration
class TestTonesSearchApi:
    async def test_search_returns_unauthenticated_paginated_tones_shape(self, make_gear) -> None:
        marker = f"tones-search-{uuid4().hex[:8]}"
        await _make_search_gear(make_gear, marker)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/tones/search", params={"query": marker})

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"data", "total", "page", "per_page", "has_next"}
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["per_page"] == 50
        assert body["has_next"] is False

        tone = body["data"][0]
        assert set(tone) == {
            "id",
            "title",
            "description",
            "gear",
            "platform",
            "tags",
            "makes",
            "links",
            "videos",
            "images",
            "models_count",
            "downloads_count",
            "favorites_count",
            "license",
            "creator",
            "created_at",
            "updated_at",
        }
        assert isinstance(tone["id"], str)
        assert tone["title"].startswith(marker)
        assert tone["gear"] in {"amp", "pedal", "ir"}
        assert tone["platform"] in {"nam", "aida-x", "ir"}
        assert tone["tags"][0]["id"] == 0
        assert isinstance(tone["tags"][0]["name"], str)
        assert tone["makes"] == []
        assert tone["links"] == []
        assert tone["videos"] == []
        assert tone["models_count"] == 1
        assert tone["license"] is None
        assert tone["creator"] is None
        assert tone["created_at"] is not None
        assert tone["updated_at"] is not None

    async def test_search_filters_by_query_gear_and_platform(self, make_gear) -> None:
        marker = f"tones-search-{uuid4().hex[:8]}"
        await _make_search_gear(make_gear, marker)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            query_response = await client.get(
                "/api/tones/search",
                params={"query": f"{marker} Alpha"},
            )
            gear_response = await client.get(
                "/api/tones/search",
                params={"query": marker, "gear": "pedal"},
            )
            platform_response = await client.get(
                "/api/tones/search",
                params={"query": marker, "platform": "aida-x"},
            )

        assert query_response.status_code == 200
        query_body = query_response.json()
        assert query_body["total"] == 1
        assert query_body["data"][0]["title"] == f"{marker} Alpha Amp"

        assert gear_response.status_code == 200
        gear_body = gear_response.json()
        assert gear_body["total"] == 1
        assert gear_body["data"][0]["gear"] == "pedal"
        assert gear_body["data"][0]["title"] == f"{marker} Beta Pedal"

        assert platform_response.status_code == 200
        platform_body = platform_response.json()
        assert platform_body["total"] == 1
        assert platform_body["data"][0]["platform"] == "aida-x"
        assert platform_body["data"][0]["title"] == f"{marker} Beta Pedal"

    async def test_search_pagination_uses_filtered_total(self, make_gear) -> None:
        marker = f"tones-search-{uuid4().hex[:8]}"
        await _make_search_gear(make_gear, marker)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            page_one_response = await client.get(
                "/api/tones/search",
                params={"query": marker, "per_page": "2", "page": "1"},
            )
            page_two_response = await client.get(
                "/api/tones/search",
                params={"query": marker, "per_page": "2", "page": "2"},
            )

        assert page_one_response.status_code == 200
        page_one = page_one_response.json()
        assert len(page_one["data"]) == 2
        assert page_one["total"] == 3
        assert page_one["page"] == 1
        assert page_one["per_page"] == 2
        assert page_one["has_next"] is True

        assert page_two_response.status_code == 200
        page_two = page_two_response.json()
        assert len(page_two["data"]) == 1
        assert page_two["total"] == 3
        assert page_two["page"] == 2
        assert page_two["per_page"] == 2
        assert page_two["has_next"] is False

    async def test_search_excludes_non_public_gear(self, make_gear) -> None:
        marker = f"tones-search-{uuid4().hex[:8]}"
        await make_gear(
            GearType.AMP,
            Platform.NAM,
            models=1,
            name=f"{marker} Public Amp",
            slug=f"{marker}-public-amp",
            is_public=True,
        )
        await make_gear(
            GearType.AMP,
            Platform.NAM,
            models=1,
            name=f"{marker} Private Amp",
            slug=f"{marker}-private-amp",
            is_public=False,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/tones/search", params={"query": marker})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["data"][0]["title"] == f"{marker} Public Amp"

    async def test_search_validation_errors(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            per_page_response = await client.get(
                "/api/tones/search",
                params={"per_page": "101"},
            )
            gear_response = await client.get(
                "/api/tones/search",
                params={"gear": "synth"},
            )
            platform_response = await client.get(
                "/api/tones/search",
                params={"platform": "quad-cortex"},
            )

        assert per_page_response.status_code == 422
        assert gear_response.status_code == 422
        assert platform_response.status_code == 422
