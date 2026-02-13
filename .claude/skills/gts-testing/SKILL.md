---
name: gts-testing
description: "Testing for GTS: regression test authoring, pytest patterns, fixtures, scaffolding, mutation verification, and anti-patterns. Use when writing tests, debugging test failures, scaffolding new test files, or verifying mutations persist."
context: fork
---

# GTS Testing

Single reference for all testing in GTS. Covers regression test authoring, pytest patterns, fixtures, scaffolding, and mutation verification.

**Philosophy:** Tests are regression nets -- written AFTER the product works, capturing current working behaviour to prevent regressions. Test against real services. No mocking. See `.claude/rules/testing-policy.md`.

## Quick Reference

| Command | Scope | Runs In |
|---------|-------|---------|
| `just tdd <path>` | Single test file | Docker |
| `just test-unit` | All unit tests | Docker |
| `just test-integration` | All integration tests | Docker |
| `just test` | Unit + integration | Docker |
| `just test-regression` | Stack connectivity (<1s) | Docker |
| `just test-golden-path` | E2E user journey | Host |
| `just check` | Full quality gates | Docker |

### Epic Workflow Commands

| Command | Purpose |
|---------|---------|
| `just epic-ingest 42` | Fetch epic from GitHub |
| `just epic-plan 42` | Plan: context -> scope -> plan -> verify -> gate |
| `just epic-start 42` | Execute stories via orchestrator |
| `just epic-status 42` | Check progress from JSONL |

---

## Regression Test Authoring

### When to Write Tests

Tests are written AFTER the product works. The validation checkpoint confirms the feature functions correctly, then a regression test story captures that working behaviour in automated tests.

### Regression Test Purpose

- Prevent future changes from breaking working features
- Capture the current contract (API responses, DOM state, database effects)
- Run automatically via `just test-golden-path` and `just test-regression`

### Common Mistakes (from Production Runs)

These have actually happened in automated runs. Do not repeat them.

| Mistake | Correct Behaviour |
|---|---|
| Modified existing test files | Only CREATE new test files. Existing tests are immutable contracts. |
| Ran the full test suite | Only run YOUR new/modified test files during development. |
| Imported from implementation packages that don't exist yet | Use standard imports. Tests should fail with ImportError or AssertionError, not SyntaxError. |
| Used `conftest.py` fixtures from integration tests in unit tests | Unit and integration fixtures are separate. Check which conftest.py applies. |
| Hit max turns without finishing | Start with the simplest test. Iterate. Don't plan everything upfront. |

---

## Test Structure & Placement

```
tests/
  conftest.py              # Root config: markers, pytest_plugins
  fixtures/                # Shared fixtures
    database.py          # DB session with transaction rollback
    auth.py              # JWT tokens, auth headers
    factories.py         # Test data factories
  unit/
    backend/             # Pure logic, no external deps
    video/               # Video composition tests (props, schemas, image prep)
  integration/
    backend/             # Real DB/Redis tests
    video/               # Video API tests (FastAPI endpoints, Remotion)
  regression/              # Stack connectivity (SQLite, <1s)
  e2e/
    python/              # E2E tests (pytest + Playwright)
      conftest.py      # Browser fixtures, auth, DB access
      tests/           # Test files
```

### Placement Decision Tree

```
Is it a browser-based test?
  YES -> tests/e2e/python/tests/  (runs on HOST)
  NO -> Does it need real DB/Redis?
    YES -> tests/integration/backend/ or integration/video/  (runs in DOCKER)
    NO -> tests/unit/backend/ or unit/video/  (runs in DOCKER)
```

### Video Test Patterns

Video composition tests follow the same placement rules as backend tests:

| Test Type | Location | What to Test |
|-----------|----------|--------------|
| **Unit** | `tests/unit/video/` (also `tests/unit/backend/video/`) | Props serialisation, schemas, image prep (Pillow) |
| **Integration** | `tests/integration/video/` (also `tests/integration/backend/video/`) | FastAPI endpoints, Remotion TypeScript compilation |

**Fixtures for video tests:**
- Use `TestClient` from `fastapi.testclient` for API tests
- Mock external Remotion render calls (test composition structure, not actual rendering)
- Use real image files from `tests/data/` for image prep tests

