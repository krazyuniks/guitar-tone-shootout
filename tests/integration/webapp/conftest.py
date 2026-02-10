"""Shared pytest fixtures for webapp integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class _TestAsyncSession(AsyncSession):
    """Test session that falls back to begin_nested() when already in a transaction.

    Fixtures call flush() which triggers autobegin. Tests then call begin()
    expecting nested transaction (SAVEPOINT) semantics. SQLAlchemy 2.0's begin()
    raises on double-begin, so we intercept and use begin_nested() instead.
    """

    def begin(self, **kw):  # type: ignore[override]
        if self.in_transaction():
            return self.begin_nested(**kw)
        return super().begin(**kw)

from uuid import uuid4

from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.gear import Gear, GearTag
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear


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
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    # Use in-memory SQLite for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with transaction management.

    The session auto-begins a transaction on first use. Tests can:
    - Use `async with db_session.begin():` for nested transactions (SAVEPOINT)
    - Use `await db_session.commit()` to commit changes

    All changes are rolled back after each test for isolation.

    This fixture auto-seeds test data for gear detail page tests.
    """
    # Create session factory with custom session class
    async_session = async_sessionmaker(
        db_engine, class_=_TestAsyncSession, expire_on_commit=False,
    )

    # Create session
    session = async_session()

    # Seed test data - create tags first
    tag_metal = GearTag(id=uuid4(), name="metal")
    tag_high_gain = GearTag(id=uuid4(), name="high-gain")
    tag_clean = GearTag(id=uuid4(), name="clean")
    tag_vintage = GearTag(id=uuid4(), name="vintage")
    session.add_all([tag_metal, tag_high_gain, tag_clean, tag_vintage])
    await session.flush()

    # Create gear with tags
    gear1 = Gear(
        id=uuid4(),
        name="Mesa Boogie Mark V",
        slug="mesa-boogie-mark-v",
        gear_type=GearType.AMP,
        description="High-gain tube amp",
        manufacturer="Mesa Boogie",
        is_public=True,
    )
    gear1.tags = [tag_metal, tag_high_gain]
    session.add(gear1)
    await session.flush()

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
    session.add_all([model1a, model1b])

    gear2 = Gear(
        id=uuid4(),
        name="Fender Twin Reverb",
        slug="fender-twin-reverb",
        gear_type=GearType.AMP,
        description="Classic clean amp",
        manufacturer="Fender",
        is_public=True,
    )
    gear2.tags = [tag_clean, tag_vintage]
    session.add(gear2)
    await session.flush()

    # Add models to gear2
    model2 = GearModel(
        id=uuid4(),
        gear_id=gear2.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
    )
    session.add(model2)

    await session.commit()

    try:
        yield session
    finally:
        # Rollback any active transaction and close session
        if session.in_transaction():
            await session.rollback()
        await session.close()


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
    should_wire = "test_user" in direct_params or "authenticated_client" in direct_params
    if should_wire and hasattr(item, "funcargs") and "test_user" in item.funcargs:
        test_user = item.funcargs["test_user"]
        set_user_override(test_user)
        print(f"[HOOK] Setting current user: {test_user.username}")


@pytest.fixture(autouse=True)
async def _wire_auth_session(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Auto-wire test DB session into the centralised auth dependencies.

    All route modules (auth, pages, html, library) now import from
    webapp.auth.dependencies, so we only need to set the override once.
    """
    from webapp.auth.dependencies import set_session_override, set_user_override

    print(f"[FIXTURE] Setting session override: {db_session}")
    set_session_override(db_session)
    yield
    set_session_override(None)
    set_user_override(None)
