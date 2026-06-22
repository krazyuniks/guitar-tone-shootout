# Infrastructure Management & Workflow

Developer tooling for parallel development and environment management.

## First-Time Setup

Tiered bootstrap process for new developers.

**Tier 0 -- Prerequisites:**
- Docker + Docker Compose v2
- uv (Python package manager)
- just (task runner)
- git + gh CLI

**Tier 1 -- Project Dependencies:**
- Worktree CLI dependencies
- E2E test dependencies (Playwright, Chromium)

**Tier 2 -- Service Startup:**
- Docker services started
- Database migrations applied
- Auth tokens restored (if available)

**Bootstrap command:**
```bash
./scripts/first-time-setup.sh
```

The script detects missing prerequisites and offers to install them via the appropriate package manager (cargo, brew, apt, pacman).

## Worktree Management

Git worktrees enable parallel development with isolated Docker environments. One worktree per feature/issue.

**CLI:** `worktree.py` (Typer-based, PEP 723 inline dependencies)

| Command Group | Purpose |
|---------------|---------|
| `setup` | Create/configure worktree (idempotent) |
| `teardown` | Remove worktree and resources |
| `info` | Show worktree details |
| `auth` | OAuth token management |
| `services` | Docker service control |
| `git` | Branch operations |
| `sync` | Session sync (start/stop) |
| `maintenance` | Cleanup, health checks |

**Key features:**
- Idempotent setup (safe to re-run)
- Automatic port and network allocation
- Docker Compose isolation per worktree
- SQLite registry for worktree state
- Auth token sharing across worktrees

## Justfile

Task runner with commands for development workflow. Use `just --list` for discovery.

| Category | Key Commands |
|----------|--------------|
| **Docker** | `up-d`, `down`, `rebuild`, `logs`, `shell`, `status` |
| **Quality** | `check`, `lint`, `check-types`, `check-imports` |
| **Testing** | `tdd`, `test-regression`, `test`, `test-unit`, `test-integration`, `test-golden-path` |
| **Database** | `migrate`, `db-export`, `db-import`, `psql` |
| **Frontend** | `build-astro`, `watch-astro`, `check-astro`, `verify-astro-build` |
| **Git Hooks** | `install-hooks`, `run-hooks`, `uninstall-hooks` |
| **Infrastructure** | `infra` (host setup), `clean` |

## Docker Compose

**Runtime Services:**

| Service | Purpose |
|---------|---------|
| `db` | PostgreSQL (data + pgmq queues) |
| `webapp` | FastAPI application + event consumers + background tasks |
| `nginx` | Reverse proxy, static files |
| `t3k-sync` | T3K source sync (eternal loop, jobs profile) |
| `audio-worker` | Audio processing consumer (jobs profile) |
| `video-worker` | Video composition consumer (jobs profile) |

**Profiles:**

| Profile | Services | Usage |
|---------|----------|-------|
| `jobs` | t3k-sync, audio-worker, video-worker | Main worktree only (BC worker containers) |
| `build` | astro | Frontend build (on-demand) |
| `tools` | cloudbeaver | Database IDE (optional) |
| `observability` | prometheus, loki, tempo, grafana, alloy | Monitoring stack (optional) |

Feature worktrees run without the `jobs` profile — they use data synced from main.

## Shared Resources

Resources shared across all worktrees:

| Resource | Location | Purpose |
|----------|----------|---------|
| Storage | `../gts-storage/` | Models, uploads, audio, videos |
| Auth tokens | `../.gts-auth.json` | OAuth tokens (600 permissions) |
| Bare repository | `../gts.git/` | Shared git objects |
| Registry | `../.worktree/registry.db` | Worktree state (SQLite) |

## Claude Code Integration

Infrastructure hooks prevent destructive operations and manage session state.

| Hook | Purpose |
|------|---------|
| `block-adhoc-infra.sh` | Prevents ad-hoc Docker volume/network operations |
| `auth-check.sh` | Warns if OAuth tokens expiring |
| `sync-start.sh` | Pulls latest from origin on session start |

## Deployment

Self-hosted Docker on dedicated server (Hetzner).

### Environments

| Environment | URL | Compose Files |
|-------------|-----|---------------|
| Development (main) | https://main.tone-shootout.com | base + override + traefik |
| Feature worktrees | https://{issue}.tone-shootout.com | base + override + traefik |
| CI | -- | base + ci |
| Production | https://www.tone-shootout.com | prod + traefik |

### Docker Compose Overlays

Deployment uses layered compose files (overlay pattern):

| File | Purpose | Committed |
|------|---------|-----------|
| `docker-compose.yml` | Base config (no ports, no worktree-specific values) | Yes |
| `docker-compose.override.yml` | Worktree-specific (ports, container names) | Yes (INTERIM) |
| `docker-compose.traefik.yml` | Public access (SSL, subdomain routing) | Yes |
| `docker-compose.ci.yml` | CI (ephemeral volumes, test isolation) | Yes |

**Key principles:**
- `docker-compose.yml` is worktree-agnostic
- `docker-compose.override.yml` provides worktree-specific values (ports, container names)
- **INTERIM:** Override is committed. Phase 7 will auto-generate it via `worktree.py` (then gitignored)
- All services use `Dockerfile.dev` for development (uv installed for testing in container)

```bash
# Local development (always use just)
just up-d  # Auto-detects Traefik, adds jobs profile on main

# Underlying compose commands (for reference):
# docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
# docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.traefik.yml up -d

# CI
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d
```

### SSL/TLS

Traefik handles SSL termination for all environments:
- Wildcard certificate for `*.tone-shootout.com`
- Cloudflare DNS challenge for Let's Encrypt
- Automatic HTTP-to-HTTPS redirect
- Per-worktree routers (e.g., `gts-main`, `gts-526`)

### Secrets Management

| Environment | Method |
|-------------|--------|
| Development | `.env` file (gitignored) |
| CI | GitHub Secrets |
| Production | Docker secrets (`/run/secrets/`) |

Production secrets:
- `secrets/secret_key` - JWT signing key
- `secrets/db_password` - Database password

```bash
# Production setup
mkdir -p secrets && chmod 700 secrets
openssl rand -hex 32 > secrets/secret_key
```

### Resource Limits (Production)

| Service | Memory | CPU |
|---------|--------|-----|
| nginx | 128M | -- |
| webapp | 1G | 1.0 |
| t3k-sync | 512M | 0.5 |
| audio-worker | 2G | 2.0 |
| video-worker | 2G | 2.0 |
| db | 512M | -- |

### CI Pipeline

GitHub Actions workflow:

| Stage | Tests | Trigger |
|-------|-------|---------|
| PR/Push | Unit, Fast Integration | Every push |
| Merge to Main | All Integration, Contract | Main branch |
| Scheduled | E2E, Data Quality | Nightly |
| Deploy | Smoke | Post-deploy |

CI uses ephemeral volumes for isolation between runs.

### Health Checks

All services have health checks with proper intervals and retries. Nginx waits for webapp health before starting.

### Deployment Workflow

```bash
# Deploy to production (manual)
git pull origin main
docker compose -f docker-compose.prod.yml -f docker-compose.traefik.yml up -d --build
just migrate  # Run migrations
```

**Not yet implemented:** Automated deployment pipeline, blue-green deployments.
