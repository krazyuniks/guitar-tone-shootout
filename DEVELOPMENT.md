# Development Guide

Technical documentation for GTS development.

## Prerequisites

- **Docker** + Docker Compose v2
- **uv** (Python package manager)
- **just** (task runner)
- **git** + **gh** CLI

## Quick Start

First time (the long-running main stack):

```bash
./scripts/first-time-setup.sh   # Host deps + mint env.local.sh + just up-d
```

Feature work (engine-driven, isolated per-branch stack):

```bash
worktree up gts <branch>     # Create + provision a feature worktree
cd ~/Work/guitar-tone-worktrees/<branch>
# ... edit, iterate ...
just check                   # worktree up (idempotent) + worktree gate
worktree down gts <branch>   # Tear it down
```

**Main entry point:** http://localhost:9000

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
│   ├── astro/                  # Public/SEO surface (Astro + React islands)
│   │   ├── src/
│   │   │   ├── pages/          # Template sources (.html.ts, .astro)
│   │   │   ├── layouts/        # Base layout wrapper
│   │   │   ├── styles/         # Tailwind, design tokens
│   │   │   └── components/     # React islands
│   │   └── dist/               # Generated build output (gitignored)
│   └── app/                    # Logged-in app SPA (Vite + React, /app/*)
├── infrastructure/             # Deployment/ops config only (NOT a workspace package; mypy-excluded)
│   ├── docker/                 # Dockerfiles, init scripts
│   ├── migrations/             # Alembic migrations (gts_core)
│   └── nginx/                  # nginx.conf.template
├── scripts/worktree/           # Engine hooks: provision/gate/teardown (+ _derive.sh, current-env)
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
| `docker-compose.override.yml` | Generated/ignored worktree-specific ports and container names |
| `docker-compose.traefik.yml` | Traefik integration for HTTPS/subdomain routing |

**Usage:**
```bash
just up-d      # Local development, routed through scripts/dc
just preview   # Add the Traefik overlay for an on-demand preview subdomain
```

---

## Worktree System

Parallel development with isolated per-branch stacks, driven by the standalone
worktree engine (`~/Work/worktree`). The engine allocates a globally-unique slot
and non-colliding host ports per feature worktree, creates the git worktree, and
runs GTS's own provision/gate/teardown hooks. It knows nothing of Docker, the
SDLC, or issues; GTS owns the stack and the engine owns host resources.

### Dev loop

```bash
worktree up gts <branch>     # create the worktree, allocate slot + ports, provision
cd ~/Work/guitar-tone-worktrees/<branch>
# ... edit, iterate ...
just check                   # worktree up (idempotent) + worktree gate
worktree down gts <branch>   # teardown + release slot/ports; reclaim volume + storage
worktree recover --all       # clear dirty leases left by an interrupted run
```

The host catalogue (`~/.worktree/projects.toml`) and the thin manifest
(`worktree.toml`) are the engine's inputs; the three hooks under
`scripts/worktree/` derive the stack from the injected `WORKTREE_SLOT` and
`WORKTREE_PORT_*`.

### Derivation (slot -> stack)

| Concern | Derived from | Form |
|---|---|---|
| Compose project | `WORKTREE_SLOT` | `gts-<slot>` (container names `gts-<slot>-<svc>`) |
| Postgres volume | `WORKTREE_SLOT` | `gts-postgres-<slot>` (base compose interpolates `GTS_WORKTREE`) |
| Host ports | `WORKTREE_PORT_*` | webapp from `WORKTREE_PORT_WEBAPP`, db from `WORKTREE_PORT_DB` |
| Storage | per-worktree | empty `uploads/videos/logs/source_downloads`; shared read-only `models/audio` |
| Migrations | provision | `alembic -c infrastructure/migrations/alembic.ini upgrade head` (in webapp) |
| Network | compose default | each project gets its own `<project>_default` bridge |

Slots are integers in [1, 256); slot 0 is the reserved baseline (main, never
engine-provisioned). The feature DB starts empty and migrates; the gate's pytest
fixtures build their own schema, so no dump is imported.

### Shared resources

| Resource | Location | Purpose |
|---|---|---|
| Auth | `../.gts-auth.json` | T3K OAuth tokens (mode 0600), shared by main and features |
| Storage | `../gts-storage/` | models/audio shared read-only; writes are per-worktree |

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

The SPA lives under `frontend/app/` and is served by the `app` Docker service (Vite dev server, port 5173 internal). nginx proxies `/app/*` to the Vite dev service in development; in production (slice A4), a `vite build` produces static files served directly by nginx.

**Workflow:**

```bash
just watch-app       # Tail the Vite dev server logs
just logs app        # Same, alternative
just build-app       # Production build to frontend/app/dist/ (slice A4)
```

**Serve topology:**

- Dev: browser → nginx (port 9000) → `app:5173` (Vite dev server with HMR). `/api/*` and `/auth/*` are handled by nginx before reaching the app location.
- Prod: `vite build` → `frontend/app/dist/` → nginx `location /app/` serves static files with SPA fallback.

**Stack:** Vite + React 19 + TanStack Router + Tailwind v4 (vendored `gts` theme tokens).

**Routes:**

| URL | Component |
|-----|-----------|
| `/app` | `routes/index.tsx` |
| `/app/build` | `routes/build.tsx` |
| `/app/shootouts` | `routes/shootouts.tsx` |
| `/app/library` | `routes/library.tsx` |

Auth guard runs in `rootRoute.beforeLoad` — calls `GET /auth/me`; redirects to `/login?next=<current-path>` on 401.

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
just build-app         # Build the Vite + React app SPA
just watch-app         # Tail the app SPA dev server logs
```

---

## Troubleshooting

### Services won't start

```bash
just down
just up-d
```

### Permission issues

Provision pre-creates the storage bind-mount dirs as the host user, so root-owned
orphans should not recur. If a stale root-owned dir remains, remove it manually,
then re-provision:

```bash
worktree down gts <branch> && worktree up gts <branch>
```

### Auth issues

```bash
just t3k-auth-status        # Check token expiry
just t3k-auth               # Login if needed, then restore session
```

### Port conflicts

The engine reserves non-colliding host ports per slot. If a port is stuck held by
a crashed run, recover the lease:

```bash
worktree recover --all      # release dirty leases whose ports are free
lsof -i :9000               # find what is holding a port
```

### Stale worktrees

```bash
worktree recover --all      # verify dirty leases' resources are gone and release them
```

---

## Contributing

### Commit Format

```
type(scope): description

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
```

### PR Process

1. Create + provision a feature worktree: `worktree up gts <branch>`
2. Implement changes
3. Run quality gates: `just check`
4. Push and create a reviewed PR, or let VF publish a `vf-ready` PR for a drain slice
5. After merge: `worktree down gts <branch>`

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
