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
| **Backend** | FastAPI, SQLAlchemy 2.0, PostgreSQL, pgmq |
| **Frontend** | Public surface: Astro SSG + Jinja2 SSR + HTMX/Alpine for small interactions; app surface: Vite + React SPA under `/app/*` (TanStack Router, design-system Dense family, vendored `gts` theme) |
| **Audio Processing** | NAM, IR convolution, pedalboard |
| **Video Processing** | Remotion (React-based video composition) |
| **Testing** | pytest, Playwright |
| **Quality** | ruff, mypy, import-linter |
| **Infrastructure** | Docker (postgres, webapp, nginx, t3k-sync, audio-worker, video-worker) |

---

## Project Structure

```
gts/
├── pyproject.toml              # Workspace root (uv workspaces)
├── model/                      # Shared libraries (workspace members)
│   ├── gts/                    # Domain (package gts-domain, import root gts)
│   │   └── src/gts/
│   │       ├── domain/
│   │       │   ├── entities/   # User, Gear, SignalChain, Shootout, Job
│   │       │   └── value_objects/  # Enums, frozen dataclasses
│   │       ├── ports/          # Repository protocols, processor protocols
│   │       ├── records/        # Sync record schemas (GearSyncRecord)
│   │       └── services/       # Domain services (validation, calculation)
│   ├── audio/                  # Audio processing (package gts-audio, import root audio)
│   │   └── src/audio/
│   │       ├── processing/     # NAM, IR, pedalboard processing
│   │       └── analysis/       # Audio analysis (loudness, waveform)
│   └── video/                  # Video composition (package gts-video, import root video)
│       └── src/video/
│           ├── remotion/       # Remotion compositions (React/TypeScript)
│           ├── api.py          # Video BC API surface
│           ├── client.py       # HttpVideoRenderClient (VideoRenderClient impl)
│           ├── props.py        # Domain-to-Remotion prop serialisation
│           └── schemas.py      # Pydantic schemas
├── infra/                      # Messaging workspace package (package gts-messaging, import root messaging)
│   └── messaging/              # pgmq client, envelope, commands, events, bus - imported by application code
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
│   ├── t3k-sync/              # T3K source sync (pgmq producer)
│   │   └── src/t3k_sync/
│   │       └── consumers/     # T3K API polling, event publishing
│   ├── audio-worker/          # Audio BC worker (pgmq consumer)
│   │   └── src/audio_worker/
│   │       └── consumers/     # Audio command handlers
│   └── video-worker/          # Video BC worker (pgmq consumer)
│       └── src/video_worker/
│           └── consumers/     # Video command handlers
├── frontend/
│   └── astro/                  # Build system (pre-bundled)
│       ├── src/
│       │   ├── pages/          # Template sources (.html.ts, .astro)
│       │   ├── layouts/        # Base layout wrapper
│       │   ├── styles/         # Tailwind, design tokens
│       │   └── components/     # React islands
│       └── dist/               # Build output (COMMITTED TO GIT)
├── infrastructure/             # Deployment/ops config only (NOT a workspace package; mypy-excluded)
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

### Onion Architecture

Onion Architecture with the domain at the centre. Dependencies point inward: adapters depend on domain, never the reverse. Ports (Protocol interfaces) sit at the I/O edge as the Dependency Inversion mechanism; import-linter enforces the inward rule.

- **Domain** (`model/gts/`) - Pure business logic, no framework dependencies
- **Ports** (`model/gts/src/gts/ports/`) - Interfaces (protocols) for external systems
- **Adapters** (`apps/webapp/adapters/`) - Implementations (SQLAlchemy, pgmq, etc.)

### Dependency Rules

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `gts` | (none) | audio, video, sources, apps |
| `audio` | gts | video, sources, apps |
| `video` | gts | audio, sources, apps |
| `source_*` | gts | audio, video, other sources, apps |
| `webapp` | gts, audio, video, messaging | sources |
| `t3k-sync` | gts, source_t3k, messaging | audio, video, webapp |
| `audio-worker` | gts, audio, messaging | video, sources, webapp |
| `video-worker` | gts, video, messaging | audio, sources, webapp |

**Enforcement:** import-linter contracts in root `pyproject.toml`.

### Single Database Architecture

| Database | Purpose | Access |
|----------|---------|--------|
| `gts_core` | All application data | All containers |

**BC separation:** Enforced via `import-linter` contracts and table naming conventions (`core_*`, `t3k_*`). Each BC's ORM models only reference their own BC's tables. Cross-BC communication via pgmq messaging.

---

## Infrastructure

### Runtime Stack

```
postgres, webapp, nginx, t3k-sync, audio-worker, video-worker
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
| Integration | `tests/integration/` | Docker | `just test-integration` | Real DB, pgmq |
| E2E | `tests/e2e/python/` | Host | `just test-golden-path` | Full user journey |

