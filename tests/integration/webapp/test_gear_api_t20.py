"""Integration tests for Gear API endpoints (T20).

Tests GET /api/v1/gear/ and GET /api/v1/gear/{id} endpoints.
These are public endpoints that do not require authentication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.entities.base import new_id
from gts.domain.entities.gear import Gear as GearEntity
from gts.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def gear_repository(db_session: AsyncSession) -> SQLAlchemyGearRepository:
    """Create a GearRepository instance."""
    return SQLAlchemyGearRepository(db_session)


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    """Create FastAPI app with gear API routes."""
    from fastapi import FastAPI

    from webapp.api.v1.gear import router, set_session_override

    # Set session override for testing
    set_session_override(db_session)

    app = FastAPI()
    app.include_router(router)

    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def sample_gear(
    gear_repository: SQLAlchemyGearRepository,
    db_session: AsyncSession,
) -> list[GearEntity]:
    """Create sample gear with unique names to avoid conflicts with real DB data."""
    from uuid import uuid4

    uid = uuid4().hex[:8]
    gear_items = [
        GearEntity(
            id=new_id(),
            name=f"ZZZTestAmp_Alpha_{uid}",
            gear_type=GearType.AMP,
            description=f"ZZZTestClassicTubeAmp_{uid}",
            manufacturer=f"ZZZTestMfg_{uid}",
            tags=[f"zzztest_clean_{uid}"],
            is_public=True,
        ),
        GearEntity(
            id=new_id(),
            name=f"ZZZTestAmp_Beta_{uid}",
            gear_type=GearType.AMP,
            description=f"ZZZTestHighGainAmp_{uid}",
            manufacturer=f"ZZZTestMfg_{uid}",
            tags=[f"zzztest_metal_{uid}"],
            is_public=True,
        ),
        GearEntity(
            id=new_id(),
            name=f"ZZZTestPedal_Alpha_{uid}",
            gear_type=GearType.PEDAL,
            description=f"ZZZTestDistortionPedal_{uid}",
            manufacturer=f"ZZZTestMfg_{uid}",
            tags=[f"zzztest_distortion_{uid}"],
            is_public=True,
        ),
    ]

    for gear in gear_items:
        await gear_repository.save(gear)
    await db_session.commit()

    return gear_items


class TestGearListAPI:
    """Tests for GET /api/v1/gear/ endpoint."""

    async def test_list_all_gear(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test listing all gear without filters (scoped by unique manufacturer)."""
        # Use the unique manufacturer from the fixture to avoid matching real DB rows
        mfr = sample_gear[0].manufacturer
        response = await client.get(f"/api/v1/gear/?manufacturer={mfr}")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        assert data["total"] == 3
        assert len(data["items"]) == 3

        # Verify gear data structure
        first_item = data["items"][0]
        assert "id" in first_item
        assert "name" in first_item
        assert "gear_type" in first_item
        assert "description" in first_item
        assert "manufacturer" in first_item

    async def test_list_gear_with_pagination(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test pagination support (scoped by unique manufacturer)."""
        mfr = sample_gear[0].manufacturer
        # First page
        response = await client.get(f"/api/v1/gear/?manufacturer={mfr}&limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Second page
        response = await client.get(f"/api/v1/gear/?manufacturer={mfr}&limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["items"]) == 1
        assert data["offset"] == 2

    async def test_filter_by_gear_type(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test filtering by gear type (scoped by unique manufacturer)."""
        mfr = sample_gear[0].manufacturer
        response = await client.get(f"/api/v1/gear/?gear_type=amp&manufacturer={mfr}")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert len(data["items"]) == 2

        # All items should be amps
        for item in data["items"]:
            assert item["gear_type"] == "amp"

    async def test_filter_by_manufacturer(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test filtering by manufacturer."""
        mfr = sample_gear[0].manufacturer
        response = await client.get(f"/api/v1/gear/?manufacturer={mfr}")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["items"]) == 3
        for item in data["items"]:
            assert item["manufacturer"] == mfr

    async def test_search_by_query(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test text search on name/description (scoped by unique name prefix)."""
        # Use the unique name of the first gear item
        unique_name = sample_gear[0].name
        response = await client.get(f"/api/v1/gear/?query={unique_name}")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["name"] == unique_name

    async def test_empty_result(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test query that returns no results."""
        response = await client.get("/api/v1/gear/?manufacturer=NonExistent")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert len(data["items"]) == 0

    async def test_default_pagination_limits(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test default pagination values."""
        response = await client.get("/api/v1/gear/")

        assert response.status_code == 200
        data = response.json()

        # Default limit should be reasonable (e.g., 50)
        assert data["limit"] >= 3  # Should include all our test items
        assert data["offset"] == 0


class TestGearDetailAPI:
    """Tests for GET /api/v1/gear/{id} endpoint."""

    async def test_get_gear_by_id(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test retrieving gear by ID."""
        gear_id = sample_gear[0].id

        response = await client.get(f"/api/v1/gear/{gear_id}")

        assert response.status_code == 200
        data = response.json()

        expected = sample_gear[0]
        assert data["id"] == str(gear_id)
        assert data["name"] == expected.name
        assert data["gear_type"] == "amp"
        assert data["description"] == expected.description
        assert data["manufacturer"] == expected.manufacturer
        assert "tags" in data
        assert set(data["tags"]) == set(expected.tags)

    async def test_get_gear_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """Test 404 for non-existent gear."""
        fake_id = new_id()

        response = await client.get(f"/api/v1/gear/{fake_id}")

        assert response.status_code == 404

    async def test_get_gear_invalid_uuid(
        self,
        client: AsyncClient,
    ) -> None:
        """Test 422 for invalid UUID format."""
        response = await client.get("/api/v1/gear/not-a-uuid")

        assert response.status_code == 422

    async def test_gear_detail_includes_all_fields(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test that detail response includes all expected fields."""
        gear_id = sample_gear[0].id

        response = await client.get(f"/api/v1/gear/{gear_id}")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        required_fields = {
            "id",
            "name",
            "gear_type",
            "description",
            "manufacturer",
            "tags",
            "is_public",
            "created_at",
            "updated_at",
        }

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestGearAPIPublicAccess:
    """Tests verifying endpoints are public (no auth required)."""

    async def test_list_endpoint_is_public(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test that list endpoint does not require authentication."""
        # Request without any auth headers
        response = await client.get("/api/v1/gear/")

        assert response.status_code == 200
        # Should not get 401 Unauthorized

    async def test_detail_endpoint_is_public(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test that detail endpoint does not require authentication."""
        gear_id = sample_gear[0].id

        # Request without any auth headers
        response = await client.get(f"/api/v1/gear/{gear_id}")

        assert response.status_code == 200
        # Should not get 401 Unauthorized


class TestGearAPIResponseSchema:
    """Tests for response schema validation."""

    async def test_list_response_schema(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test list response matches expected schema."""
        response = await client.get("/api/v1/gear/")

        assert response.status_code == 200
        data = response.json()

        # Top-level pagination fields
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["limit"], int)
        assert isinstance(data["offset"], int)

        # Item schema
        if data["items"]:
            item = data["items"][0]
            assert isinstance(item["id"], str)
            # Verify it's a valid UUID string
            UUID(item["id"])
            assert isinstance(item["name"], str)
            assert isinstance(item["gear_type"], str)

    async def test_detail_response_schema(
        self,
        client: AsyncClient,
        sample_gear: list[GearEntity],
    ) -> None:
        """Test detail response matches expected schema."""
        gear_id = sample_gear[0].id

        response = await client.get(f"/api/v1/gear/{gear_id}")

        assert response.status_code == 200
        data = response.json()

        # Verify UUID format
        assert isinstance(data["id"], str)
        UUID(data["id"])

        # Verify field types
        assert isinstance(data["name"], str)
        assert isinstance(data["gear_type"], str)
        assert isinstance(data["tags"], list)
        assert isinstance(data["is_public"], bool)
