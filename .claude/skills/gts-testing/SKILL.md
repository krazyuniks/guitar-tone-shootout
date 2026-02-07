---
name: gts-testing
description: "Testing for GTS: TDD workflow, pytest patterns, fixtures, scaffolding, mutation verification, and anti-patterns. Use when writing tests, implementing features via TDD, debugging test failures, scaffolding new test files, or verifying mutations persist."
context: fork
---

# GTS Testing

Single reference for all testing in GTS. Covers TDD workflow, pytest patterns, fixtures, scaffolding, and mutation verification.

**Philosophy:** Test real services, mock only external network APIs. See `.claude/rules/testing-policy.md`.

## Quick Reference

| Command | Purpose | Where |
|---------|---------|-------|
| `just tdd <path>` | Run single test | Docker |
| `just test-unit` | All unit tests | Docker |
| `just test-integration` | All integration tests | Docker |
| `just test-regression` | Stack connectivity (<1s) | Docker |
| `just test-golden-path` | Golden path E2E | Host |
| `just check` | Full quality gates | Docker |

### TDD Orchestration

| Command | Purpose |
|---------|---------|
| `just epic-sync 42` | Sync epic from GitHub |
| `just epic-start 42` | Begin TDD state machine |
| `just epic-status 42` | Check progress |
| `just tdd-red T43` | Verify tests fail |
| `just tdd-lock T43` | Snapshot tests |
| `just tdd-green T43` | Verify tests pass |
| `just tdd-complete T43` | Full validation |

---

## Workspace-Aware Test Taxonomy

GTS uses uv workspaces. Each workspace member is a bounded context with its own test directories.

### Test Placement by Workspace

| Workspace Member | Unit | Integration | Golden Path E2E |
|---|---|---|---|
| `libs/core` | `tests/unit/core/` | `tests/integration/core/` | Covered via webapp E2E |
| `libs/audio` | `tests/unit/audio/` | `tests/integration/audio/` | N/A |
| `apps/webapp` | `tests/unit/webapp/` | `tests/integration/webapp/` | `tests/e2e/python/` |
| `apps/worker` | `tests/unit/worker/` | `tests/integration/worker/` | N/A |
| `sources/t3k` | `tests/unit/t3k/` | `tests/integration/t3k/` | N/A |

**Key insight:** E2E tests are webapp-scoped. They cover the full stack (UI → services → models → DB) which exercises `apps/webapp` + `libs/core` together. Not every workspace member needs E2E tests.

### Directory Structure

```
tests/
├── conftest.py              # Root config: markers, pytest_plugins
├── fixtures/                # Shared fixtures
│   ├── database.py          # DB session with transaction rollback
│   ├── auth.py              # JWT tokens, auth headers
│   └── factories.py         # Test data factories
├── unit/                    # Pure logic, no external deps (Docker)
│   ├── core/                # libs/core domain logic
│   ├── audio/               # libs/audio processing
│   ├── webapp/              # apps/webapp ORM, services
│   └── worktree/            # worktree tooling
├── integration/             # Real DB/Redis tests (Docker)
│   ├── audio/               # Audio processing with real files
│   ├── webapp/              # Repository, migration tests
│   └── worker/              # Worker job tests
├── regression/              # Stack connectivity (SQLite, <1s)
│   └── test_stack.py
└── e2e/
    ├── python/              # Golden path E2E (host, Playwright)
    │   ├── conftest.py      # Browser fixtures, auth, DB access
    │   └── tests/           # Test files
    └── smoke/               # Infrastructure smoke tests
```

### Placement Decision Tree

```
Is it a browser-based / full-stack test?
├── YES → tests/e2e/python/tests/  (runs on HOST)
└── NO → Does it need real DB/Redis?
    ├── YES → tests/integration/{workspace}/  (runs in DOCKER)
    └── NO → tests/unit/{workspace}/  (runs in DOCKER)
```

Where `{workspace}` matches the source: `core`, `audio`, `webapp`, `worker`, `t3k`.

---

## Golden Path Test

A single living E2E test that proves the full stack works end-to-end. Updated as features ship.

### How It Works

- **Command:** `just test-golden-path`
- **Runs on host** (not Docker) — uses Playwright to hit the running Docker stack
- **Location:** `tests/e2e/python/tests/`
- **Isolated package:** `tests/e2e/python/pyproject.toml` with its own venv

### Living Test Philosophy

