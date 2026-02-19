# Epic Context

**Assembled:** 2026-02-19T21:01:17Z
**Detected Areas:** api_contract, audio_processing, dual_database, frontend_layers, gear_model, job_processing, signal_chain

This document is an intermediate artefact for the plan generator. It combines the epic description, selectively loaded architecture documentation, and codebase context based on detected areas. Zero AI tokens were spent producing this file.

---

> **Warning: Stale codebase files detected.** Run `just map-codebase` to refresh.

>   ENDPOINTS.md: stale by ~96.0h
>   IMPORTS.md: stale by ~96.0h
>   SCHEMA.md: stale by ~96.0h
>   STRUCTURE.md: stale by ~96.0h

---

## Epic Description

The following is the verbatim epic body as fetched from GitHub:

---
github_issue: 117
title: "Event-driven architecture migration (pgmq, BC containers)"
state: OPEN
labels: []
fetched: 2026-02-19T21:01:17Z
---

## Epic: Jobs & Event-Driven Architecture Migration

Migrate from monolithic worker with TaskIQ/Redis to event-driven architecture with one container per bounded context, pgmq-only messaging, and transactional outbox.

### Key deliverables

- Single database (merge `gts_t3k_source` into `gts_core`)
- BC-prefixed tables (`core_*`, `t3k_*`)
- Project structure rename (`libs/` → `model/`, new `infra/messaging/`)
- pgmq command/event messaging with transactional outbox
- Per-BC containers: `t3k-sync`, `audio-worker`, `video-worker`
- Remove: TaskIQ, Redis, monolithic worker, scheduler

### References

- **Implementation plan:** `docs/plans/2026-02-19-jobs-event-driven-architecture-plan.md` (48 tasks, 9 phases)
- **Wiki (source of truth):** [Jobs-Architecture-and-Operations](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Jobs-Architecture-and-Operations)
- **Design rationale:** `docs/plans/2026-02-19-jobs-event-driven-architecture-design.md`

### Phases

| Phase | Tasks | Deliverable |
|-------|-------|-------------|
| 0 | 4 | Documentation baseline |
| 0.5 | 2 | Project structure: `libs/` → `model/`, new `infra/messaging/` |
| 1 | 14 | Single database, BC-prefixed tables |
| 2 | 7 | Message schemas, consumer base classes |
| 3 | 6 | T3K sync container, scheduler removed |
| 4 | 3 | Audio BC container |
| 5 | 3 | Video BC container |
| 6 | 3 | Webapp pgmq dispatch |
| 7 | 6 | Cleanup: remove TaskIQ, Redis, monolithic worker |
| **Total** | **48** | **Event-driven architecture fully operational** |


---

## Architecture (from wiki)

The following sections were selectively loaded based on detected areas (api_contract, audio_processing, dual_database, frontend_layers, gear_model, job_processing, signal_chain):


### GTS-Technical-Architecture :: architecture-layers

## Overview

Guitar Tone Shootout is an A/B testing platform for guitar tones. Users compare audio samples processed through different gear configurations to evaluate tone quality.

### Core Value Proposition

The platform's unique value is **gear comparison through audio processing**. Users build signal chains from amp captures and IRs, process their DI recordings through these chains, and compare results side-by-side in video format.

Gear comes from multiple sources:
- **Tone3000 (T3K)** — NAM amp/pedal captures and IRs (largest volume)
- **Community uploads** — User-contributed IRs
- **Future sources** — AIDA-X, other marketplaces

All sources feed into a unified gear model for consistent handling.

### Signal Chain: The Foundation

The signal chain is the core domain concept. It defines how audio flows through gear:

```
DI Track → [Pre-Effects*] → Amp → [Loop Effects*] → [IR?] → [Post-Effects*] → Output
                                        ↑
                              (not allowed if FULL_RIG)
```

| Component | Required | Quantity | Description |
|-----------|----------|----------|-------------|
| DI Track | Yes | 1 | Clean guitar recording (input) |
| Pre-Effects | No | 0+ | Overdrive, distortion, fuzz, wah, compressor, boost |
| Amp | Yes | 1 | Either HEAD (requires IR) or FULL_RIG (IR baked in) |
| Loop Effects | No | 0+ | Effects between amp and cabinet (EQ, modulation); not allowed with FULL_RIG |
| IR | Conditional | 0-1 | Cabinet simulation; required for HEAD, forbidden for FULL_RIG |
| Post-Effects | No | 0+ | Delay, reverb, spatial effects |

**This document defines:**
- Audio processing pipeline and signal chain grammar
- Domain model (GTS ubiquitous language)
- Technology choices and rationale
- Application architecture (webapp, ingestion pipeline)
- Repository structure and workspace organisation
- Infrastructure management and workflow
- Deployment

---

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
| Caching | Redis | Job broker, sync status tracking (jobs profile only — not used by webapp) |
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
| Video composition | Remotion (React) | Programmable video, React components, server-side rendering |
| Video rendering | Docker (Node.js + Chromium) | Headless browser rendering via `@remotion/renderer` |
| Image preparation | Pillow | Crop, resize, placeholder generation for gear images |
| Video output | H.264/AAC MP4 | 1920×1080, 30fps, YouTube optimised |

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

---

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
│   │       ├── api/            # HTTP endpoints (no admin — moved to worker)
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

---


### GTS-Technical-Architecture :: domain-model

## Domain Model

GTS ubiquitous language - our terminology for the domain.

### Aggregate Roots

| Aggregate | Description |
|-----------|-------------|
| **User** | Authenticated user account with linked OAuth identities |
| **Gear** | Equipment item (amp, pedal, IR, etc.) - unified across all sources |
| **DITrack** | Uploaded guitar recording (source audio for processing) |
| **SignalChain** | Composition of blocks in processing order - independent of shootouts |
| **Shootout** | A/B tone comparison using signal chains |

### Core Entities

#### User Management
| Entity | Description |
|--------|-------------|
| User | User account |
| UserIdentity | OAuth provider link (multi-provider per user) |
| OAuthProvider | OAuth provider configuration |

#### Unified Gear Model
| Entity | Description |
|--------|-------------|
| Gear | Equipment item (unified across all sources) |
| GearModel | Specific model file (NAM, IR, etc.) within gear |
| GearSource | Source attribution (t3k, community, etc.) |
| GearTag | Categorisation tags |
| GearMake | Manufacturer/brand |
| UserGear | User's gear library (references Gear) |

#### Signal Chains
| Entity | Description |
|--------|-------------|
| SignalChain | Aggregate root - composition of blocks |
| SignalChainBlock | Single block in chain (gear OR built-in processor) |
| SignalChainGroup | Collection of chains for permutation output |
| SignalChainGroupAmp | Amp selections for group permutation |
| SignalChainGroupIR | IR selections for group permutation |
| BlockType | Built-in processor template (EQ, compressor, etc.) |
| Preset | Parameter values for a signal chain |

#### Audio & Shootouts
| Entity | Description |
|--------|-------------|
| DITrack | User-uploaded guitar recording |
| Shootout | A/B comparison configuration |
| ShootoutChain | Signal chain reference within a shootout |

#### System
| Entity | Description |
|--------|-------------|
| Job | Background job tracking |
| ErrorReport | Error tracking |
| UserNotification | User notifications |
| Audit | Audit trail |

### Gear Types

| Type | Description |
|------|-------------|
| AMP | Amplifier model (HEAD - requires IR) |
| FULL_RIG | Complete amp + cab combination (IR baked in) |
| PEDAL | Effects pedal |
| OUTBOARD | Rack/outboard gear |
| IR | Impulse response (cabinet simulation) |

### Gear Platforms

| Platform | Description |
|----------|-------------|
| NAM | Neural Amp Modeler |
| IR | Impulse Response |
| AIDA_X | AIDA-X format |
| AA_SNAPSHOT | Atomic Amplifire snapshot |
| PROTEUS | Proteus format |

### Signal Chain Blocks

A block is a single component in a signal chain. Can contain:

**Gear-based blocks:**
- Amp (exactly one required per chain)
- IR (optional, zero or one)
- Pedal (zero or more, positioned pre-amp, loop, or post)

**Built-in processor blocks (BlockType):**
| Category | Types |
|----------|-------|
| Utility | Noise Gate, Gain |
| EQ | Parametric EQ, Graphic EQ |
| Dynamics | Compressor, Limiter |
| Filter | High-pass, Low-pass |
| Delay | Delay |
| Reverb | Reverb |
| Modulation | Chorus, Flanger, Phaser |

### Signal Chain Grammar

```
DI Track → [Pre-Effects*] → Amp → [Loop Effects*] → [IR?] → [Post-Effects*] → Output
                                        ↑
                              (not allowed if FULL_RIG)
```

| Position | Allowed | Description |
|----------|---------|-------------|
| Pre-Effects | Pedals, built-in processors | Before amp (overdrive, boost, wah, compressor) |
| Amp | Exactly one | HEAD (requires IR) or FULL_RIG (forbids IR) |
| Loop Effects | Pedals, built-in processors | Between amp and cabinet (EQ, modulation); **not allowed with FULL_RIG** |
| IR | Zero or one | Cabinet simulation; required for HEAD, forbidden for FULL_RIG |
| Post-Effects | Pedals, built-in processors | After cabinet (delay, reverb, spatial) |

**Validation Rules:**
| Error | Condition |
|-------|-----------|
| NO_AMP | No amp block in chain |
| MULTIPLE_AMPS | More than one amp block |
| IR_REQUIRED | HEAD amp but no IR provided |
| IR_FORBIDDEN | FULL_RIG amp but IR provided |
| MULTIPLE_IRS | More than one IR block |
| LOOP_FORBIDDEN | Loop effects present with FULL_RIG amp |
| INVALID_ORDER | Blocks in wrong position |

### User-Uploaded IRs

User-uploaded IRs use the **unified Gear model** (same as source IRs):
- `IRUploadService` creates Gear + GearModel in one operation
- Source is "community" (not a data source adapter)
- 1:1 ratio (each uploaded IR is separate gear item)
- Accessible via UserGear → GearModel → Gear chain

### Value Objects

| Value Object | Description |
|--------------|-------------|
| GearType | Enum of gear types |
| Platform | Enum of model platforms |
| AudioChecksum | SHA256 hash of audio file |
| WaveformData | Visualisation data for audio |
| BlockCategory | Enum of block categories |
| BlockPosition | Enum of positions in signal chain (pre, loop, post) |

---


### GTS-Technical-Architecture :: data-ingestion

## Data Ingestion Pipeline

Implements [[REFERENCE-ARCHITECTURE]] patterns. Source adapters are separate workspace members (`sources/*/`), decoupled from webapp.

### Flow

**Incremental Sync:**

1. **Source adapter** fetches changes from external API
2. **Source adapter** persists durable record to source database (staging/audit log)
3. **Source adapter** publishes sync record to message queue (same transaction as step 2)
4. **Core consumer** (`apps/worker/consumers/`) reads from queue
5. **Core consumer** validates against `GearSyncRecord` schema and upserts to unified Gear model

**Bulk Reingest:**

1. Source adapter replays historical records from its durable staging store
2. Records emitted in batches via the bulk ingestion interface
3. Core applies idempotent upserts and records replay checkpoints

### Topics

One topic per aggregate (not per source):
```
gear_sync
```

Source identity embedded in record payload (`source_name` field).

Other aggregates (User, DITrack, SignalChain, Shootout) are user-created within GTS, not synced from external sources.

### Source Adapters

| Source | Description |
|--------|-------------|
| Tone3000 | NAM captures and IRs (largest volume) |
| AIDA-X | AIDA-X model marketplace (future) |

Community-uploaded IRs use `IRUploadService` in the webapp directly — they don't go through the sync pipeline.

Each source is a self-contained bounded context:

| Component | Responsibility |
|-----------|----------------|
| Domain models | Source-specific data model |
| Inbound adapters | Fetch from external API/feed |
| Outbound adapters | Map to core schema, send sync records |
| Sync service | Orchestrate incremental sync |
| File service | Download and validate physical files |
| Reingest service | Orchestrate bulk replay |

### Continuous Sync

Each source runs a single continuous sync job that:

1. **Backfill walk** — Pages through catalog oldest→newest from checkpoint
2. **Newest check** — Periodically scans from newest until hitting existing items
3. **Skip recently synced** — Items synced within threshold (e.g., 7 days) are skipped
4. **Stale detection** — If checkpoint is too old (worker was down), reset to page 1

The two algorithms "meet in the middle" for complete catalog coverage while catching new uploads quickly.

### Transactional Send

When source database and pgmq share PostgreSQL:
- Source write + queue publish in same transaction
- No outbox pattern required

When queue is external (future scaling), an outbox pattern preserves atomicity between data persistence and message publication.

### Idempotency

Upsert with `(source_name, source_record_id, source_updated_at)`:
- Last-write-wins by source timestamp
- Safe under replay
- Duplicates are possible (at-least-once delivery); consumers must be idempotent

### Consistency Model

- Delivery is **at-least-once**; duplicates are possible
- Core upserts are idempotent and safe under replay
- System state is **eventually consistent**
- Acceptable lag defined per source via SLOs (typical: seconds to minutes)

### Checkpoint Management

**Incremental Sync Checkpoints:**
- Store `last_synced_at` or `last_source_id` per source
- Sync job resumes from checkpoint on restart
- Updated atomically after successful batch processing

**Reingest Checkpoints:**
- Track progress through bulk reingest (last processed batch/offset)
- Enables resume after failure without restarting from beginning
- Cleared on successful completion

**Consumer Checkpoints:**
- Consumers track message offset via pgmq `read_ct` and archive operations
- On restart, resume from last acknowledged message

### Bulk Ingest Interface

Core provides a bulk ingest interface for replay, migration, and recovery:
- Idempotent upsert using `(source_name, source_record_id, source_updated_at)` for conflict resolution
- Returns per-batch outcomes (inserted, updated, failed) and supports partial retries
- Last-write-wins by source timestamp prevents stale replays overwriting newer data
- Rate limited per source (batch size limit, payload size limit)

### Physical File Ingestion

Physical file ingestion is owned by source adapters. Synchronisation records are emitted **only after** all required files are durably stored and validated.

**File ingest state model:**

```
metadata_fetched → files_downloading → files_validated → sync_ready
```

Source adapters provide recovery jobs to reconcile metadata with stored files and clean up orphans. Files are stored in `source_downloads/{source}/{source_uuid}/` until consumed by the core worker, which moves them to `models/{core_uuid}.nam`.

---


### GTS-Technical-Architecture :: api-design

## Web Application

The webapp workspace member. Depends on core, NOT on sources.

### Services

| Service | Purpose |
|---------|---------|
| Shootout Service | Shootout CRUD + lifecycle management |
| Signal Chain Service | Chain composition + validation |
| Preset Service | Signal chains with parameter values |
| Job Service | Background job lifecycle + retry logic |
| Identity Service | OAuth provider linking (multi-provider per user) |
| Block Type Registry | Built-in processor templates (EQ, compressor, etc.) |
| IR Upload Service | User IR uploads → unified Gear model |
| DI Track Service | DI track uploads + validation |


### GTS-Technical-Architecture :: auth

### Authentication

OAuth 2.0 with multiple providers.

| Provider | Status |
|----------|--------|
| T3K (Tone3000) | Implemented |
| Google | Planned |
| GitHub | Planned |
| Facebook | Planned |

**Implementation:**
- Generic OAuth handling in `webapp/auth/`
- Provider-specific configuration (client ID, endpoints)
- Multi-provider linking per user (Identity Service)
- Token encryption at rest (Fernet)
- No provider-specific business logic in domain


### GTS-Technical-Architecture :: frontend

### Frontend

