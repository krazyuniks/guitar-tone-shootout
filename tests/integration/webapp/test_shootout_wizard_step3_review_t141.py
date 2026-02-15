"""Integration tests for shootout creation wizard Step 3: Review, Submit, Validation (T141).

Tests the POST /api/v1/html/shootout-create endpoint for:
- Chain count validation (minimum 2, maximum 20)
- DI track required validation
- Successful creation with valid data
- Error responses for invalid submissions
- Redirect on success (HX-Redirect header)

Acceptance criteria tested:
- Validation: minimum 2 chains, maximum 20 chains
- Validation: DI track required
- Validation errors returned inline (not alert dialogs) — HTTP 422 with detail
- Submit button creates shootout via POST
- On success: redirect to shootout detail page (HX-Redirect)
- On error: show error message, stay on step 3 (422 status)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.shootout import DITrack, Shootout
from webapp.adapters.persistence.models.signal_chain import SignalChain as SignalChainModel
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.html import router

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with html router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for wizard step 3 tests."""
    user = User(username="step3user", email="step3@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def di_track(db_session: AsyncSession, test_user: User) -> DITrack:
    """Create a DI track for the test user."""
    track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Test DI Track",
        file_path="/audio/test_di.wav",
        original_filename="test_di.wav",
        duration_seconds=60.0,
        sample_rate=48000,
        guitar="Fender Stratocaster",
    )
    db_session.add(track)
    await db_session.flush()
    return track


@pytest.fixture
async def signal_chains(db_session: AsyncSession, test_user: User) -> list[SignalChainModel]:
    """Create signal chains for testing (5 chains)."""
    chains = []
    for i in range(5):
        chain = SignalChainModel(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Test Chain {i + 1}",
            platform=Platform.NAM,
        )
        db_session.add(chain)
        chains.append(chain)
    await db_session.flush()
    return chains


@pytest.fixture
async def twenty_one_chains(db_session: AsyncSession, test_user: User) -> list[SignalChainModel]:
    """Create 21 signal chains for max-chain validation testing."""
    chains = []
    for i in range(21):
        chain = SignalChainModel(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Chain {i + 1}",
            platform=Platform.NAM,
        )
        db_session.add(chain)
        chains.append(chain)
    await db_session.flush()
    return chains


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    from webapp.auth.dependencies import set_session_override, set_user_override

    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    set_session_override(None)
    set_user_override(None)


