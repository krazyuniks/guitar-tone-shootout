# Architecture Layers

Onion Architecture with the domain at the centre. Dependencies point inward -- adapters depend on domain, never the reverse. Ports (Protocol interfaces) live at the I/O edge as the Dependency Inversion Principle mechanism; import-linter enforces the inward dependency rule.

## Technology Stack

### Core Application

| Concern | Technology | Rationale |
|---------|------------|-----------|
| Language | Python 3.12+ | Team expertise, async ecosystem |
| Package management | uv workspaces | Monorepo with isolated members, fast resolution |
| Web framework | FastAPI | Async, OpenAPI, Pydantic integration |
| Database | PostgreSQL | ACID, JSON support, pgmq integration |
| Message broker | pgmq | PostgreSQL-native, transactional send, upgradeable |
| Schema validation | Pydantic v2 | Performance, strict validation |
| ORM | SQLAlchemy 2.0 | Async support, mature ecosystem |
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
| Video composition | Remotion | React-based programmatic video composition, TypeScript integration |
| Video encoding | FFmpeg | Video encoding, format conversion (used by Remotion) |
| Image preparation | Pillow | Image resizing, normalisation for video frames |

### Infrastructure

| Concern | Technology | Rationale |
|---------|------------|-----------|
| Containerisation | Docker Compose | Service orchestration, isolated environments |
| Local reverse proxy | nginx | Static file serving, backend proxy (local dev) |
| Production SSL/routing | Traefik | SSL termination, host-based routing (dev server + production) |
| Worktree management | `worktree` engine | Parallel development, port allocation, Docker isolation |

### Testing

| Concern | Technology | Rationale |
|---------|------------|-----------|
| Regression | pytest | Stack connectivity validation (<1s) |
| Unit/Integration | pytest, pytest-asyncio | Async support, fixtures |
| E2E | Playwright | Browser automation, visual verification |

## Repository Structure

```
gts/
├── pyproject.toml              # Workspace root
├── model/                      # Shared libraries (workspace members)
│   ├── gts/                    # Core domain (package gts-domain, import root gts)
│   │   ├── pyproject.toml
│   │   └── src/gts/
│   │       ├── domain/         # Entities, aggregates, value objects
│   │       ├── ports/          # Interfaces (Protocols)
│   │       ├── records/        # Sync record schemas (owned by gts)
│   │       └── services/       # Domain services
│   │
│   ├── audio/                  # Audio processing (package gts-audio, import root audio)
│   │   ├── pyproject.toml
│   │   └── src/audio/
│   │       ├── processing/     # Signal chain execution (Pedalboard, NAM)
│   │       └── analysis/       # Loudness measurement, waveform extraction
│   │
│   └── video/                  # Video composition (package gts-video, import root video)
│       ├── pyproject.toml
│       └── src/video/
│           ├── remotion/       # Remotion compositions (React/TypeScript)
│           ├── api.py          # Video BC API surface
│           ├── client.py       # HttpVideoRenderClient (VideoRenderClient impl)
│           └── schemas.py      # Pydantic schemas
│
├── infra/                      # Messaging workspace package (package gts-messaging, import root messaging)
│   └── messaging/              # pgmq client, envelope, commands, events, bus - imported by application code
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
│   │       ├── api/            # HTTP endpoints + admin API (/api/admin/*)
│   │       ├── auth/           # OAuth providers (generic)
│   │       ├── services/       # Application services
│   │       └── adapters/       # Persistence, external integrations
│   │
│   ├── t3k-sync/              # T3K source sync container
│   │   ├── pyproject.toml
│   │   └── src/t3k_sync/
│   │       ├── main.py         # Polling loop entry point
│   │       ├── consumers/      # pgmq message handlers
│   │       └── services/       # Sync orchestration
│   │
│   ├── audio-worker/          # Audio processing container
│   │   ├── pyproject.toml
│   │   └── src/audio_worker/
│   │       ├── main.py         # Polling loop entry point
│   │       └── consumers/      # pgmq message handlers
│   │
│   └── video-worker/          # Video processing container
│       ├── pyproject.toml
│       └── src/video_worker/
│           ├── main.py         # Polling loop entry point
│           └── consumers/      # pgmq message handlers
│
├── frontend/
│   └── astro/                  # Astro build system
│       ├── src/
│       │   ├── pages/          # Template sources (.html.ts, .astro)
│       │   ├── components/     # React islands (signal chain builder)
│       │   └── styles/         # Tailwind, design tokens
│       └── dist/               # Build output (committed)
│
├── infrastructure/             # Deployment/ops config only (NOT a workspace package; mypy-excluded). Distinct from infra/ (the messaging package).
│   ├── docker/                 # Dockerfiles, init scripts
│   │   ├── Dockerfile.dev     # Development (bind mounts, uv installed)
│   │   ├── Dockerfile.backend # Production webapp (multi-stage, no uv)
│   │   └── init-*.sql         # PostgreSQL init scripts
│   ├── migrations/             # Alembic migrations (gts_core)
│   └── nginx/                  # nginx.conf.template
│
├── scripts/
│   ├── first-time-setup.sh     # First-time setup (prerequisites, Playwright)
│   ├── e2e-env.sh              # E2E test environment setup
│   └── orchestrator.py          # V2 epic workflow orchestrator
│
├── worktree/                   # Worktree CLI infrastructure (PEP 723 inline deps)
│   ├── auth.py                 # T3K OAuth token management
│   ├── docker.py               # Docker Compose overlay generation
│   ├── lifecycle.py            # Worktree creation/teardown
│   └── git_ops.py              # Git operations
│
├── tests/
│   ├── regression/             # Stack connectivity tests (<1s)
│   ├── unit/                   # Unit tests (gts, audio, webapp)
│   ├── integration/            # Integration tests (real DB, pgmq)
│   └── e2e/python/             # E2E tests (Playwright, isolated workspace)
│
└── justfile                    # Task runner commands (always use just)
```

