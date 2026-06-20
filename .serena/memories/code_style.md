# Code Style & Conventions

## Python
- Python 3.14+ (pinned in `.python-version`)
- Ruff for linting and formatting (pinned version in pyproject.toml)
- mypy strict mode on `gts_core`
- Type hints required on all public functions
- No `unittest.mock` — tests use real services
- SQLAlchemy 2.0 style (select statements, not query API)
- Pydantic v2 for all API schemas

## Naming
- snake_case for Python (modules, functions, variables)
- PascalCase for Python classes
- camelCase for TypeScript/JavaScript
- PascalCase for Astro/React components

## Architecture Patterns
- Repository pattern for data access (SQLAlchemy)
- Service layer for business logic coordination
- Onion architecture: gts has no dependencies on apps
- `lazy="raise"` on all SQLAlchemy relationships
- `joinedload` for eager loading (never selectinload/subqueryload)
- One query per service method

## Frontend
- Astro SSG pre-built, dist committed to git
- Jinja2 templates extend `layouts/base.html`
- HTMX for small interactions only (not page navigation)
- Alpine.js for client-side UI state
- Tailwind CSS via design tokens
- All interactive elements need `data-testid` attributes
- No CDN resources, no inline styles, no SPA navigation

## Dependency Rules
- gts → (nothing)
- audio → gts
- video → gts
- sources → gts only
- webapp → gts, audio, video (NOT sources)
- worker → gts, audio, video (bridges sources)