The golden path test grows with the application. Each new feature adds specific `data-testid` checks:

```python
# Example: gear browse page should show gear packs from DB
async def test_gear_browse_shows_packs(page, frontend_url):
    await page.goto(f"{frontend_url}/gear")
    pack_list = page.locator('[data-testid="gear-browse"]')
    await expect(pack_list).to_be_visible()
    # Verify real data from DB (not empty)
    pack_cards = page.locator('[data-testid="item-card"]')
    count = await pack_cards.count()
    assert count > 0, "Gear browse should show packs from database"
```

### When to Update the Golden Path

- New page/route added → add navigation + visibility check
- New CRUD feature → add create/read/delete flow
- New data display → add `data-testid` presence check with data assertion

### Auth for Protected Routes

Routes under `/library/*` require authentication. Before running golden path tests:

```bash
# 1. Authenticate (once, shared across worktrees)
./worktree.py auth-login

# 2. Restore session in current worktree
./worktree.py auth-restore

# 3. Verify
./worktree.py auth-status
```

Auth tokens are stored in `../.gts-auth.json` (shared file in worktrees parent directory). `auth-restore` calls `POST /api/v1/auth/restore-session` to create a local session.

**If auth is expired:** Re-run `./worktree.py auth-login` — T3K uses passwordless OAuth (email magic link).

---

## TDD Discipline

### Why Test-First Matters in Automated Pipelines

The TDD state machine (`run_epic.py`) enforces separation: test-author writes tests, implementer makes them pass. This prevents implementation bias in test design.

If the same agent writes tests and code, it unconsciously designs tests that match its implementation rather than the specification. Separate agents with separate tool permissions eliminate this.

### Iron Law

No production code without a failing test first. If you didn't watch the test fail, you don't know if it tests the right thing.

### Common Rationalisations to Resist

| Rationalisation | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll fix the test to match my implementation" | Tests are contracts. Fix your code, not the test. |
| "This test is wrong" | Maybe. But report it — don't silently change it. |
| "All tests pass so I'm done" | Tests passing is necessary but not sufficient. Check quality. |
| "I need to modify the test to handle an edge case" | Edge cases get NEW tests. Existing tests are immutable. |

### Test-Author Workflow

1. **Read** the task spec — extract acceptance criteria and scope files
2. **Create** new test file(s) in the correct workspace directory (see Placement Decision Tree)
3. **Write** tests that import from the expected module paths — even if those modules don't exist yet. A correct red test fails with `ImportError` or `AssertionError`, not `SyntaxError`.
4. **Run only your files**: `just tdd tests/unit/webapp/test_your_file.py` — not the full suite
5. **Verify** they fail for the right reasons, then stop

### Implementer Workflow

1. **Read** the test files first — they are your specification
2. **Start small** — pick the simplest failing test, make it pass, then move to the next
3. **Run iteratively**: `just tdd <your_test_path>` after each change
4. **Don't over-plan** — write enough code to pass the current test, then reassess

### Fixture Scoping

Fixtures are scoped by directory. Only fixtures from your test's ancestor `conftest.py` files are available:

```
tests/conftest.py                     → markers, pytest_plugins (all tests)
tests/unit/conftest.py                → unit-specific (NO database)
tests/integration/webapp/conftest.py  → db_session, factories, auth
tests/e2e/python/conftest.py          → page, browser, frontend_url
```

Unit tests cannot use integration fixtures (`db_session`, `make_signal_chain`, etc.) — they live in a different conftest hierarchy.

---

## TDD Workflow Phases

### Phase 1: Test Specification
- **Agent:** `test-author` (tools: Read, Write, Edit, Bash, Glob, Grep)
- **Path:** `tests/**/*.py` only
- Tests MUST fail. No trivial assertions.

### Phase 2: Red Verification
- **Command:** `just tdd-red T43`
- Verifies all tests fail (not error)
- Retry: test-author gets 1 retry with failure context

### Phase 3: Lock
- **Command:** `just tdd-lock T43`
- SHA-256 snapshots of test files
- Committed with `test-lock:` prefix

### Phase 4: Implementation
- **Agent:** `implementer` (tools: Read, Write, Edit, Bash, Glob, Grep)
- **Path:** `libs/`, `apps/`, `sources/` only
- Tests are immutable. CANNOT modify test files.

### Phase 5: Green Verification
- **Command:** `just tdd-green T43`
- Verifies all tests pass
- Retry: implementer gets 2 retries with failure context

