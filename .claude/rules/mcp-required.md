# MCP Tools Required for UI Work

## Hard Constraints

- **Implementer (webapp project) REQUIRES Chrome DevTools MCP.** Without it, the agent cannot verify UI changes.
- **Test-author (webapp project) REQUIRES Playwright MCP.** Without it, the agent cannot write or run E2E tests.
- **If MCP is unavailable, STOP and FAIL.** Do not proceed with curl/grep workarounds.

## Pre-Flight Gate

Any entry point that dispatches agents for frontend/webapp work MUST verify MCP availability:

1. **State machine (`run_epic.py`):** `build_mcp_config()` must provide Chrome DevTools for implementer, Playwright for test-author
2. **Skills:** Any skill that involves UI work must check for MCP tools in the conversation
3. **Manual dispatch:** User must invoke with MCP enabled (e.g., `opus cp`, `sonnet c`)

## MCP Server Configuration

MCP servers are enabled via the `cld` wrapper and `--strict-mcp-config --mcp-config` flags:

| Agent | Required MCP | User CLI |
|-------|-------------|----------|
| implementer (webapp) | Chrome DevTools + Playwright | `opus cp` |
| test-author (webapp) | Playwright | `opus p` |
| implementer (other) | None | `opus` |
| test-author (other) | None | `opus` |

## What To Do If MCP Missing

1. **STOP** immediately — do not attempt any workaround
2. **Report:** "MCP server required but not available"
3. **Wait** — user must restart with MCP enabled
4. **Do NOT guess** — guessing wastes hours and produces untested code

## Anti-Patterns (NEVER DO THIS)

```bash
# BANNED — curl is not testing
curl -s http://localhost:9010/ | grep error
curl -s http://localhost:9010/gear | head
curl http://localhost:9010/api/v1/health

# BANNED — cannot verify UI without browser
echo "Page loads correctly" # How do you know?
```

## Required MCP Tools

- `chrome-devtools` MCP — Console, network, DOM inspection, headless Chromium
- `playwright` MCP — Automated browser testing, screenshots, E2E test execution
