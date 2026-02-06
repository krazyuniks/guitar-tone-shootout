# Testing Policy

## Hard Constraints

- **Use `just tdd <path>`** for running tests during development.
- **Test against real services.** No mocking internal systems (DB, Redis, backend API).
- **Mock ONLY external network APIs** (Tone3000, email, payment).
- **E2E tests MUST:** Use `page.goto()` for navigation, assert DOM visibility, verify database state.

## Forbidden Patterns

```python
@patch('app.repositories.signal_chain_repo')  # NEVER mock internal services
mock_service = Mock(spec=SignalChainService)   # NEVER mock internal services
page.route('**/api/**', ...)                   # NEVER mock API in E2E tests
```

For test structure, fixtures, markers, and patterns, see the `gts-testing` skill.
