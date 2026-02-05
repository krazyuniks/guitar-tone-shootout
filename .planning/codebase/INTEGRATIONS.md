# External Integrations

**Analysis Date:** 2026-02-05

## APIs & External Services

**Tone3000 (T3K) - Gear Catalog:**
- Service: Tone3000 gear library API
- What it's used for: Syncing gear packs, models, and presets into GTS
- SDK/Client: httpx (async HTTP client in `sources/t3k/`)
- Auth: OAuth 2.0 (email magic link, passwordless)
  - Env vars: `T3K_CLIENT_ID`, `T3K_CLIENT_SECRET`
  - Token storage: `.gts-auth.json` (shared across worktrees, encrypted)
  - Base URL: `T3K_API_URL` (default: `https://api.tone3000.com`)

**Google Fonts - Typography:**
- Service: Google Fonts CDN
- What it's used for: Font delivery for web UI
- URL: `https://fonts.googleapis.com`, `https://fonts.gstatic.com`
- Loaded via: nginx CSP policy and Jinja2/Astro templates

**UNPKG CDN - JavaScript Libraries:**
- Service: UNPKG CDN
- What it's used for: HTMX and Alpine.js delivery
- URLs: `https://unpkg.com`
- Loaded via: nginx CSP policy, HTML templates

## Data Storage

**Databases:**
- PostgreSQL 16 (dual-database architecture)
  - gts_core: Main application data (users, shootouts, chains, gear selections)
    - Accessed by: webapp, worker, scheduler
    - Connection: `postgresql+asyncpg://gts:{password}@db:5432/gts_core`
  - gts_t3k_source: T3K source data (packs, models, presets)
    - Accessed by: worker ONLY (webapp has NO direct access)
    - Connection: `postgresql+asyncpg://gts:{password}@db:5432/gts_t3k_source`
  - Client: SQLAlchemy 2.0.36+ with asyncpg driver
  - Migrations: Alembic (`infrastructure/migrations/`)

**Message Queues (PostgreSQL pgmq extension):**
- pgmq-sqlalchemy 0.1.0+ for async queue operations
- gts_t3k_source database (T3K sync):
  - `gear_pack_sync` - Pack catalog updates
  - `gear_model_sync` - Model updates
  - `preset_sync` - Preset updates
  - `sync_dead_letter` - Failed sync messages
- gts_core database (internal jobs):
  - `audio_processing` - Audio rendering jobs
  - `video_composition` - Video composition jobs
  - `notifications` - User notifications
  - `jobs_dead_letter` - Failed job messages

**File Storage:**
- Local filesystem (bind-mounted Docker volumes)
  - Upload storage: `/app/uploads` (user uploads, DI tracks)
  - Processed storage: `/app/processed` (rendered audio, videos)
  - NAM models: `/app/models/nam` (Neural Amp Modeling models)
  - IR files: `/app/models/ir` (Impulse Response files)
- Volume names: `gts-uploads-{worktree}`, `gts-processed-{worktree}`

**Caching:**
- Redis 7-alpine (via docker)
  - Purpose: TaskIQ job broker (worker/scheduler only)
  - NOT accessed by webapp
  - Connection: `redis://redis:6379`
  - Data: Job queue, background task state

## Authentication & Identity

**Auth Provider:**
- Custom session-based auth + T3K OAuth integration
- Implementation: `apps/webapp/src/webapp/auth/` (location: TBD in codebase exploration)
  - Session cookies: httponly, secure (prod), samesite=lax
  - Duration: 7 days (extended from 30 min)
  - T3K OAuth: Passwordless email magic link (no passwords stored)

**Session Storage:**
- Redis (via TaskIQ) or database (session table in gts_core)
- Encryption: `OAUTH_ENCRYPTION_KEY` (Fernet 32-byte key)

**Auth File Persistence:**
- `.gts-auth.json` (shared across worktrees in parent directory)
  - Contains: T3K user ID, username, OAuth tokens
  - Permissions: 0600 (owner read/write only)
  - Location: `guitar-tone-shootout-worktrees/.gts-auth.json`
  - Auto-refresh: Tokens refreshed on OAuth flow

