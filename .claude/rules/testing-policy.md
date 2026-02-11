# Testing Policy

## Hard Constraints

- **Use `just tdd <path>`** for running tests during development.
- **Test against real services. No mocking.** The `test_quality_check.py` gate bans all `unittest.mock` imports with zero exceptions.
- **E2E tests MUST:** Use `page.goto()` for navigation, assert DOM visibility, verify database state.
- **`just test-golden-path` is MANDATORY.** Every task must pass golden path tests before completion. This is the single regression gate for the project.
- **Golden path failures BLOCK completion.** Never swallow, skip, or work around golden path test failures.

## CRITICAL: No curl/wget as Validation

**NEVER use `curl`, `wget`, `httpie`, or any HTTP client as a substitute for actual testing.**

```bash
# BANNED — these prove nothing about the actual UI
curl -s http://localhost:9010/ | grep 200          # Can't see JS errors
curl -s http://localhost:9010/gear | head           # Can't see DOM state
curl http://localhost:9010/api/v1/health            # Not a substitute for E2E tests
wget -qO- http://localhost:9010/shootouts           # Can't verify user interaction
```

The ONLY acceptable validation is:
- `just test-golden-path` — E2E tests via Playwright
- `just tdd <path>` — unit/integration tests in Docker
- Chrome DevTools MCP — for manual UI inspection

## CRITICAL: E2E Tests Run on Host — No Internal Imports

E2E test files in `tests/e2e/python/tests/` run on the HOST, not in Docker. They **CANNOT** import internal packages:

```python
# BANNED in E2E tests — these packages are not available on host
from webapp.adapters.persistence.models.gear import Gear
from core.domain.entities.user import User
from audio.processing.nam import NAMProcessor
```

E2E tests use:
- **Playwright** for browser interaction
- **Raw SQL via `text()`** for database verification (asyncpg connects directly)
- **`conftest.py` fixtures** for `db_session`, `page`, `guest_page`, `frontend_url`

## Forbidden Patterns

```python
@patch('app.repositories.signal_chain_repo')  # NEVER mock internal services
mock_service = Mock(spec=SignalChainService)   # NEVER mock internal services
page.route('**/api/**', ...)                   # NEVER mock API in E2E tests
```

For test structure, fixtures, markers, and patterns, see the `gts-testing` skill.
For production-learned banned patterns (11 patterns), see `gts-testing` skill > "Production-Learned Banned Patterns".
