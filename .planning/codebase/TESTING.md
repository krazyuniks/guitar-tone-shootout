# Testing Patterns

**Analysis Date:** 2026-02-05

## Test Framework

**Runner:**
- `pytest` 8.3.0+
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`
- Async mode: `asyncio_mode = "auto"`
- Test paths: `tests/` directory

**Assertion Library:**
- pytest built-in assertions (no external assertion library)
- Format: `assert retrieved is not None, "Descriptive message"`

**Run Commands:**
```bash
just test-regression  # Stack connectivity tests (~0.2s, SQLite in-memory)
just test             # Unit + Integration tests (~30s)
just test-unit        # Unit tests only
just test-integration # Integration tests only
just test-golden-path         # E2E tests with Playwright (requires running containers)
just tdd <path>       # Single test during development (Docker, watches)
```

## Test File Organization

**Location:**
- Colocated with source code in `tests/` directory, mirroring source structure
- Pattern: `tests/{type}/{module}/test_{component}.py`

**Naming:**
- Test files: `test_{component}.py` (e.g., `test_user_model.py`, `test_stack.py`)
- Test classes: `Test{ComponentName}` (e.g., `TestUserRoundTrip`, `TestStackConnectivity`)
- Test functions: `test_{specific_behavior}` (e.g., `test_create_and_retrieve`, `test_user_identity_links_to_user`)

**Structure:**
```
tests/
├── regression/
│   ├── conftest.py          # Shared fixtures (db_engine, db_session)
│   └── test_stack.py        # Stack connectivity (ORM → Repo → DB)
├── unit/
│   ├── core/                # Domain entity tests
│   ├── audio/               # Audio processing tests
│   ├── webapp/              # ORM model and basic logic tests
│   └── worktree/            # Utility tests
├── integration/
│   ├── audio/               # Audio processing with real files
│   ├── webapp/              # Repository integration with real DB
│   │   └── conftest.py      # Shared fixtures
│   └── worker/              # Job processing integration
├── e2e/
│   └── python/
│       ├── pyproject.toml   # Standalone package
│       ├── conftest.py
│       └── tests/
├── fixtures/                # Shared test fixtures (empty, future use)
└── data/                    # Test data files (empty, future use)
```

## Test Structure

**Suite Organization:**
```python
"""Test module docstring explaining purpose."""

from __future__ import annotations

from typing import TYPE_CHECKING
import pytest

# Imports organized: stdlib, third-party, local

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def my_fixture() -> AsyncGenerator[T, None]:
    """Setup for tests."""
    yield value
    # Cleanup if needed


class TestStackConnectivity:
    """Group related tests in a class."""

    def test_orm_models_import(self) -> None:
        """Test something specific."""
        assert Base is not None