### Workspace Configuration

```toml
# pyproject.toml (workspace root)
[tool.uv.workspace]
members = [
    "model/*",
    "infra/*",
    "sources/*",
    "apps/webapp",
    "apps/t3k_sync",
    "apps/audio_worker",
    "apps/video_worker",
]
```

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

Enforced via import-linter in CI.

**Video layer:** `model/video/` sits above the gts domain, composing domain models into videos using Remotion (React-based video framework). Must NOT depend on application-specific concerns (webapp, BC containers) or data sources (T3K).

### Directory Purposes

| Directory | Purpose |
|-----------|---------|
| `model/` | Shared libraries used by multiple apps (workspace members: gts, audio, video) |
| `infra/` | Messaging workspace package (gts-messaging, import root messaging) - pgmq client, envelope, commands, events, bus; imported by application code |
| `sources/` | Data source adapters (one per external system) |
| `apps/` | Deployable applications |
| `frontend/` | Build-time assets (Astro compiles to static files) |
| `infrastructure/` | Deployment/ops configuration only (docker, nginx, alembic migrations); NOT a workspace package, mypy-excluded. Do not confuse with `infra/` (the messaging package). |
| `scripts/` | Developer tooling and setup |

## Layer Diagram

Onion Architecture: concentric rings with the Domain at the centre. Each ring may only depend on rings inside it. Ports (Protocol interfaces) are declared in the Domain ring and implemented by the Adapters ring at the I/O edge -- this is the Dependency Inversion that keeps the Domain free of framework concerns.

