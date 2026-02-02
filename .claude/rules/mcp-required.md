# MCP Tools Required for UI Work

## When MCP Is Required

MCP tools are required **only when UI/browser interaction is needed**:
- Debugging UI issues (click doesn't work, page blank, etc.)
- Verifying visual changes
- Running end-to-end tests
- Inspecting console/network errors

## When MCP Is NOT Required

- Planning and design discussions
- Backend-only work
- Database/API work
- Documentation
- Code review
- Admin tasks

## Critical Rule

**If UI verification is needed and MCP is unavailable, STOP.**

Do not proceed with curl/grep workarounds. They cannot see:
- JavaScript console errors
- Network request failures
- DOM state
- Why a click does nothing

## What To Do If MCP Missing Mid-Task

If working on planning/backend and a UI question arises:
1. **STOP** that line of investigation
2. **Tell the user** - "I need Chrome DevTools MCP to verify this UI behavior"
3. **Wait** - User must enable MCP or provide the info
4. **Do NOT guess** - Guessing wastes hours

## Required MCP Tools for UI Work

- `chrome-devtools` MCP - Console, network, DOM inspection
- `playwright` MCP - Automated testing, screenshots

## Anti-Pattern (NEVER DO THIS)

```
# BAD - Guessing at UI issues without tools
curl -s http://localhost:9020/ | grep error  # Can't see JS errors
curl -s http://localhost:9020/gear | head    # Can't see why click fails
# Then making "fixes" based on guesses...
```

## Correct Pattern

```
# GOOD - Stop and ask
"I need Chrome DevTools MCP enabled to debug this UI issue.
Can you enable it, or share the console errors from F12?"
```
