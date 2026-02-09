# Development Guide

Technical documentation for GTS development.

## Prerequisites

- **Docker** + Docker Compose v2
- **uv** (Python package manager)
- **just** (task runner)
- **git** + **gh** CLI

## Quick Start

```bash
./worktree.py setup main    # First-time: set up main worktree
just up-d                   # Start services (existing worktree)
```

**Entry point:** http://localhost:9000

**Discover commands:** `just --list`

---

## Stack

| Layer | Technology |
|-------|------------|
| **Package Management** | uv workspaces (monorepo) |
| **Backend** | FastAPI, SQLAlchemy 2.0, PostgreSQL (dual DB), Redis, TaskIQ, pgmq |
| **Frontend** | Astro SSG (pre-bundled), Jinja2 SSR, HTMX, Alpine.js, Tailwind |
| **Audio Processing** | NAM, IR convolution, pedalboard |
| **Video Processing** | Remotion (React-based video composition) |
| **Testing** | pytest, Playwright |
| **Quality** | ruff, mypy, import-linter |
| **Infrastructure** | Docker (db, redis, webapp, nginx, worker, scheduler) |

---

## Project Structure

```
gts/
├── pyproject.toml              # Workspace root (uv workspaces)
├── libs/
│   ├── core/                   # Domain (zero framework deps)
│   │   └── src/core/
│   │       ├── domain/
│   │       │   ├── entities/   # User, Gear, SignalChain, Shootout, Job
│   │       │   └── value_objects/  # Enums, frozen dataclasses
│   │       ├── ports/          # Repository protocols, processor protocols
│   │       ├── records/        # Sync record schemas (GearSyncRecord)
│   │       └── services/       # Domain services (validation, calculation)
│   ├── audio/                  # Audio processing
│   │   └── src/audio/
│   │       ├── processing/     # NAM, IR, pedalboard processing
│   │       └── analysis/       # Audio analysis (loudness, waveform)
│   └── video/                  # Video composition
│       └── src/video/
│           ├── composition/    # Remotion components
│           ├── rendering/      # Video rendering pipeline
│           └── effects/        # Video effects and transitions
├── sources/
│   └── t3k/                    # T3K source adapter
│       └── src/source_t3k/
│           ├── domain/         # T3K-specific entities (Pack, Model)
│           ├── adapters/
│           │   ├── inbound/    # API client, OAuth
│           │   └── outbound/   # pgmq publisher
│           └── services/       # Sync service
├── apps/
│   ├── webapp/                 # FastAPI
│   │   └── src/webapp/
│   │       ├── api/            # REST endpoints, page routes
│   │       ├── auth/           # Session, OAuth
│   │       ├── services/       # Application services
│   │       └── adapters/       # Repository implementations
│   │           └── persistence/
│   │               ├── models/     # SQLAlchemy ORM models
│   │               └── repositories/  # Repository implementations
│   ├── worker/                 # TaskIQ + pgmq consumer
│   │   └── src/worker/
│   │       ├── consumers/      # pgmq message handlers
│   │       └── jobs/           # Background job definitions
│   └── scheduler/              # TaskIQ scheduler
│       └── src/scheduler/
│           └── schedules/      # Cron definitions
├── frontend/
│   └── astro/                  # Build system (pre-bundled)
│       ├── src/
│       │   ├── pages/          # Template sources (.html.ts, .astro)
│       │   ├── layouts/        # Base layout wrapper
│       │   ├── styles/         # Tailwind, design tokens
│       │   └── components/     # React islands
│       └── dist/               # Build output (COMMITTED TO GIT)
├── infrastructure/
│   ├── docker/                 # Dockerfiles, init scripts
│   ├── migrations/             # Alembic migrations (gts_core)
│   └── nginx/                  # nginx.conf.template
├── worktree/                   # Worktree management (standalone)
│   ├── cli.py                  # Typer CLI
│   ├── registry.py             # SQLite registry
│   ├── config.py               # Port allocation
│   └── templates/              # Jinja2 for docker-compose.override
└── tests/
    ├── regression/             # Stack connectivity tests (SQLite)
    ├── unit/
    │   ├── core/               # Domain unit tests
    │   ├── audio/              # Audio processing tests
    │   └── webapp/             # ORM and service tests
    ├── integration/
    │   ├── webapp/             # Repository integration tests
    │   └── audio/              # Audio processing integration tests
    ├── e2e/
    │   └── python/             # E2E tests (pytest + Playwright)
    ├── fixtures/               # Shared test fixtures
    └── data/                   # Test data files
```

