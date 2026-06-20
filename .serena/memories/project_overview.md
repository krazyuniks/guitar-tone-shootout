# GTS (Guitar Tone Shootout) - Project Overview

## Purpose
Web application for comparing guitar tones through blind A/B listening tests ("shootouts").

## Tech Stack
- **Backend**: FastAPI + SQLAlchemy 2.0 + PostgreSQL + Alembic migrations
- **Frontend**: Astro SSG (pre-built to `frontend/astro/dist/`) + Jinja2 SSR + HTMX + Alpine.js
- **Infrastructure**: Docker Compose, nginx reverse proxy, pgmq (PostgreSQL message queues)
- **Auth**: T3K passwordless OAuth (external provider)
- **Testing**: pytest (unit/integration in Docker), Playwright (E2E on host)

## Architecture
Monorepo with uv workspaces:
- `model/gts/` — domain models, repositories, services (gts_core)
- `model/audio/` — audio processing (gts_audio)
- `model/video/` — video composition with Remotion (gts_video)
- `apps/webapp/` — FastAPI web application (gts_webapp)
- `apps/t3k-sync/` — T3K data source sync worker (gts_t3k_sync)
- `apps/audio-worker/` — audio processing worker (gts_audio_worker)
- `apps/video-worker/` — video composition worker (gts_video_worker)
- `frontend/astro/` — Astro SSG frontend (TypeScript)
- `templates/` — Jinja2 server-rendered templates
- `tests/` — all tests (unit, integration, e2e)

## Key Patterns
- Onion architecture: domain → repositories → services → handlers
- SQLAlchemy relationships use `lazy="raise"`, queries use `joinedload`
- All dev commands via `just` (Docker-first execution)
- Git worktrees for parallel feature development
