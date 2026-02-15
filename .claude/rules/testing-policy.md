<!-- domains: testing -->
# Testing Policy
- Use `just tdd <path>` for running tests during development.
- Test against real services. No mocking. `unittest.mock` imports are banned (enforced by quality gate).
- `just test-golden-path` is MANDATORY before story completion. Failures BLOCK completion.
- Tests are regression nets written AFTER the product works, not the definition of done.
- NEVER use `curl`/`wget`/`httpie` as validation. Only: `just test-golden-path`, `just tdd`, Chrome DevTools MCP, orchestrator checkpoints.
- E2E tests run on HOST, not Docker. Cannot import internal packages. Use Playwright + raw SQL via `text()`.
- E2E tests MUST: use `page.goto()` for navigation, assert DOM visibility, verify database state.
- NEVER mock internal services or APIs in any test.
