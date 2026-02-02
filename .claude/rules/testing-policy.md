# Testing Policy

## Claude's Role

- Write TDD tests during feature development
- Run the specific test(s) being implemented
- Fix failures in those tests
- If unsure → stop and ask

## Running Tests

Use: `just tdd <test_path>`

Examples:
- `just tdd tests/unit/backend/test_foo.py::test_bar` - Single test
- `just tdd tests/unit/backend/test_foo.py` - Single file

## Where to Put Tests

| Test Type | Location | When |
|-----------|----------|------|
| Unit | `tests/unit/backend/` | Pure logic, no DB/Redis |
| Integration | `tests/integration/backend/` | Needs real DB/Redis |
| E2E | `tests/e2e/python/tests/` | Browser interaction |

See `tests/AGENTS.md` for detailed structure guidance.

## What Claude Does NOT Do

- Run full test suites
- Run lint or type checks
- Worry about coverage thresholds
- Run tests unless implementing them

## Testing Philosophy

**Core Principle:** Test against real services. No mocking internal systems.

**Test against REAL:**
- PostgreSQL (catches schema issues, constraints)
- Redis (catches serialization, TTL behavior)
- Backend API (catches routing, middleware, auth)

**Mock ONLY external network APIs:**
- Tone3000 API (rate limits, flaky in CI)
- Email services (don't send real emails)
- Payment APIs (don't charge real cards)

**Forbidden patterns:**
```python
# NEVER mock internal services
@patch('app.repositories.signal_chain_repo')  # NO
mock_service = Mock(spec=SignalChainService)  # NO

# NEVER mock API in E2E tests
page.route('**/api/**', ...)  # NO
```

**E2E tests MUST:**
- Use `page.goto()` for navigation (NOT `context.request`)
- Assert DOM elements are visible
- Verify database state for data persistence

See `tests/AGENTS.md` for full structure and patterns.
