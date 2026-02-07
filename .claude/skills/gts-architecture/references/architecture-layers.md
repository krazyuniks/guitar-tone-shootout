# Architecture Layers

Hexagonal architecture with domain at centre. Dependencies point inward -- adapters depend on domain, never reverse.

## Technology Stack

### Core Application

| Concern | Technology | Rationale |
|---------|------------|-----------|
| Language | Python 3.12+ | Team expertise, async ecosystem |
| Package management | uv workspaces | Monorepo with isolated members, fast resolution |
| Web framework | FastAPI | Async, OpenAPI, Pydantic integration |
| Database | PostgreSQL | ACID, JSON support, pgmq integration |
| Message broker | pgmq | PostgreSQL-native, transactional send, upgradeable |
| Job scheduler | TaskIQ | Async-native, PostgreSQL backend |
| Schema validation | Pydantic v2 | Performance, strict validation |
| ORM | SQLAlchemy 2.0 | Async support, mature ecosystem |
| Caching | Redis | Job broker, sync status tracking (jobs profile only -- not used by webapp) |
| Encryption | Fernet (symmetric) | Token encryption at rest |

### Frontend

| Concern | Technology | Rationale |
|---------|------------|-----------|
| Build system | Astro | Static generation, TypeScript, Tailwind integration |
| Runtime | SSR (FastAPI + Jinja2) | All pages server-rendered |
| Interactivity | HTMX + Alpine.js | Minimal JS, HTML-over-the-wire |
| Signal Chain Builder | React (island) | Complex interactive UI, loaded only on builder page |
| Styling | Tailwind CSS | Utility-first, design tokens |

### Audio Processing

| Concern | Technology | Rationale |
|---------|------------|-----------|
| NAM model loading | PyTorch + `nam` library | Direct integration with .nam files (by NAM author); Pedalboard cannot load VST3 on Linux |
| Effects & routing | Pedalboard | DSP framework for filters, IR convolution, resampling, audio I/O |
| Loudness | pyloudnorm | EBU R128 measurement and normalization |

### Video Processing

| Concern | Technology | Rationale |
|---------|------------|-----------|
| Video composition | FFmpeg | Concatenation, waveform overlays, title cards |

### Infrastructure

| Concern | Technology | Rationale |
|---------|------------|-----------|
| Containerisation | Docker Compose | Service orchestration, isolated environments |
| Local reverse proxy | nginx | Static file serving, backend proxy (local dev) |
| Production SSL/routing | Traefik | SSL termination, host-based routing (dev server + production) |
| Worktree management | worktree.py | Parallel development, port allocation, Docker isolation |

### Testing

| Concern | Technology | Rationale |
|---------|------------|-----------|
| Regression | pytest (SQLite in-memory) | Fast stack validation (~0.2s) |
| Unit/Integration | pytest, pytest-asyncio | Async support, fixtures |
| E2E | Playwright | Browser automation, visual verification |

## Repository Structure