**Example: Props serialisation test**
```python
# tests/unit/video/test_props.py
from video.props import serialize_composition_props
from core.domain.value_objects.composition_spec import CompositionSpec

def test_serialize_composition_props():
    spec = CompositionSpec(
        composition_type="ShootoutVideo",
        data={"segments": [...]},
    )

    props = serialize_composition_props(spec)

    assert props["compositionType"] == "ShootoutVideo"
    assert "segments" in props["data"]
```

---

## Antipatterns

### Banned Test Patterns

| Pattern | Issue |
|---------|-------|
| `assert True` | Trivial -- proves nothing |
| `assert x` (truthy only) | Weak -- doesn't verify specific value |
| `mock.assert_called()` alone | Spy-only -- no effect verification |
| Empty test (`pass` only) | No assertions |
| `@pytest.mark.skip` | Skipped -- defeats purpose |
| `time.sleep()` | Flaky indicator |
| `importlib.util` / `find_spec` | Banned -- use standard imports |
| `db_session.get_bind()` | Banned -- use fixtures directly |

### Bad vs Good

```python
# BAD -- truthy check
def test_validate_email_works():
    result = validate_email('test@example.com')
    assert result  # What does "truthy" even mean here?

# GOOD -- specific assertion
def test_validate_email_rejects_invalid_format():
    result = validate_email('not-an-email')
    assert result.valid is False
    assert result.error == 'Invalid email format'
```

### Forbidden Mocking

**No mocking.** The `test_quality_check.py` gate bans all `unittest.mock` imports, `@patch`, `Mock()`, `MagicMock()`, and `AsyncMock()` with zero exceptions.

```python
# BANNED -- all mocking is forbidden
@patch('app.repositories.signal_chain_repo')  # NO
mock_service = Mock(spec=SignalChainService)   # NO
page.route('**/api/**', ...)                   # NO
```

All GTS services (T3K, PostgreSQL, Redis, pgmq) are available in the Docker test environment.

---

## Production-Learned Banned Patterns

These patterns caused repeated failures during automated runs. **Never use them.**

### Test-Authoring Patterns

**1. `importlib.util` / `find_spec` / `module_from_spec` -- BANNED**

Fragile and produces false failures (module found but attributes not loaded).

```python
# BANNED
import importlib.util
spec = importlib.util.find_spec("some.module")
module = importlib.util.module_from_spec(spec)

# CORRECT -- standard import; missing file = collection failure
from webapp.adapters.persistence.models.gear_model import GearModel
```

**2. `AsyncSession.get_bind()` -- BANNED**

Returns a **sync** Engine, not AsyncEngine. Creates broken sessions.

```python
# BANNED
engine = db_session.get_bind()
new_session = AsyncSession(engine)  # sync engine in async context

# CORRECT -- use fixtures directly
async def test_something(db_session: AsyncSession):
    result = await db_session.execute(select(Model))
```

**3. `AsyncClient(app=...)` -- BANNED (removed in HTTPX 0.28+)**

```python
# BANNED
async with AsyncClient(app=app, base_url="http://test") as client: ...

# CORRECT
from httpx import ASGITransport, AsyncClient
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client: ...
```

**4. Inline `FastAPI()` without `set_session_override()` -- BANNED**

Tests that create `FastAPI()` inline need `set_session_override()` from conftest autouse fixture, not `dependency_overrides`.

**5. Testing backward-compat import removal -- BANNED**

Creates unsolvable contradictions if tests assert old imports are removed.

```python
# BANNED -- creates unsolvable contradiction
assert not hasattr(signal_chain_enums, "GearType")

# CORRECT -- test the NEW location works
from core.domain.value_objects.gear_type import GearType
assert GearType.AMP is not None
```

**6. `from __future__ import annotations` in FastAPI route modules -- BANNED**

Breaks `Depends()` runtime type resolution. FastAPI treats `Depends(get_db_session)` as a query parameter, returning 422 Unprocessable Entity. Remove the annotations import and import `AsyncSession` directly.

**7. Query param name mismatch**

The query parameter name in test URLs (e.g., `?status=running`) MUST match the FastAPI endpoint parameter name. Use `Query(None, alias="status")` when the variable name differs.

### Infrastructure Patterns

**8. `db_session.expire_all()` + re-query instead of close/recreate**

Never close a session and recreate from engine. Use `db_session.expire_all()` then re-query.

**9. `db_session.begin()` nesting**

Conftest uses `_TestAsyncSession` that falls back to `begin_nested()` when autobegin is active (fixtures trigger autobegin via `flush()`). Be aware of this when writing transaction tests.

**10. Module existence testing -- just import it**