@pytest.fixture
async def unauthenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncClient:
    """Create an unauthenticated HTTP client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.integration
class TestWizardStep3SuccessfulSubmission:
    """Test successful shootout creation via wizard step 3."""

    async def test_create_shootout_with_valid_data_returns_redirect(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        di_track: DITrack,
        signal_chains: list[SignalChainModel],
    ) -> None:
        """Submitting with valid chains and DI track returns HX-Redirect to detail page."""
        chain_ids = [str(c.id) for c in signal_chains[:3]]

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "My Shootout",
                "di_track_id": str(di_track.id),
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert "/shootout/" in response.headers["HX-Redirect"]

    async def test_create_shootout_persists_with_chains(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        di_track: DITrack,
        signal_chains: list[SignalChainModel],
    ) -> None:
        """Created shootout is persisted to DB with correct chain associations."""
        chain_ids = [str(c.id) for c in signal_chains[:3]]

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "Persisted Shootout",
                "di_track_id": str(di_track.id),
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 200

        # Verify shootout persisted with chains
        stmt = (
            select(Shootout)
            .where(Shootout.user_id == test_user.id)
            .where(Shootout.name == "Persisted Shootout")
            .options(joinedload(Shootout.chains))
        )
        result = await db_session.execute(stmt)
        shootout = result.unique().scalar_one_or_none()

        assert shootout is not None
        assert len(shootout.chains) == 3
        assert shootout.di_track_id == di_track.id

    async def test_create_shootout_with_exactly_2_chains_succeeds(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        di_track: DITrack,
        signal_chains: list[SignalChainModel],
    ) -> None:
        """Minimum boundary: exactly 2 chains is valid."""
        chain_ids = [str(c.id) for c in signal_chains[:2]]

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "Two Chain Shootout",
                "di_track_id": str(di_track.id),
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    async def test_create_shootout_with_exactly_20_chains_succeeds(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        di_track: DITrack,
        twenty_one_chains: list[SignalChainModel],
    ) -> None:
        """Maximum boundary: exactly 20 chains is valid."""
        chain_ids = [str(c.id) for c in twenty_one_chains[:20]]

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "Twenty Chain Shootout",
                "di_track_id": str(di_track.id),
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 200
        assert "HX-Redirect" in response.headers


@pytest.mark.asyncio
@pytest.mark.integration
class TestWizardStep3ChainCountValidation:
    """Test chain count validation on submission."""

    async def test_submit_with_zero_chains_returns_422(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        di_track: DITrack,
    ) -> None:
        """Submitting with no chains returns 422 validation error."""
        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "No Chains Shootout",
                "di_track_id": str(di_track.id),
                # No chain_ids
            },
        )

        assert response.status_code == 422

    async def test_submit_with_one_chain_returns_422(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        di_track: DITrack,
        signal_chains: list[SignalChainModel],
    ) -> None:
        """Submitting with only 1 chain returns 422 validation error."""
        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "One Chain Shootout",
                "di_track_id": str(di_track.id),
                "chain_ids[]": [str(signal_chains[0].id)],
            },
        )

        assert response.status_code == 422

    async def test_submit_with_21_chains_returns_422(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        di_track: DITrack,
        twenty_one_chains: list[SignalChainModel],
    ) -> None:
        """Submitting with more than 20 chains returns 422 validation error.

        The domain entity defines MAX_CHAINS = 20. The form endpoint must
        enforce this limit before attempting to create the shootout.
        """
        chain_ids = [str(c.id) for c in twenty_one_chains]
        assert len(chain_ids) == 21

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "Too Many Chains Shootout",
                "di_track_id": str(di_track.id),
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 422

    async def test_chain_count_validation_error_includes_detail_message(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        di_track: DITrack,
        signal_chains: list[SignalChainModel],
    ) -> None:
        """Validation error response includes descriptive detail message for inline display."""
        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "One Chain Shootout",
                "di_track_id": str(di_track.id),
                "chain_ids[]": [str(signal_chains[0].id)],
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "chain" in data["detail"].lower() or "2" in data["detail"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestWizardStep3DITrackValidation:
    """Test DI track required validation on submission."""

    async def test_submit_without_di_track_returns_422(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        signal_chains: list[SignalChainModel],
    ) -> None:
        """Submitting without a DI track returns 422 validation error.

        The acceptance criteria state 'DI track required'. The endpoint must
        validate that di_track_id is present and not empty.
        """
        chain_ids = [str(c.id) for c in signal_chains[:3]]

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "No DI Track Shootout",
                # No di_track_id field
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 422

    async def test_submit_with_empty_di_track_id_returns_422(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        signal_chains: list[SignalChainModel],
    ) -> None:
        """Submitting with empty di_track_id string returns 422 validation error."""
        chain_ids = [str(c.id) for c in signal_chains[:3]]

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "Empty DI Track Shootout",
                "di_track_id": "",
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 422

    async def test_di_track_validation_error_includes_detail_message(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        signal_chains: list[SignalChainModel],
    ) -> None:
        """DI track validation error includes descriptive detail for inline display."""
        chain_ids = [str(c.id) for c in signal_chains[:3]]

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "No DI Track Shootout",
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "di" in data["detail"].lower() or "track" in data["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.integration
class TestWizardStep3MaxChainValidation:
    """Test maximum chain count validation specifically."""

    async def test_max_chains_error_includes_descriptive_message(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        di_track: DITrack,
        twenty_one_chains: list[SignalChainModel],
    ) -> None:
        """Max chains error includes a message mentioning the 20-chain limit."""
        chain_ids = [str(c.id) for c in twenty_one_chains]

        response = await authenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "Too Many",
                "di_track_id": str(di_track.id),
                "chain_ids[]": chain_ids,
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "20" in data["detail"] or "maximum" in data["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.integration
class TestWizardStep3AuthRequired:
    """Test authentication requirements for step 3 submission."""

    async def test_unauthenticated_submit_returns_401(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Unauthenticated POST to shootout-create returns 401."""
        response = await unauthenticated_client.post(
            "/api/v1/html/shootout-create",
            data={
                "name": "Test",
                "di_track_id": str(uuid4()),
                "chain_ids[]": [str(uuid4()), str(uuid4())],
            },
        )

        assert response.status_code in [401, 403]
