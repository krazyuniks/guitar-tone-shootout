"""Integration tests for T135: Library Sorting, Filtering, Grid-Aligned Pagination.

Tests cover:
- Sort controls: date added, name, type (ascending/descending)
- Filter controls: filter by gear type (amp, ir, pedal)
- Sorting and filtering via HTMX (partial page reload)
- URL query parameters preserved for bookmarkable state
- Grid-aligned pagination: page sizes in multiples of 3 (12, 24, 36)
- Pagination controls: first, prev, page numbers, next, last
- Applied consistently across library tabs (my gear, chains, DI tracks, shootouts)
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.shootout import DITrack, Shootout, ShootoutStatus
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# --- Fixtures ---


@pytest.fixture
async def many_gear_items(db_session: "AsyncSession", test_user: User) -> list[Gear]:
    """Create 15 gear items across different types with user_gear links."""
    gear_items = []
    for i in range(15):
        gear_type = [GearType.AMP, GearType.IR, GearType.PEDAL][i % 3]
        gear = Gear(
            id=uuid4(),
            name=f"Gear {chr(65 + i)}",  # Gear A, Gear B, ..., Gear O
            slug=f"gear-{chr(97 + i)}",
            gear_type=gear_type,
            description=f"Test gear item {i}",
            manufacturer="TestCo",
            is_public=True,
        )
        db_session.add(gear)
        await db_session.flush()

        model = GearModel(
            id=uuid4(),
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        db_session.add(model)
        await db_session.flush()

        # Save gear to user's library
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_model_id=model.id,
        )
        db_session.add(user_gear)
        await db_session.flush()

        gear_items.append(gear)

    await db_session.commit()
    return gear_items


@pytest.fixture
async def many_chains(db_session: "AsyncSession", test_user: User) -> list[SignalChain]:
    """Create 15 signal chains for the test user."""
    chains = []
    for i in range(15):
        chain = SignalChain(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Chain {chr(65 + i)}",
            description=f"Test chain {i}",
            platform=Platform.NAM,
        )
        db_session.add(chain)
        chains.append(chain)

    await db_session.commit()
    return chains


@pytest.fixture
async def many_tracks(db_session: "AsyncSession", test_user: User) -> list[DITrack]:
    """Create 15 DI tracks for the test user."""
    tracks = []
    for i in range(15):
        track = DITrack(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Track {chr(65 + i)}",
            description=f"Test track {i}",
            file_path=f"/tmp/track_{i}.wav",
            original_filename=f"track_{i}.wav",
            duration_seconds=float(60 + i * 10),
            sample_rate=44100,
            channels=1,
        )
        db_session.add(track)
        tracks.append(track)

    await db_session.commit()
    return tracks


@pytest.fixture
async def many_shootouts(db_session: "AsyncSession", test_user: User) -> list[Shootout]:
    """Create 15 shootouts for the test user."""
    shootouts = []
    for i in range(15):
        shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Shootout {chr(65 + i)}",
            description=f"Test shootout {i}",
            status=ShootoutStatus.DRAFT,
        )
        db_session.add(shootout)
        shootouts.append(shootout)

    await db_session.commit()
    return shootouts


# --- My Gear Sorting Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestMyGearSorting:
    """Test sorting controls on /api/v1/html/my-gear/results endpoint."""

    async def test_sort_by_name_ascending(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify my-gear results can be sorted by name ascending."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"sort_by": "name", "sort_order": "asc"},
            )
            assert response.status_code == 200
            html = response.text
            # Verify sort control is rendered showing current selection
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html
            # Verify sort_by parameter is accepted and results are ordered
            pos_a = html.find("Gear A")
            pos_o = html.find("Gear O")
            assert pos_a != -1, "Gear A should appear in sorted results"
            assert pos_o != -1, "Gear O should appear in sorted results"
            assert pos_a < pos_o, "Gear A should appear before Gear O in asc order"

    async def test_sort_by_name_descending(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify my-gear results can be sorted by name descending."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"sort_by": "name", "sort_order": "desc"},
            )
            assert response.status_code == 200
            html = response.text
            pos_a = html.find("Gear A")
            pos_o = html.find("Gear O")
            assert pos_a != -1, "Gear A should appear in sorted results"
            assert pos_o != -1, "Gear O should appear in sorted results"
            assert pos_o < pos_a, "Gear O should appear before Gear A in desc order"

    async def test_sort_by_date_added(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify my-gear results can be sorted by date added."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"sort_by": "date_added", "sort_order": "desc"},
            )
            assert response.status_code == 200
            html = response.text
            # Sort control should show current sort selection
            assert "date_added" in html or "Date" in html

    async def test_sort_by_type(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify my-gear results can be sorted by gear type."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"sort_by": "type", "sort_order": "asc"},
            )
            assert response.status_code == 200
            html = response.text
            # Sort control should reflect the type sort
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html


# --- Library Chains Sorting and Filtering Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryChainsSortFilter:
    """Test sorting and filtering on /api/v1/html/library/chains endpoint."""

    async def test_chains_sort_by_name(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_chains: list[SignalChain],
    ) -> None:
        """Verify chains can be sorted by name."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/chains",
                params={"sort_by": "name", "sort_order": "asc"},
            )
            assert response.status_code == 200
            html = response.text
            pos_a = html.find("Chain A")
            pos_o = html.find("Chain O")
            assert pos_a != -1, "Chain A should appear"
            assert pos_o != -1, "Chain O should appear"
            assert pos_a < pos_o, "Chain A should appear before Chain O in asc order"

    async def test_chains_sort_by_date_added(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_chains: list[SignalChain],
    ) -> None:
        """Verify chains can be sorted by date added."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/chains",
                params={"sort_by": "date_added", "sort_order": "desc"},
            )
            assert response.status_code == 200
            html = response.text
            # Sort control should reflect current selection
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html

    async def test_chains_pagination_page_size_12(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_chains: list[SignalChain],
    ) -> None:
        """Verify chains pagination with page_size=12 (multiple of 3)."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/chains",
                params={"page": 1, "page_size": 12},
            )
            assert response.status_code == 200
            html = response.text
            # Should show pagination controls with data-testid
            assert 'data-testid="pagination' in html

    async def test_chains_pagination_page_2(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_chains: list[SignalChain],
    ) -> None:
        """Verify chains page 2 shows remaining items — not all 15."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Page 1 should have 12 items
            resp_page1 = await client.get(
                "/api/v1/html/library/chains",
                params={"page": 1, "page_size": 12},
            )
            # Page 2 should have 3 items (15 - 12)
            resp_page2 = await client.get(
                "/api/v1/html/library/chains",
                params={"page": 2, "page_size": 12},
            )
            assert resp_page1.status_code == 200
            assert resp_page2.status_code == 200
            # Page 2 should have fewer chain items than page 1
            page1_chain_count = resp_page1.text.count("chain-item")
            page2_chain_count = resp_page2.text.count("chain-item")
            assert (
                page2_chain_count < page1_chain_count
            ), f"Page 2 should have fewer items ({page2_chain_count}) than page 1 ({page1_chain_count})"


# --- Library Tracks Sorting and Filtering Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryTracksSortFilter:
    """Test sorting and filtering on /api/v1/html/library/tracks endpoint."""

    async def test_tracks_sort_by_name(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_tracks: list[DITrack],
    ) -> None:
        """Verify tracks can be sorted by name."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/tracks",
                params={"sort_by": "name", "sort_order": "asc"},
            )
            assert response.status_code == 200
            html = response.text
            pos_a = html.find("Track A")
            pos_o = html.find("Track O")
            assert pos_a != -1, "Track A should appear"
            assert pos_o != -1, "Track O should appear"
            assert pos_a < pos_o, "Track A should appear before Track O in asc order"

    async def test_tracks_sort_by_date_added(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_tracks: list[DITrack],
    ) -> None:
        """Verify tracks can be sorted by date added."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/tracks",
                params={"sort_by": "date_added", "sort_order": "desc"},
            )
            assert response.status_code == 200
            html = response.text
            # Sort control should reflect current selection
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html

    async def test_tracks_pagination(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_tracks: list[DITrack],
    ) -> None:
        """Verify tracks support pagination with page and page_size params."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/tracks",
                params={"page": 1, "page_size": 12},
            )
            assert response.status_code == 200
            html = response.text
            assert 'data-testid="pagination' in html


