"""Integration tests for Preset CRUD API (T132).

Tests /api/v1/presets/ endpoints for preset management.
Presets store reusable signal chain parameter configurations.
Ownership is enforced via SignalChainBlock → SignalChain → User.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.block_category import BlockCategory
from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.block_type import BlockType
from webapp.adapters.persistence.models.preset import Preset
from webapp.adapters.persistence.models.signal_chain import (
    SignalChain,
    SignalChainBlock,
)
from webapp.adapters.persistence.models.user import User
from webapp.auth.dependencies import (
    set_session_override,
    set_user_override,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with presets router."""
    from fastapi import FastAPI

    from webapp.api.v1.presets import router
    from webapp.exception_handlers import app_exception_handler
    from webapp.exceptions import AppException

    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(AppException, app_exception_handler)
    return app


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="presetuser",
        email="presetuser@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user for isolation tests."""
    user = User(
        id=uuid4(),
        username="otherpresetuser",
        email="otherpreset@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_block_type(db_session: AsyncSession) -> BlockType:
    """Create a test block type for signal chain blocks."""
    block_type = BlockType(
        id=uuid4(),
        name="Test Compressor",
        category=BlockCategory.DYNAMICS,
        default_params={
            "threshold": -20.0,
            "ratio": 4.0,
            "attack": 5.0,
            "release": 50.0,
        },
    )
    db_session.add(block_type)
    await db_session.flush()
    await db_session.refresh(block_type)
    return block_type


@pytest.fixture
async def test_signal_chain(db_session: AsyncSession, test_user: User) -> SignalChain:
    """Create a test signal chain owned by test_user."""
    chain = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Chain",
        description="Chain for preset testing",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.flush()
    await db_session.refresh(chain)
    return chain


@pytest.fixture
async def test_block(
    db_session: AsyncSession,
    test_signal_chain: SignalChain,
    test_block_type: BlockType,
) -> SignalChainBlock:
    """Create a test signal chain block."""
    block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=test_signal_chain.id,
        block_type_id=test_block_type.id,
        position=1,
        params={"threshold": -15.0, "ratio": 3.0},
    )
    db_session.add(block)
    await db_session.flush()
    await db_session.refresh(block)
    return block


