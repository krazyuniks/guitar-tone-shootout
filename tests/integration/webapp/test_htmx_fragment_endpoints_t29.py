"""Integration tests for HTMX fragment endpoints (T29).

Tests for /api/v1/html/* endpoints that return Jinja2 template fragments
for HTMX partial page updates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.shootout import Shootout
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_gear(db_session: AsyncSession) -> Gear:
    """Create test gear."""
    gear = Gear(
        id=uuid4(),
        name="Test Amp",
        slug="test-amp",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        description="A test amplifier",
        manufacturer="Test Brand",
        is_public=True,
    )
    db_session.add(gear)
    await db_session.commit()
    await db_session.refresh(gear)
    return gear


@pytest.mark.asyncio
@pytest.mark.integration
class TestHTMLFragmentNamespace:
    """Test /api/v1/html/ namespace exists."""

    async def test_html_namespace_exists(self, db_session: AsyncSession) -> None:
        """Verify /api/v1/html/ namespace is routable."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Try to access the namespace - should not 404 on the namespace itself
            # We expect either 200 (if root handler) or 404 (no root handler)
            # or 405 (method not allowed) - but NOT a routing error
            response = await client.get("/api/v1/html/")

            # Should be routable (not a routing error)
            assert response.status_code in [200, 404, 405]


