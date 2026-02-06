# MCP Tools Required for UI Work

## When MCP Is Required

MCP tools are required **only for UI/browser interaction:**
- Debugging UI issues (click doesn't work, page blank)
- Verifying visual changes
- Inspecting console/network errors

## Critical Rule

**If UI verification is needed and MCP is unavailable, STOP.**

Do not proceed with curl/grep workarounds. They cannot see:
- JavaScript console errors
- Network request failures
- DOM state

## What To Do If MCP Missing

1. **STOP** that line of investigation
2. **Tell the user:** "I need Chrome DevTools MCP to verify this UI behaviour"
3. **Wait** — user must enable MCP or provide the info
4. **Do NOT guess** — guessing wastes hours

## Required MCP Tools

- `chrome-devtools` MCP — Console, network, DOM inspection
- `playwright` MCP — Automated testing, screenshots

## Anti-Pattern (NEVER DO THIS)

```bash
curl -s http://localhost:9020/ | grep error  # Can't see JS errors
curl -s http://localhost:9020/gear | head    # Can't see why click fails
```