### Test Commands

```bash
just test-regression  # Stack connectivity (< 1s) - run before commits
just test             # Unit + Integration (< 30s) - run before PRs
just tdd <path>       # Single test during development (Docker)
just test-golden-path # Golden path tests (host, requires running containers)
```

### Philosophy

- Test against **real services** — no mocking
- All services available in Docker: PostgreSQL, T3K API, pgmq

---

## Frontend Architecture

Two surfaces share one design system (ADR-0001).

- Public surface: Astro SSG/SSR for `/`, `/shootouts`, `/shootouts/:id`, `/gear/*`, SEO, AdSense, and the public comparison-player island. Anyone can read it.
- App surface: Vite + React SPA under `/app/*`, behind auth. `/app/build` is the signal-chain builder; `/app/shootouts` is the user's own job-aware shootouts stack; `/app/library` is My DIs and My Gear. Client-side routing is expected.

### Public Surface: Pre-Bundled Astro

`frontend/astro/dist/` is generated and gitignored. No Vite dev server runs at runtime for the public surface.

**Workflow:**
1. Edit source in `frontend/astro/src/`
2. Run `just build-astro` (or `just watch-astro` for auto-rebuild)
3. Commit source changes only

The Astro package `build` script runs `astro build`, injects the CSS hash used by Jinja templates, then runs `build:islands` so React island bundles are present after every build.

### App Surface: SPA

The `/app/*` SPA is scaffolded by the frontend-reshape epic. Build and serve recipes land with the scaffold.

### Route Model

| Surface | Route | Served by | Auth |
|---------|-------|-----------|------|
| Public | `/` | Astro SSG + nginx | none |
| Public | `/shootouts`, `/shootouts/:id` | Astro SSG + comparison-player island | none |
| Public | `/gear/*` | Astro SSG/SSR category and detail pages | none |
| App | `/app` | Vite + React SPA | required |
| App | `/app/build` | Vite + React SPA (builder) | required |
| App | `/app/shootouts` | Vite + React SPA (own job-aware shootouts) | required |
| App | `/app/library` | Vite + React SPA (My DIs + My Gear) | required |

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
```

### Frontend

```bash
just build-astro       # Build Astro frontend
just watch-astro       # Watch and auto-rebuild
just verify-astro-build # Verify the build (astro + islands) produces key artefacts
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
just t3k-auth-status        # Check token expiry
just t3k-auth               # Login if needed, then restore session
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

## Epic Workflow

**Under redesign.** The previous pipeline has been removed. See [wiki/Discovery-Workflow-Design.md](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Discovery-Workflow-Design) for the new design. Previous code preserved in git history.

---

## Related Documentation

- [AGENTS.md](./AGENTS.md) - AI/Claude agent workflow instructions
- [GitHub Wiki](https://github.com/krazyuniks/guitar-tone-shootout/wiki) - Full documentation
  - [GTS-Technical-Architecture](https://github.com/krazyuniks/guitar-tone-shootout/wiki/GTS-Technical-Architecture)
  - [Frontend-Architecture](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Frontend-Architecture)
  - [Job-Scheduling-and-Processing](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Job-Scheduling-and-Processing)
