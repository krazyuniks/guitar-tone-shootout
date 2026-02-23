"""Integration tests for T142: Shootout Detail Page Enhancement.

Tests that the shootout detail HTMX fragment endpoint provides complete
information: title, status, creation date, creator, signal chains with
gear names, DI track info, processing status, owner actions (edit title,
delete), and share link.

Verifies:
- GET /api/v1/html/shootouts/{id} returns full detail fragment
- Fragment includes status badge, creation date, creator username
- Signal chains section shows chain names from DB
- DI track section shows track name and duration
- Processing status visual indicator per status value
- Owner actions: edit title, delete (with data-testid)
- Share link element present with data-testid
- Non-owner cannot see owner actions
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from gts.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.di_track import DITrack
from webapp.adapters.persistence.models.shootout import (
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.main import create_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(db_session: "AsyncSession") -> User:
    """Create a test user for detail page tests."""
    user = User(
        id=uuid4(),
        username="detailuser",
        email="detail@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: "AsyncSession") -> User:
    """Create a second user for ownership tests."""
    user = User(
        id=uuid4(),
        username="otherdetailuser",
        email="otherdetail@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_di_track(db_session: "AsyncSession", test_user: User) -> DITrack:
    """Create a test DI track for shootout."""
    di_track = DITrack(
        user_id=test_user.id,
        name="My Clean DI Recording",
        file_path="/path/to/clean_di.wav",
        original_filename="clean_di.wav",
        duration_seconds=45.5,
        sample_rate=48000,
    )
    db_session.add(di_track)
    await db_session.flush()
    await db_session.refresh(di_track)
    return di_track


@pytest.fixture
async def test_signal_chains(db_session: "AsyncSession", test_user: User) -> list[SignalChain]:
    """Create test signal chains for shootout."""
    chain1 = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Mesa Mark V Clean",
        platform=Platform.NAM,
    )
    chain2 = SignalChain(
        id=uuid4(),
        user_id=test_user.id,
        name="Fender Twin Crunch",
        platform=Platform.NAM,
    )
    db_session.add_all([chain1, chain2])
    await db_session.flush()
    await db_session.refresh(chain1)
    await db_session.refresh(chain2)
    return [chain1, chain2]


@pytest.fixture
async def test_shootout(
    db_session: "AsyncSession",
    test_user: User,
    test_di_track: DITrack,
    test_signal_chains: list[SignalChain],
) -> Shootout:
    """Create a test shootout with chains linked."""
    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        di_track_id=test_di_track.id,
        name="My Amp Comparison",
        description="Comparing clean tones",
        status=ShootoutStatus.PENDING,
    )
    db_session.add(shootout)
    await db_session.flush()

    # Add shootout chains linking to signal chains
    for i, chain in enumerate(test_signal_chains):
        sc = ShootoutChain(
            id=uuid4(),
            shootout_id=shootout.id,
            signal_chain_id=chain.id,
            position=i,
            label=f"Chain {i + 1}",
        )
        db_session.add(sc)

    await db_session.commit()
    await db_session.refresh(shootout)
    return shootout


# ---------------------------------------------------------------------------
# 1. HTMX Fragment Endpoint Exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutDetailFragmentEndpoint:
    """Verify GET /api/v1/html/shootouts/{id} returns the detail fragment."""

    async def test_fragment_endpoint_exists_and_returns_200(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """The HTMX fragment endpoint for shootout detail must exist."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_fragment_returns_404_for_missing_shootout(
        self,
        db_session: "AsyncSession",
        test_user: User,
    ) -> None:
        """Fragment should 404 for non-existent shootout."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{uuid4()}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 2. Title, Status, Creation Date, Creator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutDetailShowsMetadata:
    """Verify the fragment includes title, status, creation date, creator."""

    async def test_fragment_shows_shootout_title(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must render the shootout name."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert "My Amp Comparison" in html

    async def test_fragment_shows_status_badge(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must show a status badge with data-testid."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="status-badge"' in html

    async def test_fragment_shows_creator_username(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must show the creator's username."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="creator-name"' in html
        assert "detailuser" in html

    async def test_fragment_shows_creation_date(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must show relative creation time."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="creation-date"' in html


# ---------------------------------------------------------------------------
# 3. Signal Chains Section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutDetailSignalChains:
    """Verify signal chains section lists all chains with names."""

    async def test_fragment_shows_signal_chain_names(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must show each signal chain's name."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert "Mesa Mark V Clean" in html
        assert "Fender Twin Crunch" in html

    async def test_fragment_has_segments_section_testid(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must have segments section with data-testid."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="segments-section"' in html


# ---------------------------------------------------------------------------
# 4. DI Track Section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutDetailDITrack:
    """Verify DI track section shows name and duration."""

    async def test_fragment_shows_di_track_name(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must show the DI track name."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert "My Clean DI Recording" in html

    async def test_fragment_shows_di_track_duration(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must show the DI track duration."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="di-track-section"' in html
        assert 'data-testid="di-track-duration"' in html


# ---------------------------------------------------------------------------
# 5. Processing Status Indicator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutDetailProcessingStatus:
    """Verify processing status visual indicator per status value."""

    async def test_pending_status_shows_indicator(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Pending shootout must show pending processing indicator."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="processing-placeholder"' in html
        assert "Pending" in html or "pending" in html

    async def test_completed_status_shows_video_container(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_di_track: DITrack,
        test_signal_chains: list[SignalChain],
    ) -> None:
        """Completed shootout with output_path must show video container."""
        shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            di_track_id=test_di_track.id,
            name="Completed Shootout",
            status=ShootoutStatus.COMPLETED,
            output_path="/media/shootout-output.mp4",
        )
        db_session.add(shootout)
        for i, chain in enumerate(test_signal_chains):
            sc = ShootoutChain(
                id=uuid4(),
                shootout_id=shootout.id,
                signal_chain_id=chain.id,
                position=i,
                label=f"Chain {i + 1}",
            )
            db_session.add(sc)
        await db_session.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="video-container"' in html


# ---------------------------------------------------------------------------
# 6. Owner Actions: Edit Title, Delete Shootout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutDetailOwnerActions:
    """Verify owner can see edit-title and delete actions."""

    async def test_owner_sees_edit_title_action(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Owner should see an edit-title action element."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="edit-title-btn"' in html

    async def test_owner_sees_delete_action(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Owner should see a delete action element."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="delete-shootout-btn"' in html

    async def test_non_owner_cannot_see_owner_actions(
        self,
        db_session: "AsyncSession",
        test_user: User,
        other_user: User,
        test_di_track: DITrack,
        test_signal_chains: list[SignalChain],
    ) -> None:
        """Non-owner should not see edit or delete actions.

        We create a shootout owned by test_user, then view it as other_user.
        The endpoint should either return 404 (ownership check) or render
        without owner actions. Since the page requires ownership for access,
        this should be a 404.
        """
        # The shootout belongs to test_user
        shootout = Shootout(
            id=uuid4(),
            user_id=test_user.id,
            di_track_id=test_di_track.id,
            name="Not My Shootout",
            status=ShootoutStatus.PENDING,
        )
        db_session.add(shootout)
        for i, chain in enumerate(test_signal_chains):
            sc = ShootoutChain(
                id=uuid4(),
                shootout_id=shootout.id,
                signal_chain_id=chain.id,
                position=i,
                label=f"Chain {i + 1}",
            )
            db_session.add(sc)
        await db_session.commit()

        # Override auth to other_user
        from webapp.auth.dependencies import set_user_override

        set_user_override(other_user)

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{shootout.id}")

        # Should be 404 (ownership check returns not found)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 7. Share Link
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutDetailShareLink:
    """Verify share link functionality is present."""

    async def test_share_link_element_present(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """Fragment must include a share link element with data-testid."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="share-link-btn"' in html