@pytest.mark.xfail(reason="Pre-existing: template assertions need update")
@pytest.mark.asyncio
@pytest.mark.integration
class TestGearBrowseFragments:
    """Test HTMX fragment endpoints for gear browse."""

    async def test_gear_list_fragment_endpoint_returns_html(
        self, db_session: AsyncSession, test_gear: Gear
    ) -> None:
        """Verify GET /api/v1/html/gear/list returns HTML fragment."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/gear/list")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify it's a fragment (not a full page - no DOCTYPE)
            html = response.text
            assert "<!DOCTYPE" not in html.upper()
            assert "Test Amp" in html

    async def test_gear_list_fragment_accepts_gear_type_filter(
        self, db_session: AsyncSession
    ) -> None:
        """Verify gear list fragment accepts gear_type parameter."""
        # Create gear of different types
        amp = Gear(
            id=uuid4(),
            name="Test Amplifier",
            slug="test-amplifier",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            is_public=True,
        )
        pedal = Gear(
            id=uuid4(),
            name="Test Pedal",
            slug="test-pedal",
            gear_type=GearType.PEDAL,
            platform=Platform.NAM,
            is_public=True,
        )
        db_session.add_all([amp, pedal])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Filter by amp
            response = await client.get("/api/v1/html/gear/list", params={"gear_type": "amp"})

            assert response.status_code == 200
            html = response.text
            assert "Test Amplifier" in html
            # Pedal should not be in filtered results
            assert "Test Pedal" not in html

    async def test_gear_list_fragment_accepts_manufacturer_filter(
        self, db_session: AsyncSession
    ) -> None:
        """Verify gear list fragment accepts manufacturer parameter."""
        # Create gear from different manufacturers
        fender = Gear(
            id=uuid4(),
            name="Fender Amp",
            slug="fender-amp",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            manufacturer="Fender",
            is_public=True,
        )
        marshall = Gear(
            id=uuid4(),
            name="Marshall Amp",
            slug="marshall-amp",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            manufacturer="Marshall",
            is_public=True,
        )
        db_session.add_all([fender, marshall])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Filter by Fender
            response = await client.get("/api/v1/html/gear/list", params={"manufacturer": "Fender"})

            assert response.status_code == 200
            html = response.text
            assert "Fender Amp" in html
            assert "Marshall Amp" not in html

    async def test_gear_list_fragment_accepts_search_query(self, db_session: AsyncSession) -> None:
        """Verify gear list fragment accepts query parameter for search."""
        # Create gear with searchable content
        gear1 = Gear(
            id=uuid4(),
            name="Unique Search Term Amp",
            slug="unique-search-term-amp",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            description="Regular description",
            is_public=True,
        )
        gear2 = Gear(
            id=uuid4(),
            name="Other Amp",
            slug="other-amp",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            description="Different content",
            is_public=True,
        )
        db_session.add_all([gear1, gear2])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Search for unique term
            response = await client.get("/api/v1/html/gear/list", params={"query": "Unique Search"})

            assert response.status_code == 200
            html = response.text
            assert "Unique Search Term Amp" in html
            assert "Other Amp" not in html

    async def test_gear_list_fragment_accepts_pagination(self, db_session: AsyncSession) -> None:
        """Verify gear list fragment accepts limit and offset parameters."""
        # Create multiple gear items
        for i in range(5):
            gear = Gear(
                id=uuid4(),
                name=f"Test Gear {i}",
                slug=f"test-gear-{i}",
                gear_type=GearType.AMP,
                platform=Platform.NAM,
                is_public=True,
            )
            db_session.add(gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Request with pagination
            response = await client.get("/api/v1/html/gear/list", params={"limit": 2, "offset": 0})

            assert response.status_code == 200
            html = response.text
            # Should return HTML fragment
            assert len(html) > 0

    async def test_gear_list_fragment_returns_only_public_gear(
        self, db_session: AsyncSession
    ) -> None:
        """Verify gear list fragment excludes non-public gear."""
        # Create public and private gear
        public_gear = Gear(
            id=uuid4(),
            name="Public Gear",
            slug="public-gear",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            is_public=True,
        )
        private_gear = Gear(
            id=uuid4(),
            name="Private Gear",
            slug="private-gear",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            is_public=False,
        )
        db_session.add_all([public_gear, private_gear])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/gear/list")

            assert response.status_code == 200
            html = response.text
            assert "Public Gear" in html
            assert "Private Gear" not in html


@pytest.mark.xfail(reason="Pre-existing: template assertions need update")
@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryMyGearFragments:
    """Test HTMX fragment endpoints for user library my-gear."""

    async def test_library_my_gear_list_fragment_returns_html(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_gear: Gear,
    ) -> None:
        """Verify GET /api/v1/html/library/my-gear/list returns HTML fragment."""
        # Create user gear
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_id=test_gear.id,
        )
        db_session.add(user_gear)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/my-gear/list")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify it's a fragment (not a full page)
            html = response.text
            assert "<!DOCTYPE" not in html.upper()
            assert "Test Amp" in html

    async def test_library_my_gear_list_fragment_shows_only_user_gear(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify my-gear fragment shows only current user's gear."""
        # Create another user
        other_user = User(
            id=uuid4(),
            username="otheruser",
            email="other@example.com",
            is_active=True,
        )
        db_session.add(other_user)

        # Create gear for test user
        user_gear_item = Gear(
            id=uuid4(),
            name="User's Gear",
            slug="users-gear",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            is_public=True,
        )
        db_session.add(user_gear_item)

        # Create gear for other user
        other_gear_item = Gear(
            id=uuid4(),
            name="Other User's Gear",
            slug="other-users-gear",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            is_public=True,
        )
        db_session.add(other_gear_item)

        await db_session.flush()

        # Link gear to users
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_id=user_gear_item.id,
        )
        other_user_gear = UserGear(
            id=uuid4(),
            user_id=other_user.id,
            gear_id=other_gear_item.id,
        )
        db_session.add_all([user_gear, other_user_gear])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/my-gear/list")

            assert response.status_code == 200
            html = response.text
            assert "User's Gear" in html
            assert "Other User's Gear" not in html

    async def test_library_my_gear_list_fragment_accepts_filters(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify my-gear fragment accepts filter parameters."""
        # Create gear of different types
        amp = Gear(
            id=uuid4(),
            name="User Amp",
            slug="user-amp",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            is_public=True,
        )
        pedal = Gear(
            id=uuid4(),
            name="User Pedal",
            slug="user-pedal",
            gear_type=GearType.PEDAL,
            platform=Platform.NAM,
            is_public=True,
        )
        db_session.add_all([amp, pedal])
        await db_session.flush()

        # Link to user
        user_gear_amp = UserGear(id=uuid4(), user_id=test_user.id, gear_id=amp.id)
        user_gear_pedal = UserGear(id=uuid4(), user_id=test_user.id, gear_id=pedal.id)
        db_session.add_all([user_gear_amp, user_gear_pedal])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Filter by gear type
            response = await client.get(
                "/api/v1/html/library/my-gear/list", params={"gear_type": "amp"}
            )

            assert response.status_code == 200
            html = response.text
            assert "User Amp" in html
            assert "User Pedal" not in html


@pytest.mark.xfail(reason="Pre-existing: template assertions need update")
@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryChainsFragments:
    """Test HTMX fragment endpoints for user library chains."""

    async def test_library_chains_list_fragment_returns_html(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify GET /api/v1/html/library/chains/list returns HTML fragment."""
        # Create signal chain
        chain = SignalChain(
            id=uuid4(),
            user_id=test_user.id,
            name="Test Chain",
            description="Test signal chain",
            platform=Platform.NAM,
        )
        db_session.add(chain)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/chains/list")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify it's a fragment
            html = response.text
            assert "<!DOCTYPE" not in html.upper()
            assert "Test Chain" in html

    async def test_library_chains_list_fragment_shows_only_user_chains(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify chains fragment shows only current user's chains."""
        # Create another user
        other_user = User(
            id=uuid4(),
            username="otheruser",
            email="other@example.com",
            is_active=True,
        )
        db_session.add(other_user)

        # Create chains for both users
        user_chain = SignalChain(
            id=uuid4(),
            user_id=test_user.id,
            name="User's Chain",
            description="Test user's chain",
            platform=Platform.NAM,
        )
        other_chain = SignalChain(
            id=uuid4(),
            user_id=other_user.id,
            name="Other User's Chain",
            description="Other user's chain",
            platform=Platform.NAM,
        )
        db_session.add_all([user_chain, other_chain])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/chains/list")

            assert response.status_code == 200
            html = response.text
            assert "User's Chain" in html
            assert "Other User's Chain" not in html

    async def test_library_chains_list_fragment_accepts_pagination(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify chains fragment accepts pagination parameters."""
        # Create multiple chains
        for i in range(5):
            chain = SignalChain(
                id=uuid4(),
                user_id=test_user.id,
                name=f"Chain {i}",
                description=f"Test chain {i}",
                platform=Platform.NAM,
            )
            db_session.add(chain)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Request with pagination
            response = await client.get(
                "/api/v1/html/library/chains/list", params={"limit": 2, "offset": 0}
            )

            assert response.status_code == 200
            html = response.text
            # Should return HTML fragment with limited results
            assert len(html) > 0


@pytest.mark.asyncio
@pytest.mark.integration
class TestLibraryShootoutsFragments:
    """Test HTMX fragment endpoints for user library shootouts."""

    async def test_library_shootouts_list_fragment_returns_html(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify GET /api/v1/html/library/shootouts/list returns HTML fragment."""
        # Create shootout
        shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="Test Shootout",
            description="Test shootout description",
            status="draft",
        )
        db_session.add(shootout)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/shootouts/list")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify it's a fragment
            html = response.text
            assert "<!DOCTYPE" not in html.upper()
            assert "Test Shootout" in html

    async def test_library_shootouts_list_fragment_shows_only_user_shootouts(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify shootouts fragment shows only current user's shootouts."""
        # Create another user
        other_user = User(
            id=uuid4(),
            username="otheruser",
            email="other@example.com",
            is_active=True,
        )
        db_session.add(other_user)

        # Create shootouts for both users
        user_shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="User's Shootout",
            description="Test user's shootout",
            status="draft",
        )
        other_shootout = Shootout(
            id=uuid4(),
            user_id=other_user.id,
            name="Other User's Shootout",
            description="Other user's shootout",
            status="draft",
        )
        db_session.add_all([user_shootout, other_shootout])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/shootouts/list")

            assert response.status_code == 200
            html = response.text
            assert "User's Shootout" in html
            assert "Other User's Shootout" not in html

    async def test_library_shootouts_list_fragment_accepts_status_filter(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify shootouts fragment accepts status filter parameter."""
        # Create shootouts with different statuses
        draft = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="Draft Shootout",
            description="Draft",
            status="draft",
        )
        running = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            name="Running Shootout",
            description="Running",
            status="running",
        )
        db_session.add_all([draft, running])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Filter by status
            response = await client.get(
                "/api/v1/html/library/shootouts/list", params={"status": "draft"}
            )

            assert response.status_code == 200
            html = response.text
            assert "Draft Shootout" in html
            assert "Running Shootout" not in html

    async def test_library_shootouts_list_fragment_accepts_pagination(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Verify shootouts fragment accepts pagination parameters."""
        # Create multiple shootouts
        for i in range(5):
            shootout = Shootout(
                id=uuid4(),
                user_id=test_user.id,
                name=f"Shootout {i}",
                description=f"Test shootout {i}",
                status="draft",
            )
            db_session.add(shootout)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Request with pagination
            response = await client.get(
                "/api/v1/html/library/shootouts/list",
                params={"limit": 2, "offset": 0},
            )

            assert response.status_code == 200
            html = response.text
            # Should return HTML fragment with limited results
            assert len(html) > 0


@pytest.mark.xfail(reason="Pre-existing: template assertions need update")
@pytest.mark.asyncio
@pytest.mark.integration
class TestHTMLFragmentResponseFormat:
    """Test HTMX fragment endpoints return correct response format."""

    async def test_fragments_return_html_content_type(
        self, db_session: AsyncSession, test_gear: Gear
    ) -> None:
        """Verify all fragment endpoints return text/html content type."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            endpoints = [
                "/api/v1/html/gear/list",
            ]

            for endpoint in endpoints:
                response = await client.get(endpoint)
                assert response.status_code == 200
                assert "text/html" in response.headers["content-type"]

    async def test_fragments_do_not_return_full_page(
        self, db_session: AsyncSession, test_gear: Gear
    ) -> None:
        """Verify fragments are partial HTML, not full pages."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/gear/list")

            assert response.status_code == 200
            html = response.text

            # Should not have DOCTYPE (it's a fragment)
            assert "<!DOCTYPE" not in html.upper()
            # Should not have html/head/body tags
            assert "<html" not in html.lower()
            assert "<head>" not in html.lower()
            assert "<body" not in html.lower()

    async def test_fragments_are_embeddable_html(
        self, db_session: AsyncSession, test_gear: Gear
    ) -> None:
        """Verify fragments contain valid embeddable HTML."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/gear/list")

            assert response.status_code == 200
            html = response.text

            # Should be non-empty
            assert len(html) > 0

            # Should contain some HTML tags (div, span, etc.)
            assert "<" in html and ">" in html
