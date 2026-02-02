---
name: frontend-architecture
description: Frontend architecture with Astro SSG (pre-built static pages) and Jinja2 SSR (server-rendered pages). HTMX for small fragment updates (card-sized or smaller). One build system, two rendering strategies.
context: fork
---

# Frontend Architecture

**Activation:** architecture, frontend routing, nginx, astro, jinja, when to use

> **CRITICAL: Pre-Bundled Architecture**
>
> **Astro is pre-bundled.** `astro/dist/` is committed to git. No Vite dev server at runtime.
>
> - nginx serves static files directly from bind-mounted `astro/dist/`
> - Runtime containers: db, backend, nginx
> - Astro container only used for builds (`just build-astro`)

> **CRITICAL:** Two rendering strategies, NOT two frontends.
>
> Astro is the **build system** for all templates. Static pages are served by nginx,
> dynamic pages are rendered by FastAPI/Jinja2. Both use the same design tokens and CSS.

## Architecture Overview

```
                           ┌─────────────────────────────────────────┐
                           │                 Nginx                    │
                           │  Port 80/443 (production) or 9000 (dev)  │
                           └──────────────────┬──────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
         ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
         │   Static Files   │      │   FastAPI/Jinja2 │      │     API Routes   │
         │  (Astro SSG)     │      │   (Dynamic)      │      │   /api/v1/*      │
         └──────────────────┘      └──────────────────┘      └──────────────────┘
                    │                         │                         │
                    │                         │                         │
         /, /about, /login        /shootouts, /library/*         REST + HTML
         /404, /500, /jobs        /shootout/*                   Fragments
```

## Route Ownership

### Static Pages (Astro SSG via Nginx)

| Route | Purpose |
|-------|---------|
| `/` | Home page |
| `/about` | About page |
| `/login` | OAuth login initiation |
| `/404` | Not found error page |
| `/500` | Server error page |
| `/report-error` | Error reporting form |
| `/report-error/thanks` | Error report confirmation |
| `/jobs` | Background jobs status |
| `/dev/showcase/*` | Component showcase (dev only) |

**Characteristics:**
- Pre-built at deploy time
- Served directly by nginx (fastest)
- No runtime server needed
- Uses Tailwind CSS

### Dynamic Pages (Jinja2/HTMX via FastAPI)

| Route | Purpose |
|-------|---------|
| `/shootouts` | Public shootout discovery |
| `/gear/{slug}` | Public pack detail page |
| `/library/my-gear` | User's saved gear |
| `/library/shootouts` | User's shootouts |
| `/library/chains` | User's signal chains |
| `/library/chains/build` | Signal chain builder (React island) |
| `/library/di-tracks` | User's DI tracks |
| `/shootout/{id}` | Shootout detail view |
| `/shootout/create` | Shootout creation wizard |

**Characteristics:**
- Server-rendered on each request
- Authentication-aware
- Uses HTMX for interactivity
- Uses Alpine.js for UI state

## Unified Design Tokens

Design tokens (CSS variables, Tailwind config) are defined ONCE in the Astro source and shared with Jinja2 templates via a build-time wrapper.

### Architecture

```
astro/src/styles/global.css (design tokens - single source of truth)
    ↓ Astro build (just build-astro)
astro/dist/layouts/base.html (Jinja2-compatible wrapper with CSS link)
astro/dist/_astro/*.css (compiled Tailwind with all design tokens)
    ↓ Committed to git, bind-mounted into containers
FastAPI loads templates from astro/dist (all templates pre-built by Astro)
    ↓
Dynamic pages extend the Astro-built wrapper
```

**Note:** `astro/dist/` is committed to git. Commit both source and dist after changes.

### How It Works

1. **Design tokens defined once:** `astro/src/styles/global.css` contains all CSS custom properties
2. **Astro builds a Jinja2 wrapper:** `astro/src/pages/layouts/base.html.astro` outputs a Jinja2-compatible template
3. **Compiled CSS included:** The wrapper links to the Astro-built CSS with all design tokens
4. **FastAPI loads templates:** All Jinja2 templates are served from `astro/dist`
5. **Jinja2 templates extend the wrapper:** Dynamic pages use `{% extends "layouts/base.html" %}` to get consistent styling

### Adding Design Tokens

To add or modify design tokens:

1. Edit `astro/src/styles/global.css`
2. Run `just build-astro` (or use `just watch-astro` for auto-rebuild)
3. Both static and dynamic pages automatically use the updated tokens
4. No backend restart needed - Jinja2 templates auto-reload from disk

### Shared Dependencies

Both rendering strategies load these libraries (via the unified wrapper):

| Library | Version | Purpose |
|---------|---------|---------|
| HTMX | 2.0.4 | Server-driven DOM updates |
| Alpine.js | 3.14.8 | Lightweight reactivity |
| Tailwind CSS | Built | Utility-first styling |

### Template Inheritance

**Astro pages:** Use `Layout.astro` component
**Jinja2 pages:** Extend `layouts/base.html` (from Astro build output)

## React Islands

React is used ONLY for `SignalChainBuilder` at `/library/chains/build`.

**Why React here:**
- Complex drag-drop interactions
- React DnD library requirements
- State management complexity

**Loading pattern:**
```html
<!-- In Jinja2 template -->
{% block scripts %}
<script src="/static/islands/signal-chain-builder.js"></script>
<script>
  window.SignalChainBuilder.mount('signal-chain-builder');
</script>
{% endblock %}
```

React is NOT loaded on any other page. Verify with browser DevTools if unsure.

## Decision Guide: Which Rendering Strategy?

| Requirement | Use This |
|-------------|----------|
| No authentication needed | Static (Astro SSG) |
| Content rarely changes | Static (Astro SSG) |
| SEO critical, no user data | Static (Astro SSG) |
| User-specific content | Dynamic (Jinja2/HTMX) |
| Authentication required | Dynamic (Jinja2/HTMX) |
| Real-time data needed | Dynamic (Jinja2/HTMX) |
| Complex interactivity (drag-drop) | React island |

## Nginx Routing Configuration

```nginx
# Static pages - served directly
location = / { try_files /index.html @backend; }
location = /about { try_files /about/index.html @backend; }
location = /login { try_files /login/index.html @backend; }

# Dynamic pages - proxy to FastAPI
location /shootouts { proxy_pass http://backend:8000; }
location /gear { proxy_pass http://backend:8000; }
location /library { proxy_pass http://backend:8000; }
location /shootout { proxy_pass http://backend:8000; }

# API routes
location /api { proxy_pass http://backend:8000; }
```

## Common Misconceptions

### "We should have only one rendering strategy"

**WRONG.** Each strategy serves its purpose:
- Static pages are faster (pre-built, nginx-served)
- Dynamic pages handle authentication and user-specific data
- Using both is intentional and optimal

### "HTMX is only for Jinja2 pages"

**WRONG.** HTMX can be used in Astro pages too. The home page uses HTMX for loading featured shootouts.

### "React is forbidden"

**WRONG.** React is used for SignalChainBuilder. The guidance is "React only where needed" not "never use React."

## File Locations

| Component | Location |
|-----------|----------|
| **Design tokens** | `astro/src/styles/global.css` |
| **Astro pages** | `astro/src/pages/` |
| **Astro layout** | `astro/src/layouts/Layout.astro` |
| **Jinja2 wrapper source** | `astro/src/pages/layouts/base.html.astro` |
| **Jinja2 wrapper (built)** | `astro/dist/layouts/base.html` (committed to git) |
| **Jinja2 pages** | `astro/dist/pages/` (built from `astro/src/pages/pages/`) |
| **HTMX fragments** | `astro/dist/fragments/` (built from `astro/src/pages/fragments/`) |
| **React island** | `astro/src/islands/` |
| **Compiled CSS** | `astro/dist/_astro/*.css` (committed to git) |
| **Static pages (built)** | `astro/dist/*.html` (committed to git) |

## Quality Verification

When modifying templates:

```bash
# Build Astro (auto-reloads in backend)
just build-astro

# Watch mode (run in separate terminal) - auto-rebuilds on file changes
just watch-astro

# Astro checks
docker compose --profile build exec astro pnpm lint
docker compose --profile build exec astro pnpm check

# Backend checks (templates served by FastAPI)
docker compose exec backend mypy app/
docker compose exec backend pytest /tests/integration/backend/ -k page

# Full check
just check
```

## Related Skills

- `gts-frontend-dev` - Jinja2/HTMX development patterns
- `htmx` - HTMX-specific patterns
- `testing` - Playwright tests for both rendering strategies
