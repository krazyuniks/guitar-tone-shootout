# Technology Stack

**Analysis Date:** 2026-02-05

## Languages

**Primary:**
- Python 3.12+ - Backend services (webapp, worker, scheduler), audio processing, testing
- TypeScript/Node.js - Frontend build system (Astro)
- SQL - Database schema and migrations

**Secondary:**
- Jinja2 - Server-side template rendering
- HTML/CSS - Frontend templates and styling
- Bash - Container initialization, scripts

## Runtime

**Environment:**
- Python 3.12+ (defined in root `pyproject.toml`)
- Node.js (via Astro/pnpm for frontend builds)

**Package Manager:**
- uv (Python workspace monorepo)
  - Lockfile: `uv.lock` (implied in workspace structure)
  - Workspace members: `libs/*`, `sources/*`, `apps/*`
- pnpm (Node.js frontend dependencies)
  - Package file: `frontend/astro/package.json`

## Frameworks

**Core:**
- FastAPI 0.115.0+ - Web framework, REST API, SSR page routing
  - Entry point: `apps/webapp/src/webapp/main.py`
  - Serves both API (`/api/v1`) and SSR pages (`/gear`, `/shootouts`, `/library/*`)

**Database & ORM:**
- SQLAlchemy 2.0.36+ (asyncio) - ORM for `gts_core` and `gts_t3k_source` databases
  - Async driver: asyncpg 0.30.0+
  - Migrations: Alembic 1.14.0+
  - Location: `infrastructure/migrations/`

**Background Jobs:**
- TaskIQ 0.11.0+ - Background job broker
  - Redis backend: taskiq-redis 1.0.0+
  - Worker container: processes async jobs and pgmq messages
  - Scheduler container: runs cron-based tasks

**Frontend Build:**
- Astro 5.1.6+ - Static site generator, builds to pre-compiled output
  - Styling: Tailwind CSS 3.4.1+
  - Type checking: Astro check (via @astrojs/check)
  - Output: `frontend/astro/dist/` (committed to git, served by nginx)

**Testing:**
- pytest 8.3.0+ - Test runner
  - Async support: pytest-asyncio 0.24.0+
  - Coverage: pytest-cov 6.0.0+
- Playwright (E2E tests, location: `tests/e2e/python/`)

**Build/Dev:**
- Hatchling - Python build backend
- Ruff 0.9.0+ - Linter and formatter
- mypy 1.14.0+ - Static type checker (strict mode)
- import-linter 2.1+ - Enforce dependency contracts (location: `pyproject.toml` root)

## Key Dependencies

**Critical:**
- uvicorn 0.34.0+ - ASGI application server for FastAPI
- Pydantic 2.10.0+ - Request/response validation
- SQLAlchemy + asyncpg - Async database access
- cryptography 44.0.0+ - Session encryption, OAuth token encryption
- httpx 0.28.0+ - Async HTTP client (T3K API, external integrations)

**Audio Processing:**
- pedalboard 0.9.0+ - Guitar signal processing (amp models, effects)
- torch 2.5.0+ - PyTorch for NAM (Neural Amp Modeling) inference
- torchaudio 2.5.0+ - Audio utilities
- scipy 1.14.0+ - Scientific computing
- numpy 2.0.0+ - Numerical arrays
- soundfile 0.12.0+ - Audio file I/O
- pyloudnorm 0.1.1+ - Loudness analysis and normalization
- moviepy 2.0.0+ - Video composition and rendering

**Message Queue:**
- pgmq-sqlalchemy 0.1.0+ - PostgreSQL message queue client
  - Message queues:
    - `gear_pack_sync`, `gear_model_sync`, `preset_sync` (T3K → gts_core via worker)
    - `audio_processing`, `video_composition`, `notifications` (internal jobs)
    - `sync_dead_letter`, `jobs_dead_letter` (failed message handling)

**Caching & Sessions:**
- Redis 7-alpine (Docker container) - Job broker, session storage
  - Accessed by worker and scheduler
  - NOT accessed by webapp (worker is the bridge)

**Session & Auth:**
- itsdangerous 2.2.0+ - Session token signing
- pydantic-settings 2.7.0+ - Environment configuration

**Request Handling:**
- python-multipart 0.0.18 - Form data parsing
- Jinja2 3.1.0+ - Template rendering for SSR pages

**Database Connectivity:**
- psycopg2-binary 2.9.0+ - PostgreSQL adapter
- redis 5.2.0+ - Redis client

## Configuration

**Environment:**
- `.env` (development) and `.env.example` (template) at project root
- `.env.local` (auto-generated per worktree, git-ignored)
- Environment variables manage:
  - Database credentials (`DB_PASSWORD`, `DATABASE_URL`, `T3K_DATABASE_URL`)
  - Security keys (`SECRET_KEY`, `OAUTH_ENCRYPTION_KEY`)
  - Service URLs (`NGINX_PORT`, `BACKEND_PORT`, `DB_PORT`, `REDIS_PORT`)
  - Storage paths (`UPLOAD_PATH`, `PROCESSED_PATH`, `NAM_MODELS_PATH`, `IR_FILES_PATH`)
  - T3K OAuth (`T3K_CLIENT_ID`, `T3K_CLIENT_SECRET`, `T3K_API_URL`)

**Build:**
- `pyproject.toml` (root) - Workspace configuration, linting, type checking, testing
- `pyproject.toml` (per app/lib) - Dependencies, build targets
- `.pre-commit-config.yaml` - Pre-commit hooks for git

**Linting & Formatting:**
- `tool.ruff` in root `pyproject.toml`:
  - Target: Python 3.12
  - Line length: 100 characters
  - Rules: E, W, F, I, B, C4, UP, ARG, SIM, TCH, PTH, RUF
  - Ignore: E501 (long lines), B008 (FastAPI Depends), B904, ARG001

**Type Checking:**
- `tool.mypy` in root `pyproject.toml`:
  - Strict mode enabled
  - Python version: 3.12
  - Excludes: `infrastructure/migrations/`

**Testing:**
- `tool.pytest` in root `pyproject.toml`:
  - Async mode: auto
  - Test paths: `tests/`
  - Markers: slow, integration, e2e, smoke

## Platform Requirements

**Development:**
- Python 3.12+
- Docker (dev environment)
- Docker Compose (orchestration)
- Node.js/pnpm (frontend builds only)
- Port availability: 5432 (DB), 6379 (Redis), 8000 (backend), 9000 (nginx)

**Production:**
- PostgreSQL 16+ (via docker image `postgres:16-alpine`)
- Redis 7+ (via docker image `redis:7-alpine`)
- nginx (via docker image `nginx:alpine`)
- Python 3.12 runtime (in container)

**Testing:**
- E2E tests run on host with Playwright
- Integration/Unit tests run in Docker containers
- Coverage tracking via pytest-cov

---

*Stack analysis: 2026-02-05*