```
      ┌────────────────────────────────────────────────────────────┐
      │                      External World                        │
      │            (HTTP, Source APIs, PostgreSQL, CLI)            │
      └──────────────────────────────┬─────────────────────────────┘
                                     │
      ┌──────────────────────────────┼─────────────────────────────┐
      │                              ▼                             │
      │  ┌───────────────────────────────────────────────────────┐ │
      │  │                Adapters Ring (outermost)               │ │
      │  │  Implements Domain ports. HTTP, persistence, sources.  │ │
      │  │  apps/*/api/    │ apps/*/adapters/ │ sources/*/        │ │
      │  └─────────────────────────┬─────────────────────────────┘ │
      │                            │                               │
      │  ┌─────────────────────────▼─────────────────────────────┐ │
      │  │                 Application Ring                       │ │
      │  │                                                        │ │
      │  │   ┌─────────────────┐      ┌───────────────────────┐  │ │
      │  │   │  Shared Libs    │      │   App Services        │  │ │
      │  │   │  model/audio/   │ ◀─── │   apps/*/services/    │  │ │
      │  │   │  (standalone)   │      │   (use case orch.)    │  │ │
      │  │   └────────┬────────┘      └───────────────────────┘  │ │
      │  │            │                                           │ │
      │  └────────────┼───────────────────────────────────────────┘ │
      │               │                                             │
      │  ┌────────────▼───────────────────────────────────────────┐ │
      │  │              Domain Ring (centre)                       │ │
      │  │   model/gts/ -- entities, value objects, services,      │ │
      │  │   and the ports (Protocols) that adapters implement.    │ │
      │  └─────────────────────────────────────────────────────────┘ │
      └──────────────────────────────────────────────────────────────┘
                  Dependencies flow inward (Adapters -> Application -> Domain)
```

## Workspace to Layer Mapping

| Layer | Location | Contents |
|-------|----------|----------|
| **Domain** | `model/gts/src/gts/domain/` | Entities, aggregates, value objects |
| | `model/gts/src/gts/ports/` | Protocol interfaces (repository contracts) |
| | `model/gts/src/gts/services/` | Domain services (pure business logic) |
| | `model/gts/src/gts/records/` | Sync record schemas (DTOs owned by gts) |
| **Application** | `model/audio/src/audio/` | Audio processing (standalone library) |
| | `model/video/src/video/` | Video composition (standalone library) |
| | `apps/webapp/src/webapp/services/` | Use case orchestration |
| | `apps/*/src/*/consumers/` | pgmq message handlers (BC containers) |
| **Adapters** | `apps/webapp/src/webapp/api/` | HTTP endpoints (inbound) |
| | `apps/webapp/src/webapp/adapters/` | Persistence, file storage (outbound) |
| | `apps/webapp/src/webapp/auth/` | OAuth handlers (inbound) |
| | `sources/*/src/source_*/adapters/inbound/` | External API clients |
| | `sources/*/src/source_*/adapters/outbound/` | Queue publishers |

## Layer Responsibilities

**Domain Ring** (`model/gts/`)
- Defines ubiquitous language (entities, value objects)
- Declares ports (Protocol interfaces) for external dependencies
- Contains pure business logic (domain services)
- Zero framework dependencies, persistence-agnostic

**Application Ring** (`model/audio/`, `model/video/`, `apps/*/services/`)
- Shared libraries (`model/`) are standalone, callable from any context
- App services orchestrate use cases and manage transaction boundaries
- `model/audio/` coordinates domain models with DSP libraries (Pedalboard, NAM, FFmpeg)
- `model/video/` composes audio segments and domain models into videos via Remotion

**Adapters Ring** (`apps/*/api/`, `apps/*/adapters/`, `sources/*/`)
- HTTP endpoints (FastAPI routes)
- Persistence (SQLAlchemy repositories implementing gts ports)
- External API clients (T3K API, OAuth providers)
- Queue publishers and consumers

## Shared Libraries Are Decoupled

`model/` are shared libraries, not tied to any application. They can be called from:
- Web application services
- BC container consumers (t3k-sync, audio-worker, video-worker)
- CLI scripts
- Bulk import scripts
- Tests

This is enforced by dependency rules -- `model/audio/` depends only on `model/gts/`, never on `apps/` or `sources/`.

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

Core owns all synchronisation record schemas (`model/gts/src/gts/records/`). Source adapters import and conform to these schemas. Schema changes are validated in CI -- all source adapters must pass against the current core schema before merge.