---

## Architecture

### Hexagonal (Ports/Adapters)

- **Domain** (`libs/core/`) - Pure business logic, no framework dependencies
- **Ports** (`libs/core/ports/`) - Interfaces (protocols) for external systems
- **Adapters** (`apps/webapp/adapters/`) - Implementations (SQLAlchemy, Redis, etc.)

### Dependency Rules

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `core` | (none) | audio, video, sources, apps |
| `audio` | core | video, sources, apps |
| `video` | core, audio | sources, apps |
| `source_*` | core | audio, video, other sources, apps |
| `webapp` | core, audio, video | sources |
| `worker` | core, audio, video | sources |
| `scheduler` | core | audio, video, sources |

**Enforcement:** import-linter contracts in root `pyproject.toml`.

### Dual Database Architecture

| Database | Purpose | Access |
|----------|---------|--------|
| `gts_core` | Application data (users, shootouts, chains) | Webapp, worker |
| `gts_t3k_source` | T3K source data (packs, models, presets) | Worker only |

**Critical:** Webapp has NO direct access to T3K source database. Worker bridges the two via pgmq.

---

## Infrastructure

### Runtime Stack

```
db, redis, webapp, nginx, worker, scheduler
```

### Build-Only Services

```bash
# Astro container only starts with --profile build
docker compose --profile build up astro
just build-astro        # Starts astro, runs build
just watch-astro        # Starts astro, watches for changes
```

### Docker Compose Architecture

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base config (no ports, no worktree-specific values) |
| `docker-compose.override.yml` | Worktree-specific ports, container names |
| `docker-compose.traefik.yml` | Traefik integration for HTTPS/subdomain routing |
| `docker-compose.ci.yml` | CI ephemeral volumes, isolation |

**Usage:**
```bash
# Local development (auto-loads override)
docker compose up -d

# With Traefik (public deployment)
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.traefik.yml up -d

# CI
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d
```

---

## Worktree System

Parallel development with isolated Docker environments.

### Commands

```bash
./worktree.py setup <issue>    # Create worktree from GitHub issue
./worktree.py setup main       # Set up main worktree (idempotent)
./worktree.py list             # List all worktrees
./worktree.py status           # Show current worktree status
./worktree.py ports            # Show port allocations
./worktree.py teardown <name>  # Remove worktree
```

### Port Allocation

| Service | Main (offset 0) | Feature (offset 1) | Formula |
|---------|-----------------|-------------------|---------|
| nginx | 9000 | 9010 | 9000 + (offset * 10) |
| webapp | 8000 | 8010 | 8000 + (offset * 10) |
| PostgreSQL | 5432 | 5433 | 5432 + (offset * 1) |
| Redis | 6379 | 6380 | 6379 + (offset * 1) |
| Astro | 4321 | 4331 | 4321 + (offset * 10) |

### Shared Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| Registry | `../.worktree/registry.db` | Worktree state |
| Auth | `../.gts-auth.json` | OAuth tokens (mode 0600) |
| Storage | `../gts-storage/` | Models, uploads, audio |

---

## Testing Strategy

| Test Type | Location | Runs In | Command | Purpose |
|-----------|----------|---------|---------|---------|
| Regression | `tests/regression/` | Docker | `just test-regression` | Stack connectivity (ORM → Repo → DB) |
| Unit | `tests/unit/` | Docker | `just test-unit` | Isolated logic, no I/O |
| Integration | `tests/integration/` | Docker | `just test-integration` | Real DB/Redis |
| E2E | `tests/e2e/python/` | Host | `just test-golden-path` | Full user journey |