class TestUserRoundTrip:
    """Another test class."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
        """Test async behavior with fixture."""
        # Setup
        identity = UserIdentity(...)
        user = UserEntity.create_with_identity(identity=identity)

        # Act
        repo = SQLAlchemyUserRepository(db_session)
        await repo.save(user)
        await db_session.commit()
        retrieved = await repo.get_by_id(user.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == user.id
```

**Patterns:**
- Setup-Act-Assert pattern (comments optional but helpful)
- Fixtures injected as parameters
- `@pytest.mark.asyncio` on all async tests
- Type hints on all test functions
- Clear test names describing behavior, not implementation

## Mocking

**Framework:** `unittest.mock` (not currently heavily used)

**Patterns:**
- Avoid mocking internal services (test against real objects)
- Mock only external APIs and I/O-heavy operations
- For audio tests: create minimal test audio files instead of mocking audio libraries
- For model tests: use in-memory SQLite instead of mocking database

**What to Mock:**
- External APIs (Tone3000 API, email services, payment systems)
- File I/O in unit tests (not in integration tests)
- Time-dependent behavior (mock `datetime.now()` if needed)

**What NOT to Mock:**
- Domain entities and value objects
- Repositories (use real DB with SQLite in-memory)
- SQLAlchemy ORM (test with real models)
- Core business logic

**Example of correct pattern (test real, not mock):**
```python
@pytest.mark.asyncio
async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
    """Create user via repository, retrieve it - validates full stack."""
    # Real domain entity
    identity = UserIdentity(
        provider="t3k", external_id="test-001", username="test_user"
    )
    user = UserEntity.create_with_identity(identity=identity, email="test@gts.dev")

    # Real repository
    repo = SQLAlchemyUserRepository(db_session)
    await repo.save(user)  # Real database operation
    await db_session.commit()

    # Real query
    retrieved = await repo.get_by_id(user.id)

    # Assertion
    assert retrieved is not None
```

## Fixtures and Factories

**Test Data:**
- Fixtures created inline in test functions (small, simple data)
- Reusable fixtures defined at top of test file or in `conftest.py`

**Fixture pattern:**
```python
@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite engine with all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async with async_session() as session:
        yield session
```

**Location:**
- Shared fixtures: `tests/{type}/conftest.py` (e.g., `tests/regression/conftest.py`)
- Fixture scope: Function scope (default, isolated tests)
- No global fixtures unless truly needed

**Naming:**
- Fixture functions: `fixture_name` (e.g., `db_session`, `test_audio_dir`)
- Factory functions: `make_user()`, `create_job()` (not currently used, prefer inline)

## Coverage

**Requirements:** Not enforced by default, but configured

**View Coverage:**
```bash
# After running tests with pytest-cov
pytest --cov=libs --cov=sources --cov=apps --cov-report=html
# Then open htmlcov/index.html
```

**Configuration:** `pyproject.toml` under `[tool.coverage.run]` and `[tool.coverage.report]`
- Source: `libs`, `sources`, `apps`
- Branch coverage: enabled
- Exclusions: tests, pycache, abstract methods, TYPE_CHECKING blocks

## Test Types

**Unit Tests:**
- Location: `tests/unit/{module}/test_{component}.py`
- Scope: Pure logic, no I/O
- Database: None (test domain entities, value objects, validators)
- Examples: `tests/unit/core/`, `tests/unit/audio/test_ir_loader.py`
- Approach: Test domain entities, enums, value objects in isolation

**Regression Tests:**
- Location: `tests/regression/test_stack.py`
- Purpose: Verify ORM → Repository → Database stack works end-to-end
- Database: In-memory SQLite
- Run before commits to catch fundamental breaks
- Includes: User entity round-trip, Job state machine, query operations
- Speed: ~0.2 seconds

**Integration Tests:**
- Location: `tests/integration/{module}/test_{component}.py`
- Scope: Real database (in-memory SQLite), real services
- Database: In-memory SQLite with schema
- Examples: `tests/integration/webapp/` (repositories), `tests/integration/audio/` (processing)
- Approach: Test repository implementations, service interactions with real DB

**E2E Tests:**
- Location: `tests/e2e/python/tests/`
- Framework: pytest + Playwright
- Scope: Full user journeys through web UI
- Database: Docker PostgreSQL (running containers required)
- Approach: Browser automation, assert DOM state and database persistence
- Run: `just test-golden-path` (on host, not in Docker)
- Note: Standalone package (`tests/e2e/python/pyproject.toml`), isolated from main workspace

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_async_function(self, db_session: AsyncSession) -> None:
    """Test async behavior."""
    result = await some_async_function(db_session)
    assert result is not None
```

**Error Testing:**
```python
@pytest.mark.asyncio
async def test_invalid_state_transition(self) -> None:
    """Test that invalid state transition raises error."""
    job = JobEntity(job_type=JobType.AUDIO_PROCESSING)
    job.queue(task_id="test-123")

    # Cannot transition from QUEUED directly to COMPLETED
    with pytest.raises(InvalidStateTransitionError):
        job.complete(result_path="/path")
```

**Fixture Usage:**
```python
@pytest.mark.asyncio
async def test_user_email_index(self, db_session: AsyncSession) -> None:
    """Test email column has index for performance."""
    user1 = User(username="user1", email="user1@example.com")
    user2 = User(username="user2", email="user2@example.com")
    db_session.add_all([user1, user2])
    await db_session.commit()

    # Query by email
    result = await db_session.execute(
        select(User).where(User.email == "user1@example.com")
    )
    found = result.scalar_one()

    assert found.username == "user1"
```

**Fresh Session per Test:**
```python
@pytest.mark.asyncio
async def test_relationships_fresh_session(self, db_session: AsyncSession) -> None:
    """Test relationships load correctly with fresh query."""
    # Create data
    provider = OAuthProvider(name="t3k", enabled=True)
    db_session.add(provider)
    await db_session.commit()

    user = User(username="test_user", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Close session and create new one for fresh query
    await db_session.close()

    # New session
    async_session = async_sessionmaker(
        db_session.bind, class_=AsyncSession, expire_on_commit=False
    )
    new_session = async_session()

    # Query and verify
    result = await new_session.execute(select(User).where(User.id == user_id))
    loaded_user = result.scalar_one()

    assert loaded_user is not None
```

## Test Markers

**Available markers:**
```
@pytest.mark.slow           # Slow tests
@pytest.mark.integration    # Integration tests
@pytest.mark.e2e            # End-to-end tests
@pytest.mark.smoke          # Smoke tests
```

**Configuration:** Defined in `pyproject.toml` under `[tool.pytest.ini_options]` markers

## Special Considerations

**SQLite in-memory vs PostgreSQL:**
- Unit/regression/integration: Use in-memory SQLite for speed (~0.2s for regression, <30s for all)
- E2E: Uses Docker PostgreSQL (real production database)
- Rationale: Speed + isolation for most tests, real schema validation for E2E

**Async Fixtures:**
- All database fixtures are async: `async def fixture(...) -> AsyncGenerator[T, None]:`
- Marked with `@pytest.fixture` (asyncio_mode="auto" handles async automatically)

**Test Isolation:**
- Each test gets fresh in-memory SQLite database
- No test order dependencies
- No shared state between tests

---

*Testing analysis: 2026-02-05*
