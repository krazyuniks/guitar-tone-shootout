---
description: Interactive site verification - walk through user journey with MCP tools
allowed-tools: Bash(docker compose:*), Bash(curl:*), Read, Grep, Edit, Write, mcp__chrome-devtools__*, mcp__playwright__*
context: conversation
---

# /site-verify - Interactive Site Verification

Walk through the complete user journey, verifying each page with Chrome DevTools MCP.

## Prerequisites Check

First verify environment:

```bash
# Check services
docker compose ps | grep -E "(backend|nginx)" | grep -q "running" && echo "Services: OK" || echo "Services: NOT RUNNING"

# Check backend health
curl -s http://localhost:9010/health | grep -q "ok" && echo "Backend: OK" || echo "Backend: UNHEALTHY"
```

If prerequisites fail, stop and inform user.

## Required: Chrome DevTools MCP

This command requires Chrome DevTools MCP to be connected. If not available:
- Stop immediately
- Tell user: "Chrome DevTools MCP required. Please connect and retry."

## Verification Workflow

Work through each step interactively with the user:

### Phase 1: Public Pages

1. Navigate to `/` - Verify home page loads
2. Navigate to `/about` - Verify static page
3. Navigate to `/gear` - Verify gear browse
4. Navigate to `/gear/{first-pack-slug}` - Verify gear detail
5. Navigate to `/di-tracks` - Verify DI tracks browse

At each step:
- Take snapshot (`mcp__chrome-devtools__take_snapshot`)
- Check console for errors (`mcp__chrome-devtools__list_console_messages`)
- Report status to user
- Wait for user acknowledgment before proceeding

### Phase 2: Authentication

If user wants to test authenticated flows:
1. Check auth status: `./worktree.py auth-status`
2. If not authenticated, guide through `./worktree.py auth-login`
3. Verify session via `/api/v1/auth/me`

### Phase 3: Authenticated Pages

Only if auth available:
1. Navigate to `/library/my-gear`
2. Navigate to `/library/chains`
3. Navigate to `/library/di-tracks`
4. Navigate to `/library/shootouts`

At each step, verify page loads and check for errors.

### Phase 4: Full Journey (Optional)

If user wants complete journey:
1. Add gear to library
2. Create signal chain group
3. Build a chain
4. Upload DI track (or use existing)
5. Create shootout
6. Verify job processing

## Bug Resolution

When a bug is found:
1. **Stop** and document the issue
2. **Investigate** root cause
3. **Ask user** if they want to fix now or continue
4. If fixing: implement fix, verify, update tests
5. **Continue** verification

## Output

After verification, provide summary:

```markdown
## Verification Summary

| Phase | Pages | Status |
|-------|-------|--------|
| Public | 5/5 | PASS |
| Auth | 1/1 | PASS |
| Library | 4/4 | PASS |

Issues: [none / list issues]
```
