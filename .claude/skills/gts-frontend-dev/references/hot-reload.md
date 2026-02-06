# Hot Reload Behaviour

How file changes trigger rebuilds in development.

## Quick Start

```bash
# Start services (astro auto-starts with chokidar watcher)
just up-d
```

No separate watch command needed — the astro service runs chokidar automatically.

## How Changes Work

| Component | Behaviour |
|-----------|-----------|
| Frontend (Astro) | Chokidar watches source, auto-builds to `astro/dist/`, nginx serves immediately |
| Backend (Python) | uvicorn auto-reloads on file changes |
| Jinja2 templates | Auto-reload on request (no restart needed) |

## Frontend (chokidar + Astro Build)

| File Type | Watch Pattern | Rebuild Output |
|-----------|---------------|----------------|
| `.astro` | `src/**/*.astro` | `astro/dist/` |
| `.tsx/.ts` | `src/**/*.{ts,tsx}` | `astro/dist/` |
| `.css` | `src/**/*.css` | `astro/dist/_astro/*.css` |
| React islands | `src/islands/*.tsx` | `astro/dist/islands/*.js` |

**Rebuild process:** chokidar detects change -> triggers `pnpm build` (includes `inject-css-hash.js`) -> output to `astro/dist/` -> nginx serves immediately (bind mount) -> browser refresh shows changes.

**CSS hash injection:** After each build, `scripts/inject-css-hash.js` replaces the `CSS_PLACEHOLDER` in `dist/layouts/base.html` with the actual hashed CSS filename, ensuring Jinja2 templates always reference the correct CSS file.

## Backend (uvicorn --reload)

| File Type | Behaviour |
|-----------|-----------|
| `.py` | uvicorn auto-restarts |
| Jinja2 templates | Auto-reload on request (no restart needed) |
| Static files | Served directly by nginx, no restart needed |

## File Type Quick Reference

| Change This | Requires | Appears After |
|-------------|----------|---------------|
| `.astro` page | nothing (auto) | ~4s + refresh |
| `.css` styles | nothing (auto) | ~4s + refresh |
| React island | nothing (auto) | ~4s + refresh |
| Python code | nothing | ~2s (auto) |
| Jinja2 template | nothing | instant on refresh |
| Static file | nothing | instant on refresh |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No CSS changes | Astro not running | `docker compose up -d astro` |
| Astro not rebuilding | Container unhealthy | `docker compose restart astro` |
| Python not reloading | Container issue | `docker compose restart webapp` |
| Build errors | Syntax error | `just watch-astro` (view logs) |

### Changes Don't Appear

1. Check astro is healthy: `docker compose ps astro`
2. Check for build errors: `just watch-astro` (follows logs)
3. Force rebuild: `just build-astro`
4. Verify dist/ is updated: `ls -la frontend/astro/dist/`

### CSS Not Updating

1. Verify `astro/src/styles/global.css` exists
2. Check astro container is running: `docker compose ps astro`
3. Look for `astro/dist/_astro/*.css` file
4. Check `dist/layouts/base.html` has correct CSS filename (not `CSS_PLACEHOLDER`)
5. Hard refresh browser (Cmd+Shift+R)

## Key Difference from Traditional Dev Servers

No Vite dev server at runtime. The workflow is:
1. Edit files in `astro/src/`
2. Chokidar detects change and triggers `pnpm build`
3. Post-build script injects CSS hash into `base.html`
4. nginx serves pre-built files from bind-mounted directory
5. No HMR — full page refresh needed
