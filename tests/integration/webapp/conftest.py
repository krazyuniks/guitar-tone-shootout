"""Shared pytest fixtures for webapp integration tests.

Provides:
- Factory fixtures (make_user, make_di_track, make_shootout, make_gear,
  make_signal_chain) — each returns an async callable for flexible creation.
- Singleton fixtures (test_user, test_di_track, test_gear, test_shootout,
  test_signal_chain) — one canonical instance per test.
- authenticated_client — HTTPX AsyncClient with auth wired.
- seeded_db_session — pre-populated gear catalogue for page tests.
- Auto-wiring hooks for auth session and user override.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine
    from typing import Any

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

from datetime import UTC, datetime
from uuid import uuid4

from gts.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear, GearTag
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource
from webapp.adapters.persistence.models.shootout import DITrack, Shootout, ShootoutChain
from webapp.adapters.persistence.models.signal_chain import (
    SignalChain,
    SignalChainBlock,
)
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear

# ---------------------------------------------------------------------------
# Factory fixtures — return async callables for flexible test data creation
# ---------------------------------------------------------------------------


@pytest.fixture
def make_user(db_session: AsyncSession) -> Callable[..., Coroutine[Any, Any, User]]:
    """Factory fixture for creating User instances.

    Returns an async callable ``_make(**overrides)`` that creates and
    persists a User with sensible defaults. Any keyword argument
    overrides the default value.

    Usage::

        user = await make_user()
        admin = await make_user(username="admin", email="admin@example.com")
    """

    async def _make(**overrides: Any) -> User:
        suffix = uuid4().hex[:8]
        defaults = {
            "id": uuid4(),
            "username": f"testuser_{suffix}",
            "email": f"test_{suffix}@example.com",
            "is_active": True,
        }
        defaults.update(overrides)
        user = User(**defaults)
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        return user

    return _make


@pytest.fixture
def make_di_track(db_session: AsyncSession) -> Callable[..., Coroutine[Any, Any, DITrack]]:
    """Factory fixture for creating DITrack instances.

    Returns an async callable ``_make(user, **overrides)``.

    Usage::

        track = await make_di_track(test_user)
        track = await make_di_track(test_user, name="Custom DI")
    """

    async def _make(user: User, **overrides: Any) -> DITrack:
        defaults = {
            "id": uuid4(),
            "user_id": user.id,
            "name": "Test DI Track",
            "file_path": "/audio/test_di.wav",
            "original_filename": "test_di.wav",
            "duration_seconds": 60.0,
            "sample_rate": 48000,
        }
        defaults.update(overrides)
        track = DITrack(**defaults)
        db_session.add(track)
        await db_session.flush()
        await db_session.refresh(track)
        return track

    return _make


@pytest.fixture
def make_shootout(
    db_session: AsyncSession,
) -> Callable[..., Coroutine[Any, Any, Shootout]]:
    """Factory fixture for creating Shootout instances.

    Returns an async callable ``_make(user, di_track, chains=0, **overrides)``.
    When ``chains > 0``, creates that many ShootoutChain stubs (each
    referencing a new empty SignalChain).

    Usage::

        shootout = await make_shootout(test_user, test_di_track)
        shootout = await make_shootout(test_user, test_di_track, chains=3)
    """

    async def _make(
        user: User, di_track: DITrack, *, chains: int = 0, **overrides: Any
    ) -> Shootout:
        defaults = {
            "id": uuid4(),
            "user_id": user.id,
            "di_track_id": di_track.id,
            "name": "Test Shootout",
        }
        defaults.update(overrides)
        shootout = Shootout(**defaults)
        db_session.add(shootout)
        await db_session.flush()

        for i in range(chains):
            chain_model = SignalChain(
                id=uuid4(),
                user_id=user.id,
                name=f"Chain {i + 1}",
                platform=Platform.NAM,
            )
            db_session.add(chain_model)
            await db_session.flush()
            link = ShootoutChain(
                id=uuid4(),
                shootout_id=shootout.id,
                signal_chain_id=chain_model.id,
                position=i,
                label=f"Chain {i + 1}",
            )
            db_session.add(link)

        await db_session.flush()
        await db_session.refresh(shootout)
        return shootout

    return _make


@pytest.fixture
def make_gear(db_session: AsyncSession) -> Callable[..., Coroutine[Any, Any, Gear]]:
    """Factory fixture for creating Gear instances with source, tags, and models.

    Returns an async callable
    ``_make(gear_type, platform, models=1, **overrides)``.

    Usage::

        gear = await make_gear(GearType.AMP, Platform.NAM)
        gear = await make_gear(GearType.PEDAL, Platform.NAM, models=3)
    """

    async def _make(
        gear_type: GearType = GearType.AMP,
        platform: Platform = Platform.NAM,
        *,
        models: int = 1,
        **overrides: Any,
    ) -> Gear:
        suffix = uuid4().hex[:8]
        now = datetime.now(UTC)

        source = GearSource(
            id=uuid4(),
            source_name="t3k",
            source_record_id=f"t3k-gear-{suffix}",
            source_updated_at=now,
        )
        db_session.add(source)
        await db_session.flush()

        tag = GearTag(id=uuid4(), name=f"tag_{suffix}")
        db_session.add(tag)
        await db_session.flush()

        defaults = {
            "id": uuid4(),
            "name": f"Test Gear {suffix}",
            "slug": f"test-gear-{suffix}",
            "gear_type": gear_type,
            "platform": platform,
            "manufacturer": "Test Manufacturer",
            "is_public": True,
            "source_id": source.id,
        }
        defaults.update(overrides)
        gear = Gear(**defaults)
        gear.tags = [tag]
        db_session.add(gear)
        await db_session.flush()

        for i in range(models):
            size = [ModelSize.STANDARD, ModelSize.LITE, ModelSize.NANO][i % 3]
            model = GearModel(
                id=uuid4(),
                gear_id=gear.id,
                platform=platform,
                size=size,
            )
            db_session.add(model)

        await db_session.flush()
        await db_session.refresh(gear)
        return gear

    return _make


@pytest.fixture
def make_signal_chain(
    db_session: AsyncSession,
) -> Callable[..., Coroutine[Any, Any, SignalChain]]:
    """Factory fixture for creating SignalChain instances.

    Returns an async callable ``_make(user, blocks=[], **overrides)``.
    Each entry in *blocks* is a dict of column overrides for
    ``SignalChainBlock``; at minimum provide ``gear_type``.

    Usage::

        chain = await make_signal_chain(test_user)
        chain = await make_signal_chain(
            test_user,
            blocks=[{"gear_type": GearType.FULL_RIG}],
        )
    """

    async def _make(
        user: User, *, blocks: list[dict[str, Any]] | None = None, **overrides: Any
    ) -> SignalChain:
        defaults = {
            "id": uuid4(),
            "user_id": user.id,
            "name": "Test Signal Chain",
            "platform": Platform.NAM,
        }
        defaults.update(overrides)
        chain = SignalChain(**defaults)
        db_session.add(chain)
        await db_session.flush()

        for i, block_kw in enumerate(blocks or []):
            block_defaults = {
                "id": uuid4(),
                "signal_chain_id": chain.id,
                "position": i,
                "user_gear_id": uuid4(),
            }
            block_defaults.update(block_kw)
            block = SignalChainBlock(**block_defaults)
            db_session.add(block)

        await db_session.flush()
        await db_session.refresh(chain)
        return chain

    return _make


# ---------------------------------------------------------------------------
# Singleton fixtures — one canonical instance per test
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_user(make_user: Callable[..., Coroutine[Any, Any, User]]) -> User:
    """Create a single test user (canonical fixture).

    Uses ``make_user`` factory internally. All integration tests under
    ``tests/integration/webapp/`` should use this fixture instead of
    defining their own.
    """
    return await make_user()


@pytest.fixture
async def test_di_track(
    make_di_track: Callable[..., Coroutine[Any, Any, DITrack]],
    test_user: User,
) -> DITrack:
    """Create a single test DI track owned by ``test_user``."""
    return await make_di_track(test_user)


@pytest.fixture
async def test_gear(
    make_gear: Callable[..., Coroutine[Any, Any, Gear]],
) -> Gear:
    """Create a single test gear item with source, tag, and one model."""
    return await make_gear(GearType.AMP, Platform.NAM, models=1)


@pytest.fixture
async def test_shootout(
    make_shootout: Callable[..., Coroutine[Any, Any, Shootout]],
    test_user: User,
    test_di_track: DITrack,
) -> Shootout:
    """Create a single test shootout with two chains."""
    return await make_shootout(test_user, test_di_track, chains=2)


@pytest.fixture
async def test_signal_chain(
    make_signal_chain: Callable[..., Coroutine[Any, Any, SignalChain]],
    test_user: User,
) -> SignalChain:
    """Create a single test signal chain with one FULL_RIG block."""
    return await make_signal_chain(test_user, blocks=[{"gear_type": GearType.FULL_RIG}])


# ---------------------------------------------------------------------------
# Authenticated client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def authenticated_client(
    db_session: AsyncSession,
    test_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX AsyncClient with auth wired for ``test_user``.

    The ``_wire_auth_session`` autouse fixture already sets the session
    override; this fixture additionally sets the user override and
    yields a client bound to the main webapp.

    Usage::

        async def test_something(authenticated_client):
            resp = await authenticated_client.get("/library/shootouts")
            assert resp.status_code == 200
    """
    from httpx import ASGITransport, AsyncClient

    from webapp.auth.dependencies import set_user_override
    from webapp.main import app

    set_user_override(test_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Existing fixtures (kept for backwards compatibility)
# ---------------------------------------------------------------------------


@pytest.fixture
async def make_user_gear(db_session: AsyncSession):
    """Factory fixture for creating UserGear instances."""

    async def _make_user_gear(user_id, gear_model_id):
        user_gear = UserGear(
            id=uuid4(),
            user_id=user_id,
            gear_model_id=gear_model_id,
        )
        db_session.add(user_gear)
        await db_session.flush()
        await db_session.refresh(user_gear)
        return user_gear

    return _make_user_gear


@pytest.fixture
async def seeded_db_session(db_session: AsyncSession) -> AsyncSession:
    """Seed the session with test data for gear detail page tests.

    Returns the same db_session after seeding gear, tags, sources, and models.
    """
    suffix = uuid4().hex[:8]

    # Seed test data - create tags first
    tag_metal = GearTag(id=uuid4(), name=f"metal_{suffix}")
    tag_high_gain = GearTag(id=uuid4(), name=f"high-gain_{suffix}")
    tag_clean = GearTag(id=uuid4(), name=f"clean_{suffix}")
    tag_vintage = GearTag(id=uuid4(), name=f"vintage_{suffix}")
    db_session.add_all([tag_metal, tag_high_gain, tag_clean, tag_vintage])
    await db_session.flush()

    # Create gear sources for T3K attribution
    now = datetime.now(UTC)
    source1 = GearSource(
        id=uuid4(),
        source_name="t3k",
        source_record_id=f"t3k-mesa-mark-v-{suffix}",
        source_updated_at=now,
    )
    source2 = GearSource(
        id=uuid4(),
        source_name="t3k",
        source_record_id=f"t3k-fender-twin-{suffix}",
        source_updated_at=now,
    )
    db_session.add_all([source1, source2])
    await db_session.flush()

    # Create gear with tags
    gear1 = Gear(
        id=uuid4(),
        name=f"Mesa Boogie Mark V {suffix}",
        slug=f"mesa-boogie-mark-v-{suffix}",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        description="High-gain tube amp",
        manufacturer="Mesa Boogie",
        is_public=True,
        source_id=source1.id,
    )
    gear1.tags = [tag_metal, tag_high_gain]
    db_session.add(gear1)
    await db_session.flush()

    # Add models to gear1
    model1a = GearModel(
        id=uuid4(),
        gear_id=gear1.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
    )
    model1b = GearModel(
        id=uuid4(),
        gear_id=gear1.id,
        platform=Platform.NAM,
        size=ModelSize.LITE,
    )
    db_session.add_all([model1a, model1b])

    gear2 = Gear(
        id=uuid4(),
        name=f"Fender Twin Reverb {suffix}",
        slug=f"fender-twin-reverb-{suffix}",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        description="Classic clean amp",
        manufacturer="Fender",
        is_public=True,
        source_id=source2.id,
    )
    gear2.tags = [tag_clean, tag_vintage]
    db_session.add(gear2)
    await db_session.flush()

    # Add models to gear2
    model2 = GearModel(
        id=uuid4(),
        gear_id=gear2.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
    )
    db_session.add(model2)

    await db_session.commit()

    return db_session


# ---------------------------------------------------------------------------
# Hooks — auth wiring
# ---------------------------------------------------------------------------


def pytest_runtest_call(item: pytest.Item) -> None:
    """Hook that runs during test execution to wire test_user as current user.

    Only wires when test_user is a DIRECT parameter of the test function,
    or when authenticated_client is a direct parameter (which depends on
    test_user). Tests that only use test_user as an indirect dependency
    (e.g., via group_with_2x2) won't get auto-wired, allowing them to
    test unauthenticated access.
    """
    import inspect

    from webapp.auth.dependencies import set_user_override

    # Get the actual function's parameter names
    func = item.obj if hasattr(item, "obj") else None
    if func is None:
        return
    direct_params = set(inspect.signature(func).parameters.keys()) - {"self"}

    # Wire test_user if: (a) test_user is a direct param, or
    # (b) authenticated_client is a direct param (it manages auth explicitly)
    # BUT never wire if unauthenticated_client is also a direct param
    should_wire = (
        "test_user" in direct_params or "authenticated_client" in direct_params
    ) and "unauthenticated_client" not in direct_params
    if should_wire and hasattr(item, "funcargs") and "test_user" in item.funcargs:
        test_user = item.funcargs["test_user"]
        set_user_override(test_user)
        print(f"[HOOK] Setting current user: {test_user.username}")


@pytest.fixture(autouse=True)
async def _wire_auth_session(db_session: AsyncSession, tmp_path) -> AsyncGenerator[None, None]:  # type: ignore[no-untyped-def]
    """Auto-wire test DB session into the centralised auth dependencies.

    All route modules (auth, pages, html, library) now import from
    webapp.auth.dependencies, so we only need to set the override once.

    Also sets upload base directory to tmp_path for file upload tests
    and secret key to test-secret for HMAC signature tests.
    """
    from webapp.auth.dependencies import set_session_override, set_user_override
    from webapp.config.uploads import set_secret_key_override, set_upload_base_override

    print(f"[FIXTURE] Setting session override: {db_session}")
    set_session_override(db_session)
    set_upload_base_override(tmp_path)
    set_secret_key_override("test-secret")
    yield
    set_session_override(None)
    set_user_override(None)
    set_upload_base_override(None)
    set_secret_key_override(None)
