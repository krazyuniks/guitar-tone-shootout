---
name: gts-testing
description: "Testing for GTS: regression test authoring, pytest patterns, fixtures, scaffolding, mutation verification, and anti-patterns. Use when writing tests, debugging test failures, scaffolding new test files, or verifying mutations persist."
context: fork
---

# GTS Testing

Single reference for all testing in GTS. See `.claude/rules/testing-policy.md` for policy (auto-loaded).

## Reference Files

| Working On | Read |
|---|---|
| Test scaffolding templates (unit, integration, E2E, factory) | references/test-scaffolding.md |
| Test suite audit (dead code, coverage gaps, health score) | references/audit.md |

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

---

## Regression Test Authoring

Tests are written AFTER the product works. Validation confirms the feature functions, then a regression test captures that working behaviour.

### Common Mistakes (from Production Runs)

| Mistake | Correct Behaviour |
|---|---|
| Modified existing test files | Only CREATE new test files. Existing tests are immutable contracts. |
| Ran the full test suite | Only run YOUR new/modified test files during development. |
| Imported non-existent packages | Use standard imports. Fail with ImportError, not SyntaxError. |
| Used wrong conftest fixtures | Unit and integration fixtures are separate. Check which conftest applies. |
| Hit max turns without finishing | Start with the simplest test. Iterate. Don't plan upfront. |

---

## Test Structure & Placement

```
tests/
  conftest.py              # Root config: markers, pytest_plugins
  fixtures/                # Shared fixtures (database, auth, factories)
  unit/
    backend/               # Pure logic, no external deps
    video/                 # Video composition tests
  integration/
    backend/               # Real DB, pgmq tests
    video/                 # Video API tests
  regression/              # Stack connectivity (<1s)
  e2e/
    python/                # E2E tests (pytest + Playwright, HOST only)
      conftest.py          # Browser fixtures, auth, DB access
      tests/               # Test files
```

### Placement Decision

| Question | Yes | No |
|---|---|---|
| Browser-based? | `tests/e2e/python/tests/` (HOST) | Continue below |
| Needs real DB/pgmq? | `tests/integration/` (Docker) | `tests/unit/` (Docker) |

---

## Antipatterns

### Banned Test Patterns

| Pattern | Issue |
|---------|-------|
| `assert True` / `assert x` (truthy only) | Trivial or weak |
| `mock.assert_called()` alone | Spy-only, no effect verification |
| `pass` only / `@pytest.mark.skip` | No assertions / defeats purpose |
| `time.sleep()` | Flaky indicator |
| `importlib.util` / `find_spec` | Fragile, use standard imports |
| `db_session.get_bind()` | Returns sync Engine, breaks async |

### Forbidden Mocking

No mocking. The quality gate bans `unittest.mock`, `@patch`, `Mock()`, `MagicMock()`, `AsyncMock()`.

---

## Production-Learned Banned Patterns

These caused repeated failures in automated runs.

### Test-Authoring

| # | Pattern | Why Banned | Correct Approach |
|---|---------|-----------|-----------------|
| 1 | `importlib.util` / `find_spec` | False failures (module found, attrs not loaded) | Standard import; missing file = collection failure |
| 2 | `AsyncSession.get_bind()` | Returns sync Engine | Use fixtures directly |
| 3 | `AsyncClient(app=...)` | Removed in HTTPX 0.28+ | `AsyncClient(transport=ASGITransport(app=app), ...)` |
| 4 | Inline `FastAPI()` without `set_session_override()` | Missing DB session | Use conftest autouse fixture |
| 5 | Testing backward-compat import removal | Unsolvable contradiction | Test NEW location works |
| 6 | `from __future__ import annotations` in route modules | Breaks `Depends()` runtime resolution (422 errors) | Import types directly |
| 7 | Query param name mismatch | Test URL param != endpoint param | Use `Query(None, alias="...")` |

### Infrastructure

| # | Pattern | Correct Approach |
|---|---------|-----------------|
| 8 | Close session + recreate from engine | `db_session.expire_all()` + re-query |
| 9 | `db_session.begin()` nesting | Conftest uses `_TestAsyncSession` with `begin_nested()` fallback |
| 10 | Module existence testing | Just import it; missing file = collection failure |
| 11 | `conftest.py` is NOT a test file | Can be modified by ALL agents for fixture changes |
| 12 | Test helpers in production modules | Put in `tests/fixtures/` or `conftest.py` |
| 13 | `lazy="raise"` relationship access | Use `joinedload()` or `session.refresh(obj, ["rel"])` |

---

## E2E Testing (Golden Path)

E2E tests live in `tests/e2e/python/tests/` and run on **HOST only** via `just test-golden-path`.

### Three-Layer Verification

1. **UI action** -- `page.goto()`, `page.click()`, `page.fill()`
2. **DOM verification** -- `expect(locator).to_be_visible()`, text content checks
3. **Database verification** -- Direct DB queries via `text()` (no ORM imports on host)

### Key Constraints

- Uses Playwright (not available in Docker)
- CANNOT import internal packages (`webapp`, `gts`, `audio`) -- use raw SQL via `text()`
- Regression gate for the project

---

## Key Fixtures

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

## Mutation Verification

For CRUD operations, verify persistence across three layers:

1. **UI Response** -- Success toast, no errors, expected state change
2. **API Response** -- 2xx status (watch for 409 conflict, 422 validation, 500 crash)
3. **Database State** -- Direct query to confirm persistence

| Symptom | Cause | Fix |
|---------|-------|-----|
| UI success, DB empty | Transaction not committed | `await session.commit()` |
| 409 Conflict | Unique constraint | Check for existing record |
| 500 Error | Missing foreign key | Verify related entity exists |
| Stale after refresh | Cache not invalidated | Clear cache after mutation |

---

## Markers

| Marker | Use When | Auto-Applied |
|--------|----------|--------------|
| `unit` | Single function/class | `tests/unit/` |
| `integration` | Real DB, pgmq | `tests/integration/` |
| `e2e` | Browser-based | `tests/e2e/` |
| `e2e_quick` / `e2e_full` | Fast/comprehensive E2E | Manual |
| `smoke` | Critical path | Manual |
| `t3k_integration` | Real T3K API (skip in CI) | Manual |

---

## Failure Recovery

| Failure | Action |
|---------|--------|
| Tests won't pass | `just tdd <path> -v --tb=long` |
| Test quality failed | Rewrite -- no trivial assertions |
| Golden path failing | Fix product code, then re-run |