**Build System:** Astro
- Compiles Jinja2 templates (`.html.ts` → `.html`) and Tailwind CSS
- Output committed to `frontend/astro/dist/`
- Bind-mounted to FastAPI container for template access
- No Astro dev server at runtime

**Route Architecture:**

| Route Type | Technology | URL Patterns |
|------------|------------|--------------|
| Static (SSG) | Astro pre-built, nginx serves | `/`, `/about`, `/login` |
| Dynamic (SSR) | Jinja2 + FastAPI | `/gear/{slug}`, `/shootouts`, `/shootout/{id}`, `/library/*`, `/chain/*` |

All templates (static and dynamic) are authored in Astro. Dynamic templates contain Jinja2 syntax evaluated at request time by FastAPI.

**Interactivity:**
- HTMX for partial page updates (HTML-over-the-wire)
- Alpine.js for client-side UI state (tabs, toggles)
- WebSocket for real-time notifications (job completion, alerts)
- No SPA, no client-side routing

**Testability and Navigation:**
- All interactive elements MUST have `data-testid` attributes for Playwright E2E tests
- Links to SSR pages (e.g., `/gear/*`, `/shootouts`, `/library/*`) need `data-astro-reload` in Astro components — ClientRouter intercepts clicks otherwise

**HTMX Fragment Convention:**

| Backend Route | Template Path |
|---------------|---------------|
| `/api/v1/html/{domain}/{action}` | `fragments/{domain}/{action}.html` |

Examples:
- `DELETE /api/v1/html/chains/{id}` → returns empty (element removed)
- `POST /api/v1/html/chains/{id}/process` → returns updated status fragment
- `GET /api/v1/html/gear/browse` → returns gear list fragment for filtering

**React Island: Signal Chain Builder**

Complex interactive UI for composing signal chains. React assets loaded ONLY on builder page.

| Mode | Description | Output |
|------|-------------|--------|
| Permutation | Multiple gear per block (3 amps × 4 IRs) | SignalChainGroup |
| Single Chain | One gear per block | SignalChain (reusable) |

**Signal Chain Library**

SSR page for managing saved chains. HTMX for inline actions (delete, submit processing jobs).

- List user's SignalChains and SignalChainGroups
- Add DI tracks to chains for processing
- Delete chains/groups
- View audio segments generated from chains

Shootouts are optional — users can build chains, process audio, and manage their library without creating comparisons.

### API Design

| Route Prefix | Purpose |
|--------------|---------|
| `/api/v1/` | JSON API (data operations, auth) |
| `/api/v1/html/` | HTML fragments (HTMX responses) |
| `/` | SSR pages |

