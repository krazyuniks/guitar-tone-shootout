"""Integration tests for Block Types API (T133).

Tests GET /api/v1/block-types endpoint that returns built-in processor
block types with their parameter definitions. This is a public,
read-only, cacheable endpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.api.v1.block_types import router
from webapp.auth.dependencies import set_session_override

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with block_types router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def client(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncClient:
    """Create an HTTP client (no auth needed — public endpoint)."""
    set_session_override(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    set_session_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
class TestBlockTypesAPI:
    """Tests for GET /api/v1/block-types endpoint."""

    async def test_list_block_types_returns_200(
        self,
        client: AsyncClient,
    ) -> None:
        """Test GET /api/v1/block-types returns 200 OK."""
        response = await client.get("/api/v1/block-types")

        assert response.status_code == 200

    async def test_list_block_types_returns_all_builtin_types(
        self,
        client: AsyncClient,
    ) -> None:
        """Test response includes all registered block types."""
        response = await client.get("/api/v1/block-types")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # BlockTypeRegistry has 5 built-in types
        assert len(data) >= 5

        names = {bt["name"] for bt in data}
        assert "Compressor" in names
        assert "EQ" in names
        assert "Delay" in names
        assert "Reverb" in names
        assert "Noise Gate" in names

    async def test_block_type_response_includes_name(
        self,
        client: AsyncClient,
    ) -> None:
        """Test each block type includes name field."""
        response = await client.get("/api/v1/block-types")

        data = response.json()
        for bt in data:
            assert "name" in bt
            assert isinstance(bt["name"], str)
            assert len(bt["name"]) > 0

    async def test_block_type_response_includes_description(
        self,
        client: AsyncClient,
    ) -> None:
        """Test each block type includes description field."""
        response = await client.get("/api/v1/block-types")

        data = response.json()
        for bt in data:
            assert "description" in bt

    async def test_block_type_response_includes_category(
        self,
        client: AsyncClient,
    ) -> None:
        """Test each block type includes category field."""
        response = await client.get("/api/v1/block-types")

        data = response.json()
        for bt in data:
            assert "category" in bt
            assert isinstance(bt["category"], str)

    async def test_block_type_response_includes_parameters(
        self,
        client: AsyncClient,
    ) -> None:
        """Test each block type includes default_params with types/ranges/defaults."""
        response = await client.get("/api/v1/block-types")

        data = response.json()
        for bt in data:
            assert "default_params" in bt
            assert isinstance(bt["default_params"], dict)

    async def test_compressor_has_expected_params(
        self,
        client: AsyncClient,
    ) -> None:
        """Test Compressor block type has expected parameter keys."""
        response = await client.get("/api/v1/block-types")

        data = response.json()
        compressor = next(bt for bt in data if bt["name"] == "Compressor")

        params = compressor["default_params"]
        assert "threshold" in params
        assert "ratio" in params
        assert "attack" in params
        assert "release" in params

    async def test_response_is_cacheable(
        self,
        client: AsyncClient,
    ) -> None:
        """Test response includes Cache-Control header (block types are static)."""
        response = await client.get("/api/v1/block-types")

        assert response.status_code == 200
        cache_control = response.headers.get("cache-control")
        assert cache_control is not None
        assert "max-age" in cache_control

    async def test_no_authentication_required(
        self,
        app: FastAPI,
        db_session: AsyncSession,
    ) -> None:
        """Test endpoint works without any authentication."""
        set_session_override(db_session)

        # Create a client without any auth
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as bare_client:
            response = await bare_client.get("/api/v1/block-types")

        set_session_override(None)

        # Should succeed without auth — 200, not 401
        assert response.status_code == 200

    async def test_block_type_has_id_field(
        self,
        client: AsyncClient,
    ) -> None:
        """Test each block type includes an id field."""
        response = await client.get("/api/v1/block-types")

        data = response.json()
        for bt in data:
            assert "id" in bt

    async def test_response_categories_are_valid_enum_values(
        self,
        client: AsyncClient,
    ) -> None:
        """Test category values match BlockCategory enum values."""
        from core.domain.value_objects.block_category import BlockCategory

        valid_categories = {c.value for c in BlockCategory}

        response = await client.get("/api/v1/block-types")

        data = response.json()
        for bt in data:
            assert bt["category"] in valid_categories


@pytest.mark.asyncio
@pytest.mark.integration
class TestBlockTypeSchema:
    """Tests for Pydantic response schema."""

    async def test_schema_importable(self) -> None:
        """Test BlockTypeResponse schema can be imported."""
        from webapp.api.v1.schemas.block_type import BlockTypeResponse

        assert BlockTypeResponse is not None

    async def test_schema_has_required_fields(self) -> None:
        """Test schema defines expected fields."""
        from webapp.api.v1.schemas.block_type import BlockTypeResponse

        fields = BlockTypeResponse.model_fields
        assert "id" in fields
        assert "name" in fields
        assert "description" in fields
        assert "category" in fields
        assert "default_params" in fields


@pytest.mark.asyncio
@pytest.mark.integration
class TestBlockTypesRouterMount:
    """Tests verifying router is mounted in main app."""

    async def test_block_types_router_mounted_in_main_app(self) -> None:
        """Test block_types router is included in the main FastAPI app."""
        from webapp.main import create_app

        app = create_app()

        # Collect all route paths
        routes = [route.path for route in app.routes]

        assert "/api/v1/block-types" in routes
