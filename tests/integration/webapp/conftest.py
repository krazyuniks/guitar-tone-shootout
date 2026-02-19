"""Shared pytest fixtures for webapp integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

from datetime import UTC, datetime
from uuid import uuid4

from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear, GearTag
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    suffix = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        username=f"testuser_{suffix}",
        email=f"test_{suffix}@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


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