**Note:** Admin APIs (`/admin/*`) are not in webapp. See [[#Admin API Architecture]] for worker (port 8001) and source adapter (port 8002+) admin endpoints.

---


### GTS-Technical-Architecture :: persistence

## File Storage

Shared bind mount (`../gts-storage/`) — all worktrees share one storage directory on the host, mapped to `/app/storage/` in containers.

### Storage Layout

```
/app/storage/
├── models/              # Core gear models ({uuid}.nam)
├── uploads/
│   ├── di_tracks/       # User-uploaded guitar recordings
│   └── irs/             # User-uploaded impulse responses
├── audio/               # Processed shootout audio segments
├── videos/              # Generated shootout comparison videos
└── source_downloads/    # Raw source adapter downloads
    └── t3k/             # T3K models ({model_id}/{filename}.nam)
```

**Audio segments** are the processed output from running a DI track through a signal chain with a preset. Files are named by UUIDv7 from the audio table.

Audio segments include:
- Standalone processing (signal chain library)
- Individual permutation outputs (shootout processing)
- Full concatenated audio track (for video)

### Upload Handling

- Validate format, size, sample rate
- Compute SHA256 checksum
- Extract waveform visualisation data
- Access controlled via API (not direct HTTP)

---

## Database

PostgreSQL server with separate logical databases per bounded context.

### Database Separation

| Database | Connects From | Purpose |
|----------|---------------|---------|
| `gts_core` | Webapp, Worker | Core domain model (users, gear, signal chains, audio) |
| `gts_t3k_source` | T3K Adapter, Worker | T3K source staging + pgmq queue |

**Isolation rule:** Webapp has NO connection to source databases. Source adapters have NO connection to core database.

Worker is the only component with connections to both — it consumes from source queues and writes to core database.

### Transactional Send

Each source database has its own pgmq queue. Source adapter writes staging data + enqueues sync record in single transaction. Worker consumes and upserts to core database.

### Core Database Tables (`gts_core`)

| Category | Tables |
|----------|--------|
| User | `users`, `user_identities`, `oauth_providers` |
| Unified Gear | `gear`, `gear_models`, `gear_sources`, `gear_tags`, `gear_makes`, `user_gear` |
| Signal Chains | `signal_chains`, `signal_chain_blocks`, `signal_chain_groups`, `signal_chain_group_amps`, `signal_chain_group_irs`, `block_types` |
| Audio | `di_tracks`, `audio_segments`, `shootouts`, `shootout_chains` |
| System | `jobs`, `error_reports`, `user_notifications`, `audit` |
| Sync | `sources`, `source_checkpoints` |

### Source Database Tables (`gts_t3k_source`)

| Category | Tables |
|----------|--------|
| T3K Staging | `packs`, `models`, `creators`, `tags`, `makes`, `pack_images`, `pack_links` |

Source tables are owned by the source adapter. Core domain model has no knowledge of source table structure.

### Schema Evolution

Core owns synchronisation record schemas and compatibility rules.

**Compatibility Policy:**
- Default: backward-compatible changes (additive)
- Schema changes validated in CI prior to deployment
- Removals require deprecation windows with advance notice

**Zero-Downtime Expand-Contract Pattern** (for breaking changes):

| Phase | Action | Rollback |
|-------|--------|----------|
| **Expand** | Add new column/structure alongside old; deploy dual-write code | Drop new column, revert code |
| **Migrate** | Backfill existing data to new structure (in batches) | Re-run backfill |
| **Contract** | Deploy read-from-new code; stop writing to old; remove old structure after confidence period | Restore from backup (point of no return) |

Each phase is independently deployable. Non-breaking changes (adding nullable columns, new tables, new indexes) can be deployed directly without consumer pause.

**Handling In-Flight Messages:**
1. Deploy consumers that accept both old and new schema formats
2. Deploy sources sending new format
3. After drain period, remove old format handling

In a monorepo, schema changes can be atomic: single change updates core schema + all source adapters. CI validates all adapters conform before merge.

---

## Message Queue (pgmq)

PostgreSQL-native queue for gear sync pipeline. Each source database hosts its own pgmq queue.

### Queue Location

| Database | Queue | Producer | Consumer |
|----------|-------|----------|----------|
| `gts_t3k_source` | `gear_sync` | T3K Adapter | Worker |
| `gts_aidax_source` | `gear_sync` | AIDA-X Adapter | Worker |

**Why queues in source databases?** Enables transactional send — source adapter writes staging data and enqueues sync record in single transaction. No outbox pattern needed.

Worker polls from all source database queues, consuming messages and upserting to core database.

### Topic Structure

One topic per aggregate (not per source):

```
gear_sync
```

Source identity embedded in message payload (`source_name` field). Each source database has the same queue name; worker connects to each database separately.

### Message Schema

Messages conform to `GearSyncRecord` (defined in `libs/core/records/`):

| Field | Type | Description |
|-------|------|-------------|
| `source_name` | string | Source identifier (e.g., "t3k") |
| `source_record_id` | string | ID from source system |
| `source_updated_at` | datetime | Timestamp from source |
| `operation` | enum | CREATE, UPDATE, DELETE |
| `payload` | object | Gear data in core schema |

Core owns this schema. Source adapters import and conform to it.

### Consumer Pattern

Worker polls each source database queue:

1. `pgmq.read_with_poll()` with visibility timeout
2. Validate message against `GearSyncRecord` schema
3. Upsert to core database (idempotent)
4. `pgmq.archive()` on success

```sql
-- Read batch with 60s visibility timeout
SELECT * FROM pgmq.read_with_poll('gear_sync', vt => 60, qty => 10);

-- Archive after successful processing
SELECT pgmq.archive('gear_sync', msg_ids => ARRAY[1, 2, 3]);
```

### Dead Letter Queue

pgmq tracks read attempts via `read_ct` field. Worker implements automatic DLQ:

1. On read, check `read_ct` against max retries threshold
2. If exceeded, move message to `gear_sync_dlq` queue
3. Archive from main queue

```sql
-- Move to DLQ when read_ct exceeds threshold
INSERT INTO pgmq.q_gear_sync_dlq (msg)
SELECT msg FROM pgmq.q_gear_sync WHERE msg_id = $1;

SELECT pgmq.archive('gear_sync', msg_id => $1);
```

DLQ messages retain original payload plus failure metadata for investigation.

### Delivery Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| At-least-once | Messages reappear after visibility timeout if not archived |
| Idempotent consumers | Upsert with `(source_name, source_record_id, source_updated_at)` |
| Order preserved | Single consumer per source database |

### Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Visibility timeout (`vt`) | 60s | Processing time without blocking |
| Max retries | 3 | Balance reliability and throughput |
| Poll interval | 1s | Responsive without excessive load |
| Batch size (`qty`) | 10 | Small batches for responsiveness |

### Migration Path

Current: pgmq in PostgreSQL (simple, transactional).

**Scaling triggers** — Consider migration when any of:
- Throughput exceeds ~10k messages/second sustained
- Operational risk isolation required (source failure affecting core)
- Organisational boundaries emerge (team ownership of source adapters)
- Broker features needed (fan-out, replay, cross-DC replication)

**Note:** Scaling is an optional migration path, not a near-term driver.

**Migration to outbox pattern:**
1. Add outbox table to each source database
2. Replace direct queue send with outbox insert in same transaction
3. Deploy outbox workers per source
4. Switch to external broker (e.g., RabbitMQ, SQS)
5. Core consumer logic unchanged (same message schema)

---

## Job Scheduling (TaskIQ)

Async job scheduler for background processing. Separate from pgmq (gear sync message queue).

### Scope Separation

| System | Purpose | Trigger |
|--------|---------|---------|
| TaskIQ | Scheduled tasks + processing jobs | Scheduler cron, user action |
| pgmq | Gear sync messages (source → core) | Source adapter publishes |

TaskIQ triggers source adapter sync and handles user-initiated processing. pgmq transports sync messages between source and core databases.

### Job Types

| Job Type | Parent | Purpose |
|----------|--------|---------|
| `SOURCE_SYNC` | — | Source adapter sync (fetch + download + stage + enqueue) |
| `SHOOTOUT` | — | Orchestrate shootout creation (parent) |
| `SHOOTOUT_AUDIO` | SHOOTOUT | Process single tone for shootout (child) |
| `VIDEO_COMPOSE` | SHOOTOUT | Generate comparison video (child) |
| `SIGNALCHAIN_AUDIO` | — | Process chain from library (standalone) |
| `ORPHAN_CLEANUP` | — | Clean orphaned files from failed transactions |

### Job Hierarchy

Shootout processing uses parent/child jobs:

```
SHOOTOUT (parent)
├── SHOOTOUT_AUDIO (tone A)
├── SHOOTOUT_AUDIO (tone B)
├── SHOOTOUT_AUDIO (tone C)
└── VIDEO_COMPOSE (after all segments complete)
```

Parent job tracks aggregate progress. Child jobs execute independently and report to parent.

### Scheduled Tasks

| Task | Schedule | Purpose |
|------|----------|---------|
| `ensure_source_sync_running` | */5 min | Auto-start source sync if not running |
| `monitor_stale_jobs` | */2 min | Detect crashed workers |
| `process_pending_retries` | */2 min | Retry failed jobs |
| `orphan_cleanup` | Daily | Remove orphaned files |
| `scheduler_heartbeat` | */1 min | Health monitoring + lock renewal |

### Source Sync Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         Scheduler                                 │
│  ensure_source_sync_running (*/5 min)                            │
│  - Check if sync enabled (env var)                               │
│  - Check if sync already running (Redis lock)                    │
│  - Create SOURCE_SYNC job and queue task                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SOURCE_SYNC Job (Worker)                       │
│  1. Acquire sync lock (Redis)                                    │
│  2. Fetch gear + metadata from external API                      │
│  3. Download models to source_downloads/{source}/{source_uuid}   │
│  4. Stage gear record in source DB                               │
│  5. Enqueue GearSyncRecord to pgmq (same transaction as step 4)  │
│  6. Update checkpoint                                            │
│  7. Release lock                                                 │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    pgmq Consumer (Worker)                         │
│  1. Consume message from pgmq                                    │
│  2. Validate GearSyncRecord schema                               │
│  3. Verify model file exists in source_downloads/                │
│  4. Begin UoW transaction:                                       │
│     a. Insert Gear + GearModel in gts_core (core UUIDv7)         │
│     b. Move file to models/{core_uuid}.nam                       │
│     c. Commit                                                    │
│  5. Archive pgmq message                                         │
└──────────────────────────────────────────────────────────────────┘
```

### Job Lifecycle

```
PENDING → RUNNING → COMPLETED
              ↓
           FAILED → RETRY → RUNNING (up to max_attempts)
              ↓
           DEAD (after max retries)
```

| Status | Description |
|--------|-------------|
| PENDING | Created, waiting for worker |
| RUNNING | Worker executing |
| COMPLETED | Finished successfully |
| FAILED | Error occurred, may retry |
| RETRY | Scheduled for retry |
| DEAD | Exceeded max retries |

### Containers

| Container | Purpose | Admin Port |
|-----------|---------|------------|
| `scheduler` | Triggers scheduled tasks | — |
| `worker` | Executes jobs + consumes sync messages + admin API | 8001 |

**Worker container runs:**
- Admin API (FastAPI on port 8001) — serves all admin endpoints
- TaskIQ worker (job execution)
- pgmq consumer (gear sync messages)

The worker serves T3K admin endpoints (`/admin/t3k/*`) by querying `gts_t3k_source` directly — it already has this database connection for the pgmq consumer.

Scheduler and worker run with `--profile jobs` (main worktree only).

### Distributed Lock

Single scheduler instance enforced via Redis lock:

| Setting | Value |
|---------|-------|
| Lock key | `scheduler:lock` |
| TTL | 60 seconds |
| Renewal | Heartbeat task every minute |

Source sync also uses per-source locks to prevent overlapping runs.

### Heartbeat Monitoring

Workers emit heartbeats during job execution:

| Setting | Value |
|---------|-------|
| Interval | 30 seconds |
| Stale threshold | 2 minutes |

Jobs without heartbeat update beyond threshold are marked failed (crash detection).

### Retry Strategy

Exponential backoff with jitter:

| Attempt | Base Delay | Max Delay |
|---------|------------|-----------|
| 1 | 30s | 30s |
| 2 | 60s | 120s |
| 3 | 120s | 300s |

After max attempts, job moves to DEAD status.

### Progress Reporting

**User-initiated jobs** (SHOOTOUT, SIGNALCHAIN_AUDIO):
- Real-time progress via Redis pub/sub
- WebSocket broadcasts to subscribed clients
- Live progress display in UI

**System jobs** (SOURCE_SYNC, ORPHAN_CLEANUP):
- Observability stack (metrics, logs, traces)
- Managed via worker admin API (CLI planned)

### Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Max attempts | 3 | Balance reliability and resource usage |
| Heartbeat interval | 30s | Detect crashes without excessive overhead |
| Stale threshold | 2 min | Allow for slow operations |
| Concurrency | 4 workers | Match available CPU cores |

---

## Admin API Architecture

Internal admin API for infrastructure management. Not exposed publicly — access controlled at network level.

### Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Centralised in worker** | Worker already has all database connections needed |
| **No authentication** | Network-level access control (port not exposed) |
| **Composite health** | Single `/health` endpoint reports all component status |

### Admin API (Worker — port 8001)

All admin endpoints served by the worker container:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/jobs` | GET | List jobs with status filter |
| `/admin/jobs/{id}` | GET | Get job details |
| `/admin/jobs/dead-lettered` | GET | List dead-lettered jobs |
| `/admin/jobs/{id}/retry` | POST | Retry failed job |
| `/admin/jobs/pending-retries/count` | GET | Pending retry count |
| `/admin/t3k/sync/status` | GET | Current sync state and pagination |
| `/admin/t3k/sync` | POST | Trigger catalog sync |
| `/admin/t3k/sync/stats` | GET | Pack/model counts |
| `/admin/t3k/sync/lag` | GET | Time since last sync |
| `/admin/t3k/auth/status` | GET | OAuth token validity |
| `/admin/t3k/errors/summary` | GET | Error aggregation by type |
| `/health` | GET | Composite health check |

**Why worker serves T3K endpoints:** The worker already connects to `gts_t3k_source` for the pgmq consumer. It can query sync status, stats, and checkpoints from the same database connection. No need for a separate T3K HTTP server.

**Future sources:** When AIDA-X or other sources are added, their admin endpoints (`/admin/aidax/*`) will also be served by the worker, which will have connections to those source databases for their pgmq queues.

### Composite Health Endpoint

The `/health` endpoint reports on all worker components:

```json
{
  "status": "healthy",
  "components": {
    "admin_api": "ok",
    "taskiq_broker": "connected",
    "pgmq_consumer": "polling"
  }
}
```

Docker healthchecks use this endpoint. If any component is unhealthy, the container is marked unhealthy.

### Admin API Access

> **Note:** A `gts-admin` CLI is planned. Currently, use `curl` to access the worker admin API directly.

```bash
# All requests → Worker (port 8001)
curl http://localhost:8001/admin/jobs           # List all jobs
curl http://localhost:8001/admin/jobs/{id}      # Get job details
curl http://localhost:8001/admin/jobs/dead-lettered  # Dead-lettered jobs
curl http://localhost:8001/admin/t3k/sync/status     # Sync status
curl -X POST http://localhost:8001/admin/t3k/sync    # Trigger sync
curl http://localhost:8001/admin/t3k/auth/status     # T3K auth check
curl http://localhost:8001/health               # Health check
```

### Port Allocation

| Port | Container | Profile |
|------|-----------|---------|
| 8000 | webapp | default |
| 8001 | worker | jobs |

Worktree offsets apply: main uses 8001, worktree with offset 10 uses 8011.

### Dependency Flow

```
┌─────────────┐
│ curl/CLI    │
│  (client)   │
└──────┬──────┘
       │
       └──── all requests ──▶ Worker Admin API (:8001)
                                    │
                        ┌───────────┼───────────┐
                        │           │           │
                  ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────────┐
                  │ gts_core  │ │ Redis │ │gts_t3k_source │
                  └───────────┘ └───────┘ └───────────────┘
```

---


### GTS-Technical-Architecture :: audio

## Audio Processing

Audio processing transforms DI tracks through signal chains to produce audio segments. Implemented in `libs/audio/`.

### Output

**Audio segment:** Processed output from running a DI track through a signal chain with a preset. Segments can be:
- Played standalone (signal chain library)
- Grouped into comparison video (parent job orchestrates)

### Processing Pipeline

Signal flow through blocks:

```
DI Track (WAV mono)
    ↓
Resample (if sample rate mismatch)
    ↓
[Pre-Effect Blocks]* (highpass, compressor, overdrive, etc.)
    ↓
Amp Block (NAM model — HEAD or FULL_RIG)
    ↓
[Loop Effect Blocks]* (EQ, modulation — NOT allowed if FULL_RIG)
    ↓
[IR Block]? (cabinet convolution — required for HEAD, forbidden for FULL_RIG)
    ↓
[Post-Effect Blocks]* (reverb, delay, etc.)
    ↓
LUFS Normalization (EBU R128)
    ↓
Output WAV (mono, 48kHz)
```

**Block execution:** Each block processes audio sequentially. Block parameters come from the preset, which stores gear-specific settings (e.g., parametric EQ with 3 bands vs graphic EQ with 10 bands).

**FULL_RIG constraint:** FULL_RIG amps have cabinet baked in. Loop blocks and IR block are forbidden — audio flows directly from amp to post-effects.

### Block Execution

Blocks are processed through their respective engines. Consecutive blocks on the same engine may be batched.

**Processing engines:**

| Engine | Block Types | Notes |
|--------|-------------|-------|
| Pedalboard | Built-in effects (EQ, compressor, delay, reverb, filters), IR convolution | Supports stereo |
| NAM/PyTorch | Amp captures, pedal captures | Outside Pedalboard |

**Current approach:** NAM/PyTorch blocks run independently, Pedalboard handles effects and IR convolution. This works — audio quality is good.

**Batching:** Consecutive Pedalboard blocks could run as a single chain to reduce overhead. Requires experimentation to verify no sound quality impact. If issues arise, simplify chain rules.

**Swappability:** Engine selection is behind an adapter interface (`AudioProcessor` protocol). Pedalboard is the default; alternatives (LSP IR, other DSP libraries) can be swapped without changing domain logic.

**Implementation note:** Existing audio processing tests provide a foundation for experimenting with block ordering and batching strategies.

### NAM Model Execution

Neural Amp Modeler inference via PyTorch and the `nam` library.

**Model format:** `.nam` files (JSON configuration + weights)

**Loading:**
1. Parse JSON config from `.nam` file
2. Initialize PyTorch model via `nam.models.init_from_nam()`
3. Set to eval mode (inference only)

**Processing:**
```python
# Input: float32 numpy array (mono)
# Output: float32 numpy array (mono)
model(audio_tensor, pad_start=True)
```

**Caching:** Models cached in memory (LRU) to avoid repeated loading. Critical for permutation processing where the same amp processes multiple DI tracks.

**Sample rate:** Models report native sample rate. Audio resampled to match if needed.

### Loudness Normalization

EBU R128 loudness normalization ensures consistent playback volume across segments.

**Library:** `pyloudnorm` (ITU-R BS.1770 standard)

**Process:**
1. Measure integrated loudness (LUFS) of processed audio
2. Calculate gain adjustment to reach target
3. Apply gain

**Default target:** -14.0 LUFS (streaming platform standard)

**Silent audio:** Fails the job. Silent input indicates a problem (missing model output, corrupt DI track). Failure propagates through job pipeline to user notification and observability stack (Loki).

**Why normalize:** A/B comparisons require matched loudness. Louder audio is perceived as "better" — normalization removes this bias.

### Permutation Processing

Signal chain groups generate multiple audio segments by varying gear selections across blocks.

**What multiplies permutations:**

| Block Type | Can Multiply | Can Be Null | Example |
|------------|--------------|-------------|---------|
| DI Track | Yes | No | [DI₁, DI₂] |
| Pre-Effect / Pedal | Yes | Yes | [(null, Overdrive)] or [(OD₁, OD₂)] |
| Amp (HEAD/FULL_RIG) | Yes | No | [Amp₁, Amp₂] |
| Loop Effect | Yes | Yes | [(null, EQ)] |
| IR | Yes | No | [IR₁, IR₂] (HEAD only) |
| Post-Effect | Yes | Yes | [(null, Reverb)] |

**Null gear:** Represents "no gear in this position". Allows A/B comparison of chain with vs without an effect. Amps and IRs cannot be null — they're required chain components.

**Permutation expansion example:**

```
SignalChainGroup
├── DI Tracks: [DI₁]
├── Pre-Effects: [(null, Overdrive)]      ← 2 options (with/without)
├── Amps: [Amp₁ (HEAD)]
├── Loop Effects: [EQ]                     ← 1 option (static)
├── IRs: [IR₁, IR₂]                        ← 2 options
└── Post-Effects: [Reverb]                 ← 1 option (static)

Permutations: 1 × 2 × 1 × 2 × 1 = 4

├── DI₁ → (none) → Amp₁ → EQ → IR₁ → Reverb
├── DI₁ → (none) → Amp₁ → EQ → IR₂ → Reverb
├── DI₁ → OD → Amp₁ → EQ → IR₁ → Reverb
└── DI₁ → OD → Amp₁ → EQ → IR₂ → Reverb
```

**Limits:**

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max permutations | 27 | Keeps processing time reasonable |
| Max options per block | 3 | UI/UX simplicity |

Total permutations = product of all block option counts. Validated before processing.

### File Formats & Quality

**Input:**

| Type | Format | Constraints |
|------|--------|-------------|
| DI Track | WAV mono | Any sample rate (resampled if needed) |
| NAM Model | `.nam` (JSON) | Must match expected schema |
| IR | WAV mono | ≤2 seconds, 44.1/48/96 kHz |

**Output:**

| Type | Format | Settings |
|------|--------|----------|
| Audio segment | WAV mono | 48 kHz, float32 internal, 16-bit PCM saved |

**Sample rate:** 48 kHz standard (video compatibility). Input audio resampled via Pedalboard if mismatched.

**Bit depth:** Float32 throughout pipeline for headroom. Final output saved as 16-bit PCM (sufficient for playback, smaller files).

### Error Handling

**Validation errors (fail fast):**

| Error | Cause | Response |
|-------|-------|----------|
| `FileNotFoundError` | DI track, model, or IR missing | Job fails, user notified |
| `NAMLoadError` | Invalid `.nam` file or model init failure | Job fails with details |
| `IRValidationError` | Stereo IR, duration >2s, unreadable | Job fails with details |
| `InvalidChainError` | HEAD without IR, FULL_RIG with IR, etc. | Rejected at submission |

**Processing errors (may retry):**

| Error | Cause | Response |
|-------|-------|----------|
| `ProcessingError` | PyTorch/Pedalboard failure | Retry up to max attempts |
| `NormalizationError` | Silent audio, invalid LUFS | Job fails, user notified |

**Partial failure:** If one permutation fails in a group, others continue. Parent job reports partial completion with failed segment details.

---


### GTS-Technical-Architecture :: infrastructure

## Infrastructure Management & Workflow

Developer tooling for parallel development and environment management. The existing tooling from the archive will be adapted to the new repository structure.

### First-Time Setup

Tiered bootstrap process for new developers.

**Tier 0 — Prerequisites:**
- Docker + Docker Compose v2
- uv (Python package manager)
- just (task runner)
- git + gh CLI

**Tier 1 — Project Dependencies:**
- Worktree CLI dependencies
- E2E test dependencies (Playwright, Chromium)

**Tier 2 — Service Startup:**
- Docker services started
- Database migrations applied
- Auth tokens restored (if available)

**Bootstrap command:**
```bash
./scripts/first-time-setup.sh
```

The script detects missing prerequisites and offers to install them via the appropriate package manager (cargo, brew, apt, pacman).

### Worktree Management

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

### Justfile

Task runner with commands for development workflow. Use `just --list` for discovery.

| Category | Key Commands |
|----------|--------------|
| **Docker** | `up-d`, `down`, `rebuild`, `logs`, `shell`, `status` |
| **Quality** | `check`, `lint`, `check-types`, `check-imports` |
| **Testing** | `tdd`, `test-regression`, `test`, `test-unit`, `test-integration`, `test-e2e` |
| **Database** | `migrate`, `db-export`, `db-import`, `psql`, `psql-t3k` |
| **Frontend** | `build-astro`, `watch-astro`, `check-astro`, `verify-astro-sync` |
| **Git Hooks** | `install-hooks`, `run-hooks`, `uninstall-hooks` |
| **Infrastructure** | `infra` (host setup), `clean` |

### Docker Compose

**Runtime Services:**

| Service | Purpose |
|---------|---------|
| `db` | PostgreSQL (data + pgmq) |
| `redis` | Job broker for TaskIQ (jobs profile only — not used by webapp) |
| `webapp` | FastAPI application |
| `nginx` | Reverse proxy, static files |

**Profiles:**

| Profile | Services | Usage |
|---------|----------|-------|
| `jobs` | worker, scheduler | Main worktree only (background processing) |
| `build` | astro | Frontend build (on-demand) |
| `tools` | cloudbeaver | Database IDE (optional) |
| `observability` | prometheus, loki, tempo, grafana, alloy | Monitoring stack (optional) |

Feature worktrees run without the `jobs` profile — they use data synced from main.

### Shared Resources

Resources shared across all worktrees:

| Resource | Location | Purpose |
|----------|----------|---------|
| Storage | `../gts-storage/` | Models, uploads, audio, videos |
| Auth tokens | `../.gts-auth.json` | OAuth tokens (600 permissions) |
| Bare repository | `../gts.git/` | Shared git objects |
| Registry | `../.worktree/registry.db` | Worktree state (SQLite) |

### Claude Code Integration

Infrastructure hooks prevent destructive operations and manage session state. Brief mention here; see `AGENTS.md` for details.

**Programmatic Enforcement:** `.claude/rules/` files enforce these constraints for AI agents — container-first execution, infrastructure protection, testing policy, security, and authentication rules are loaded into every Claude Code session automatically.

| Hook | Purpose |
|------|---------|
| `block-adhoc-infra.sh` | Prevents ad-hoc Docker volume/network operations |
| `auth-check.sh` | Warns if OAuth tokens expiring |
| `sync-start.sh` | Pulls latest from origin on session start |

---

## Deployment

Self-hosted Docker on dedicated server (Hetzner).

### Environments

| Environment | URL | Compose Files |
|-------------|-----|---------------|
| Development (main) | https://dev.tone-shootout.com | base + override + traefik |
| Feature worktrees | https://{name}.dev.tone-shootout.com | base + override + traefik |
| CI | — | base + ci |
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

### Testing Strategy

**Clear boundary: Regression/Unit/Integration in Docker, E2E on Host.**

| Test Type | Location | Runs In | Command | Purpose |
|-----------|----------|---------|---------|---------|
| Regression | `tests/regression/` | Docker | `just test-regression` | Stack connectivity (ORM → Repo → DB) |
| Unit | `tests/unit/` | Docker | `just test-unit` | Isolated logic, no I/O |
| Integration | `tests/integration/` | Docker | `just test-integration` | Real DB/Redis |
| E2E | `tests/e2e/python/` | Host | `just test-golden-path` | Full user journey |

**Regression tests** validate the ORM → Repository → Database stack works:
- User and Job entity round-trips
- Uses SQLite in-memory for speed (~0.2s)
- Run before commits to catch fundamental breaks

**Why E2E on host?**
- E2E tests use Playwright to hit running containers from outside
- Isolated dependencies in `tests/e2e/python/pyproject.toml`
- No pollution of main workspace venv

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
| nginx | 128M | — |
| webapp | 1G | 1.0 |
| worker | 2G | 2.0 |
| db | 512M | — |
| redis | 512M | — |

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

---


### Audio-Processing

# Audio Processing

Implementation details for `libs/audio/`. For architectural overview, see [[GTS-Technical-Architecture]].

---

## Overview

The audio library processes DI guitar tracks through signal chains to produce audio segments for shootout comparisons.

| Component | Purpose |
|-----------|---------|
| `processing/processor.py` | Main AudioProcessor implementation |
| `processing/nam_loader.py` | NAM model loading with LRU cache |
| `processing/ir_loader.py` | Impulse response file loading |
| `processing/loudness.py` | EBU R128 loudness measurement/normalization |
| `processing/chain_executor.py` | Signal chain block execution |
| `processing/permutation.py` | Signal chain group expansion |
| `analysis/waveform.py` | Waveform visualization data |

---

## Directory Structure

```
libs/audio/
├── src/audio/
│   ├── __init__.py
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── processor.py         # PedalboardAudioProcessor
│   │   ├── nam_loader.py        # load_nam_model()
│   │   ├── ir_loader.py         # load_ir()
│   │   ├── loudness.py          # measure_loudness(), normalize_loudness()
│   │   ├── chain_executor.py    # execute_signal_chain()
│   │   └── permutation.py       # expand_signal_chain_group()
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── waveform.py          # extract_waveform()
│   └── video/
│       └── __init__.py          # Placeholder for video composition
└── pyproject.toml
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pedalboard` | ^0.9.0 | Effects, IR convolution, audio I/O |
| `pyloudnorm` | ^0.1.1 | EBU R128 loudness measurement |
| `torch` | ^2.5.0 | NAM model loading and inference |
| `scipy` | ^1.14.0 | Audio resampling |
| `soundfile` | ^0.12.0 | Audio file I/O |
| `numpy` | - | Array operations |

---

## PedalboardAudioProcessor

**File:** `processing/processor.py`

Main audio processor implementing the `AudioProcessor` protocol from `libs/core/ports/`.

### Supported Formats

WAV, FLAC, OGG, MP3

### Public Methods

```python
class PedalboardAudioProcessor:
    def get_supported_formats(self) -> list[str]
    def is_format_supported(self, format_ext: str) -> bool
    async def extract_waveform(self, audio_path: Path, num_peaks: int = 200) -> WaveformData
    async def measure_loudness(self, audio_path: Path) -> tuple[float, float]
    async def normalize_loudness(self, input_path: Path, output_path: Path, target_lufs: float = -14.0) -> AudioResult
    async def process_di_track(self, input_path: Path, output_path: Path, config: ToneConfig) -> AudioResult
```

### Processing Pipeline

`process_di_track()` executes the following steps:

```
1. Load DI audio file
   ↓ (stereo converted to mono by averaging)
2. Resample if needed
   ↓ (match config sample rate)
3. Apply highpass filter (optional)
   ↓ (Pedalboard HighpassFilter)
4. Apply NAM model
   ↓ (sample-by-sample PyTorch inference)
5. Apply IR convolution (optional)
   ↓ (Pedalboard Convolution)
6. Normalize loudness
   ↓ (EBU R128 to target LUFS)
7. Write output file
```

### Return Value

```python
AudioResult(
    duration=float,        # seconds
    sample_rate=int,       # Hz
    peak_dbfs=float,       # dBFS
    integrated_lufs=float, # LUFS
    processing_time=float, # seconds
)
```

---

## NAM Model Loading

**File:** `processing/nam_loader.py`

Loads Neural Amp Modeler models with LRU caching for repeated use.

### Function

```python
def load_nam_model(model_path: Path) -> tuple[torch.nn.Module, int]
```

Returns `(model, sample_rate)`. Default sample rate: 48,000 Hz.

### Implementation

- Checkpoint format: Dictionary with `model` (state dict) and optional `sample_rate`
- Uses `torch.load(..., weights_only=False)`
- Model set to evaluation mode after loading
- Cache key: file path (via `functools.lru_cache`)

### Cache Configuration

| Setting | Value |
|---------|-------|
| Cache size | 10 models |
| Cache key | File path |

### Error Handling

```python
class NAMLoadError(Exception):
    """Raised for missing files, invalid formats, or loading failures."""
```

---

## IR Loading

**File:** `processing/ir_loader.py`

Loads impulse response files for cabinet convolution.

### Function

```python
def load_ir(path: str | Path) -> Convolution
```

Returns a Pedalboard `Convolution` effect object.

### Supported Formats

| Format | Magic Bytes |
|--------|-------------|
| WAV | RIFF header + WAVE signature |
| FLAC | fLaC header |

### Validation Steps

1. Check file exists
2. Validate format via magic bytes
3. For WAV: additional validation via `wave` module
4. Check file is non-empty
5. Load into Pedalboard `Convolution`

### Error Handling

```python
class IRLoadError(Exception):
    """Raised for missing files, invalid formats, or corruption."""
```

---

## Loudness Processing

**File:** `processing/loudness.py`

EBU R128 standard loudness measurement and normalization using PyLoudnorm.

### Functions

```python
def measure_loudness(audio_path: Path) -> tuple[float, float]
    """Returns (integrated_lufs, peak_dbfs)."""

def normalize_loudness(
    input_path: Path,
    output_path: Path,
    target_lufs: float = -14.0
) -> tuple[float, float]
    """Normalizes to target LUFS. Returns (result_lufs, result_peak_dbfs)."""
```

### Default Target

-14.0 LUFS (broadcast/streaming standard)

### Silent Audio Detection

Audio with peak < 1e-6 is rejected. Silent input indicates a problem (missing model output, corrupt DI track).

### Error Handling

```python
class LoudnessError(Exception):
    """Raised for silent audio or measurement failures."""
```

---

## Signal Chain Execution

**File:** `processing/chain_executor.py`

Sequential block-by-block signal chain execution with constraint validation.

### Function

```python
async def execute_signal_chain(
    chain: SignalChain,
    di_audio: np.ndarray,
    sample_rate: int,
    gear_path_resolver: Callable[[UUID], Path]
) -> np.ndarray
```

### Processing Logic

1. Validate chain is not empty
2. Sort blocks by position (enforces execution order)
3. Validate chain constraints
4. Process each block sequentially

### Supported Gear Types

| Gear Type | Processing |
|-----------|------------|
| `AMP`, `FULL_RIG`, `PEDAL`, `POST_EFFECT` | NAM model |
| `IR` | Convolution |

### Chain Constraints

| Rule | Constraint |
|------|------------|
| FULL_RIG | Cannot combine with IR (cabinet baked in) |
| HEAD (AMP) | Requires IR block for cabinet simulation |

### Error Handling

```python
class ChainExecutionError(Exception):
    """Raised for invalid chains or processing failures."""
```

---

## Permutation Processing

**File:** `processing/permutation.py`

Expands signal chain groups into all valid permutations.

### Functions

```python
def expand_signal_chain_group(group: SignalChainGroup) -> list[dict[int, UUID | None]]
    """Returns list of permutations. Each: slot position → gear ID or None."""

def generate_permutation_labels(
    permutations: list[dict[int, UUID | None]],
    gear_names: dict[UUID, str],
    null_label: str = "None"
) -> list[str]
    """Creates human-readable labels for each permutation."""
```

### Permutation Limits

| Constraint | Value |
|------------|-------|
| Max permutations | 27 |
| Max options per block | 3 |

### Null Gear

`None` in a slot means "no gear in this position". Enables A/B comparison with/without an effect.

Amps and IRs cannot be null - they're required chain components.

### Error Handling

```python
class PermutationError(Exception):
    """Raised for invalid config or exceeded limits."""
```

---

## Waveform Extraction

**File:** `analysis/waveform.py`

Extracts waveform visualization data for UI display.

### Function

```python
def extract_waveform(
    audio_path: Path,
    num_peaks: int = 200
) -> WaveformData
```

### Return Value

```python
WaveformData(
    peaks=tuple[float, ...],  # Peak values, normalized [-1.0, 1.0]
    sample_rate=int,
    duration_seconds=float,
    samples_per_peak=int,
)
```

### Algorithm

1. Load audio (stereo → mono by averaging)
2. Divide into segments (one per peak)
3. For each segment: find max absolute value, preserve sign
4. Normalize to [-1.0, 1.0]

---

## Integration

### Port/Adapter Pattern

`PedalboardAudioProcessor` implements `AudioProcessor` protocol defined in `libs/core/ports/audio_processor.py`.

### Domain Types

Imports from `libs/core`:
- `AudioResult` - Processing result
- `ToneConfig` - Processing configuration
- `WaveformData` - Visualization data
- `SignalChain` - Chain definition
- `GearType` - Gear type enum

### Usage Example

```python
from audio.processing.processor import PedalboardAudioProcessor
from core.domain.value_objects import ToneConfig

processor = PedalboardAudioProcessor()

# Process a DI track
result = await processor.process_di_track(
    input_path=Path("/app/storage/uploads/di_tracks/123.wav"),
    output_path=Path("/app/storage/audio/456.wav"),
    config=ToneConfig(
        nam_model_path="/app/storage/models/amp.nam",
        ir_path="/app/storage/models/cab.wav",
        sample_rate=48000,
        highpass_freq=80.0,
        target_lufs=-14.0,
    ),
)

print(f"Duration: {result.duration}s, LUFS: {result.integrated_lufs}")
```

---

## Error Hierarchy

| Exception | Module | Cause |
|-----------|--------|-------|
| `NAMLoadError` | nam_loader | Missing/invalid NAM file |
| `IRLoadError` | ir_loader | Missing/invalid IR file |
| `LoudnessError` | loudness | Silent audio or measurement failure |
| `ChainExecutionError` | chain_executor | Invalid chain or processing failure |
| `PermutationError` | permutation | Invalid config or exceeded limits |
| `ProcessingError` | processor | Wrapped exception for any failure |

---

## File Formats

### Input

| Type | Formats | Constraints |
|------|---------|-------------|
| DI Track | WAV, FLAC, OGG, MP3 | Any sample rate (resampled) |
| NAM Model | `.nam` | PyTorch checkpoint |
| IR | WAV, FLAC | Mono, ≤2 seconds |

### Output

| Type | Format | Settings |
|------|--------|----------|
| Audio segment | WAV | 48 kHz, 16-bit PCM |

---

## References

- [[GTS-Technical-Architecture]] - Architecture overview
- `libs/core/ports/audio_processor.py` - Protocol definition
- `libs/core/domain/value_objects/` - Domain types


### Frontend-Architecture

# Frontend Architecture

Implementation details for GTS frontend. For architectural overview, see [[GTS-Technical-Architecture]].

---

## Overview

GTS uses a **pre-bundled static architecture**:

| Component | Technology | Purpose |
|-----------|------------|---------|
| Build system | Astro 5 | Compiles templates and Tailwind CSS |
| Static pages | Astro `.astro` files | Pre-rendered HTML (nginx serves directly) |
| Dynamic pages | Jinja2 templates | Server-rendered by FastAPI |
| Interactivity | HTMX + Alpine.js | HTML-over-the-wire updates |
| Complex UI | React island | SignalChainBuilder only |
| Styling | Tailwind CSS 4 | Utility classes with design tokens |

**Key principle:** `frontend/astro/dist/` is committed to git. No Vite dev server at runtime.

---

## Build System

### Astro Configuration

**File:** `frontend/astro/astro.config.mjs`

```javascript
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import react from '@astrojs/react';

export default defineConfig({
  output: 'static',
  outDir: './dist',
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
  },
  build: {
    format: 'file',
  },
});
```

| Setting | Value | Purpose |
|---------|-------|---------|
| `output` | `static` | Pre-render all pages |
| `outDir` | `./dist` | Build output directory |
| `build.format` | `file` | Individual files (e.g. `/about.html` not `/about/index.html`) |
| `integrations` | `[react()]` | React island support (SignalChainBuilder) |
| `vite.plugins` | `[tailwindcss()]` | Tailwind 4 via `@tailwindcss/vite` |

### Build Commands

```bash
just build-astro         # Production build (in Docker)
just watch-astro         # View chokidar auto-rebuild logs
just check-astro         # Lint and type check
just verify-astro-sync   # CI: verify dist/ matches src/
```

All commands run inside the `astro` Docker container.

### Post-Build CSS Injection

**File:** `frontend/astro/scripts/inject-css-hash.js`

Astro generates hashed CSS filenames for cache busting (e.g. `about.CGYyzrQz.css`). The `inject-css-hash.js` script runs automatically after `astro build` and patches `dist/layouts/base.html` with the correct CSS filename. This is wired into the build script:

```json
"build": "astro build && node scripts/inject-css-hash.js"
```

### Chokidar Auto-Rebuild (Docker)

The `astro` container runs chokidar in watch mode as its default command:

```json
"watch:build": "chokidar 'src/**/*.{ts,tsx,astro,css}' -c 'pnpm build' --initial --debounce 1000"
```

**Dockerfile** (`frontend/astro/Dockerfile`):

```dockerfile
FROM node:24-alpine
RUN npm install -g pnpm@10
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile
COPY . .
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
  CMD test -f /app/dist/layouts/base.html
CMD ["pnpm", "watch:build"]
```

The healthcheck verifies the build has run at least once by checking for `base.html`.

**docker-compose.yml** service:

```yaml
astro:
  build:
    context: ./frontend/astro
    dockerfile: Dockerfile
  environment:
    SHELL: /bin/sh
  volumes:
    - ./frontend/astro:/app
    - /app/node_modules    # Prevent host node_modules override
  working_dir: /app
  restart: unless-stopped
```

Source changes on host propagate via the bind mount and trigger chokidar rebuild inside the container.

### Package Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `astro` | ^5.17.0 | Build system |
| `@tailwindcss/vite` | ^4.1.0 | Tailwind 4 Vite plugin |
| `tailwindcss` | ^4.1.0 | CSS framework |
| `@astrojs/react` | ^4.4.0 | React island integration |
| `react` | ^19.2.0 | React island runtime |
| `react-dom` | ^19.2.0 | React island DOM |
| `htmx.org` | ^2.0.8 | HTML-over-the-wire (loaded via CDN) |
| `alpinejs` | ^3.15.0 | Lightweight reactivity (loaded via CDN) |
| `chokidar-cli` | ^3.0.0 | File watcher for auto-rebuild |
| `typescript` | ^5.7.3 | Type checking |

---

## Template Architecture

### Two Template Types

| Type | Pattern | Purpose | Output |
|------|---------|---------|--------|
| `.astro` | Astro syntax | Pure static pages | HTML in `dist/` root |
| `.html.ts` | TypeScript `GET()` | Jinja2 templates | HTML in `dist/` subdirectories |

### Directory Structure

```
frontend/astro/src/pages/
├── index.astro                     # Static: home page
├── about.astro                     # Static: about page
├── login.astro                     # Static: login page
├── 404.astro                       # Static: error page
├── 500.astro                       # Static: error page
├── report-error.astro              # Static: error report page
├── report-error/thanks.astro       # Static: error report confirmation
├── jobs/index.astro                # Static: jobs page
├── dev/showcase/                   # Dev: component showcase & styleguide
├── layouts/
│   └── base.astro                  # Jinja2 base wrapper (builds to base.html)
├── partials/
│   ├── header.html.ts              # Jinja2 reusable header
│   └── footer.html.ts              # Jinja2 reusable footer
├── gear/
│   └── detail.html.ts              # Gear detail page template
├── pages/
│   ├── gear.html.ts                # Gear browse page
│   ├── shootouts.html.ts           # Public shootouts listing
│   ├── shootout_detail.html.ts     # Shootout detail page
│   ├── shootout_create.html.ts     # Shootout creation wizard
│   ├── chain_detail.html.ts        # Signal chain detail
│   ├── di-tracks.html.ts           # Public DI tracks
│   ├── di-tracks/detail.html.ts    # DI track detail
│   ├── settings_account.html.ts    # Account settings
│   └── library/                    # Library pages (authenticated)
│       ├── my_gear.html.ts
│       ├── chains.html.ts
│       ├── chains_build.html.ts
│       ├── shootouts.html.ts
│       └── di-tracks.html.ts
└── fragments/                      # HTMX response templates
    ├── ping.html.ts
    ├── sample.html.ts
    ├── gear/
    │   ├── public_browse.html.ts
    │   ├── public_pack_card.html.ts
    │   └── model_row.html.ts
    ├── di-tracks/
    │   └── public_browse.html.ts
    ├── library/
    │   ├── my_gear.html.ts
    │   ├── my_gear_pack.html.ts
    │   ├── chains.html.ts
    │   ├── chain_item.html.ts
    │   ├── groups.html.ts
    │   ├── group_item.html.ts
    │   ├── shootouts.html.ts
    │   ├── shootout_item.html.ts
    │   ├── tracks.html.ts
    │   └── track_item.html.ts
    └── shootouts/
        ├── list.html.ts
        ├── detail.html.ts
        ├── sections.html.ts
        ├── shootout_card.html.ts
        ├── comments.html.ts
        └── create/
            ├── step1-chains.html.ts
            ├── step2-ditrack.html.ts
            ├── step3-review.html.ts
            ├── chain-list.html.ts
            └── ditrack-list.html.ts
```

### Build Output

```
frontend/astro/dist/
├── index.html               # nginx serves at /
├── about.html               # nginx serves at /about
├── login.html               # nginx serves at /login
├── 404.html                 # nginx error page
├── 500.html                 # nginx error page
├── report-error.html        # Error report page
├── report-error/thanks.html
├── jobs.html                # Jobs page
├── _astro/
│   ├── about.CGYyzrQz.css   # Compiled Tailwind (hashed filename)
│   └── *.js                 # Astro client scripts (ClientRouter etc.)
├── layouts/
│   └── base.html            # Jinja2 extends target
├── partials/
│   ├── header.html          # Jinja2 include target
│   └── footer.html          # Jinja2 include target
├── gear/
│   └── detail.html          # Gear detail template
├── pages/
│   ├── gear.html            # Gear browse template
│   ├── shootouts.html
│   ├── shootout_detail.html
│   ├── shootout_create.html
│   ├── chain_detail.html
│   ├── di-tracks.html
│   ├── di-tracks/detail.html
│   ├── settings_account.html
│   └── library/
│       ├── my_gear.html
│       ├── chains.html
│       ├── chains_build.html
│       ├── shootouts.html
│       └── di-tracks.html
├── fragments/               # HTMX-loadable snippets
│   ├── ping.html
│   ├── sample.html
│   ├── gear/
│   ├── di-tracks/
│   ├── library/
│   └── shootouts/
└── dev/                     # Showcase/styleguide (dev only)
```

### Static Pages (.astro)

Standard Astro components with Tailwind styling:

```astro
---
// index.astro
import "../styles/global.css";
---

<html lang="en">
  <head>
    <title>Guitar Tone Shootout</title>
  </head>
  <body class="bg-bg-base text-text-primary">
    <main class="container mx-auto px-4 py-8">
      <h1 class="text-4xl font-bold">Welcome</h1>
    </main>
  </body>
</html>
```

### Template Generators (.html.ts)

TypeScript files that export raw HTML strings with Jinja2 syntax:

```typescript
// pages/gear.html.ts
import type { APIRoute } from "astro";
import '../../styles/global.css';  // Tailwind class scanning

export const GET: APIRoute = async () => {
  const html = `{% extends "layouts/base.html" %}

{% block title %}Gear{% endblock %}

{% block content %}
<div data-testid="gear-page" class="container mx-auto px-4 py-8">
  <h1 class="text-2xl font-bold mb-6">Gear</h1>
  <div id="gear-list" data-testid="gear-list"
       hx-get="/api/v1/html/gear/browse" hx-trigger="load">
    <div class="animate-pulse">Loading...</div>
  </div>
</div>
{% endblock %}`;

  return new Response(html, {
    headers: { "Content-Type": "text/html" },
  });
};
```

**Note:** Each `.html.ts` file imports `global.css` so Tailwind scans the Jinja2 template strings for utility classes.

### Base Layout (layouts/base.astro)

The base layout is an Astro component that outputs Jinja2 syntax as literal text. It uses `set:html` to pass Jinja2 block/include directives through Astro's template engine.

Key features:
- Jinja2 blocks: `title`, `description`, `head`, `content`, `scripts`, OG/Twitter meta
- Jinja2 includes: `partials/header.html`, `partials/footer.html`
- Pre-compiled Tailwind CSS (hashed filename, injected by post-build script)
- HTMX 2.0.4 from CDN
- Alpine.js 3.14.8 from CDN
- Global utilities: WebSocket notifications, toast system, confirm modal, delete handler

---

## Serving Architecture

### nginx Static Files

**File:** `infrastructure/nginx/nginx.conf.template`

```nginx
# Astro CSS/JS bundles (immutable, long cache)
location /_astro/ {
    root /usr/share/nginx/html/static;
    expires 1y;
    add_header Cache-Control "public, immutable";
}

# Static files (uploaded content, etc.)
location /static/ {
    alias /usr/share/nginx/html/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}

# Static pages served directly
location = /       { root /usr/share/nginx/html/static; try_files /index.html =404; }
location = /about  { root /usr/share/nginx/html/static; try_files /about.html =404; }
location = /login  { root /usr/share/nginx/html/static; try_files /login.html =404; }

# Error pages
error_page 404 /404.html;
error_page 500 502 503 504 /500.html;

# SSR pages proxy to backend
location /gear      { proxy_pass http://backend:8000; }
location /shootouts { proxy_pass http://backend:8000; }
location /library   { proxy_pass http://backend:8000; }
location /chain     { proxy_pass http://backend:8000; }
location /shootout  { proxy_pass http://backend:8000; }
```

### FastAPI/Jinja2 SSR

**Volume mount (docker-compose.yml):**

```yaml
webapp:
  volumes:
    - ./frontend/astro/dist:/app/static:ro
```

**Template configuration:**

```python
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="/app/static")
```

**Rendering pattern:**

```python
@router.get("/shootouts", response_class=HTMLResponse)
async def get_shootouts(request: Request, user: CurrentUser):
    shootouts = await shootout_service.list_by_user(user.id)
    return templates.TemplateResponse(
        request=request,
        name="pages/shootouts.html",
        context={"shootouts": shootouts, "user": user},
    )
```

**Template inheritance:**

```jinja2
{% extends "layouts/base.html" %}

{% block title %}Shootouts{% endblock %}

{% block content %}
<div data-testid="shootouts-page">
  <h1 class="text-2xl font-bold mb-6">My Shootouts</h1>
  <div
    id="shootout-list"
    data-testid="shootout-list"
    hx-get="/api/v1/html/shootouts/list"
    hx-trigger="load"
  >
    <div class="animate-pulse">Loading...</div>
  </div>
</div>
{% endblock %}
```

### Tailwind Class Scanning for Jinja2 Templates

Backend Jinja2 templates (in `apps/webapp/`) may use Tailwind classes that aren't in the Astro source files. To ensure these classes are included in the CSS bundle, the global CSS uses Tailwind 4's `@source` directive:

```css
@import "tailwindcss";
@source "/backend/templates";
```

The backend templates directory is mounted read-only into the astro container via docker-compose.

---

## Design System

### Design Tokens

**File:** `frontend/astro/src/styles/global.css`

Uses Tailwind 4's `@theme inline` directive to define CSS custom properties:

```css
@theme inline {
  /* Background layers (three-tier depth system) */
  --color-bg-base: #0a0a0a;
  --color-bg-surface: #141414;
  --color-bg-elevated: #1f1f1f;
  --color-bg-secondary: #1a1a1a;

  /* Text (high contrast for dark backgrounds) */
  --color-text-primary: #ffffff;
  --color-text-secondary: #a1a1a1;
  --color-text-muted: #666666;

  /* Accent colors (semantic) */
  --color-accent-primary: #3b82f6;       /* Blue - primary actions */
  --color-accent-primary-hover: #2563eb;
  --color-accent-secondary: #60a5fa;     /* Light blue */
  --color-accent-success: #22c55e;       /* Green */
  --color-accent-warning: #f59e0b;       /* Amber */
  --color-accent-error: #ef4444;         /* Red */

  /* Signal chain block types */
  --color-block-di: #3b82f6;            /* Blue - DI/Input */
  --color-block-amp: #f59e0b;           /* Amber - Amp/NAM */
  --color-block-cab: #22c55e;           /* Green - Cabinet/IR */
  --color-block-effect: #a855f7;        /* Purple - Pre-amp pedals */
  --color-block-post-effect: #06b6d4;   /* Cyan - Post-amp effects */

  /* Typography */
  --font-sans: 'Inter', ui-sans-serif, system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;
}
```

Also includes shadcn/ui CSS variables for React island compatibility.

### Tailwind Configuration

**File:** `frontend/astro/tailwind.config.mjs`

Maps CSS custom properties to Tailwind utility classes:

```javascript
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        'bg-base': 'var(--color-bg-base)',
        'bg-surface': 'var(--color-bg-surface)',
        'bg-elevated': 'var(--color-bg-elevated)',
        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-muted': 'var(--color-text-muted)',
        'accent-primary': 'var(--color-accent-primary)',
        // ... all tokens mapped
      },
    },
  },
};
```

### Usage Patterns

```html
<!-- Named classes (preferred) -->
<div class="bg-bg-surface text-text-primary">

<!-- Direct variable access -->
<div class="bg-[var(--color-bg-elevated)]">

<!-- Combined with standard Tailwind -->
<button class="bg-accent-primary hover:bg-accent-primary/90 text-white px-4 py-2 rounded-lg">
```

---

## HTMX Integration

### Base Layout Setup

HTMX 2.0.4 loaded via CDN in `layouts/base.astro`:

```html
<script src="https://unpkg.com/htmx.org@2.0.4" integrity="sha384-..." crossorigin="anonymous"></script>
```

### Fragment Pattern

**Page template:**

```html
<div
  id="gear-list"
  data-testid="gear-list"
  hx-get="/api/v1/html/gear/browse"
  hx-trigger="load"
  hx-swap="innerHTML"
>
  <div class="animate-pulse">Loading...</div>
</div>
```

**Fragment template (`fragments/gear/public_browse.html`):**

```jinja2
{% for item in items %}
<div
  data-testid="gear-card"
  data-item-id="{{ item.id }}"
  class="bg-bg-elevated rounded-lg p-4"
>
  <h3 class="text-text-primary font-semibold">{{ item.name }}</h3>
  <button
    data-testid="gear-add-btn"
    hx-post="/api/v1/html/library/gear"
    hx-vals='{"gear_id": "{{ item.id }}"}'
    hx-swap="none"
  >
    Add to Library
  </button>
</div>
{% endfor %}
```

**Backend endpoint:**

```python
@router.get("/api/v1/html/gear/browse", response_class=HTMLResponse)
async def browse_gear(request: Request, query: str = None):
    items = await gear_service.search(query=query)
    return templates.TemplateResponse(
        request=request,
        name="fragments/gear/public_browse.html",
        context={"items": items},
    )
```

### HTMX Loading Indicator

CSS defined in `global.css` for automatic show/hide:

```css
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline-block; }
.htmx-request.htmx-indicator { display: inline-block; }
```

### Error Handling

The base layout handles 401 responses by redirecting to login:

```javascript
document.body.addEventListener('htmx:responseError', (event) => {
  if (event.detail?.xhr?.status === 401) {
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
  }
});
```

---

## Alpine.js Integration

### Base Layout Setup

Alpine.js 3.14.8 loaded via CDN in `layouts/base.astro`:

```html
<script defer src="https://unpkg.com/alpinejs@3.14.8/dist/cdn.min.js"></script>
```

### Global Components

The base layout registers:

- **Confirm modal** (`window.showConfirmModal()`) — Promise-based, Alpine.js store for reactivity
- **Delete handler** (`window.handleDelete(url, itemName, targetSelector)`) — Confirm + fetch DELETE + toast
- **Toast notifications** (`window.showToast(message, type)`) — Auto-dismiss, deduplication

### Usage Patterns

**Tabs:**

```html
<div x-data="{ tab: 'browse' }">
  <nav>
    <button @click="tab = 'browse'" :class="tab === 'browse' && 'border-b-2'">Browse</button>
    <button @click="tab = 'library'" :class="tab === 'library' && 'border-b-2'">My Library</button>
  </nav>
  <div x-show="tab === 'browse'" x-transition>Browse content</div>
  <div x-show="tab === 'library'" x-transition>Library content</div>
</div>
```

**Toggles:**

```html
<div x-data="{ open: false }">
  <button @click="open = !open">Toggle</button>
  <div x-show="open" x-transition>Content</div>
</div>
```

---

## React Island (SignalChainBuilder)

Complex interactive UI for composing signal chains. React assets loaded ONLY on the builder page.

### Vite Build Configuration

**File:** `frontend/astro/vite.config.island.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: 'dist/islands',
    emptyOutDir: true,
    lib: {
      entry: 'src/islands/signal-chain-builder.tsx',
      name: 'SignalChainBuilder',
      formats: ['iife'],
      fileName: () => 'signal-chain-builder.js',
    },
  },
});
```

Built separately via `pnpm build:islands`. Output: `dist/islands/signal-chain-builder.js` (self-contained IIFE with React bundled).

### Page Integration

```jinja2
{% extends "layouts/base.html" %}

