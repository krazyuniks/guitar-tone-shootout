# GTS (Guitar Tone Shootout) - Project Overview

## Purpose
Web application for comparing guitar tones through blind A/B listening tests ("shootouts").

## Tech Stack
- **Backend**: FastAPI + SQLAlchemy 2.0 + PostgreSQL + Alembic migrations
- **Frontend**: Astro SSG (pre-built to `frontend/astro/dist/`) + Jinja2 SSR + HTMX + Alpine.js
- **Infrastructure**: Docker Compose, nginx reverse proxy, Redis (job queues)
- **Auth**: T3K passwordless OAuth (external provider)
- **Testing**: pytest (unit/integration in Docker), Playwright (E2E on host)

## Architecture
Monorepo with uv workspaces:
- `libs/core/` — domain models, repositories, services (gts_core)
- `libs/audio/` — audio processing (gts_audio)
- `libs/video/` — video composition with Remotion (gts_video)
- `apps/webapp/` — FastAPI web application (gts_webapp)
- `apps/worker/` — background job worker (gts_worker)
- `apps/scheduler/` — cron-like scheduler (gts_scheduler)
- `sources/t3k/` — T3K data source integration (gts_t3k_source)
- `frontend/astro/` — Astro SSG frontend (TypeScript)
- `templates/` — Jinja2 server-rendered templates
- `tests/` — all tests (unit, integration, e2e)

## Key Patterns
- Hexagonal architecture: domain → repositories → services → handlers
- SQLAlchemy relationships use `lazy="raise"`, queries use `joinedload`
- All dev commands via `just` (Docker-first execution)
- Git worktrees for parallel feature development
