# Test Scaffolding Patterns

Quick-start patterns for common GTS test scenarios. Extracted from production-proven templates.

## Unit Test with Async SQLite (ORM Models)

Use this pattern when testing ORM models in isolation without the full integration test stack.

```python
"""Unit tests for SomeModel."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.some_model import SomeModel


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestSomeModel:
    async def test_creation(self, session: AsyncSession) -> None:
        obj = SomeModel(name="test")
        session.add(obj)
        await session.commit()

        result = await session.execute(select(SomeModel))
        saved = result.scalar_one()
        assert saved.name == "test"
```

## Verifying a Module/Class Exists

Just import it. If the file does not exist, pytest collection fails -- that IS the red phase. No special existence checks needed.

```python
from core.domain.value_objects.gear_type import GearType

def test_gear_type_has_expected_values():
    assert GearType.AMP.value == "amp"
    assert GearType.PEDAL.value == "pedal"
```

## Verifying Enum Values

```python
from core.domain.value_objects.platform import Platform

def test_platform_enum_has_required_values():
    expected = {"nam", "ir", "aida_x"}
    actual = {p.value for p in Platform}
    assert expected.issubset(actual)
```

## Service Test with Real Repository (NOT Mock)

```python
"""Unit tests for SomeService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.repositories.some_repo import SomeRepository
from webapp.services.some_service import SomeService


@pytest.fixture
def service(session: AsyncSession) -> SomeService:
    repository = SomeRepository(session=session)
    return SomeService(repository=repository)


class TestSomeService:
    async def test_creates_entity(self, service: SomeService, session: AsyncSession) -> None:
        result = await service.create(name="test")
        assert result.name == "test"

        # Verify it persisted to the database
        from sqlalchemy import select
        from webapp.adapters.persistence.models.some_model import SomeModel
        stmt = select(SomeModel).where(SomeModel.name == "test")
        db_result = await session.execute(stmt)
        assert db_result.scalar_one() is not None
```

## E2E Test Pattern (Host-Only)

E2E tests go in `tests/e2e/python/tests/`. They run on HOST via `just test-golden-path`, NOT in Docker.

**CRITICAL: E2E tests CANNOT import internal packages.** The host does not have `webapp`, `core`, `audio`, etc. installed. Use raw SQL via `text()` for database queries:

```python
# CORRECT -- raw SQL for E2E database verification
from sqlalchemy import text
result = await db_session.execute(text("SELECT id, slug FROM gear WHERE is_public = true LIMIT 1"))

# BANNED -- internal packages not available on host
from webapp.adapters.persistence.models.gear import Gear  # ModuleNotFoundError
from core.domain.entities.user import User                # ModuleNotFoundError
```
