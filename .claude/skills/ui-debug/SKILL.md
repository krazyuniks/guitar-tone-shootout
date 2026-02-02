# UI Debug Skill

Proactive error detection during frontend development using Chrome DevTools MCP.

## When to Use

- After editing UI files (`.astro`, `.html`, `.ts`, `.tsx`, `.css`, `.jinja2`)
- When user reports "it doesn't work" or "nothing happens"
- When testing UI changes or features
- When page loads but doesn't behave as expected

## Prerequisites

- Chrome DevTools MCP must be available
- Docker services running (`just up-d`)
- Browser connected to DevTools

## Error Detection Checklist

After any UI change, run this checklist:

### 1. Navigate to Affected Page

```
mcp__chrome-devtools__navigate url="http://localhost:9000/..."
```

### 2. Check Console for JavaScript Errors

```
mcp__chrome-devtools__get_console_logs
```

**Look for:**
- `TypeError` - Property access on undefined/null
- `ReferenceError` - Undefined variable
- `SyntaxError` - JavaScript syntax issues
- `NetworkError` - Fetch/AJAX failures
- HTMX errors: `htmx:xhr:error`, `htmx:responseError`
- Alpine.js errors: `Alpine Expression Error`

### 3. Check Network for Failed Requests

```
mcp__chrome-devtools__get_network_logs
```

**Look for:**
- Status >= 400 (client/server errors)
- Status 0 (request blocked or CORS)
- Pending requests that never complete
- `OPTIONS` preflight failures

### 4. Take Screenshot for Verification

```
mcp__chrome-devtools__screenshot
```

## Common Error Patterns

| Console Error | Likely Cause | Fix |
|---------------|--------------|-----|
| `Uncaught TypeError: Cannot read property 'x' of undefined` | Missing data or timing issue | Check API response, add null checks |
| `404 Not Found` | Missing endpoint or asset | Verify route exists, check URL typos |
| `500 Internal Server Error` | Backend exception | Check Docker logs |
| `CORS policy blocked` | Cross-origin issue | Check CORS config, use nginx proxy |
| `htmx:responseError` | HTMX request failed | Check network tab for actual error |
| `Alpine Expression Error` | Bad Alpine.js syntax | Check x-data, x-on expressions |

## Integration with PostToolUse Hook

When Edit/Write modifies UI files:
1. Hook prints reminder to check DevTools
2. Wait for hot reload (~3 seconds)
3. Run console/network checks
4. Fix any new errors before continuing

## UI File Types

| Extension | Technology | Hot Reload |
|-----------|------------|------------|
| `.astro` | Astro SSG | Automatic (Vite) |
| `.html` | Jinja2 templates | Automatic (FastAPI) |
| `.jinja2` | Jinja2 templates | Automatic |
| `.ts`, `.tsx` | TypeScript/React | Automatic (Vite) |
| `.css` | Tailwind/CSS | Automatic |

## Debugging Flow

```
1. Make UI change
    ↓
2. Wait for hot reload (3s)
    ↓
3. Check console logs (JS errors?)
    ↓
4. Check network logs (API failures?)
    ↓
5. If errors found → FIX FIRST
    ↓
6. If no errors → Continue work
```

## Common Fixes

### HTMX Request Fails

1. Check network tab for actual HTTP status
2. If 401: Add auth redirect handler
3. If 404: Verify endpoint route
4. If 500: Check Docker backend logs

### Alpine.js Not Working

1. Check console for expression errors
2. Verify `x-data` is valid JSON/JS object
3. Check for typos in directive names

### Page Loads But Empty

1. Check network for failed data fetches
2. Verify API returns expected data
3. Check for JavaScript errors blocking render

### Click Does Nothing

1. Check console for JS errors
2. Verify event handlers are attached
3. Check if element has `disabled` or pointer-events issues

## MCP Not Available?

If Chrome DevTools MCP is not available and UI debugging is needed:

1. **STOP** - Don't guess at errors
2. Ask user to enable MCP or share console errors
3. Do NOT use curl/grep as substitutes
4. Do NOT make blind fixes

See `.claude/rules/mcp-required.md` for full policy.