If the module file doesn't exist, pytest collection fails -- that IS the expected failure. No need for special existence checks.

**11. `conftest.py` is NOT a test file**

`conftest.py` can be modified by ALL agents. It is not locked. Fixture changes go in conftest.

**12. Test helpers in production modules -- BANNED**

Never put test utility functions (`set_session_override()`, `set_user_override()`, test factory functions) in production modules like `pages.py`, `library.py`, or service files. When those modules are refactored, the test helpers disappear and cause cascading `ImportError` across unrelated tests.

```python
# BANNED -- test helper in production module
# apps/webapp/src/webapp/api/pages.py
def set_session_override(session):  # NO -- this breaks when pages.py is refactored
    ...

# CORRECT -- test helper in test fixtures
# tests/fixtures/overrides.py or tests/conftest.py
def set_session_override(session):
    ...
```

**13. `lazy="raise"` relationship access in tests**

When models use `lazy="raise"`, tests that access relationships after querying MUST either:
- Use `joinedload()` in the query
- Use `session.refresh(obj, ["relationship_name"])` to explicitly load

```python
# BANNED -- will raise InvalidRequestError with lazy="raise"
user = await session.get(User, user_id)
print(user.identities)  # BOOM

# CORRECT -- eager load the relationship
stmt = select(User).where(User.id == user_id).options(joinedload(User.identities))
result = await session.execute(stmt)
user = result.unique().scalar_one()
print(user.identities)  # OK

# ALSO CORRECT -- refresh with specific attribute
user = await session.get(User, user_id)
await session.refresh(user, ["identities"])
print(user.identities)  # OK
```

---

## E2E Testing (Golden Path)

E2E tests live in `tests/e2e/python/tests/` and run on **HOST only** via `just test-golden-path`.

### Key Facts

- Uses **Playwright** (not available in Docker containers)
- Tests the full user journey through the browser
- The regression gate for the project

### Writing E2E Tests

```python
# tests/e2e/python/tests/test_gear_library.py
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
@pytest.mark.e2e
class TestGearLibraryE2E:
    async def test_user_can_view_gear(self, page: Page, db_session, frontend_url: str):
        # Layer 1: UI action
        await page.goto(f"{frontend_url}/gear")

        # Layer 2: DOM verification
        await expect(page.locator('[data-testid="gear-list"]')).to_be_visible()

        # Layer 3: Database verification
        result = await db_session.execute(text("SELECT count(*) FROM gear"))
        assert result.scalar() > 0
```

### Three-Layer Verification

1. **UI action** -- `page.goto()`, `page.click()`, `page.fill()`
2. **DOM verification** -- `expect(locator).to_be_visible()`, text content checks
3. **Database verification** -- Direct DB queries to confirm persistence

---

## Key Fixtures

### Database Session (Transaction Rollback)

```python
@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await db_engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(bind=connection, class_=AsyncSession, expire_on_commit=False)()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
```

### Factory Pattern

```python
@pytest.fixture(scope="function")
def make_signal_chain(db_session: AsyncSession, test_user):
    async def _make(name: str = "Test Chain", **kwargs):
        chain = SignalChain(id=uuid4(), user_id=test_user.id, name=name, **kwargs)
        db_session.add(chain)
        await db_session.flush()
        await db_session.refresh(chain)
        return chain
    return _make
```

### Fixture Quick Reference

**Integration:**

| Fixture | Description |
|---------|-------------|
| `db_session` | Async DB session with transaction rollback |
| `test_user` | Authenticated test user |
| `other_user` | Second user for isolation tests |
| `client` | httpx AsyncClient (unauthenticated) |
| `authenticated_client` | httpx AsyncClient with auth |
| `auth_headers` | `{"Authorization": "Bearer ..."}` |
| `make_signal_chain` | Factory for SignalChain |
| `make_user_gear` | Factory for UserGear |
| `make_shootout` | Factory for Shootout |

**E2E:**

| Fixture | Description |
|---------|-------------|
| `page` | Authenticated Playwright page |
| `guest_page` | Unauthenticated page |
| `frontend_url` | Base URL (e.g., `http://localhost:9000`) |
| `db_session` | Direct DB access for verification |

---

## Test Templates

### Unit Test (Service with Real Repository)

