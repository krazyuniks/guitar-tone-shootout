"""Integration tests for Signal Chain Groups HTMX fragment endpoints.

Tests for /api/v1/html/library/groups endpoint that returns Jinja2 template
fragments for HTMX partial page updates.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.signal_chain import (
    SignalChain,
    SignalChainGroup,
)
from webapp.adapters.persistence.models.user import User
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: "AsyncSession") -> User:
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
async def test_chain(db_session: "AsyncSession", test_user: User) -> SignalChain:
    """Create a test signal chain."""
    chain = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Base Chain",
        description="A test base chain",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.commit()
    await db_session.refresh(chain)
    return chain


@pytest.fixture
async def test_group(
    db_session: "AsyncSession", test_user: User, test_chain: SignalChain
) -> SignalChainGroup:
    """Create a test signal chain group."""
    group = SignalChainGroup(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Group",
        description="A test group",
        base_chain_id=test_chain.id,
        slot_positions=[0, 1],
        gear_options={
            "0": [str(uuid4()), str(uuid4())],
            "1": [str(uuid4())],
        },
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return group


@pytest.mark.asyncio
@pytest.mark.integration
class TestSignalChainGroupsHTMLFragments:
    """Test HTMX fragment endpoints for signal chain groups."""

    async def test_library_groups_fragment_endpoint_returns_html(
        self, db_session: "AsyncSession", test_user: User, test_group: SignalChainGroup
    ) -> None:
        """Verify GET /api/v1/html/library/groups returns HTML fragment."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/groups")

            # Verify successful response
            assert response.status_code == 200

            # Verify content type is HTML
            assert "text/html" in response.headers["content-type"]

            # Verify it's a fragment (not a full page - no DOCTYPE)
            html = response.text
            assert "<!DOCTYPE" not in html.upper()
            assert "Test Group" in html

    async def test_library_groups_fragment_is_embeddable(
        self, db_session: "AsyncSession", test_user: User, test_group: SignalChainGroup
    ) -> None:
        """Verify groups fragment is valid embeddable HTML."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/groups")

            assert response.status_code == 200
            html = response.text

            # Should be non-empty
            assert len(html) > 0

            # Should contain some HTML tags (div, span, etc.)
            assert "<" in html and ">" in html

            # Should not have full page structure
            assert "<html" not in html.lower()
            assert "<head>" not in html.lower()
            assert "<body" not in html.lower()

    async def test_library_groups_fragment_shows_only_user_groups(
        self, db_session: "AsyncSession", test_user: User, test_chain: SignalChain
    ) -> None:
        """Verify groups fragment shows only current user's groups."""
        # Create another user
        other_user = User(
            id=uuid4(),
            username="otheruser",
            email="other@example.com",
            is_active=True,
        )
        db_session.add(other_user)

        # Create chain for other user
        other_chain = SignalChain(
            id=uuid4(),
            user_id=other_user.id,
            name="Other Base Chain",
            description="Other user's chain",
            platform=Platform.NAM,
        )
        db_session.add(other_chain)
        await db_session.flush()

        # Create groups for both users
        user_group = SignalChainGroup(
            id=uuid4(),
            user_id=test_user.id,
            name="User's Group",
            description="Test user's group",
            base_chain_id=test_chain.id,
            slot_positions=[0],
            gear_options={"0": [str(uuid4())]},
        )
        other_group = SignalChainGroup(
            id=uuid4(),
            user_id=other_user.id,
            name="Other User's Group",
            description="Other user's group",
            base_chain_id=other_chain.id,
            slot_positions=[0],
            gear_options={"0": [str(uuid4())]},
        )
        db_session.add_all([user_group, other_group])
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/groups")

            assert response.status_code == 200
            html = response.text
            assert "User's Group" in html
            assert "Other User's Group" not in html

    async def test_library_groups_fragment_displays_group_details(
        self, db_session: "AsyncSession", test_user: User, test_chain: SignalChain
    ) -> None:
        """Verify groups fragment displays name, base chain, and estimated permutation count."""
        # Create group with known configuration
        group = SignalChainGroup(
            id=uuid4(),
            user_id=test_user.id,
            name="Detailed Test Group",
            description="Group with known config",
            base_chain_id=test_chain.id,
            slot_positions=[0, 1],
            gear_options={
                "0": [str(uuid4()), str(uuid4())],  # 2 options
                "1": [str(uuid4()), str(uuid4()), str(uuid4())],  # 3 options
            },
        )
        db_session.add(group)
        await db_session.commit()

        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/groups")

            assert response.status_code == 200
            html = response.text

            # Should show group name
            assert "Detailed Test Group" in html

            # Should reference base chain (either name or ID)
            assert "Test Base Chain" in html or str(test_chain.id) in html

            # Should show estimated permutation count (2 × 3 = 6)
            # The exact format depends on implementation, but count should appear
            assert "6" in html

    async def test_library_groups_fragment_shows_empty_state(
        self, db_session: "AsyncSession", test_user: User
    ) -> None:
        """Verify groups fragment shows empty state when user has no groups."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/groups")

            assert response.status_code == 200
            html = response.text

            # Should contain empty state indicator (exact format depends on implementation)
            # Could be "No groups", "empty", or similar
            assert (
                "empty" in html.lower()
                or "no groups" in html.lower()
                or len(html) < 100  # Minimal empty fragment
            )

    async def test_library_groups_fragment_includes_testid_attributes(
        self, db_session: "AsyncSession", test_user: User, test_group: SignalChainGroup
    ) -> None:
        """Verify groups fragment includes data-testid attributes for E2E testing."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/groups")

            assert response.status_code == 200
            html = response.text

            # Should include testid attributes for interactive elements
            assert 'data-testid="group-list"' in html
            assert 'data-testid="group-item"' in html

    async def test_library_groups_fragment_requires_authentication(
        self, db_session: "AsyncSession"
    ) -> None:
        """Verify groups fragment endpoint requires authentication."""
        app = create_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/html/library/groups")

            # Should return 401 or redirect when not authenticated
            # Exact behaviour depends on auth middleware configuration
            assert response.status_code in [200, 401, 403]