# ---------------------------------------------------------------------------
# 8. Delete Shootout API Endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutDeleteEndpoint:
    """Verify DELETE endpoint for shootout exists with owner check."""

    async def test_delete_endpoint_exists(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """DELETE /api/v1/html/shootouts/{id} should delete and return redirect."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 200
        # Should include HX-Redirect to shootouts list
        assert (
            "hx-redirect" in response.headers.get("hx-redirect", "").lower()
            or response.headers.get("HX-Redirect", "") != ""
        )

    async def test_delete_endpoint_returns_404_for_non_owner(
        self,
        db_session: "AsyncSession",
        test_user: User,
        other_user: User,
        test_shootout: Shootout,
    ) -> None:
        """DELETE should return 404 if user doesn't own the shootout."""
        from webapp.auth.dependencies import set_user_override

        set_user_override(other_user)

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(f"/api/v1/html/shootouts/{test_shootout.id}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 9. Edit Title API Endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutEditTitleEndpoint:
    """Verify PATCH endpoint for editing shootout title."""

    async def test_edit_title_endpoint_exists(
        self,
        db_session: "AsyncSession",
        test_user: User,
        test_shootout: Shootout,
    ) -> None:
        """PATCH /api/v1/html/shootouts/{id}/title should update the title."""
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/html/shootouts/{test_shootout.id}/title",
                data={"name": "Updated Shootout Name"},
            )

        assert response.status_code == 200
        html = response.text
        assert "Updated Shootout Name" in html

    async def test_edit_title_returns_404_for_non_owner(
        self,
        db_session: "AsyncSession",
        test_user: User,
        other_user: User,
        test_shootout: Shootout,
    ) -> None:
        """PATCH title should return 404 if user doesn't own the shootout."""
        from webapp.auth.dependencies import set_user_override

        set_user_override(other_user)

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/html/shootouts/{test_shootout.id}/title",
                data={"name": "Hacked Title"},
            )

        assert response.status_code == 404
