"""Integration tests for T134: Save/Remove Model UI + Model Counts + Download Status.

Tests cover:
- Download status indicator in gear detail page model context
- Download status indicator in model toggle HTMX fragment
- Bulk select UI for adding/removing multiple models
- Model count badge on gear cards
- All interactive elements have data-testid attributes
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from gts.domain.value_objects.download_status import DownloadStatus
from gts.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# --- Fixtures ---


@pytest.fixture
async def other_user(db_session: "AsyncSession") -> User:
    """Create a second test user for isolation tests."""
    user = User(
        id=uuid4(),
        username="otheruser",
        email="other@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def gear_with_models(db_session: "AsyncSession") -> Gear:
    """Create a gear item with multiple models having different download statuses."""
    gear = Gear(
        id=uuid4(),
        name="Test Amp Pack",
        slug="test-amp-pack",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        description="A test amp for download status testing",
        manufacturer="TestCo",
        is_public=True,
    )
    db_session.add(gear)
    await db_session.flush()

    # Create models with different download statuses
    model_pending = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
        download_status=DownloadStatus.PENDING,
    )
    model_downloading = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.LITE,
        download_status=DownloadStatus.DOWNLOADING,
    )
    model_completed = GearModel(
        id=uuid4(),
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.NANO,
        download_status=DownloadStatus.COMPLETED,
        file_path="/models/test.nam",
    )
    db_session.add_all([model_pending, model_downloading, model_completed])
    await db_session.commit()

    # Refresh with relationships loaded
    result = await db_session.execute(
        select(Gear).where(Gear.id == gear.id).options(joinedload(Gear.models))
    )
    return result.unique().scalar_one()


# --- Download Status in Gear Detail Page ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearDetailDownloadStatus:
    """Test that gear detail page includes download status for each model."""

    async def test_gear_detail_page_includes_download_status_in_model_context(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify gear detail page passes download_status for each model."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            # Download status indicator should be present for each model
            # At minimum, the HTML should contain download status data attributes
            # or status text for the different states
            assert 'data-testid="model-download-status"' in html

    async def test_gear_detail_shows_completed_download_indicator(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify completed download status shows 'downloaded' indicator."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            # Should show a visual indicator for completed/downloaded status
            assert "downloaded" in html.lower() or "completed" in html.lower()

    async def test_gear_detail_shows_downloading_status_indicator(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify in-progress download shows 'downloading' indicator."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            # Should show a visual indicator for downloading/in-progress status
            assert "downloading" in html.lower()

    async def test_gear_detail_shows_available_status_for_pending(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify pending download shows 'available' indicator."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            # Pending models should show as "available" for download
            assert "available" in html.lower() or "pending" in html.lower()


# --- Download Status in Model Toggle Fragment ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestModelToggleDownloadStatus:
    """Test that model toggle HTMX fragment includes download status."""

    async def test_model_toggle_response_includes_download_status(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify toggle response fragment includes download_status data."""
        # Get a model with completed status
        completed_model = next(
            m for m in gear_with_models.models if m.download_status == DownloadStatus.COMPLETED
        )

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/api/v1/html/gear/model/{completed_model.id}/toggle")

            assert response.status_code == 200
            html = response.text

            # The returned model row fragment should include download status
            assert 'data-testid="model-download-status"' in html

    async def test_model_toggle_preserves_download_status_after_save(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify toggle preserves download_status in the returned fragment."""
        pending_model = next(
            m for m in gear_with_models.models if m.download_status == DownloadStatus.PENDING
        )

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Toggle to save the model
            response = await client.post(f"/api/v1/html/gear/model/{pending_model.id}/toggle")

            assert response.status_code == 200
            html = response.text

            # Fragment should indicate pending/available status even after save
            assert "pending" in html.lower() or "available" in html.lower()


# --- Bulk Select UI ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestBulkSelectModels:
    """Test bulk select UI for adding/removing multiple models at once."""

    async def test_bulk_add_models_endpoint_exists(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify bulk add endpoint accepts list of model IDs."""
        model_ids = [str(m.id) for m in gear_with_models.models]

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/html/gear/models/bulk-toggle",
                json={"model_ids": model_ids, "action": "add"},
            )

            # Should return 200 with updated fragment
            assert response.status_code == 200

    async def test_bulk_remove_models_endpoint_exists(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify bulk remove endpoint accepts list of model IDs."""
        # First save all models
        for model in gear_with_models.models:
            user_gear = UserGear(
                id=uuid4(),
                user_id=test_user.id,
                gear_model_id=model.id,
            )
            db_session.add(user_gear)
        await db_session.commit()

        model_ids = [str(m.id) for m in gear_with_models.models]

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/html/gear/models/bulk-toggle",
                json={"model_ids": model_ids, "action": "remove"},
            )

            assert response.status_code == 200

    async def test_bulk_add_persists_all_models_to_library(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify bulk add actually persists all selected models."""
        model_ids = [str(m.id) for m in gear_with_models.models]

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/html/gear/models/bulk-toggle",
                json={"model_ids": model_ids, "action": "add"},
            )

        # Verify all models are now in the user's library
        result = await db_session.execute(select(UserGear).where(UserGear.user_id == test_user.id))
        saved = result.scalars().all()
        saved_model_ids = {str(ug.gear_model_id) for ug in saved}

        for mid in model_ids:
            assert mid in saved_model_ids, f"Model {mid} not found in user library"

    async def test_bulk_remove_removes_all_models_from_library(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify bulk remove removes all selected models from library."""
        # First save all models
        for model in gear_with_models.models:
            user_gear = UserGear(
                id=uuid4(),
                user_id=test_user.id,
                gear_model_id=model.id,
            )
            db_session.add(user_gear)
        await db_session.commit()

        model_ids = [str(m.id) for m in gear_with_models.models]

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/html/gear/models/bulk-toggle",
                json={"model_ids": model_ids, "action": "remove"},
            )

        # Verify all models removed from library
        result = await db_session.execute(select(UserGear).where(UserGear.user_id == test_user.id))
        saved = result.scalars().all()
        assert len(saved) == 0

    async def test_gear_detail_has_bulk_select_ui(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify gear detail page has bulk select UI elements."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            # Should have a "select all" checkbox
            assert 'data-testid="bulk-select-all"' in html

            # Should have bulk action buttons
            assert 'data-testid="bulk-save-btn"' in html or 'data-testid="bulk-remove-btn"' in html

    async def test_bulk_toggle_requires_authentication(
        self,
        db_session: "AsyncSession",
        gear_with_models: Gear,
    ) -> None:
        """Verify bulk toggle endpoint requires authentication."""
        model_ids = [str(m.id) for m in gear_with_models.models]

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/html/gear/models/bulk-toggle",
                json={"model_ids": model_ids, "action": "add"},
            )

            # Should require auth
            assert response.status_code in [401, 403]


# --- Model Count on Gear Cards ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestModelCountBadge:
    """Test model count badge on gear cards and detail page."""

    async def test_gear_detail_header_shows_model_count(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify gear detail page header shows correct model count."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            # Gear has 3 models, count should appear in header
            assert "3" in html
            # The models count should be in the header area with testid
            assert 'data-testid="model-count-badge"' in html

    async def test_gear_browse_cards_show_model_count(
        self,
        db_session: "AsyncSession",
        gear_with_models: Gear,
    ) -> None:
        """Verify gear browse page cards include model count badge."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/gear")

            assert response.status_code == 200
            html = response.text

            # Should show model count badge with testid
            assert 'data-testid="pack-models-count"' in html


# --- data-testid Attributes ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestDataTestIdAttributes:
    """Verify all interactive elements have data-testid attributes."""

    async def test_model_row_has_save_checkbox_testid(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify model row has data-testid on save checkbox."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            assert 'data-testid="model-save-checkbox"' in html

    async def test_model_row_has_download_status_testid(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify model row has data-testid on download status indicator."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            assert 'data-testid="model-download-status"' in html

    async def test_bulk_select_elements_have_testids(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify bulk select UI elements have data-testid attributes."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            assert 'data-testid="bulk-select-all"' in html

    async def test_model_count_badge_has_testid(
        self,
        db_session: "AsyncSession",
        test_user: User,
        gear_with_models: Gear,
    ) -> None:
        """Verify model count badge in detail header has data-testid."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/gear/{gear_with_models.slug}")

            assert response.status_code == 200
            html = response.text

            assert 'data-testid="model-count-badge"' in html