## Monitoring & Observability

**Error Tracking:**
- Not detected (no Sentry/Rollbar integration)

**Logs:**
- Container logs via `docker compose logs`
- Application logs: stdout/stderr (captured by Docker)
- Health checks:
  - Webapp: `GET /health` (FastAPI health endpoint)
  - Database: pg_isready check
  - Redis: redis-cli ping

**Admin API (Worker port 8001, not exposed publicly):**
- Job monitoring: `/admin/jobs/`, `/admin/jobs/{id}`, `/admin/jobs/dead-lettered`
- Retry endpoint: `/admin/jobs/{id}/retry`
- T3K sync status: `/admin/t3k/sync/status`, `/admin/t3k/sync`, `/admin/t3k/sync/stats`
- Auth status: `/admin/t3k/auth/status`
- Health: `/health` (composite health check)

**CLI Admin Tool:**
- `gts-admin` command (location: `scripts/gts-admin`)
  - Commands: `jobs`, `job {id}`, `t3k-status`, `auth-status`

## CI/CD & Deployment

**Hosting:**
- Docker Compose (development/feature worktrees)
- Docker containers (webapp, worker, scheduler, db, redis, nginx)
- Traefik support (via `docker-compose.traefik.yml`) for HTTPS/subdomain routing
- Kubernetes-ready (Docker images with no host dependencies)

**CI Pipeline:**
- GitHub Actions (`.github/workflows/`)
  - TDD enforcement workflow: `tdd-enforcement.yml`
  - Triggers: Pull requests, commits to main

**Build Pipeline:**
- Astro frontend builds to `frontend/astro/dist/` (committed to git)
- Multi-stage Dockerfiles for production builds:
  - `infrastructure/docker/Dockerfile.dev` (development with bind mounts)
  - `infrastructure/docker/Dockerfile.webapp` (production webapp)
  - `infrastructure/docker/Dockerfile.worker` (production worker)
  - `infrastructure/docker/Dockerfile.scheduler` (production scheduler)

**Deployment Patterns:**
- Docker Compose overlay pattern:
  - `docker-compose.yml` (base, committed)
  - `docker-compose.override.yml` (worktree-specific, auto-generated)
  - `docker-compose.traefik.yml` (HTTPS, committed)
  - `docker-compose.ci.yml` (ephemeral for CI, committed)

## Environment Configuration

**Required env vars:**
- Database: `DB_PASSWORD`, `DATABASE_URL`, `T3K_DATABASE_URL`
- Security: `SECRET_KEY`, `OAUTH_ENCRYPTION_KEY`
- Ports: `NGINX_PORT`, `BACKEND_PORT`, `DB_PORT`, `REDIS_PORT`
- T3K OAuth: `T3K_CLIENT_ID`, `T3K_CLIENT_SECRET`, `T3K_API_URL`
- Storage: `UPLOAD_PATH`, `PROCESSED_PATH`, `NAM_MODELS_PATH`, `IR_FILES_PATH`
- Environment: `ENV` (development/staging/production)

**Secrets location:**
- Development: `.env` and `.env.local` (git-ignored)
- CI: GitHub Secrets repository settings
- Production: Platform-specific (Railway, Fly.io, K8s secrets)

**Configuration files:**
- `.env.example` - Template with no real values
- `pyproject.toml` - Workspace and app configuration
- `docker-compose.yml`, `docker-compose.override.yml`, `docker-compose.traefik.yml`
- `infrastructure/nginx/nginx.conf.template` (processed via envsubst)

## Webhooks & Callbacks

**Incoming:**
- OAuth callback: T3K → `POST /auth/oauth/callback` (FastAPI route)
  - Handles token exchange and session creation
  - Saves tokens to `.gts-auth.json` for worktree sharing

**Outgoing:**
- None detected (no outbound webhooks)

**Internal Message Queues:**
- pgmq (PostgreSQL message queues):
  - T3K adapter publishes sync messages → worker consumes
  - Worker publishes job messages → TaskIQ processes
  - Failed messages go to dead-letter queues for manual inspection

---

*Integration audit: 2026-02-05*
