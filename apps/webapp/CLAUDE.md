# Webapp Bounded Context

User-facing FastAPI web application. Port 8000. Jinja2 SSR + HTMX + Alpine.js frontend.

## Dependencies

Can import: core, audio, video
Cannot import: sources (worker bridges this gap)

## Key Patterns

- All `/api/v1/*` routes require `CurrentUser` token authentication
- Resource ownership: always verify `resource.user_id == current_user.id`, return 404 not 403
- Jinja2 templates extend `layouts/base.html` (built by Astro)
- HTMX for small interactions only — not for page navigation
- All interactive elements need `data-testid` for Playwright
- Services → Repositories → ORM models (hexagonal layers)
- `joinedload` only, `.unique()` on collection results, `lazy="raise"` everywhere

## Key Files

- `src/webapp/main.py` — `create_app()` FastAPI entrypoint
- `src/webapp/auth/dependencies.py` — CurrentUser auth guard
- `src/webapp/api/v1/` — REST API endpoints (~17 route modules)
- `src/webapp/services/` — Business logic (~15 service classes)
- `src/webapp/adapters/persistence/repositories/` — SQLAlchemy repositories
- `src/webapp/adapters/persistence/models/` — ORM models (~19)
