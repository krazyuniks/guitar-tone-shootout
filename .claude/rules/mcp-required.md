# MCP Tools Required for UI Work

## Hard Constraints

- **UI work REQUIRES Chrome DevTools MCP.** Without it, the agent cannot verify UI changes.
- **E2E test authoring REQUIRES Playwright MCP.** Without it, the agent cannot write or run E2E tests.
- **If MCP is unavailable, STOP and FAIL.** Do not proceed with curl/grep workarounds.

## Automated Enforcement

The orchestrator's pre-flight check in `scripts/dispatch.py` verifies MCP availability before dispatching agents that need browser access. Stories with `http+dom`, `browser+db`, or `screenshot` validation checkpoints require Chrome DevTools MCP. Stories that author regression tests require Playwright MCP.

If MCP is unavailable at dispatch time, the orchestrator logs an `env` failure category and exits immediately (0 retries).

## Manual Sessions

For manual (non-orchestrated) sessions, the same rule applies:

1. **UI implementation** requires Chrome DevTools MCP -- invoke with `opus cp`
2. **E2E test authoring** requires Playwright MCP -- invoke with `opus p`
3. **Non-UI work** requires no MCP -- invoke with `opus`

## What To Do If MCP Missing

1. **STOP** immediately -- do not attempt any workaround
2. **Report:** "MCP server required but not available"
3. **Wait** -- user must restart with MCP enabled
4. **Do NOT guess** -- guessing wastes hours and produces untested code

## Anti-Patterns (NEVER DO THIS)

```bash
# BANNED -- curl is not testing
curl -s http://localhost:9010/ | grep error
curl -s http://localhost:9010/gear | head
curl http://localhost:9010/api/v1/health

# BANNED -- cannot verify UI without browser
echo "Page loads correctly" # How do you know?
```

## Required MCP Tools

- `chrome-devtools` MCP -- Console, network, DOM inspection, headless Chromium
- `playwright` MCP -- Automated browser testing, screenshots, E2E test execution
