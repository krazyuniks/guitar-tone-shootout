# Hot Reload Behaviour

How file changes trigger rebuilds in development.

## Quick Start

```bash
# Terminal 1: Start services
just up-d

# Terminal 2: Watch for changes (REQUIRED for frontend hot reload)
just watch-templates
```

## How Changes Work

| Component | Behaviour |
|-----------|-----------|
| Frontend (Astro) | Build to `astro/dist/`, nginx serves immediately |
| Backend (Python) | uvicorn auto-reloads on file changes |
| Jinja2 templates | Auto-reload on request (no restart needed) |

## Frontend (chokidar + Astro Build)

| File Type | Watch Pattern | Rebuild Output |
|-----------|---------------|----------------|
| `.astro` | `src/**/*.astro` | `astro/dist/` |
| `.tsx/.ts` | `src/**/*.{ts,tsx}` | `astro/dist/` |
| `.css` | `src/**/*.css` | `astro/dist/_astro/*.css` |
| React islands | `src/islands/*.tsx` | `astro/dist/islands/*.js` |

**Rebuild process:** chokidar detects change → triggers `pnpm build` → output to `astro/dist/` → nginx serves immediately (bind mount) → browser refresh shows changes.

**Prerequisite:** `just watch-templates` must be running.

## Backend (uvicorn --reload)

| File Type | Behaviour |
|-----------|-----------|
| `.py` | uvicorn auto-restarts |
| Jinja2 templates | Auto-reload on request (no restart needed) |
| Static files | Served directly by nginx, no restart needed |

## File Type Quick Reference

| Change This | Requires | Appears After |
|-------------|----------|---------------|
| `.astro` page | watch running | ~4s + refresh |
| `.css` styles | watch running | ~4s + refresh |
| React island | watch running | ~4s + refresh |
| Python code | nothing | ~2s (auto) |
| Jinja2 template | nothing | instant on refresh |
| Static file | nothing | instant on refresh |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No CSS changes | Watch not running | `just watch-templates` |
| Astro not rebuilding | chokidar not started | Restart frontend or run watch |
| Python not reloading | Container issue | `docker compose restart backend` |
| Islands stale | Cache issue | `just fix-frontend-rebuild` |
| Build errors | Syntax error | Check `docker compose logs frontend` |

### Changes Don't Appear

1. Check watch is running: `docker compose exec -T frontend pgrep -f "chokidar"`
2. Check for build errors: `docker compose logs frontend --tail=20`
3. Force rebuild: `just build-astro`
4. Verify dist/ is updated: `ls -la astro/dist/`

### CSS Not Updating

1. Verify `astro/src/styles/global.css` exists
2. Check `just watch-templates` is running
3. Look for `astro/dist/_astro/*.css` file
4. Hard refresh browser (Cmd+Shift+R)

## Key Difference from Traditional Dev Servers

No Vite dev server at runtime. The workflow is:
1. Edit files in `astro/src/`
2. Watch process compiles to `astro/dist/`
3. nginx serves pre-built files from bind-mounted directory
4. No HMR - full page refresh needed