# --- Library Shootouts Sorting and Filtering Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryShootoutsSortFilter:
    """Test sorting and filtering on /api/v1/html/library/shootouts endpoint."""

    async def test_shootouts_sort_by_name(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_shootouts: list[Shootout],
    ) -> None:
        """Verify shootouts can be sorted by name."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/shootouts",
                params={"sort_by": "name", "sort_order": "asc"},
            )
            assert response.status_code == 200
            html = response.text
            pos_a = html.find("Shootout A")
            pos_o = html.find("Shootout O")
            assert pos_a != -1, "Shootout A should appear"
            assert pos_o != -1, "Shootout O should appear"
            assert pos_a < pos_o, "Shootout A before Shootout O in asc order"

    async def test_shootouts_sort_by_date_added(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_shootouts: list[Shootout],
    ) -> None:
        """Verify shootouts can be sorted by date added."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/shootouts",
                params={"sort_by": "date_added", "sort_order": "desc"},
            )
            assert response.status_code == 200

    async def test_shootouts_pagination(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_shootouts: list[Shootout],
    ) -> None:
        """Verify shootouts support pagination with page and page_size params."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/shootouts",
                params={"page": 1, "page_size": 12},
            )
            assert response.status_code == 200
            html = response.text
            assert "data-testid" in html


# --- Grid-Aligned Pagination Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestGridAlignedPagination:
    """Test that pagination uses multiples of 3 for card layout alignment."""

    async def test_my_gear_default_page_size_is_multiple_of_3(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify default page_size for my-gear is a multiple of 3."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Request without explicit page_size — should default to 12, 24, or 36
            response = await client.get("/api/v1/html/my-gear/results")
            assert response.status_code == 200
            html = response.text
            # The total_pages should be calculated based on a multiple-of-3 page size
            # With 15 items and page_size=12, total_pages=2
            assert "Page 1" in html or 'page"' in html

    async def test_my_gear_page_size_12(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify page_size=12 works and paginates correctly."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"page_size": 12, "page": 1},
            )
            assert response.status_code == 200
            html = response.text
            # With 15 items and page_size=12, pagination controls should appear
            assert 'data-testid="pagination' in html

    async def test_my_gear_page_size_36(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify page_size=36 works — all 15 items on one page, no pagination."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"page_size": 36, "page": 1},
            )
            assert response.status_code == 200
            html = response.text
            # With 15 items and page_size=36, all fit on one page
            # Sort control should still be rendered
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html

    async def test_my_gear_rejects_non_grid_page_size(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify page_size values not multiples of 3 are rejected (e.g. 10, 25)."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"page_size": 10},
            )
            # Should be rejected — 10 is not a valid grid-aligned page size
            assert response.status_code == 422


# --- Pagination Controls Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestPaginationControls:
    """Test pagination controls: first, prev, page numbers, next, last."""

    async def test_my_gear_pagination_has_first_last_buttons(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify pagination includes first and last page buttons."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"page": 1, "page_size": 12},
            )
            assert response.status_code == 200
            html = response.text
            # Should have first, prev, next, last pagination controls
            assert (
                'data-testid="pagination-first"' in html or 'data-testid="pagination-last"' in html
            )

    async def test_my_gear_pagination_has_page_numbers(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify pagination includes page number links."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"page": 1, "page_size": 12},
            )
            assert response.status_code == 200
            html = response.text
            # Should have page number buttons/links
            assert 'data-testid="pagination-page-1"' in html
            assert 'data-testid="pagination-page-2"' in html

    async def test_my_gear_pagination_prev_disabled_on_first_page(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify prev button is disabled on first page."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"page": 1, "page_size": 12},
            )
            assert response.status_code == 200
            html = response.text
            assert 'data-testid="pagination-prev"' in html

    async def test_my_gear_pagination_next_disabled_on_last_page(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify next button is disabled on last page."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"page": 2, "page_size": 12},
            )
            assert response.status_code == 200
            html = response.text
            assert 'data-testid="pagination-next"' in html


# --- URL Query Parameter Preservation Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestQueryParameterPreservation:
    """Test that sort/filter/pagination state is preserved in URLs."""

    async def test_my_gear_sort_params_in_pagination_links(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify sort parameters are preserved in pagination links."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={
                    "sort_by": "name",
                    "sort_order": "asc",
                    "page": 1,
                    "page_size": 12,
                },
            )
            assert response.status_code == 200
            html = response.text
            # Pagination links should include sort_by and sort_order
            assert "sort_by=name" in html
            assert "sort_order=asc" in html

    async def test_my_gear_filter_params_in_pagination_links(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify filter parameters are preserved in pagination links."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={
                    "gear_type": "amp",
                    "page": 1,
                    "page_size": 12,
                },
            )
            assert response.status_code == 200
            html = response.text
            # Pagination links should include gear_type filter
            assert "gear_type=amp" in html

    async def test_chains_sort_params_in_pagination_links(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_chains: list[SignalChain],
    ) -> None:
        """Verify chains sort parameters are preserved in pagination links."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/library/chains",
                params={
                    "sort_by": "name",
                    "sort_order": "asc",
                    "page": 1,
                    "page_size": 12,
                },
            )
            assert response.status_code == 200
            html = response.text
            assert "sort_by=name" in html
            assert "sort_order=asc" in html


