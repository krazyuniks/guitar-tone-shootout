# Web Application Foundation - Implementation Plan

**Epic:** #5
**Milestone:** v2.0 - Web Application Foundation
**Created:** 2025-12-26

---

## Executive Summary

Establish the Docker-based development infrastructure for the Guitar Tone Shootout web application. This epic creates the foundation that all other epics depend on: containerized services, FastAPI backend, PostgreSQL database, and Astro frontend.

---

## Current State

- Project has `pipeline/` with audio processing code (preserved)
- Project has `web/` with Flask + HTMX (deprecated, to be removed after frontend complete)
- Docker Compose dev/prod environments operational
- `backend/` with FastAPI, SQLAlchemy 2.0, Alembic migrations
- `frontend/` with Astro + React + Tailwind CSS 4

---

## Target State

```
guitar-tone-shootout/
├── backend/                    # FastAPI (NEW)
│   ├── app/
│   ├── alembic/
│   ├── Dockerfile.dev
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                   # Astro + React (NEW)
│   ├── src/
│   ├── Dockerfile.dev
│   ├── Dockerfile
│   └── package.json
├── pipeline/                   # Audio/video (PRESERVED)
├── docker-compose.yml          # Dev environment (NEW)
├── docker-compose.prod.yml     # Prod environment (NEW)
└── .env.example                # Environment template (NEW)
```

---

## Implementation Phases

### Phase 1: Docker Development Environment (#6)

**Goal:** `docker compose up` starts all services with hot-reload

**Deliverables:**
- `docker-compose.yml` with db, redis, backend, frontend, worker services
- `backend/Dockerfile.dev` with Python 3.12, uv, hot-reload
- `frontend/Dockerfile.dev` with Node 20, pnpm, Astro dev server
- `.env.example` with all required environment variables

**Acceptance Criteria:**
- [ ] `docker compose up` starts all 5 services
- [ ] Backend code changes trigger uvicorn reload
- [ ] Frontend code changes trigger Astro rebuild
- [ ] Database data persists across restarts
- [ ] Logs visible in terminal

### Phase 2: Docker Production Environment (#7)

**Goal:** Production-ready Docker images

**Deliverables:**
- `docker-compose.prod.yml` with production configuration
- `backend/Dockerfile` with multi-stage build, gunicorn
- `frontend/Dockerfile` with static build output

**Acceptance Criteria:**
- [ ] Production images are optimized (small size)
- [ ] Backend runs with gunicorn
- [ ] Frontend serves static files

### Phase 3: FastAPI Project Structure (#8)

**Goal:** Minimal FastAPI application with health endpoint

**Deliverables:**
- `backend/app/main.py` with FastAPI app
- `backend/app/api/health.py` with health endpoint
- `backend/app/core/config.py` with settings
- `backend/pyproject.toml` with dependencies

**Acceptance Criteria:**
- [ ] `GET /health` returns 200 OK
- [ ] Settings loaded from environment
- [ ] OpenAPI docs at `/docs`

### Phase 4: Database Setup (#9)

**Goal:** SQLAlchemy 2.0 async with Alembic migrations

**Deliverables:**
- `backend/app/core/database.py` with async engine
- `backend/app/models/base.py` with Base class
- `backend/alembic/` with migration configuration
- Initial migration with users table

**Acceptance Criteria:**
- [ ] Async database connection works
- [ ] `alembic upgrade head` applies migrations
- [ ] `alembic revision --autogenerate` creates migrations

### Phase 5: Documentation Update (#10)

**Goal:** README and AGENTS.md reflect new workflow

**Deliverables:**
- Updated README.md with Docker instructions
- Updated AGENTS.md with new patterns
- Remove references to old CLI workflow

**Acceptance Criteria:**
- [ ] Quick start instructions work
- [ ] Development workflow documented
- [ ] No references to deprecated `web/` directory

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Docker performance on macOS | Medium | Use Docker Desktop with VirtioFS |
| Hot-reload latency | Low | Optimize volume mounts |
| Dependency conflicts | Medium | Use uv for reproducible Python |

---

## Dependencies

This epic has no dependencies and blocks all other epics:
- v2.1 (Tone 3000) depends on v2.0
- v2.2 (Jobs) depends on v2.0
- v2.3 (Frontend) depends on v2.0
- v2.4 (Pipeline) depends on v2.0

---

## Success Metrics

1. `docker compose up` starts in <60 seconds
2. Hot-reload triggers in <3 seconds
3. All quality gates pass in containers
4. Zero host machine dependencies (except Docker)