### Test Commands

```bash
just test-regression  # Stack connectivity (< 1s) - run before commits
just test             # Unit + Integration (< 30s) - run before PRs
just tdd <path>       # Single test during development (Docker)
just test-golden-path # Golden path tests (host, requires running containers)
```

### Philosophy

- Test against **real services** (PostgreSQL, Redis)
- **No mocking** internal systems
- Mock only **external APIs** (T3K, email)

---

## Frontend Architecture

### Pre-Bundled Astro

`frontend/astro/dist/` is committed to git. No Vite dev server at runtime.

**Workflow:**
1. Edit source in `frontend/astro/src/`
2. Run `just build-astro` (or `just watch-astro` for auto-rebuild)
3. Commit both `frontend/astro/src/` and `frontend/astro/dist/`

### Route Types

| Route Type | Technology | Example |
|------------|------------|---------|
| Static pages | Astro SSG (pre-built) + nginx | `/`, `/about`, `/login` |
| Dynamic pages | Jinja2 + FastAPI | `/library/*`, `/shootouts`, `/gear/*` |
| Complex UI | React island | `/library/chains/build` |

### Navigation Caveat

Astro's `<ClientRouter />` intercepts link clicks. SSR pages require `data-astro-reload`:

```html
<!-- In Astro components -->
<a href="/gear" data-astro-reload>Gear</a>
<a href="/shootouts" data-astro-reload>Shootouts</a>
```

---

## Common Commands

### Services

```bash
just up-d         # Start all services
just down         # Stop all services
just restart      # Restart all services
just logs [svc]   # View logs (follow mode)
just status       # Show service status
just rebuild      # Rebuild and restart
```

### Quality

```bash
just check        # Run all quality checks (lint, types, tests, imports)
just lint         # Fix lint issues
just check-types  # Type checking
```

### Database

```bash
just migrate           # Run migrations
just migration "name"  # Create new migration
just psql              # Connect to gts_core
just psql-t3k          # Connect to gts_t3k_source
```

### Frontend

```bash
just build-astro       # Build Astro frontend
just watch-astro       # Watch and auto-rebuild
just verify-astro-sync # Verify dist is in sync with source
```

---

## Troubleshooting

### Services won't start

```bash
just down
docker compose down -v  # Remove volumes (WARNING: deletes data)
just up-d
```

### Permission issues

```bash
./worktree.py setup main  # Re-run setup (idempotent, fixes permissions)
```

### Auth issues

```bash
./worktree.py auth-status   # Check token expiry
./worktree.py auth-login    # Re-authenticate
```

### Port conflicts

```bash
./worktree.py ports         # Check what's allocated
lsof -i :9000               # Find what's using port 9000
```

### Stale worktrees

```bash
./worktree.py prune         # Remove stale registry entries
./worktree.py cleanup       # Clean up merged branches and orphaned Docker resources
```

---

## Contributing

### Commit Format

```
type(scope): description

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
```

### PR Process

1. Create branch from GitHub issue: `./worktree.py setup <issue>`
2. Implement changes
3. Run quality gates: `just check`
4. Push and create PR
5. After merge: `./worktree.py complete <pr>`

### Code Style

- Follow existing patterns in codebase
- Use ruff for formatting/linting (auto-fixed on commit)
- Keep functions small and focused
- Add comments only where logic isn't self-evident

---

## Related Documentation

- [AGENTS.md](./AGENTS.md) - AI/Claude agent workflow instructions
- [GitHub Wiki](https://github.com/krazyuniks/guitar-tone-shootout/wiki) - Full documentation
  - [GTS-Technical-Architecture](https://github.com/krazyuniks/guitar-tone-shootout/wiki/GTS-Technical-Architecture)
  - [Frontend-Architecture](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Frontend-Architecture)
  - [Job-Scheduling-and-Processing](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Job-Scheduling-and-Processing)
