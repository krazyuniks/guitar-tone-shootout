# Frontend Architecture

Two rendering strategies, one build system.

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
         │  (Astro SSG)     │      │   (Dynamic)      │      │   /api/*      │
         └──────────────────┘      └──────────────────┘      └──────────────────┘
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

## Unified Design Tokens

```
astro/src/styles/global.css (define tokens here)
    ↓ Astro build (just build-astro)
astro/dist/layouts/base.html (Jinja2-compatible wrapper with CSS link)
astro/dist/_astro/*.css (compiled Tailwind with all design tokens)
    ↓ Committed to git, bind-mounted into containers
FastAPI loads templates from astro/dist (all templates pre-built by Astro)
    ↓
Dynamic pages extend the Astro-built wrapper
```

## Shared Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| HTMX | 2.0.4 | Server-driven DOM updates |
| Alpine.js | 3.14.8 | Lightweight reactivity |
| Tailwind CSS | Built | Utility-first styling |

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

## React Islands

React is used ONLY for `SignalChainBuilder` at `/library/chains/build`.

**Why React here:** Complex drag-drop interactions, React DnD library requirements, state management complexity.

React is NOT loaded on any other page.

## File Locations

| Component | Location |
|-----------|----------|
| **Design tokens** | `astro/src/styles/global.css` |
| **Astro pages** | `astro/src/pages/` |
| **Astro layout** | `astro/src/layouts/Layout.astro` |
| **Jinja2 wrapper source** | `astro/src/pages/layouts/base.html.astro` |
| **Jinja2 wrapper (built)** | `astro/dist/layouts/base.html` |
| **Jinja2 pages** | `astro/dist/pages/` |
| **HTMX fragments** | `astro/dist/fragments/` |
| **React island** | `astro/src/islands/` |
| **Compiled CSS** | `astro/dist/_astro/*.css` |