```python
# tests/unit/backend/services/test_{module}.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.repositories.{module}_repo import {Module}Repository
from webapp.services.{module} import {Module}Service


class Test{Module}Service:
    @pytest.fixture
    def service(self, session: AsyncSession) -> {Module}Service:
        repository = {Module}Repository(session=session)
        return {Module}Service(repository=repository)

    async def test_validates_input(self, service):
        result = await service.validate({"name": "test"})
        assert result.is_valid is True

    async def test_rejects_empty_name(self, service):
        with pytest.raises(ValueError, match="Name cannot be empty"):
            await service.validate({"name": ""})
```

### Integration Test

```python
# tests/integration/backend/api/test_{endpoint}.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
@pytest.mark.integration
class Test{Endpoint}API:
    async def test_create(self, client: AsyncClient, auth_headers, test_user):
        response = await client.post(
            "/api/v1/{endpoint}",
            json={"name": "Test Item"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Test Item"

    async def test_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/{endpoint}")
        assert response.status_code == 401
```

### E2E Test (Playwright)

```python
# tests/e2e/python/tests/test_{feature}.py
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
@pytest.mark.e2e
class Test{Feature}E2E:
    async def test_creates_item(self, page: Page, db_session, frontend_url: str):
        # Layer 1: UI action
        await page.goto(f"{frontend_url}/{path}")
        await page.fill('[data-testid="name-input"]', 'My Item')
        await page.click('[data-testid="submit-btn"]')

        # Layer 2: DOM verification
        await expect(page.locator('[data-testid="success"]')).to_be_visible()

        # Layer 3: Database verification
        result = await db_session.execute(
            text("SELECT id FROM {table} WHERE name = :name"),
            {"name": "My Item"}
        )
        assert result.fetchone() is not None
```

### Page Object

```python
# tests/e2e/python/pages/{page}_page.py
from playwright.async_api import Page, expect

class {Page}Page:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.heading = page.locator('[data-testid="{page}-heading"]')
        self.submit = page.locator('[data-testid="submit-btn"]')

    async def goto(self):
        await self.page.goto(f"{self.base_url}/{path}")
        await expect(self.heading).to_be_visible()
```

### Factory Fixture

```python
# tests/integration/backend/conftest.py
@pytest.fixture(scope="function")
def make_{entity}(db_session: AsyncSession, test_user):
    async def _make(name: str = "Test {Entity}", **kwargs) -> {Entity}:
        entity = {Entity}(id=uuid4(), user_id=test_user.id, name=name, **kwargs)
        db_session.add(entity)
        await db_session.flush()
        await db_session.refresh(entity)
        return entity
    return _make
```

---

## Mutation Verification

For CRUD operations, verify persistence across three layers.

### Layer 1: UI Response
Check visual feedback -- success toast, no errors, expected state change.

### Layer 2: API Response
Check network tab for 2xx status. Watch for 409 (conflict), 422 (validation), 500 (crash).

### Layer 3: Database State

```bash
docker compose exec -T webapp python -c "
import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models import YourModel

async def check():
    async with async_session_factory() as session:
        result = await session.execute(
            select(YourModel).where(YourModel.id == 'your-id')
        )
        row = result.scalar_one_or_none()
        print('FOUND:', row.id if row else 'NOT_FOUND')
asyncio.run(check())
"
```

### Common Failure Patterns

| Symptom | Cause | Fix |
|---------|-------|-----|
| UI success, DB empty | Transaction not committed | `await session.commit()` |
| 409 Conflict | Unique constraint | Check for existing record |
| 500 Error | Missing foreign key | Verify related entity exists |
| Stale after refresh | Cache not invalidated | Clear cache after mutation |

---

## Markers Reference

| Marker | Use When | Auto-Applied |
|--------|----------|--------------|
| `unit` | Single function/class | `tests/unit/` |
| `integration` | Real DB/Redis | `tests/integration/` |
| `e2e` | Browser-based | `tests/e2e/` |
| `e2e_quick` | Fast E2E for CI | Manual |
| `e2e_full` | Comprehensive E2E | Manual |
| `smoke` | Critical path | Manual |
| `t3k_integration` | Real T3K API (skip in CI) | Manual |

---

## Failure Recovery

| Failure | Action |
|---------|--------|
| Tests won't pass | `just tdd <path> -v --tb=long` for verbose output |
| Test quality failed | Rewrite tests -- no trivial assertions |
| Golden path failing | Fix the product code, then re-run `just test-golden-path` |

---

## Related

- `.claude/rules/testing-policy.md` -- Testing policy (auto-loaded rule)
- [Validation and Testing](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Validation-and-Testing) -- wiki