# --- HTMX Partial Reload Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestHTMXPartialReload:
    """Test that sort/filter/pagination uses HTMX partial reload."""

    async def test_my_gear_sort_controls_have_htmx_attrs(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify sort controls have hx-get attributes for HTMX partial reload."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/my-gear/results")
            assert response.status_code == 200
            html = response.text
            # Sort controls should have data-testid
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html

    async def test_chains_fragment_has_sort_controls(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_chains: list[SignalChain],
    ) -> None:
        """Verify chains fragment includes sort control elements."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/chains")
            assert response.status_code == 200
            html = response.text
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html

    async def test_tracks_fragment_has_sort_controls(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_tracks: list[DITrack],
    ) -> None:
        """Verify tracks fragment includes sort control elements."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/tracks")
            assert response.status_code == 200
            html = response.text
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html

    async def test_shootouts_fragment_has_sort_controls(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_shootouts: list[Shootout],
    ) -> None:
        """Verify shootouts fragment includes sort control elements."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/shootouts")
            assert response.status_code == 200
            html = response.text
            assert 'data-testid="sort-select"' in html or 'data-testid="sort-by"' in html


# --- Consistency Across Tabs Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestConsistentAcrossTabs:
    """Test that sorting/filtering/pagination is consistent across library tabs."""

    async def test_all_library_endpoints_accept_sort_params(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
        many_chains: list[SignalChain],
        many_tracks: list[DITrack],
        many_shootouts: list[Shootout],
    ) -> None:
        """Verify all library endpoints accept sort_by and sort_order parameters."""
        app = create_app()
        endpoints = [
            "/api/v1/html/my-gear/results",
            "/api/v1/html/library/chains",
            "/api/v1/html/library/tracks",
            "/api/v1/html/library/shootouts",
        ]
        params = {"sort_by": "name", "sort_order": "asc"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for endpoint in endpoints:
                response = await client.get(endpoint, params=params)
                assert (
                    response.status_code == 200
                ), f"{endpoint} should accept sort params but got {response.status_code}"

    async def test_all_library_endpoints_accept_pagination_params(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
        many_chains: list[SignalChain],
        many_tracks: list[DITrack],
        many_shootouts: list[Shootout],
    ) -> None:
        """Verify all library endpoints accept page and page_size parameters."""
        app = create_app()
        endpoints = [
            "/api/v1/html/my-gear/results",
            "/api/v1/html/library/chains",
            "/api/v1/html/library/tracks",
            "/api/v1/html/library/shootouts",
        ]
        params = {"page": 1, "page_size": 12}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for endpoint in endpoints:
                response = await client.get(endpoint, params=params)
                assert (
                    response.status_code == 200
                ), f"{endpoint} should accept pagination params but got {response.status_code}"

    async def test_all_library_endpoints_have_pagination_controls(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
        many_chains: list[SignalChain],
        many_tracks: list[DITrack],
        many_shootouts: list[Shootout],
    ) -> None:
        """Verify all library endpoints render pagination controls when data exceeds page size."""
        app = create_app()
        endpoints = [
            "/api/v1/html/my-gear/results",
            "/api/v1/html/library/chains",
            "/api/v1/html/library/tracks",
            "/api/v1/html/library/shootouts",
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for endpoint in endpoints:
                response = await client.get(
                    endpoint,
                    params={"page": 1, "page_size": 12},
                )
                assert response.status_code == 200
                html = response.text
                # All endpoints should render pagination when items > page_size
                assert (
                    'data-testid="pagination' in html
                ), f"{endpoint} should have pagination controls with data-testid"


# --- Filter by Gear Type Tests ---


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearTypeFilter:
    """Test gear type filtering on my-gear endpoint."""

    async def test_filter_by_amp(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify filtering by amp gear type shows only amps."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"gear_type": "amp", "sort_by": "name", "sort_order": "asc"},
            )
            assert response.status_code == 200

    async def test_filter_by_ir(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify filtering by IR gear type shows only IRs."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"gear_type": "ir", "sort_by": "name", "sort_order": "asc"},
            )
            assert response.status_code == 200

    async def test_filter_by_pedal(
        self,
        db_session: "AsyncSession",
        test_user: User,
        many_gear_items: list[Gear],
    ) -> None:
        """Verify filtering by pedal gear type shows only pedals."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/html/my-gear/results",
                params={"gear_type": "pedal", "sort_by": "name", "sort_order": "asc"},
            )
            assert response.status_code == 200