```
gts/
├── pyproject.toml              # Workspace root
├── libs/
│   ├── core/                   # Core domain (source-agnostic)
│   │   ├── pyproject.toml
│   │   └── src/core/
│   │       ├── domain/         # Entities, aggregates, value objects
│   │       ├── ports/          # Interfaces (Protocols)
│   │       ├── records/        # Sync record schemas (owned by core)
│   │       └── services/       # Domain services
│   │
│   └── audio/                  # Audio/video processing
│       ├── pyproject.toml
│       └── src/audio/
│           ├── processing/     # Signal chain execution (Pedalboard, NAM)
│           ├── video/          # FFmpeg composition
│           └── analysis/       # Loudness measurement, waveform extraction
│
├── sources/
│   └── {source}/               # One per data source (e.g., t3k)
│       ├── pyproject.toml
│       └── src/source_{name}/
│           ├── domain/         # Source-specific models
│           ├── adapters/
│           │   ├── inbound/    # External API client
│           │   └── outbound/   # Publishes to queue
│           └── services/       # Sync, file download, reingest
│
├── apps/
│   ├── webapp/                 # Web application (user-facing only)
│   │   ├── pyproject.toml
│   │   └── src/webapp/
│   │       ├── api/            # HTTP endpoints (no admin -- moved to worker)
│   │       ├── auth/           # OAuth providers (generic)
│   │       ├── services/       # Application services
│   │       └── adapters/       # Persistence, external integrations
│   │
│   ├── worker/                 # Job consumer + admin API
│   │   ├── pyproject.toml
│   │   └── src/worker/
│   │       ├── main.py         # FastAPI app for admin API
│   │       ├── api/
│   │       │   └── admin/      # Job management endpoints
│   │       ├── consumers/      # Queue message handlers
│   │       ├── jobs/           # Job implementations
│   │       └── services/       # Admin service
│   │
│   └── scheduler/              # Job scheduler
│       ├── pyproject.toml
│       └── src/scheduler/
│           └── schedules/      # Cron-like job definitions
│
├── frontend/
│   └── astro/                  # Astro build system
│       ├── src/
│       │   ├── pages/          # Template sources (.html.ts, .astro)
│       │   ├── components/     # React islands (signal chain builder)
│       │   └── styles/         # Tailwind, design tokens
│       └── dist/               # Build output (committed)
│
├── infrastructure/
│   ├── docker/                 # Dockerfiles, init scripts
│   │   ├── Dockerfile.dev     # Development (bind mounts, uv installed)
│   │   ├── Dockerfile.backend # Production webapp (multi-stage, no uv)
│   │   ├── Dockerfile.worker  # Production worker
│   │   └── init-*.sql         # PostgreSQL init scripts
│   ├── migrations/             # Alembic migrations (gts_core)
│   └── nginx/                  # nginx.conf.template
│
├── scripts/
│   ├── first-time-setup.sh     # First-time setup (prerequisites, Playwright)
│   ├── e2e-env.sh              # E2E test environment setup
│   └── run_epic.py             # TDD state machine + agent dispatch
│
├── worktree/                   # Worktree CLI infrastructure (PEP 723 inline deps)
│   ├── auth.py                 # T3K OAuth token management
│   ├── docker.py               # Docker Compose overlay generation
│   ├── lifecycle.py            # Worktree creation/teardown
│   └── git_ops.py              # Git operations
│
├── tests/
│   ├── regression/             # Stack connectivity tests (SQLite, ~0.2s)
│   ├── unit/                   # Unit tests (core, audio, webapp)
│   ├── integration/            # Integration tests (real DB/Redis)
│   └── e2e/python/             # E2E tests (Playwright, isolated workspace)
│
├── worktree.py                 # Worktree management CLI entry point
└── justfile                    # Task runner commands (always use just)
```

### Workspace Configuration

```toml
# pyproject.toml (workspace root)
[tool.uv.workspace]
members = [
    "libs/*",
    "sources/*",
    "apps/*",
]
```

### Dependency Rules

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `core` | (none) | audio, sources, apps |
| `audio` | core | sources, apps |
| `source_*` | core | audio, other sources, apps |
| `webapp` | core, audio | sources |
| `worker` | core, audio | sources |
| `scheduler` | core | audio, sources |

Enforced via import-linter in CI.

### Directory Purposes

| Directory | Purpose |
|-----------|---------|
| `libs/` | Shared libraries used by multiple apps |
| `sources/` | Data source adapters (one per external system) |
| `apps/` | Deployable applications |
| `frontend/` | Build-time assets (Astro compiles to static files) |
| `infrastructure/` | Deployment configuration |
| `scripts/` | Developer tooling and setup |

## Layer Diagram

```
      ┌────────────────────────────────────────────────────────────┐
      │                      External World                        │
      │            (HTTP, Source APIs, PostgreSQL, CLI)            │
      └──────────────────────────────┬─────────────────────────────┘
                                     │
      ┌──────────────────────────────┼─────────────────────────────┐
      │                              ▼                             │
      │  ┌───────────────────────────────────────────────────────┐ │
      │  │                   Adapters Layer                       │ │
      │  │  HTTP endpoints │ Repositories │ Source clients        │ │
      │  │  apps/*/api/    │ apps/*/adapters/ │ sources/*/        │ │
      │  └─────────────────────────┬─────────────────────────────┘ │
      │                            │                               │
      │  ┌─────────────────────────▼─────────────────────────────┐ │
      │  │                 Application Layer                      │ │
      │  │                                                        │ │
      │  │   ┌─────────────────┐      ┌───────────────────────┐  │ │
      │  │   │  Shared Libs    │      │   App Services        │  │ │
      │  │   │  libs/audio/    │ ◀─── │   apps/*/services/    │  │ │
      │  │   │  (standalone)   │      │   (use case orch.)    │  │ │
      │  │   └────────┬────────┘      └───────────────────────┘  │ │
      │  │            │                                           │ │
      │  └────────────┼───────────────────────────────────────────┘ │
      │               │                                             │
      │  ┌────────────▼───────────────────────────────────────────┐ │
      │  │                   Domain Layer                          │ │
      │  │                     libs/core/                          │ │
      │  └─────────────────────────────────────────────────────────┘ │
      └──────────────────────────────────────────────────────────────┘
                           Dependencies flow inward
```