### Phase 6: Full Validation
- **Command:** `just tdd-complete T43`
- Tests pass + unchanged since lock + quality checks + regression + golden path

### State Location

```
.tasks/projects/guitar-tone-shootout/epics/E{n}/
├── index.md      # Status, dependency graph
├── tasks/        # Task specs (source of truth)
├── snapshots/    # Test file hashes (TDD enforcement)
└── logs/         # Execution logs, error reports
```

---

## Antipatterns

### Banned Test Patterns

| Pattern | Issue |
|---------|-------|
| `assert True` | Trivial — proves nothing |
| `assert x` (truthy only) | Weak — doesn't verify specific value |
| `mock.assert_called()` alone | Spy-only — no effect verification |
| Empty test (`pass` only) | No assertions |
| `@pytest.mark.skip` | Skipped — defeats purpose |
| `time.sleep()` | Flaky indicator |
| `importlib.util` / `find_spec` | Banned — use standard imports |
| `db_session.get_bind()` | Banned — use fixtures directly |

### Bad vs Good

```python
# BAD — truthy check
def test_validate_email_works():
    result = validate_email('test@example.com')
    assert result  # What does "truthy" even mean here?

# GOOD — specific assertion
def test_validate_email_rejects_invalid_format():
    result = validate_email('not-an-email')
    assert result.valid is False
    assert result.error == 'Invalid email format'
```

### Forbidden Mocking

```python
# NEVER mock internal services
@patch('app.repositories.signal_chain_repo')  # NO
mock_service = Mock(spec=SignalChainService)   # NO

# NEVER mock API in E2E tests
page.route('**/api/**', ...)  # NO
```

**Mock ONLY external network APIs:** T3K API, email services, payment APIs.

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

**E2E (Golden Path):**

| Fixture | Description |
|---------|-------------|
| `page` | Authenticated Playwright page |
| `guest_page` | Unauthenticated page |
| `frontend_url` | Base URL (e.g., `http://localhost:9000`) |
| `db_session` | Direct DB access for verification |

---

## Test Templates

### Unit Test

```python
# tests/unit/webapp/services/test_{module}.py
import pytest
from webapp.services.{module} import {Module}Service

class Test{Module}Service:
    @pytest.fixture
    def service(self) -> {Module}Service:
        return {Module}Service(repository=Mock())

    def test_validates_input(self, service):
        result = service.validate({"name": "test"})
        assert result.is_valid is True

    def test_rejects_empty_name(self, service):
        with pytest.raises(ValueError, match="Name cannot be empty"):
            service.validate({"name": ""})
```

### Integration Test

```python
# tests/integration/webapp/api/test_{endpoint}.py
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

### Golden Path E2E Test

```python
# tests/e2e/python/tests/test_golden_path.py
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
@pytest.mark.e2e
class TestGoldenPath:
    """Living test — updated as features ship."""

    async def test_homepage_loads(self, page: Page, frontend_url: str):
        await page.goto(frontend_url)
        await expect(page).to_have_title(re.compile("Guitar Tone"))

    async def test_gear_browse_shows_data(self, page: Page, frontend_url: str):
        await page.goto(f"{frontend_url}/gear")
        browse = page.locator('[data-testid="gear-browse"]')
        await expect(browse).to_be_visible()
        cards = page.locator('[data-testid="item-card"]')
        assert await cards.count() > 0
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
# tests/integration/webapp/conftest.py
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
Check visual feedback — success toast, no errors, expected state change.

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
| `regression` | Golden path gate | `tests/e2e/python/` |
| `t3k_integration` | Real T3K API (skip in CI) | Manual |

---

## Failure Recovery

| Failure | Action |
|---------|--------|
| Tests modified during impl | `just snapshot-diff T43` then reset impl files |
| Tests won't pass | `just tdd <path> -v --tb=long` for verbose output |
| Epic halted | Check `logs/errors/`, fix issue, re-run `run_epic.py run 42` |
| Test quality failed | Rewrite tests — no trivial assertions |
| Golden path auth fails | `./worktree.py auth-login` then `./worktree.py auth-restore` |

---

## Related

- `.claude/rules/testing-policy.md` — Claude's testing role (auto-loaded rule)
- [TDD Workflow](https://github.com/krazyuniks/guitar-tone-shootout/wiki/TDD-Workflow) — wiki
- [Validation and Testing](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Validation-and-Testing) — wiki