@pytest.fixture
async def other_user_chain(db_session: AsyncSession, other_user: User) -> SignalChain:
    """Create a signal chain owned by other_user."""
    chain = SignalChain(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Chain",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.flush()
    await db_session.refresh(chain)
    return chain


@pytest.fixture
async def other_user_block(
    db_session: AsyncSession,
    other_user_chain: SignalChain,
    test_block_type: BlockType,
) -> SignalChainBlock:
    """Create a block owned by other_user (via their chain)."""
    block = SignalChainBlock(
        id=uuid4(),
        signal_chain_id=other_user_chain.id,
        block_type_id=test_block_type.id,
        position=1,
        params={"threshold": -10.0},
    )
    db_session.add(block)
    await db_session.flush()
    await db_session.refresh(block)
    return block


@pytest.fixture
async def test_preset(
    db_session: AsyncSession,
    test_block: SignalChainBlock,
) -> Preset:
    """Create a test preset on test_user's block."""
    preset = Preset(
        signal_chain_block_id=test_block.id,
        name="Heavy Compression",
        params={"threshold": -30.0, "ratio": 8.0, "attack": 2.0, "release": 100.0},
    )
    db_session.add(preset)
    await db_session.flush()
    await db_session.refresh(preset)
    return preset


@pytest.fixture
async def other_user_preset(
    db_session: AsyncSession,
    other_user_block: SignalChainBlock,
) -> Preset:
    """Create a preset owned by other_user (via their block → chain → user)."""
    preset = Preset(
        signal_chain_block_id=other_user_block.id,
        name="Other User Preset",
        params={"threshold": -5.0},
    )
    db_session.add(preset)
    await db_session.flush()
    await db_session.refresh(preset)
    return preset


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    set_session_override(None)
    set_user_override(None)


@pytest.fixture
async def unauthenticated_client(
    app: FastAPI,
) -> AsyncClient:
    """Create an unauthenticated HTTP client."""
    set_session_override(None)
    set_user_override(None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ── API Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
class TestPresetListAPI:
    """Test GET /api/v1/presets — list current user's presets."""

    async def test_list_presets_returns_users_presets(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_preset: Preset,
    ) -> None:
        """Test GET /api/v1/presets returns presets owned by current user."""
        response = await authenticated_client.get("/api/v1/presets")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        preset_names = {p["name"] for p in data}
        assert "Heavy Compression" in preset_names

    async def test_list_presets_excludes_other_users(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_preset: Preset,
        other_user_preset: Preset,
    ) -> None:
        """Test GET /api/v1/presets excludes presets owned by other users."""
        response = await authenticated_client.get("/api/v1/presets")

        assert response.status_code == 200
        data = response.json()
        preset_names = {p["name"] for p in data}
        assert "Other User Preset" not in preset_names

    async def test_list_presets_empty(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
    ) -> None:
        """Test GET /api/v1/presets returns empty list when user has no presets."""
        response = await authenticated_client.get("/api/v1/presets")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_list_presets_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test GET /api/v1/presets requires authentication."""
        response = await unauthenticated_client.get("/api/v1/presets")

        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestPresetCreateAPI:
    """Test POST /api/v1/presets — create preset."""

    async def test_create_preset_success(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_block: SignalChainBlock,
    ) -> None:
        """Test POST /api/v1/presets creates a preset with valid data."""
        response = await authenticated_client.post(
            "/api/v1/presets",
            json={
                "name": "My Preset",
                "description": "A test preset",
                "signal_chain_block_id": str(test_block.id),
                "chain_parameters": {
                    "threshold": -25.0,
                    "ratio": 6.0,
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Preset"
        assert "id" in data

    async def test_create_preset_with_invalid_parameters_rejected(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_block: SignalChainBlock,
    ) -> None:
        """Test POST /api/v1/presets rejects invalid chain parameters via PresetProcessor."""
        response = await authenticated_client.post(
            "/api/v1/presets",
            json={
                "name": "Bad Preset",
                "signal_chain_block_id": str(test_block.id),
                "chain_parameters": {
                    "nonexistent_param": 999.0,
                },
            },
        )

        # PresetProcessor should reject invalid parameters
        assert response.status_code == 422

    async def test_create_preset_for_other_users_block_returns_404(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        other_user_block: SignalChainBlock,
    ) -> None:
        """Test POST /api/v1/presets returns 404 for other user's block (no existence leak)."""
        response = await authenticated_client.post(
            "/api/v1/presets",
            json={
                "name": "Sneaky Preset",
                "signal_chain_block_id": str(other_user_block.id),
                "chain_parameters": {"threshold": -10.0},
            },
        )

        assert response.status_code == 404

    async def test_create_preset_requires_name(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_block: SignalChainBlock,
    ) -> None:
        """Test POST /api/v1/presets rejects missing name."""
        response = await authenticated_client.post(
            "/api/v1/presets",
            json={
                "signal_chain_block_id": str(test_block.id),
                "chain_parameters": {"threshold": -10.0},
            },
        )

        assert response.status_code == 422

    async def test_create_preset_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test POST /api/v1/presets requires authentication."""
        response = await unauthenticated_client.post(
            "/api/v1/presets",
            json={
                "name": "Test",
                "signal_chain_block_id": str(uuid4()),
                "chain_parameters": {},
            },
        )

        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestPresetDetailAPI:
    """Test GET /api/v1/presets/{id} — get preset detail."""

    async def test_get_preset_detail(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_preset: Preset,
    ) -> None:
        """Test GET /api/v1/presets/{id} returns preset detail."""
        response = await authenticated_client.get(f"/api/v1/presets/{test_preset.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_preset.id)
        assert data["name"] == "Heavy Compression"

    async def test_get_preset_not_found(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
    ) -> None:
        """Test GET /api/v1/presets/{id} returns 404 for non-existent preset."""
        response = await authenticated_client.get(f"/api/v1/presets/{uuid4()}")

        assert response.status_code == 404

    async def test_get_preset_other_user_returns_404(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        other_user_preset: Preset,
    ) -> None:
        """Test GET /api/v1/presets/{id} returns 404 for other user's preset (no existence leak)."""
        response = await authenticated_client.get(f"/api/v1/presets/{other_user_preset.id}")

        assert response.status_code == 404

    async def test_get_preset_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test GET /api/v1/presets/{id} requires authentication."""
        response = await unauthenticated_client.get(f"/api/v1/presets/{uuid4()}")

        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestPresetUpdateAPI:
    """Test PUT /api/v1/presets/{id} — update preset."""

    async def test_update_preset_success(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_preset: Preset,
    ) -> None:
        """Test PUT /api/v1/presets/{id} updates preset name and parameters."""
        response = await authenticated_client.put(
            f"/api/v1/presets/{test_preset.id}",
            json={
                "name": "Updated Preset",
                "description": "Updated description",
                "chain_parameters": {
                    "threshold": -40.0,
                    "ratio": 10.0,
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Preset"

    async def test_update_preset_validates_parameters(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_preset: Preset,
    ) -> None:
        """Test PUT /api/v1/presets/{id} validates chain parameters via PresetProcessor."""
        response = await authenticated_client.put(
            f"/api/v1/presets/{test_preset.id}",
            json={
                "name": "Bad Update",
                "chain_parameters": {
                    "nonexistent_param": 999.0,
                },
            },
        )

        assert response.status_code == 422

    async def test_update_preset_not_found(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
    ) -> None:
        """Test PUT /api/v1/presets/{id} returns 404 for non-existent preset."""
        response = await authenticated_client.put(
            f"/api/v1/presets/{uuid4()}",
            json={
                "name": "Ghost Preset",
                "chain_parameters": {"threshold": -10.0},
            },
        )

        assert response.status_code == 404

    async def test_update_preset_other_user_returns_404(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        other_user_preset: Preset,
    ) -> None:
        """Test PUT /api/v1/presets/{id} returns 404 for other user's preset."""
        response = await authenticated_client.put(
            f"/api/v1/presets/{other_user_preset.id}",
            json={
                "name": "Hijack Preset",
                "chain_parameters": {"threshold": -10.0},
            },
        )

        assert response.status_code == 404

    async def test_update_preset_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test PUT /api/v1/presets/{id} requires authentication."""
        response = await unauthenticated_client.put(
            f"/api/v1/presets/{uuid4()}",
            json={"name": "Test", "chain_parameters": {}},
        )

        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestPresetDeleteAPI:
    """Test DELETE /api/v1/presets/{id} — delete preset."""

    async def test_delete_preset_success(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_preset: Preset,
        db_session: AsyncSession,
    ) -> None:
        """Test DELETE /api/v1/presets/{id} deletes the preset."""
        preset_id = test_preset.id

        response = await authenticated_client.delete(f"/api/v1/presets/{preset_id}")

        assert response.status_code == 204

        # Verify deletion in DB
        from sqlalchemy import select

        stmt = select(Preset).where(Preset.id == preset_id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

    async def test_delete_preset_not_found(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
    ) -> None:
        """Test DELETE /api/v1/presets/{id} returns 404 for non-existent preset."""
        response = await authenticated_client.delete(f"/api/v1/presets/{uuid4()}")

        assert response.status_code == 404

    async def test_delete_preset_other_user_returns_404(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        other_user_preset: Preset,
    ) -> None:
        """Test DELETE /api/v1/presets/{id} returns 404 for other user's preset."""
        response = await authenticated_client.delete(f"/api/v1/presets/{other_user_preset.id}")

        assert response.status_code == 404

    async def test_delete_preset_requires_authentication(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Test DELETE /api/v1/presets/{id} requires authentication."""
        response = await unauthenticated_client.delete(f"/api/v1/presets/{uuid4()}")

        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestPresetResponseSchema:
    """Test Pydantic response schema for preset endpoints."""

    async def test_preset_response_contains_expected_fields(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_preset: Preset,
    ) -> None:
        """Test preset response includes all expected fields."""
        response = await authenticated_client.get(f"/api/v1/presets/{test_preset.id}")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "signal_chain_block_id" in data
        assert "chain_parameters" in data

    async def test_create_preset_response_schema(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_block: SignalChainBlock,
    ) -> None:
        """Test POST response matches expected schema."""
        response = await authenticated_client.post(
            "/api/v1/presets",
            json={
                "name": "Schema Test",
                "signal_chain_block_id": str(test_block.id),
                "chain_parameters": {"threshold": -20.0},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert data["name"] == "Schema Test"