{% block content %}
<div id="signal-chain-builder" data-testid="signal-chain-builder"></div>
{% endblock %}

{% block scripts %}
<script src="/static/islands/signal-chain-builder.js"></script>
<script>
  window.SignalChainBuilder.mount('signal-chain-builder');
</script>
{% endblock %}
```

### Dependencies

React island uses: React 19, React Query, Radix UI, @dnd-kit, Lucide React, shadcn/ui patterns.

---

## Navigation Between Static and SSR

**Critical:** Astro's ClientRouter intercepts link clicks. SSR pages require full navigation.

### The Problem

ClientRouter fetches pages via AJAX. FastAPI/Jinja2 pages fail silently because Astro can't process them.

### The Solution

Add `data-astro-reload` to links targeting SSR pages:

```html
<!-- In static pages (Astro .astro files) -->
<a href="/gear" data-astro-reload>Gear</a>
<a href="/shootouts" data-astro-reload>Shootouts</a>
<a href="/library/my-gear" data-astro-reload>My Gear</a>

<!-- Links to other static pages - no attribute needed -->
<a href="/">Home</a>
<a href="/about">About</a>
```

### SSR Routes (require `data-astro-reload`)

- `/gear`, `/gear/*`
- `/shootouts`
- `/shootout/*`
- `/library/*`
- `/chain/*`
- `/di-tracks`, `/di-tracks/*`
- `/settings/*`

---

## Testability Requirements

All interactive elements MUST have `data-testid` attributes for Playwright testing.

### Required Attributes

```html
<!-- Page containers -->
<div data-testid="gear-library">

<!-- List containers -->
<div data-testid="shootout-list">

<!-- Items with entity identity -->
<div data-testid="item-card" data-item-id="{{ item.id }}">

<!-- Action buttons -->
<button data-testid="item-card-delete-btn">

<!-- Form inputs -->
<input data-testid="form-email-input">

<!-- HTMX containers -->
<div id="results" data-testid="results-container" hx-get="/api/v1/html/results">
```

### Naming Convention

| Pattern | Example |
|---------|---------|
| `{page}` | `gear-library`, `browse-page` |
| `{component}` | `shootout-card`, `chain-item` |
| `{component}-{element}` | `shootout-card-title` |
| `{component}-{action}-btn` | `shootout-card-delete-btn` |
| `{component}-{field}-input` | `login-email-input` |

---

## Development Workflow

### Initial Setup

Services start automatically with `just up-d`. The astro container runs chokidar on startup.

### Build and Run

```bash
just build-astro        # Explicit build (runs in Docker)
just up-d               # Start all services (astro auto-rebuilds)
curl http://localhost:9000
```

### Watch Mode

```bash
# Astro container auto-rebuilds on source changes (chokidar)
# View rebuild logs:
just watch-astro

# Edit src/ files -> chokidar detects -> pnpm build runs -> dist/ updated
# nginx serves updated files on next request (bind mount)
```

### CI Verification

```bash
just verify-astro-sync  # Builds and fails if dist/ has uncommitted changes
```

PRs fail CI if `dist/` is not committed with matching `src/` changes.

---

## References

- [[GTS-Technical-Architecture]] - Architecture overview
- `frontend/astro/` - Source code
- `.claude/rules/frontend-standards.md` - Development rules


### GTS-Remotion-Architecture

# Remotion Integration — Guitar Tone Shootout (GTS)

## Decision Summary

Replace the existing empty video stub (`libs/audio/src/audio/video/`) with a dedicated video bounded context powered by Remotion. Clean start — the video BC owns all server-side video rendering. Frontend hero animation and how-to videos are separate Astro/Remotion Player concerns.

---

## Requirements

| Requirement | Detail |
|-------------|--------|
| Signal chain images | JPEGs on background. Crop/resize to normalise. Placeholder images for missing gear. |
| Audio | Per-segment audio files, variable length. Hard cuts at segment boundaries. |
| Video output | 1920x1080, 30fps, H.264, AAC 256-320kbps (YouTube optimised) |
| Transitions | 3-frame (100ms) slide transition centred on audio cut point (1.5 frames either side). |
| Site integration | Remotion Player as async React island in Astro for hero animation + how-to videos (frontend concern, not video BC). |
| Scope | Clean start. Remove existing video stub from audio BC. |

---

## Bounded Context Architecture

### Video BC — Ownership

The video BC is a **new bounded context** at `libs/video/` and a **uv workspace member** with its own:

- `pyproject.toml` (Python dependencies: FastAPI, Pillow for image processing)
- `package.json` (Node.js dependencies: Remotion, React, Tailwind CSS)
- `Dockerfile` (Node.js + Chromium + Python via uv)
- Docker container on `jobs` profile
- Remotion compositions for **server-side rendering only** (shootout videos)

```
gts/
├── pyproject.toml              # uv workspace root
├── libs/
│   ├── video/                  # ← new video BC
│   │   ├── pyproject.toml      # uv workspace member
│   │   ├── package.json        # npm package
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   ├── video/          # Python package
│   │   │   │   ├── api.py      # FastAPI render endpoint
│   │   │   │   ├── image_prep.py
│   │   │   │   └── props.py    # JSON props generation
│   │   │   └── remotion/       # Remotion project
│   │   │       ├── src/
│   │   │       │   ├── Root.tsx
│   │   │       │   ├── ShootoutVideo.tsx
│   │   │       │   └── components/
│   │   │       │       ├── SignalChainSegment.tsx
│   │   │       │       ├── SlideTransition.tsx
│   │   │       │       ├── MetadataOverlay.tsx
│   │   │       │       └── GearBlock.tsx
│   │   │       ├── remotion.config.ts
│   │   │       └── tsconfig.json
│   │   └── tests/
│   ├── core/                   # domain (zero framework deps)
│   └── audio/                  # audio BC
├── frontend/
│   └── astro/                  # Astro site
│       └── src/
│           ├── remotion/       # frontend-only compositions (hero, how-to)
│           │   ├── Root.tsx
│           │   ├── HeroAnimation.tsx
│           │   └── HowToVideo.tsx
│           └── components/
│               └── HeroVideo.tsx   # Remotion Player island
└── docker-compose.yml
```

**Key boundary:** `libs/video/` handles server-side rendering (shootout videos via Docker). `frontend/astro/src/remotion/` handles client-side compositions (hero animation, how-to videos via Remotion Player). No code sharing between them.

### Video BC `package.json`

```json
{
  "name": "@gts/video",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "npx remotion studio src/remotion/src/Root.tsx",
    "render": "npx remotion render src/remotion/src/Root.tsx",
    "test": "vitest"
  },
  "dependencies": {
    "remotion": "^4.0",
    "@remotion/renderer": "^4.0",
    "react": "^19",
    "react-dom": "^19"
  },
  "devDependencies": {
    "@remotion/cli": "^4.0",
    "tailwindcss": "^4",
    "typescript": "^5",
    "vitest": "^3"
  }
}
```

Note: No `@remotion/player` — that's a frontend dependency only.

### Dependency Rules

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `video` | core | audio, sources, apps |

Same pattern as `audio`. Enforced via import-linter contract.

---

## Consumer Contracts

### 1. TaskIQ Worker → Video BC (HTTP API)

The video BC container runs a FastAPI service. The TaskIQ worker sends render requests over the Docker network.

```
POST /render
Content-Type: application/json

{
  "composition_id": "GuitarToneShootout",
  "props": { ... },          // full Remotion input props
  "output_format": "mp4",
  "codec": "h264",
  "audio_bitrate": "320k"
}

→ 202 Accepted
{
  "job_id": "render-xyz",
  "status": "queued"
}
```

```
GET /render/{job_id}

→ 200 OK
{
  "job_id": "render-xyz",
  "status": "complete",
  "output_path": "/app/processed/videos/abc-123.mp4",
  "duration_seconds": 45.2,
  "render_time_seconds": 12.8
}
```

The render endpoint internally calls:

```python
# video/api.py
import asyncio, json
from pathlib import Path

async def render_video(composition_id: str, props: dict, output_path: str) -> str:
    props_file = Path(f"/tmp/{props.get('title', 'render')}.json")
    props_file.write_text(json.dumps(props))

    proc = await asyncio.create_subprocess_exec(
        "npx", "remotion", "render",
        "src/remotion/src/Root.tsx",
        composition_id,
        "--props", str(props_file),
        "--output", output_path,
        "--codec", "h264",
        "--audio-bitrate", "320k",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

    if proc.returncode != 0:
        raise RenderError(stderr.decode())

    return output_path
```

### 2. Frontend — Remotion Player (Astro Island)

Frontend compositions live in `frontend/astro/src/remotion/` — **not imported from video BC**.

```tsx
// frontend/astro/src/components/HeroVideo.tsx
import { Player } from '@remotion/player';
import { HeroAnimation } from '../remotion/HeroAnimation';

export default function HeroVideo() {
  return (
    <Player
      component={HeroAnimation}
      durationInFrames={240}  // 8s at 30fps
      fps={30}
      compositionWidth={1920}
      compositionHeight={600}
      style={{ width: '100%' }}
      autoPlay
      loop
      controls={false}
    />
  );
}
```

Mounted in Astro pages: `<HeroVideo client:idle />`

### 3. Remotion Studio (Dev Iteration)

**Server-side compositions:**
```bash
cd libs/video
npm run dev    # opens Remotion Studio at localhost:3000
```

**Frontend compositions:**
```bash
cd frontend/astro
pnpm remotion:dev    # opens Remotion Studio at localhost:3001
```

Remotion Studio provides:
- Frame-by-frame scrubbing
- Hot reload on component changes
- Mock props for testing without DB/audio
- Visual timeline of all sequences

---

## Component Design

### Core Components (Server-Side — `libs/video/`)

```tsx
// GearBlock.tsx — single gear item in the signal chain
type GearBlockProps = {
  name: string;
  imageUrl: string;       // normalised JPEG path
  type: 'di' | 'pedal' | 'amp' | 'cab' | 'mic';
  isPlaceholder: boolean;
  enterAtFrame: number;   // staggered entrance
};

// SignalChainSegment.tsx — full chain for one segment
type SignalChainSegmentProps = {
  blocks: GearBlockProps[];
  metadata: SegmentMetadata;
  durationFrames: number;
};

// SlideTransition.tsx — 3-frame slide between segments
type SlideTransitionProps = {
  transitionFrames: number;  // 3 at 30fps = 100ms
  direction: 'left' | 'right';
  children: React.ReactNode;
};

// MetadataOverlay.tsx — segment info text
type MetadataOverlayProps = {
  title: string;
  bpm: number;
  genre: string;
  notes?: string;
};
```

### Composition: ShootoutVideo

```tsx
// ShootoutVideo.tsx
import { Sequence, Audio, useVideoConfig } from 'remotion';
import { SignalChainSegment } from './components/SignalChainSegment';
import { SlideTransition } from './components/SlideTransition';

type Segment = {
  id: string;
  durationSeconds: number;
  audioFile: string;
  metadata: SegmentMetadata;
  signalChain: GearBlockProps[];
};

type ShootoutProps = {
  segments: Segment[];
  title: string;
};

const TRANSITION_FRAMES = 3; // 100ms at 30fps

export const ShootoutVideo: React.FC<ShootoutProps> = ({ segments, title }) => {
  const { fps } = useVideoConfig();

  let currentFrame = 0;
  return (
    <>
      {segments.map((segment, i) => {
        const segmentFrames = Math.ceil(segment.durationSeconds * fps);
        const from = i === 0 ? 0 : currentFrame - Math.floor(TRANSITION_FRAMES / 2);
        const duration = segmentFrames + (i === 0 ? 0 : Math.floor(TRANSITION_FRAMES / 2));

        const el = (
          <Sequence key={segment.id} from={from} durationInFrames={duration} name={segment.metadata.title}>
            {i > 0 && <SlideTransition transitionFrames={TRANSITION_FRAMES} direction="left">
              <SignalChainSegment
                blocks={segment.signalChain}
                metadata={segment.metadata}
                durationFrames={segmentFrames}
              />
            </SlideTransition>}
            {i === 0 && (
              <SignalChainSegment
                blocks={segment.signalChain}
                metadata={segment.metadata}
                durationFrames={segmentFrames}
              />
            )}
            <Audio src={segment.audioFile} />
          </Sequence>
        );

        currentFrame += segmentFrames;
        return el;
      })}
    </>
  );
};
```

### Dynamic Duration via `calculateMetadata`

```tsx
// Root.tsx
import { Composition } from 'remotion';
import { ShootoutVideo } from './ShootoutVideo';

export const RemotionRoot = () => (
  <Composition
    id="GuitarToneShootout"
    component={ShootoutVideo}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={{ segments: [], title: '' }}
    calculateMetadata={async ({ props }) => {
      const totalSeconds = props.segments.reduce(
        (sum, s) => sum + s.durationSeconds, 0
      );
      return {
        durationInFrames: Math.ceil(totalSeconds * 30),
        props,
      };
    }}
  />
);
```

---

## JSON Props Schema (Python → Remotion)

```json
{
  "title": "Clean Tone Shootout: Fender vs Marshall",
  "segments": [
    {
      "id": "seg-1",
      "durationSeconds": 12.5,
      "audioFile": "static/audio/seg-1.wav",
      "metadata": {
        "title": "Fender Twin Reverb - Clean",
        "bpm": 120,
        "genre": "Blues",
        "notes": "Bridge pickup, volume 6"
      },
      "signalChain": [
        {
          "name": "Strat DI",
          "imageUrl": "static/gear/strat-di-normalized.jpg",
          "type": "di",
          "isPlaceholder": false,
          "enterAtFrame": 0
        },
        {
          "name": "TS808",
          "imageUrl": "static/gear/ts808-normalized.jpg",
          "type": "pedal",
          "isPlaceholder": false,
          "enterAtFrame": 15
        },
        {
          "name": "SM57",
          "imageUrl": "static/gear/placeholder-mic.jpg",
          "type": "mic",
          "isPlaceholder": true,
          "enterAtFrame": 45
        }
      ]
    }
  ]
}
```

---

## Image Preprocessing (Python — Video BC)

```python
# video/image_prep.py
from pathlib import Path
from PIL import Image, ImageDraw

TARGET_SIZE = (240, 240)
BACKGROUND = (26, 26, 46)

def normalize_gear_image(image_path: str | None, output_path: str) -> str:
    if image_path is None or not Path(image_path).exists():
        return _generate_placeholder(output_path)

    img = Image.open(image_path).convert("RGB")
    img.thumbnail(TARGET_SIZE, Image.LANCZOS)

    canvas = Image.new("RGB", TARGET_SIZE, BACKGROUND)
    offset = ((TARGET_SIZE[0] - img.width) // 2, (TARGET_SIZE[1] - img.height) // 2)
    canvas.paste(img, offset)
    canvas.save(output_path, "JPEG", quality=90)
    return output_path

def _generate_placeholder(output_path: str) -> str:
    canvas = Image.new("RGB", TARGET_SIZE, (40, 40, 60))
    draw = ImageDraw.Draw(canvas)
    draw.text((60, 110), "No Image", fill=(120, 120, 140))
    canvas.save(output_path, "JPEG", quality=90)
    return output_path
```

---

## Dev Workflow — Iterate Outside the Pipeline

### Component Development (fast loop)

```bash
cd libs/video
npm run dev                    # Remotion Studio on :3000
```

- Edit `SignalChainSegment.tsx` → hot reloads instantly
- Use mock props in `Root.tsx` `defaultProps` — no DB, no audio needed
- Scrub timeline, inspect per-frame rendering
- Test transitions, animations, text overlays visually

### Component Testing (automated)

```bash
cd libs/video
npm test                       # vitest
```

```tsx
// tests/SignalChainSegment.test.tsx
import { renderFrames } from '@remotion/renderer';

test('renders correct number of gear blocks', async () => {
  // Remotion supports rendering individual frames for snapshot testing
});
```

### Full Pipeline Test (integration)

```bash
just up-d  # with jobs profile
curl -X POST http://localhost:8001/render \
  -H 'Content-Type: application/json' \
  -d @test-props.json
```

---

## Video BC Dockerfile

```dockerfile
FROM node:20-slim AS node-base

# Install Chromium for Remotion rendering + Python
RUN apt-get update && apt-get install -y \
    chromium \
    fonts-liberation \
    curl \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for Python
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Node dependencies (cached layer)
COPY libs/video/package.json libs/video/package-lock.json ./
RUN npm ci

# Python dependencies (cached layer)
COPY pyproject.toml uv.lock ./
COPY libs/core/pyproject.toml libs/core/
COPY libs/video/pyproject.toml libs/video/
RUN mkdir -p libs/core/src/core libs/video/src/video
RUN uv sync --frozen --package gts-video

# Application code
COPY libs/core/ libs/core/
COPY libs/video/ libs/video/

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "video.api:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## What Gets Removed (Clean Start)

**Delete from existing codebase:**

1. `libs/audio/src/audio/video/` — empty stub directory
2. `moviepy` dependency from `libs/audio/pyproject.toml`
3. `VideoComposer` protocol from `libs/core/src/core/ports/video_composer.py`

**Replace with:**

1. Video BC (`libs/video/`)
2. Generic `VideoRenderer` port in `libs/core/src/core/ports/`
3. `CompositionSpec` and `RenderStatus` value objects in core
4. Image normalisation (`video/image_prep.py`)
5. Remotion compositions and React components
6. JSON props generation (`video/props.py`)
7. FastAPI render endpoint (`video/api.py`)

---

## Implementation Order (GitHub Issues)

| Phase | Issue | Description | Depends on |
|-------|-------|-------------|------------|
| 1 | #71 | Core domain — generic `VideoRenderer` port + value objects | — |
| 2 | #72 | `libs/video/` scaffold + audio cleanup (remove moviepy, video stub) | #71 |
| 3 | #73 | Docker container for video BC on `jobs` profile | #72 |
| 4 | #74 | Video BC Python implementation (API + image prep + props) | #73 |
| 5 | #75 | Remotion components (ShootoutVideo, GearBlock, etc.) | #74 |
| 6a | #83 | Alembic migration — Shootout video fields | #71 |
| 6b | #76 | Worker integration — HTTP client + render job | #75, #83 |
| 7 | #77 | Frontend — Remotion Player for hero animation + how-to (Astro) | #72 |
| 8 | #78 | Tooling — `just` commands + quality gate updates | #72 |
| 9 | #80 | worktree.py — video service port allocation + override template | #73 |
| 10 | #81 | Documentation — DEVELOPMENT.md, AGENTS.md, wiki updates | #74 |
| 11 | #82 | .claude skills/agents — new `gts-video` skill + updates | #74 |
| 12 | #84 | Integration test — end-to-end render pipeline | #76 |

---

## Licensing

Remotion free license applies — individual / company ≤3 people. No cost for GTS at current scale.


---

## Codebase Structure

The following files were selectively loaded from `.planning/codebase/`:


### ENDPOINTS

# API Endpoints

*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*

**104 endpoints extracted** from `apps/webapp/src/webapp/api`

### `apps/webapp/src/webapp/api/pages.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/gear` | `gear_browse_page` |  |  |
| GET | `/gear/{slug}` | `gear_detail_page` |  |  |
| GET | `/fragments/gear/list` | `gear_list_fragment` |  |  |
| GET | `/shootouts` | `shootouts_page` | None |  |
| GET | `/di-tracks` | `di_tracks_browse_page` |  |  |
| GET | `/sitemap.xml` | `sitemap_xml` |  |  |
| GET | `/library/my-gear` | `library_my_gear_page` |  |  |
| GET | `/library/chains` | `library_chains_page` |  |  |
| GET | `/fragments/chains/list` | `chain_list_fragment` |  |  |
| DELETE | `/fragments/chains/{chain_id}` | `chain_delete_fragment` |  |  |
| POST | `/fragments/chains/{chain_id}/duplicate` | `chain_duplicate_fragment` |  |  |
| GET | `/library/chains/build` | `chain_builder_page` |  |  |
| GET | `/library/shootouts` | `library_shootouts_page` |  |  |
| GET | `/shootout/create` | `shootout_create_page` |  |  |
| GET | `/shootout/{shootout_id}` | `shootout_detail_page` |  |  |
| GET | `/fragments/shootouts/list` | `shootout_list_fragment` |  |  |
| DELETE | `/fragments/shootouts/{shootout_id}` | `shootout_delete_fragment` |  |  |
| GET | `/chain/{chain_id}` | `chain_detail_page` |  |  |
| GET | `/library/di-tracks` | `library_di_tracks_page` |  |  |
| GET | `/settings/account` | `settings_account_page` |  |  |

### `apps/webapp/src/webapp/api/v1/auth.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/auth/login/t3k` | `login_t3k` |  |  |
| GET | `/api/v1/auth/login/{provider}` | `login_provider` |  |  |
| GET | `/api/v1/auth/callback` | `callback` |  |  |
| GET | `/api/v1/auth/me` | `get_me` |  |  |
| POST | `/api/v1/auth/logout` | `logout_post` |  |  |
| GET | `/api/v1/auth/logout` | `logout_get` |  |  |
| GET | `/api/v1/auth/status` | `auth_status` |  |  |
| POST | `/api/v1/auth/save-session` | `save_session` |  |  |
| POST | `/api/v1/auth/restore-session` | `restore_session_post` |  |  |
| GET | `/api/v1/auth/restore-session` | `restore_session_get` | None |  |
| DELETE | `/api/v1/auth/unlink/{provider}` | `unlink_provider` |  |  |

### `apps/webapp/src/webapp/api/v1/block_types.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/block-types` | `list_block_types` | list[BlockTypeResponse] |  |

### `apps/webapp/src/webapp/api/v1/di_tracks.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| POST | `/api/v1/di-tracks` | `upload_di_track` | DITrackResponse | status.HTTP_201_CREATED |
| GET | `/api/v1/di-tracks` | `list_di_tracks` | list[DITrackResponse] |  |
| GET | `/api/v1/di-tracks/{track_id}` | `get_di_track` | DITrackResponse |  |
| DELETE | `/api/v1/di-tracks/{track_id}` | `delete_di_track` |  | status.HTTP_204_NO_CONTENT |
| GET | `/api/v1/di-tracks/{track_id}/stream` | `stream_di_track` |  |  |

### `apps/webapp/src/webapp/api/v1/files.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/files/{signature}` | `serve_file` | None |  |

### `apps/webapp/src/webapp/api/v1/gear.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/gear/` | `list_gear` | GearListResponse |  |
| GET | `/api/v1/gear/{gear_id}` | `get_gear` | GearResponse |  |

### `apps/webapp/src/webapp/api/v1/health.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/health` | `liveness` |  |  |
| GET | `/health/ready` | `readiness` |  |  |

### `apps/webapp/src/webapp/api/v1/html.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/html/` | `html_namespace_root` |  |  |
| GET | `/api/v1/html/gear/list` | `gear_list_fragment` |  |  |
| GET | `/api/v1/html/library/my-gear/list` | `library_my_gear_list_fragment` |  |  |
| GET | `/api/v1/html/library/chains/list` | `library_chains_list_fragment` |  |  |
| GET | `/api/v1/html/library/shootouts/list` | `library_shootouts_list_fragment` |  |  |
| GET | `/api/v1/html/my-gear/results` | `my_gear_results_fragment` |  |  |
| GET | `/api/v1/html/di-tracks/results` | `di_tracks_results_fragment` |  |  |
| GET | `/api/v1/html/library/tracks` | `library_tracks_fragment` |  |  |
| POST | `/api/v1/html/library/tracks/{track_id}/toggle-public` | `library_track_toggle_public` |  |  |
| POST | `/api/v1/html/library/tracks/{track_id}/save` | `library_track_save` |  |  |
| GET | `/api/v1/html/library/chains` | `library_chains_fragment` |  |  |
| GET | `/api/v1/html/library/shootouts` | `library_shootouts_fragment` |  |  |
| GET | `/api/v1/html/library/groups` | `library_groups_fragment` |  |  |
| GET | `/api/v1/html/shootout-create/group-chains/{group_id}` | `shootout_create_group_chains_fragment` |  |  |
| GET | `/api/v1/html/shootout-create/chains` | `shootout_create_chains_fragment` |  |  |
| GET | `/api/v1/html/shootout-create/ditracks` | `shootout_create_ditracks_fragment` |  |  |
| POST | `/api/v1/html/shootout-create` | `shootout_create_submit` |  |  |
| GET | `/api/v1/html/shootouts/sections` | `shootouts_sections_fragment` |  |  |
| GET | `/api/v1/html/shootouts/{shootout_id}/comments` | `shootout_comments_fragment` |  |  |
| POST | `/api/v1/html/gear/model/{model_id}/toggle` | `gear_model_toggle` |  |  |
| POST | `/api/v1/html/gear/models/bulk-toggle` | `gear_models_bulk_toggle` |  |  |

### `apps/webapp/src/webapp/api/v1/irs.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| POST | `/api/v1/irs/upload` | `upload_ir` | IRUploadResponse | status.HTTP_201_CREATED |

### `apps/webapp/src/webapp/api/v1/jobs.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/jobs/` | `list_jobs` | list[JobResponse] |  |
| GET | `/api/v1/jobs/{job_id}` | `get_job` | JobResponse |  |

### `apps/webapp/src/webapp/api/v1/library.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/library/gear` | `list_user_gear` | list[UserGearResponse] |  |
| POST | `/api/v1/library/gear` | `add_gear_to_library` | UserGearResponse | status.HTTP_201_CREATED |
| DELETE | `/api/v1/library/gear/{user_gear_id}` | `remove_gear_from_library` |  | status.HTTP_204_NO_CONTENT |
| POST | `/api/v1/library/gear/{gear_model_id}/toggle` | `toggle_gear_in_library` | ToggleGearResponse |  |

### `apps/webapp/src/webapp/api/v1/notifications.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/notifications` | `list_notifications` | list[NotificationResponse] |  |
| PUT | `/api/v1/notifications/{notification_id}/read` | `mark_notification_read` | MarkReadResponse |  |
| PUT | `/api/v1/notifications/read-all` | `mark_all_notifications_read` | MarkAllReadResponse |  |

### `apps/webapp/src/webapp/api/v1/presets.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/presets` | `list_presets` | list[PresetResponse] |  |
| POST | `/api/v1/presets` | `create_preset` | PresetResponse | status.HTTP_201_CREATED |
| GET | `/api/v1/presets/{preset_id}` | `get_preset` | PresetResponse |  |
| PUT | `/api/v1/presets/{preset_id}` | `update_preset` | PresetResponse |  |
| DELETE | `/api/v1/presets/{preset_id}` | `delete_preset` |  | status.HTTP_204_NO_CONTENT |

### `apps/webapp/src/webapp/api/v1/shootouts.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/shootouts/` | `list_shootouts` | list[ShootoutResponse] |  |
| POST | `/api/v1/shootouts/` | `create_shootout` | ShootoutResponse | status.HTTP_201_CREATED |
| GET | `/api/v1/shootouts/{shootout_id}` | `get_shootout` | ShootoutResponse |  |
| DELETE | `/api/v1/shootouts/{shootout_id}` | `delete_shootout` |  | status.HTTP_204_NO_CONTENT |
| POST | `/api/v1/shootouts/{shootout_id}/process` | `process_shootout` |  | status.HTTP_202_ACCEPTED |
| POST | `/api/v1/shootouts/{shootout_id}/comments` | `create_comment` | CommentResponse | status.HTTP_201_CREATED |
| GET | `/api/v1/shootouts/{shootout_id}/comments` | `list_comments` |  |  |
| DELETE | `/api/v1/shootouts/{shootout_id}/comments/{comment_id}` | `delete_comment` |  | status.HTTP_204_NO_CONTENT |

### `apps/webapp/src/webapp/api/v1/signal_chain_groups.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/signal-chain-groups/` | `list_signal_chain_groups` | list[SignalChainGroupResponse] |  |
| POST | `/api/v1/signal-chain-groups/` | `create_signal_chain_group` | SignalChainGroupResponse | status.HTTP_201_CREATED |
| GET | `/api/v1/signal-chain-groups/{group_id}` | `get_signal_chain_group` | SignalChainGroupResponse |  |
| PUT | `/api/v1/signal-chain-groups/{group_id}` | `update_signal_chain_group` | SignalChainGroupResponse |  |
| POST | `/api/v1/signal-chain-groups/{group_id}/generate` | `generate_permutations` | list[str] |  |
| DELETE | `/api/v1/signal-chain-groups/{group_id}` | `delete_signal_chain_group` |  | status.HTTP_204_NO_CONTENT |

### `apps/webapp/src/webapp/api/v1/signal_chains.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/signal-chains/` | `list_signal_chains` | list[SignalChainResponse] |  |
| POST | `/api/v1/signal-chains/` | `create_signal_chain` | SignalChainResponse | status.HTTP_201_CREATED |
| PUT | `/api/v1/signal-chains/{chain_id}` | `update_signal_chain` | SignalChainResponse |  |
| DELETE | `/api/v1/signal-chains/{chain_id}` | `delete_signal_chain` |  | status.HTTP_204_NO_CONTENT |

### `apps/webapp/src/webapp/api/v1/tags.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/tags` | `list_tags` | list[TagResponse] |  |
| POST | `/api/v1/tags` | `create_tag` | TagResponse | status.HTTP_201_CREATED |
| DELETE | `/api/v1/tags/{tag_id}` | `delete_tag` |  | status.HTTP_204_NO_CONTENT |

### `apps/webapp/src/webapp/api/v1/test.py`

| Method | Path | Function | Response Model | Status |
|--------|------|----------|----------------|--------|
| GET | `/api/v1/test/error/404` | `trigger_404` |  |  |
| GET | `/api/v1/test/error/400` | `trigger_400` |  |  |
| GET | `/api/v1/test/error/409` | `trigger_409` |  |  |
| GET | `/api/v1/test/error/422` | `trigger_422` |  |  |
| GET | `/api/v1/test/error/500` | `trigger_500` |  |  |


### IMPORTS

# Internal Import Graph

*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*

**7 internal packages** scanned from `libs, apps, sources`

Internal packages: audio, core, scheduler, source_t3k, video, webapp, worker

## Dependencies

- **audio** -> core
- **core** -> (none)
- **scheduler** -> core, source_t3k, webapp, worker
- **source_t3k** -> core
- **video** -> core
- **webapp** -> audio, core
- **worker** -> audio, core, source_t3k, webapp


### SCHEMA

# ORM Schema

*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*

**23 models extracted** from `apps/webapp/src/webapp/adapters/persistence/models/`

### BlockType (`block_types`)
*File: block_type.py*

**Columns:**

| Column | Type |
|--------|------|
| `name` | `Mapped[str]` |
| `category` | `Mapped[BlockCategory]` |
| `description` | `Mapped[str | None]` |
| `default_params` | `Mapped[dict[str, Any]]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `blocks` | SignalChainBlock | block_type | raise |

### GearTag (`tags`)
*File: gear.py*

**Columns:**

| Column | Type |
|--------|------|
| `name` | `Mapped[str]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `gear_items` | Gear | tags | raise |

### GearMake (`gear_makes`)
*File: gear.py*

**Columns:**

| Column | Type |
|--------|------|
| `name` | `Mapped[str]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `gear_items` | Gear | make | raise |

### Gear (`gear`)
*File: gear.py*

**Columns:**

| Column | Type |
|--------|------|
| `name` | `Mapped[str]` |
| `slug` | `Mapped[str]` |
| `gear_type` | `Mapped[GearType]` |
| `platform` | `Mapped[str | None]` |
| `description` | `Mapped[str | None]` |
| `manufacturer` | `Mapped[str | None]` |
| `make_id` | `Mapped[uuid.UUID | None]` |
| `thumbnail_url` | `Mapped[str | None]` |
| `is_public` | `Mapped[bool]` |
| `source_id` | `Mapped[uuid.UUID | None]` |
| `license_text` | `Mapped[str | None]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `make` | GearMake | gear_items | raise |
| `source` | GearSource | gear | raise |
| `models` | GearModel | gear | raise |
| `tags` | GearTag | gear_items | raise |

### GearModel (`gear_models`)
*File: gear_model.py*

**Columns:**

| Column | Type |
|--------|------|
| `id` | `Mapped[uuid.UUID]` |
| `gear_id` | `Mapped[uuid.UUID]` |
| `platform` | `Mapped[Platform]` |
| `size` | `Mapped[ModelSize]` |
| `file_path` | `Mapped[str | None]` |
| `download_url` | `Mapped[str | None]` |
| `download_status` | `Mapped[DownloadStatus]` |
| `file_hash` | `Mapped[str | None]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `gear` | Gear | models | raise |
| `user_gear` | UserGear | gear_model | raise |

### GearSource (`gear_sources`)
*File: gear_source.py*

**Columns:**

| Column | Type |
|--------|------|
| `id` | `Mapped[uuid.UUID]` |
| `created_at` | `Mapped[datetime]` |
| `updated_at` | `Mapped[datetime]` |
| `source_name` | `Mapped[str]` |
| `source_record_id` | `Mapped[str]` |
| `source_updated_at` | `Mapped[datetime]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `gear` | Gear | source | raise |

### Job (`jobs`)
*File: job.py*

**Columns:**

| Column | Type |
|--------|------|
| `user_id` | `Mapped[uuid.UUID | None]` |
| `job_type` | `Mapped[JobType]` |
| `parent_job_id` | `Mapped[uuid.UUID | None]` |
| `depends_on` | `Mapped[list[str]]` |
| `status` | `Mapped[JobStatus]` |
| `progress` | `Mapped[int]` |
| `message` | `Mapped[str | None]` |
| `started_at` | `Mapped[datetime | None]` |
| `completed_at` | `Mapped[datetime | None]` |
| `last_heartbeat` | `Mapped[datetime | None]` |
| `attempt` | `Mapped[int]` |
| `max_attempts` | `Mapped[int]` |
| `next_retry_at` | `Mapped[datetime | None]` |
| `result_path` | `Mapped[str | None]` |
| `error` | `Mapped[str | None]` |
| `task_id` | `Mapped[str | None]` |
| `entity_id` | `Mapped[uuid.UUID | None]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | jobs | raise |

### AuditLog (`audit_logs`)
*File: job.py*

**Columns:**

| Column | Type |
|--------|------|
| `id` | `Mapped[uuid.UUID]` |
| `timestamp` | `Mapped[datetime]` |
| `user_id` | `Mapped[uuid.UUID | None]` |
| `ip_address` | `Mapped[str | None]` |
| `user_agent` | `Mapped[str | None]` |
| `action` | `Mapped[str]` |
| `resource_type` | `Mapped[str]` |
| `resource_id` | `Mapped[uuid.UUID | None]` |
| `changes` | `Mapped[dict[str, Any] | None]` |
| `extra_data` | `Mapped[dict[str, Any] | None]` |
| `request_id` | `Mapped[str | None]` |
| `trace_id` | `Mapped[str | None]` |

### UserNotification (`user_notifications`)
*File: notification.py*

**Columns:**

| Column | Type |
|--------|------|
| `user_id` | `Mapped[UUID]` |
| `type` | `Mapped[str]` |
| `title` | `Mapped[str]` |
| `message` | `Mapped[str]` |
| `read_at` | `Mapped[datetime | None]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | notifications | raise |

### Preset (`presets`)
*File: preset.py*

**Columns:**

| Column | Type |
|--------|------|
| `signal_chain_block_id` | `Mapped[uuid.UUID]` |
| `name` | `Mapped[str]` |
| `description` | `Mapped[str | None]` |
| `params` | `Mapped[dict[str, Any]]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `signal_chain_block` | SignalChainBlock | presets | raise |

### DITrack (`di_tracks`)
*File: shootout.py*

**Columns:**

| Column | Type |
|--------|------|
| `user_id` | `Mapped[uuid.UUID]` |
| `name` | `Mapped[str]` |
| `file_path` | `Mapped[str]` |
| `original_filename` | `Mapped[str]` |
| `duration_seconds` | `Mapped[float]` |
| `sample_rate` | `Mapped[int]` |
| `channels` | `Mapped[int | None]` |
| `waveform` | `Mapped[Any]` |
| `description` | `Mapped[str | None]` |
| `guitar` | `Mapped[str | None]` |
| `pickup` | `Mapped[str | None]` |
| `tuning` | `Mapped[str | None]` |
| `checksum` | `Mapped[Any]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | di_tracks | raise |
| `shootouts` | Shootout | di_track | raise |

### Shootout (`shootouts`)
*File: shootout.py*

**Columns:**

| Column | Type |
|--------|------|
| `user_id` | `Mapped[uuid.UUID]` |
| `di_track_id` | `Mapped[uuid.UUID | None]` |
| `name` | `Mapped[str]` |
| `description` | `Mapped[str | None]` |
| `status` | `Mapped[ShootoutStatus]` |
| `video_path` | `Mapped[str | None]` |
| `video_status` | `Mapped[str | None]` |
| `video_job_id` | `Mapped[str | None]` |
| `output_path` | `Mapped[str | None]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | shootouts | raise |
| `di_track` | DITrack | shootouts | raise |
| `chains` | ShootoutChain | shootout | raise |
| `comments` | ShootoutComment | shootout | raise |

### ShootoutChain (`shootout_chains`)
*File: shootout.py*

**Columns:**

| Column | Type |
|--------|------|
| `shootout_id` | `Mapped[uuid.UUID]` |
| `signal_chain_id` | `Mapped[uuid.UUID]` |
| `position` | `Mapped[int]` |
| `label` | `Mapped[str]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `shootout` | Shootout | chains | raise |
| `signal_chain` | SignalChain |  | raise |
| `segments` | AudioSegment | shootout_chain | raise |

### AudioSegment (`audio_segments`)
*File: shootout.py*

**Columns:**

| Column | Type |
|--------|------|
| `shootout_chain_id` | `Mapped[uuid.UUID]` |
| `file_path` | `Mapped[str]` |
| `duration_seconds` | `Mapped[float]` |
| `integrated_lufs` | `Mapped[float]` |
| `peak_dbfs` | `Mapped[float]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `shootout_chain` | ShootoutChain | segments | raise |

### ShootoutComment (`shootout_comments`)
*File: shootout_comment.py*

**Columns:**

| Column | Type |
|--------|------|
| `shootout_id` | `Mapped[uuid.UUID]` |
| `user_id` | `Mapped[uuid.UUID]` |
| `content` | `Mapped[str]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `shootout` | Shootout | comments | raise |
| `user` | User |  | raise |

### SignalChain (`signal_chains`)
*File: signal_chain.py*

**Columns:**

| Column | Type |
|--------|------|
| `user_id` | `Mapped[uuid.UUID]` |
| `name` | `Mapped[str]` |
| `description` | `Mapped[str | None]` |
| `platform` | `Mapped[Platform]` |
| `group_id` | `Mapped[uuid.UUID | None]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | signal_chains | raise |
| `blocks` | SignalChainBlock | signal_chain | raise |
| `group` | SignalChainGroup |  | raise |

### SignalChainBlock (`signal_chain_blocks`)
*File: signal_chain.py*

**Columns:**

| Column | Type |
|--------|------|
| `signal_chain_id` | `Mapped[uuid.UUID]` |
| `position` | `Mapped[int]` |
| `user_gear_id` | `Mapped[uuid.UUID | None]` |
| `gear_type` | `Mapped[GearType | None]` |
| `block_type_id` | `Mapped[uuid.UUID | None]` |
| `params` | `Mapped[dict[str, Any]]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `signal_chain` | SignalChain | blocks | raise |
| `block_type` | BlockType | blocks | raise |
| `presets` | Preset | signal_chain_block | raise |

### SignalChainGroup (`signal_chain_groups`)
*File: signal_chain.py*

**Columns:**

| Column | Type |
|--------|------|
| `user_id` | `Mapped[uuid.UUID]` |
| `name` | `Mapped[str]` |
| `description` | `Mapped[str | None]` |
| `base_chain_id` | `Mapped[uuid.UUID | None]` |
| `slot_positions` | `Mapped[list[int]]` |
| `gear_options` | `Mapped[dict[int, list[str]]]` |
| `include_null` | `Mapped[bool]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | signal_chain_groups | raise |
| `base_chain` | SignalChain |  | raise |

### Tag (`user_tags`)
*File: tag.py*

**Columns:**

| Column | Type |
|--------|------|
| `name` | `Mapped[str]` |
| `user_id` | `Mapped[UUID]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | tags | raise |

### OAuthProvider (`oauth_providers`)
*File: user.py*

**Columns:**

| Column | Type |
|--------|------|
| `name` | `Mapped[str]` |
| `client_id` | `Mapped[str | None]` |
| `client_secret` | `Mapped[str | None]` |
| `enabled` | `Mapped[bool]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `identities` | UserIdentity | provider | raise |

### User (`users`)
*File: user.py*

**Columns:**

| Column | Type |
|--------|------|
| `username` | `Mapped[str]` |
| `email` | `Mapped[str | None]` |
| `avatar_url` | `Mapped[str | None]` |
| `is_active` | `Mapped[bool]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `identities` | UserIdentity | user | raise |
| `signal_chains` | SignalChain | user | raise |
| `signal_chain_groups` | SignalChainGroup | user | raise |
| `di_tracks` | DITrack | user | raise |
| `shootouts` | Shootout | user | raise |
| `jobs` | Job | user | raise |
| `user_gear` | UserGear | user | raise |
| `notifications` | UserNotification | user | raise |
| `tags` | Tag | user | raise |

### UserGear (`user_gear`)
*File: user_gear.py*

**Columns:**

| Column | Type |
|--------|------|
| `user_id` | `Mapped[uuid.UUID]` |
| `gear_model_id` | `Mapped[uuid.UUID]` |
| `nickname` | `Mapped[str | None]` |
| `notes` | `Mapped[str | None]` |
| `is_favourite` | `Mapped[bool]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | user_gear | raise |
| `gear_model` | GearModel | user_gear | raise |

### UserIdentity (`user_identities`)
*File: user_identity.py*

**Columns:**

| Column | Type |
|--------|------|
| `user_id` | `Mapped[uuid.UUID]` |
| `provider_id` | `Mapped[uuid.UUID]` |
| `external_id` | `Mapped[str]` |
| `username` | `Mapped[str]` |
| `avatar_url` | `Mapped[str | None]` |

**Relationships:**

| Name | Target | back_populates | lazy |
|------|--------|----------------|------|
| `user` | User | identities | raise |
| `provider` | OAuthProvider | identities | raise |


### STRUCTURE

# Codebase Structure

*Auto-generated by `workflow/codebase_mapper.py` -- do not edit.*

## Directory Tree

```
95-phase-4-completion-di-tracks-groups-shoo/  (21 files)
  .agents/
    skills/
      chrome-devtools/  (1 files)
      codebase-review/  (1 files)
        references/  (3 files)
      docker-infra/  (1 files)
        references/  (2 files)
      documentation-style/  (1 files)
      epic/  (1 files)
        references/  (4 files)
      gts-architecture/  (1 files)
        references/  (13 files)
      gts-auth/  (1 files)
        references/  (4 files)
      gts-backend-dev/  (1 files)
      gts-frontend-dev/  (1 files)
        references/  (6 files)
      gts-security/  (1 files)
        references/  (4 files)
      gts-testing/  (1 files)
        references/  (2 files)
      gts-video/  (1 files)
      incident-response/  (1 files)
      micro-task-workflow/  (1 files)
      prompt-builder/  (1 files)
        references/  (1 files)
      python-cheatsheet/  (1 files)
      ralph-hybrid-overview/  (1 files)
        references/  (1 files)
      ralph-hybrid-plan/  (1 files)
        references/  (4 files)
      screenshot-eval/  (1 files)
        resources/  (1 files)
      site-verify/  (1 files)
      ui-contract/  (1 files)
      ui-debug/  (1 files)
  .claude/  (3 files)
    agents/  (5 files)
    archive/
      2026-01-consolidation/  (1 files)
        software-architecture/  (1 files)
      2026-02-uv-workspace-migration/  (2 files)
    commands/  (14 files)
    hooks/  (11 files)
    prompts/  (4 files)
      completed/  (1 files)
    rules/  (15 files)
    scripts/  (1 files)
    skills/
      chrome-devtools/  (1 files)
      codebase-review/  (1 files)
        references/  (3 files)
      docker-infra/  (1 files)
        references/  (2 files)
      documentation-style/  (1 files)
      epic/  (1 files)
        references/  (4 files)
      gts-architecture/  (1 files)
        references/  (13 files)
      gts-auth/  (1 files)
        references/  (4 files)
      gts-backend-dev/  (1 files)
      gts-frontend-dev/  (1 files)
        references/  (6 files)
      gts-security/  (1 files)
        references/  (4 files)
      gts-testing/  (1 files)
        references/  (2 files)
      gts-video/  (1 files)
      incident-response/  (1 files)
      micro-task-workflow/  (1 files)
      prompt-builder/  (1 files)
        references/  (1 files)
      python-cheatsheet/  (1 files)
      ralph-hybrid-overview/  (1 files)
        references/  (1 files)
      ralph-hybrid-plan/  (1 files)
        references/  (4 files)
      screenshot-eval/  (1 files)
        resources/  (1 files)
      site-verify/  (1 files)
      ui-contract/  (1 files)
      ui-debug/  (1 files)
  .gemini/
    commands/  (14 files)
  .github/
    ISSUE_TEMPLATE/  (2 files)
  .planning/
    codebase/  (6 files)
    epics/
    logs/
    wiki-indexes/  (18 files)
  .ralph-hybrid/  (2 files)
    callbacks/  (3 files)
    main/  (6 files)
      logs/  (21 files)
    skills/  (4 files)
  .scratch/  (2 files)
  .serena/  (2 files)
    cache/
      python/  (2 files)
    memories/
  apps/
    scheduler/  (2 files)
      src/
        scheduler/  (5 files)
          schedules/  (3 files)
    webapp/  (2 files)
      src/
        webapp/  (7 files)
          adapters/  (1 files)
            persistence/  (1 files)
              models/  (18 files)
              repositories/  (11 files)
          api/  (2 files)
            v1/  (18 files)
              schemas/  (13 files)
          auth/  (5 files)
            providers/  (2 files)
          config/  (1 files)
          middleware/  (3 files)
          services/  (18 files)
    worker/  (2 files)
      src/
        worker/  (8 files)
          consumers/  (2 files)
          jobs/  (6 files)
          services/  (2 files)
  frontend/
    astro/  (10 files)
      .astro/  (4 files)
        collections/
      scripts/  (1 files)
      src/
        components/  (7 files)
          RemotionPlayer/  (3 files)
          SignalChain/  (18 files)
          common/  (1 files)
          ui/  (13 files)
        hooks/  (1 files)
        islands/  (1 files)
        layouts/  (1 files)
        lib/  (5 files)
        pages/  (6 files)
          dev/
            showcase/  (3 files)
          di-tracks/  (1 files)
          fragments/  (2 files)
            di-tracks/  (1 files)
            gear/  (3 files)
            library/  (11 files)
            shootouts/  (5 files)
              create/  (6 files)
          gear/  (1 files)
          jobs/  (1 files)
          layouts/  (1 files)
          pages/  (6 files)
            di-tracks/  (1 files)
            library/  (5 files)
          partials/  (2 files)
          report-error/  (1 files)
        styles/  (1 files)
        types/  (1 files)
  infrastructure/
    docker/  (7 files)
    migrations/  (4 files)
      versions/  (11 files)
    nginx/  (1 files)
      error-pages/  (3 files)
  libs/
    audio/  (2 files)
      src/
        audio/  (1 files)
          analysis/  (2 files)
          processing/  (7 files)
    core/  (2 files)
      src/
        core/  (1 files)
          domain/  (1 files)
            entities/  (11 files)
            value_objects/  (17 files)
          ports/  (5 files)
          records/  (2 files)
          services/  (3 files)
    video/  (8 files)
      src/
        video/  (7 files)
          remotion/  (3 files)
            compositions/  (5 files)
  scripts/  (22 files)
    schemas/  (4 files)
  sources/
    t3k/  (3 files)
      alembic/  (2 files)
        versions/  (2 files)
      src/
        source_t3k/  (1 files)
          adapters/  (1 files)
            inbound/  (6 files)
            outbound/  (3 files)
          domain/  (3 files)
          services/  (3 files)
  src/
    gts/  (1 files)
  tests/  (2 files)
    e2e/  (1 files)
      python/  (4 files)
        tests/  (8 files)
      smoke/  (1 files)
    fixtures/  (1 files)
    integration/  (1 files)
      audio/  (5 files)
      backend/
        frontend/  (4 files)
        migrations/  (1 files)
        models/  (1 files)
        tooling/  (4 files)
        webapp/  (1 files)
      infrastructure/  (1 files)
      scheduler/  (2 files)
      t3k/  (3 files)
      video/  (4 files)
      webapp/  (68 files)
        repositories/  (4 files)
      worker/  (11 files)
    regression/  (5 files)
    unit/  (2 files)
      audio/  (4 files)
      backend/
        core/
          ports/  (2 files)
          value_objects/  (2 files)
        docs/  (2 files)
        documentation/  (5 files)
        domain/  (1 files)
        migrations/  (1 files)
        models/  (2 files)
        services/  (5 files)
      core/  (7 files)
        services/  (1 files)
      frontend/  (3 files)
      scheduler/  (6 files)
      t3k/  (12 files)
      video/  (7 files)
      webapp/  (37 files)
        services/  (1 files)
      worker/  (12 files)
      worktree/  (5 files)
  workflow/  (18 files)
    schemas/  (5 files)
    templates/  (5 files)
  worktree/  (16 files)
    cli_utils/  (5 files)
    commands/  (11 files)
    hooks/  (2 files)
    services/  (1 files)
    templates/  (2 files)
    tests/  (2 files)
```