## Workspace to Layer Mapping

| Layer | Location | Contents |
|-------|----------|----------|
| **Domain** | `libs/core/src/core/domain/` | Entities, aggregates, value objects |
| | `libs/core/src/core/ports/` | Protocol interfaces (repository contracts) |
| | `libs/core/src/core/services/` | Domain services (pure business logic) |
| | `libs/core/src/core/records/` | Sync record schemas (DTOs owned by core) |
| **Application** | `libs/audio/src/audio/` | Audio/video processing (standalone library) |
| | `apps/webapp/src/webapp/services/` | Use case orchestration |
| | `apps/worker/src/worker/jobs/` | Job implementations |
| **Adapters** | `apps/webapp/src/webapp/api/` | HTTP endpoints (inbound) |
| | `apps/webapp/src/webapp/adapters/` | Persistence, file storage (outbound) |
| | `apps/webapp/src/webapp/auth/` | OAuth handlers (inbound) |
| | `sources/*/src/source_*/adapters/inbound/` | External API clients |
| | `sources/*/src/source_*/adapters/outbound/` | Queue publishers |

## Layer Responsibilities

**Domain Layer** (`libs/core/`)
- Defines ubiquitous language (entities, value objects)
- Declares ports (Protocol interfaces) for external dependencies
- Contains pure business logic (domain services)
- Zero framework dependencies, persistence-agnostic

**Application Layer** (`libs/audio/`, `apps/*/services/`)
- Shared libraries (`libs/`) are standalone, callable from any context
- App services orchestrate use cases and manage transaction boundaries
- `libs/audio/` coordinates domain models with DSP libraries (Pedalboard, NAM, FFmpeg)

**Adapters Layer** (`apps/*/api/`, `apps/*/adapters/`, `sources/*/`)
- HTTP endpoints (FastAPI routes)
- Persistence (SQLAlchemy repositories implementing core ports)
- External API clients (T3K API, OAuth providers)
- Queue publishers and consumers

## Shared Libraries Are Decoupled

`libs/` are shared libraries, not tied to any application. They can be called from:
- Web application services
- Background worker jobs
- CLI scripts
- Bulk import scripts
- Tests
- Cron jobs

This is enforced by dependency rules -- `libs/audio/` depends only on `libs/core/`, never on `apps/` or `sources/`.

## Context Map

DDD context map showing bounded context relationships.

```
┌─────────────────┐         ┌─────────────────┐
│   Source T3K    │         │   Source XXX    │
│  (Upstream)     │         │  (Upstream)     │
└────────┬────────┘         └────────┬────────┘
         │ Conformist                │ Conformist
         │                           │
         ▼                           ▼
┌─────────────────────────────────────────────┐
│                   Core                       │
│              (Downstream)                    │
│         Owns canonical schema                │
└─────────────────────────────────────────────┘
         │
         │ (consumed by)
         ▼
┌─────────────────────────────────────────────┐
│                  Webapp                      │
│              (Downstream)                    │
└─────────────────────────────────────────────┘
```

### Relationship Types

| Relationship | Type | Meaning |
|--------------|------|---------|
| Sources -> Core | Conformist | Sources conform to core's schema. Core does not adapt to sources. |
| Webapp -> Core | Customer/Supplier | Webapp consumes core's domain model. Core may evolve to serve webapp needs. |
| Sources <-> Sources | None | Sources are isolated from each other. No direct dependencies. |

### Schema Ownership

Core owns all synchronisation record schemas (`libs/core/src/core/records/`). Source adapters import and conform to these schemas. Schema changes are validated in CI -- all source adapters must pass against the current core schema before merge.
