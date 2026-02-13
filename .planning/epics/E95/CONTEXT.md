# Epic Context

**Assembled:** 2026-02-13T17:08:31Z

This document is an intermediate artefact for the plan generator. It combines the epic description, codebase context, architecture documentation, and detected architecture areas into a single reference. Zero AI tokens were spent producing this file.

---

## Epic Description

The following is the verbatim epic body as fetched from GitHub:

---
github_issue: 95
title: "Phase 4 Completion — DI Tracks, Groups, Shootout Workflow, Content APIs, Platform Infra"
state: OPEN
labels: ["epic"]
fetched: 2026-02-13T17:08:31Z
---

## Epic: Phase 4 Completion

Complete all remaining Phase 4 web application features identified in the gap analysis. Phases 4A–4E are partially implemented or pending. This epic fills every gap to provide a solid foundation for Phase 5.

### Context

Phase 4 (core) delivered FastAPI auth, CRUD services, API endpoints, SSR pages, and the React SignalChainBuilder. But gap analysis against the archive revealed significant missing functionality in the sub-phases:

- **4A:** Frontend/API contract mismatch, IR upload service, asset/file serving — all missing
- **4B:** Router not mounted in main.py — endpoints exist but unreachable
- **4C:** Shootout wizard needs end-to-end validation, comments feature missing
- **4D:** Tags, Presets, Block Types APIs not implemented despite entities existing
- **4E:** Entirely pending — exceptions, error pages, audit, notifications, OAuth providers

### Pre-requisites

Phases 1–4 (core) ✅ complete.

**Can run in parallel with:** Phase 5 Pipeline epic (5A/5B/5D)

### Scope

#### Phase 4A — DI Track & IR Upload (Partial → Complete)

**Exists:** Upload endpoint, DITrackService, partial upload UI
**Gaps:**
- Fix frontend/API contract mismatch (URL: `/di-tracks/upload` → `/di-tracks`, fields: `title`→`name`, `pickups`→`pickup`)
- DI track browse page with real data, pagination, waveforms
- Upload UI with drag-and-drop, progress indicator, metadata form (guitar, pickup, notes)
- Library page showing user's DI tracks with delete capability
- System/seed DI tracks for testing and demo
- Waveform extraction on upload (WaveformExtractor from `libs/audio`)
- Audio metadata extraction (duration, sample rate, channels)
- `POST /api/v1/irs/upload` — community IR upload creating Gear + GearModel with `source="community"`
- Asset/file serving service — HMAC signed URLs, ownership validation, path traversal prevention
- File serving endpoint (`/api/v1/files/*`) for DI tracks, IRs, audio segments

**Archive refs:** `di_track_service.py`, `ir_upload_service.py`, `asset_service.py`, `files.py`

#### Phase 4B — Signal Chain Groups (Partial → Complete)

**Exists:** Group CRUD API and service code
**Gaps:**
- Mount `signal_chain_groups` router in `apps/webapp/src/webapp/main.py`
- Verify group CRUD API endpoints functional end-to-end
- Batch chain generation endpoint (N amps × M IRs)
- Group list page with tabs
- Group detail page with chain list
- Builder integration for group creation

**Archive refs:** `signal_chain_groups.py`, `signal_chain_group_service.py`

#### Phase 4C — Shootout Workflow (Partial → Complete)

**Depends on:** 4A (DI tracks must exist for selection)

**Exists:** Wizard page template, HTMX wizard fragments, submit endpoints
**Gaps:**
- Wizard step 1: chain selection from user's library (with group support from 4B)
- Wizard step 2: DI track selection modal with search/filter
- Wizard step 3: review and submit (summary of chains + DI track)
- Shootout detail page showing chains, DI track, processing status
- Validation: min 2 / max 20 chains, DI track required
- `ShootoutComment` entity + ORM model
- Comments CRUD API: `POST/GET/DELETE /api/v1/shootouts/{id}/comments`
- Comments HTMX fragment on shootout detail page

**Archive refs:** `fragments/shootouts/comments.html.ts`

#### Phase 4D — Library, Gear & Content APIs (Partial → Complete)

**Exists:** Model count wiring, save/remove toggle endpoints (partial)
**Gaps:**
- Gear model detail pages showing metadata, download status, audio preview
- Save/remove checkbox UI for bulk add/remove models to/from library
- Model counts on gear cards and detail pages
- Download status indicators on models
- Library sorting and filtering (date added, name, type; filter by gear type)
- Grid-aligned pagination (multiples of 3 for card layout)
- Tag CRUD API: `GET/POST/DELETE /api/v1/tags` with `TagService` + lowercase normalisation
- Preset CRUD API: `GET/POST/PUT/DELETE /api/v1/presets` with `PresetProcessor` for chain parameter validation
- Block types API: `GET /api/v1/block-types` listing built-in processor templates with effect parameter definitions
- License text display on gear detail pages

**Archive refs:** `tag_service.py`, `tags.py`, `preset_service.py`, `preset_processor.py`, `presets.py`, `block_type_registry.py`, `block_types.py`, `license_text.html.ts`

#### Phase 4E — Platform Infrastructure (Pending → Complete)

**Exists:** Nothing — entirely new
**Gaps:**
- Custom exception hierarchy: `AppException`, `NotFoundError`, `AuthorizationError`, `ConflictError`, `BadRequestError`, `ValidationError`
- Exception handlers for `AppException`, `HTTPException`, `RequestValidationError`, `SQLAlchemyError`, unhandled exceptions
- Content negotiation: HTML vs JSON error responses based on Accept header and route type
- Error sanitisation for production (strip stack traces)
- Custom 404 + 500 pages (Astro-built)
- nginx error pages (502, 503, 504 static HTML)
- Settings/account page at `/settings/account` (connected OAuth providers, account details)
- Dynamic `sitemap.xml` endpoint (static pages, public shootouts, gear pages)
- `AuditLog` ORM model + `AuditService` logging security-relevant events (login, CRUD operations)
- `UserNotification` ORM model + `NotificationService` (queue, get unread, mark read)
- Notification API endpoints (get unread, mark read, mark all read)
- Google OAuth provider
- GitHub OAuth provider
- Facebook OAuth provider
- Graceful shutdown with signal handlers (503 during drain)
- Test error endpoints (debug-mode only, used by Phase 6 E2E)

**Archive refs:** `exceptions.py`, `exception_handlers.py`, `content_negotiation.py`, `error_sanitizer.py`, `audit_service.py`, `notification_service.py`, `google.py`, `github.py`, `facebook.py`, `shutdown.py`, `test.py`

### Dependency Graph

```
Wave 1:  4A  4B  4D  4E  (all independent, parallel)
          │   │
Wave 2:  4A──→4C  (DI tracks needed for shootout wizard)
```

### Verification

- `just check` passes
- `just test-regression` passes
- `just test-golden-path` passes
- All API routers mounted and reachable (including signal_chain_groups)
- DI track upload → browse → playback works
- IR upload creates Gear + GearModel
- Shootout wizard creates shootouts end-to-end
- Comments appear on shootout detail page
- Tag, Preset, Block Type APIs respond correctly
- Custom error pages render (404, 500)
- Settings page shows connected providers
- Audit trail captures login events

### Key Files

| File | Action |
|------|--------|
| `apps/webapp/src/webapp/main.py` | Mount signal_chain_groups router, add exception handlers |
| `apps/webapp/src/webapp/api/v1/irs.py` | Create — IR upload endpoint |
| `apps/webapp/src/webapp/services/ir_upload_service.py` | Create — community IR upload service |
| `apps/webapp/src/webapp/services/asset_service.py` | Create — HMAC signed URLs, file serving |
| `apps/webapp/src/webapp/api/v1/files.py` | Create — secure file streaming |
| `apps/webapp/src/webapp/api/v1/tags.py` | Create — Tag CRUD API |
| `apps/webapp/src/webapp/services/tag_service.py` | Create — TagService |
| `apps/webapp/src/webapp/api/v1/presets.py` | Create — Preset CRUD API |
| `apps/webapp/src/webapp/services/preset_service.py` | Create — PresetService |
| `apps/webapp/src/webapp/api/v1/block_types.py` | Create — Block types API |
| `apps/webapp/src/webapp/exceptions.py` | Create — exception hierarchy |
| `apps/webapp/src/webapp/exception_handlers.py` | Create — exception handlers |
| `apps/webapp/src/webapp/services/audit_service.py` | Create — AuditService |
| `apps/webapp/src/webapp/services/notification_service.py` | Create — NotificationService |
| `apps/webapp/src/webapp/auth/providers/google.py` | Create — Google OAuth |
| `apps/webapp/src/webapp/auth/providers/github.py` | Create — GitHub OAuth |
| `apps/webapp/src/webapp/auth/providers/facebook.py` | Create — Facebook OAuth |
| `apps/webapp/src/webapp/shutdown.py` | Create — graceful shutdown |
| `frontend/astro/src/pages/404.astro` | Create — custom 404 page |
| `frontend/astro/src/pages/500.astro` | Create — custom 500 page |
| `frontend/astro/src/pages/fragments/shootouts/comments.html.ts` | Create — comments HTMX fragment |

### References

- [IMPLEMENTATION.md](../wiki/IMPLEMENTATION.md) — Phases 4A–4E
- [GTS-Technical-Architecture](../wiki/GTS-Technical-Architecture.md) — Architecture patterns


---

## Detected Architecture Areas

Based on keyword analysis of the epic body, the following architecture areas are relevant:

### API Contract (`api_contract`)

**Description:** Endpoints, Pydantic schemas, errors

**Key questions:** REST vs HTML endpoints, validation, pagination

**Scope discussion questions:**

- REST endpoint path? (/api/v1/...)
- HTML endpoint path? (/api/v1/html/...)
- Pydantic request/response schemas?
- Validation error format?
- Pagination approach (offset or cursor)?

### Audio Processing (`audio_processing`)

**Description:** NAM, IR, loudness normalization

**Key questions:** libs/audio vs apps/worker, processing pipeline

**Scope discussion questions:**

- Does this involve audio processing?
- NAM model loading?
- IR convolution?
- Loudness normalization?
- libs/audio or apps/worker?

### Data Model (`data_model`)

**Description:** Tables, columns, relations (SQLAlchemy ORM)

**Key questions:** Primary entity, lifecycle, indexes

**Scope discussion questions:**

- What's the primary entity?
- What fields are required vs optional?
- What's the status/lifecycle?
- Relations to existing tables in gts_core?
- Indexes or constraints needed?
- Soft delete or hard delete?

### Dual Database (`dual_database`)

**Description:** gts_core vs gts_t3k_source boundaries

**Key questions:** Which database, worker access, pgmq messages

**Scope discussion questions:**

- Which database is this for? (gts_core or gts_t3k_source)
- If source data, is worker the access point?
- pgmq messages involved?
- Sync records needed?
- Cross-database implications?

### Frontend Layers (`frontend_layers`)

**Description:** Astro SSG vs Jinja2 SSR vs HTMX fragments

**Key questions:** Page type, React island, navigation patterns

**Scope discussion questions:**

- Is this a static page (Astro SSG)?
- Is this a dynamic page (Jinja2 SSR)?
- Does it need HTMX fragments?
- Is it the SignalChainBuilder (React)?
- Design tokens from Astro CSS?

### Gear Model (`gear_model`)

**Description:** Unified gear, sources, sync records

**Key questions:** Source attribution, GearModel files, UserGear

**Scope discussion questions:**

- Does this feature involve gear?
- Unified Gear model or source-specific?
- GearModel files involved? (NAM, IR)
- Source attribution needed?
- User-uploaded (community) or synced from source?
- UserGear library implications?

### Jobs/Queues (`job_processing`)

**Description:** TaskIQ jobs, pgmq consumers, parent/child

**Key questions:** Retry strategy, progress reporting, Redis locks

**Scope discussion questions:**

- Does this trigger background jobs?
- TaskIQ job or pgmq consumer?
- Parent/child job hierarchy? (like SHOOTOUT)
- Retry strategy and max attempts?
- Progress reporting (WebSocket for user jobs)?
- Redis locks needed?

### Security (`security`)

**Description:** Auth, session cookies, ownership checks

**Key questions:** Authentication required, CurrentUser, rate limiting

**Scope discussion questions:**

- Does endpoint require authentication?
- CurrentUser dependency?
- Ownership check (user_id match)?
- Return 404 for unauthorised (not 403)?
- Rate limiting?

### Signal Chain (`signal_chain`)

**Description:** Block types, ordering, validation rules

**Key questions:** HEAD vs FULL_RIG, IR requirements, loop effects

**Scope discussion questions:**

- Does this feature involve signal chains?
- Which block types are affected? (amp, IR, pedal, built-in)
- HEAD vs FULL_RIG considerations? (IR required vs forbidden)
- Loop effects allowed? (not with FULL_RIG)
- Block ordering constraints?
- Permutation support needed? (SignalChainGroup)


---

## Codebase Context

The following sections are from `.planning/codebase/` analysis files:


### STRUCTURE

# Codebase Structure

**Analysis Date:** 2026-02-05

## Directory Layout

```
gts/
├── .planning/                  # GSD planning documents (not git tracked)
│   └── codebase/               # Architecture analysis (STACK.md, ARCHITECTURE.md, etc.)
├── .claude/                    # Claude agent configuration
│   ├── agents/                 # Agent skill definitions
│   ├── commands/               # Custom commands
│   ├── skills/                 # Reusable skills for agents
│   └── rules/                  # Policies (authentication, infrastructure, security)
├── pyproject.toml              # uv workspace root (dependency groups, import-linter)
├── justfile                    # Task runner (just --list for discovery)
├── docker-compose.yml          # Base Docker config (no ports, no container names)
├── docker-compose.override.yml # Worktree-specific (auto-generated, gitignored)
│
├── libs/                       # Shared domain and utility libraries
│   ├── core/                   # Domain logic (zero framework dependencies)
│   │   └── src/core/
│   │       ├── domain/
│   │       │   ├── entities/   # User, Gear, SignalChain, Shootout, Job, DITrack
│   │       │   └── value_objects/  # Enums, frozen dataclasses, IDs, results
│   │       ├── ports/          # Repository protocols, AudioProcessor, VideoComposer
│   │       ├── records/        # Sync record schemas (GearSyncRecord)
│   │       └── services/       # Domain services (validation, calculation)
│   │
│   └── audio/                  # Audio processing (depends on core only)
│       └── src/audio/
│           ├── processing/     # NAM, IR, pedalboard, loudness, permutation
│           ├── video/          # Video composition
│           └── analysis/       # Audio analysis (waveform, loudness)
│
├── sources/                    # External data source adapters (depend on core only)
│   └── t3k/                    # Tone3000 integration
│       └── src/source_t3k/
│           ├── domain/         # T3K-specific entities (Pack, Model)
│           ├── adapters/
│           │   ├── inbound/    # T3K API client, OAuth
│           │   └── outbound/   # pgmq publisher
│           └── services/       # Sync service, catalog download
│
├── apps/                       # Applications
│   ├── webapp/                 # FastAPI web application
│   │   └── src/webapp/
│   │       ├── main.py         # FastAPI app factory
│   │       ├── api/            # REST endpoints, page routes
│   │       ├── auth/           # Session management, OAuth flow
│   │       ├── services/       # Application services (higher-level logic)
│   │       └── adapters/       # Framework-specific implementations
│   │           └── persistence/
│   │               ├── models/     # SQLAlchemy ORM models
│   │               └── repositories/  # Repository implementations
│   │
│   ├── worker/                 # TaskIQ background job worker
│   │   └── src/worker/
│   │       ├── main.py         # TaskIQ broker and example task
│   │       ├── consumers/      # pgmq message handlers
│   │       └── jobs/           # Job definitions (tone processing, sync)
│   │
│   └── scheduler/              # TaskIQ scheduler (cron jobs)
│       └── src/scheduler/
│           ├── main.py         # TaskIQ scheduler config
│           └── schedules/      # Cron definitions (T3K sync, cleanup)
│
├── frontend/                   # Frontend build system (not runtime)
│   └── astro/
│       ├── src/
│       │   ├── pages/          # Template sources (.html.ts, .astro files)
│       │   │   ├── layouts/    # Base layout wrapper
│       │   │   ├── pages/      # Full page templates (gear, shootouts, library)
│       │   │   ├── fragments/  # HTMX response templates
│       │   │   └── partials/   # Reusable components
│       │   ├── components/     # React islands (SignalChainBuilder only)
│       │   ├── styles/         # Tailwind CSS, design tokens
│       │   └── lib/            # Build-time utilities
│       │
│       ├── dist/               # Build output (COMMITTED TO GIT)
│       │   ├── layouts/        # Built Jinja2 wrappers
│       │   ├── pages/          # Built page templates
│       │   ├── fragments/      # Built HTMX fragments
│       │   ├── _astro/         # Compiled Tailwind CSS
│       │   └── *.html          # Static pages (index, about, login, 404, 500)
│       │
│       └── astro.config.mjs    # Build configuration
│
├── infrastructure/
│   ├── docker/                 # Container images
│   │   ├── Dockerfile.dev      # Development image (uv installed)
│   │   ├── Dockerfile.webapp   # Production webapp image
│   │   ├── Dockerfile.worker   # Production worker image
│   │   ├── init-db.sql         # PostgreSQL initialization
│   │   └── init-pgmq.sql       # pgmq extension setup
│   │
│   ├── migrations/             # Alembic schema migrations
│   │   ├── versions/           # Individual migration files
│   │   ├── env.py              # Alembic environment
│   │   └── script.py.mako      # Migration template
│   │
│   └── nginx/                  # Reverse proxy configuration
│       └── nginx.conf.template # Template processed at runtime via envsubst
│
├── tests/
│   ├── regression/             # Stack connectivity tests (SQLite in-memory)
│   │   └── conftest.py         # Pytest fixtures (test_db session)
│   │
│   ├── unit/                   # Isolated unit tests
│   │   ├── core/               # Domain logic tests
│   │   ├── audio/              # Audio processing tests
│   │   └── webapp/             # ORM and service tests
│   │
│   ├── integration/            # Real database/service tests
│   │   ├── webapp/             # Repository integration tests
│   │   ├── audio/              # Audio processing with real files
│   │   └── worker/             # Worker consumer tests
│   │
│   ├── e2e/
│   │   ├── python/             # Playwright pytest tests (isolated uv env)
│   │   │   ├── tests/          # Test files (browser automation)
│   │   │   ├── conftest.py     # Playwright fixtures
│   │   │   └── pyproject.toml  # Isolated from workspace
│   │   │
│   │   └── smoke/              # Smoke tests (simple health checks)
│   │
│   ├── fixtures/               # Shared test fixtures
│   │   └── factories.py        # Entity factories for tests
│   │
│   └── data/                   # Test data files (audio samples, fixtures)
│
├── worktree/                   # Worktree lifecycle management
│   ├── auth.py                 # OAuth flow, .gts-auth.json management
│   ├── setup.py                # Idempotent worktree setup
│   └── cleanup.py              # Teardown and orphan cleanup
│
├── scripts/                    # Standalone scripts
│   └── gts-admin               # Admin CLI tool (job management, sync status)
│
├── src/                        # Root-level utilities
│   └── gts/                    # Shared utilities (if any)
│
└── README.md                   # Project overview
```

## Directory Purposes

**libs/core (`libs/core/src/core/`):**
- Purpose: Framework-agnostic domain logic shared by all modules
- Contains: Domain entities, value objects, business rules, ports (protocols)
- Key files:
  - `domain/entities/{user.py, gear.py, shootout.py, signal_chain.py, job.py, di_track.py}`
  - `domain/value_objects/{job_status.py, audio_result.py, signal_chain_enums.py}`
  - `ports/repositories.py` - UserRepository, GearRepository, JobRepository protocols
  - `ports/audio_processor.py` - AudioProcessor protocol
  - `services/{signal_chain_validator.py, permutation_calculator.py}` - Business rules

**libs/audio (`libs/audio/src/audio/`):**
- Purpose: Audio effects processing, loudness measurement, visualization
- Contains: Pedalboard integration, NAM models, IR loading, waveform extraction
- Key files:
  - `processing/processor.py` - PedalboardAudioProcessor (implements AudioProcessor protocol)
  - `processing/nam_loader.py` - Load NAM neural amp models
  - `processing/ir_loader.py` - Load impulse response files
  - `processing/loudness.py` - PyLoudnorm loudness measurement
  - `analysis/waveform.py` - Extract waveform peaks for visualization

**sources/t3k (`sources/t3k/src/source_t3k/`):**
- Purpose: Tone3000 catalog integration and sync
- Contains: API client, OAuth, sync service, database bridge
- Key files:
  - `adapters/inbound/` - T3K API client, OAuth endpoints
  - `adapters/outbound/` - pgmq queue publisher
  - `services/` - Sync orchestration, catalog download

**apps/webapp (`apps/webapp/src/webapp/`):**
- Purpose: Web application (HTTP server for pages and API)
- Contains: FastAPI routes, ORM models, repositories, session management
- Key files:
  - `main.py` - FastAPI app factory
  - `api/` - REST endpoints and Jinja2 page routes
  - `auth/` - Session middleware, OAuth callback handler
  - `adapters/persistence/models/` - SQLAlchemy ORM (User, Gear, Shootout, Job, SignalChain)
  - `adapters/persistence/repositories/` - SQLAlchemy implementations of core protocols
  - `adapters/persistence/unit_of_work.py` - Transaction management

**apps/worker (`apps/worker/src/worker/`):**
- Purpose: Background job processing and T3K sync
- Contains: TaskIQ broker, job handlers, pgmq consumers
- Key files:
  - `main.py` - TaskIQ broker initialization
  - `consumers/` - pgmq message handlers (receives jobs from webapp)
  - `jobs/` - Job definitions (tone processing, sync tasks)

**apps/scheduler (`apps/scheduler/src/scheduler/`):**
- Purpose: Cron job scheduling
- Contains: TaskIQ scheduler, schedule definitions
- Key files:
  - `main.py` - TaskIQ scheduler initialization
  - `schedules/` - Cron job definitions (T3K sync, cleanup)

**frontend/astro/src/ (`frontend/astro/src/`):**
- Purpose: Static site source (pre-built to dist/ and committed)
- Contains: Astro templates, React islands, Tailwind styles
- Key locations:
  - `pages/` - Astro page templates (.astro, .html.ts files)
  - `fragments/` - HTMX response templates (built to dist/fragments/)
  - `partials/` - Reusable components (Header, Footer)
  - `styles/global.css` - Tailwind configuration, design tokens

**frontend/astro/dist/ (`frontend/astro/dist/`):**
- Purpose: Build output (COMMITTED TO GIT - this is deployed)
- Contains: Pre-built HTML, CSS, JavaScript
- Served by: nginx directly (not FastAPI)
- Update: `just build-astro` compiles src/ to dist/

**infrastructure/ (`infrastructure/`):**
- Purpose: Deployment configuration
- Contains: Dockerfiles, migrations, nginx config
- Key files:
  - `docker/Dockerfile.dev` - Development image with uv
  - `docker/Dockerfile.webapp` - Production webapp image
  - `docker/init-db.sql` - Create gts_core and gts_t3k_source databases
  - `migrations/versions/*.py` - Alembic schema migrations
  - `nginx/nginx.conf.template` - Reverse proxy routing

**tests/ (`tests/`):**
- Purpose: Test suites for all test types
- Contains: Unit, integration, E2E, regression tests
- Substructure:
  - `regression/` - Stack connectivity (minimal, fast)
  - `unit/` - Isolated unit tests
  - `integration/` - Real database/service tests
  - `e2e/python/` - Playwright browser tests (isolated venv)
  - `fixtures/` - Shared test utilities
  - `data/` - Test data files (audio samples)

## Key File Locations

**Entry Points:**

- `apps/webapp/src/webapp/main.py` - FastAPI app creation
- `apps/worker/src/worker/main.py` - TaskIQ broker initialization
- `apps/scheduler/src/scheduler/main.py` - TaskIQ scheduler setup
- `infrastructure/nginx/nginx.conf.template` - Reverse proxy configuration
- `frontend/astro/src/pages/` - Frontend template sources

**Configuration:**

- `pyproject.toml` - Root workspace config, import-linter rules, tool config
- `docker-compose.yml` - Base Docker services (no worktree-specific values)
- `docker-compose.override.yml` - Worktree ports/names (auto-generated)
- `infrastructure/docker/init-db.sql` - Database initialization
- `infrastructure/migrations/env.py` - Alembic configuration

**Core Logic:**

- `libs/core/src/core/domain/entities/` - Domain entities (User, Gear, Shootout, SignalChain, Job)
- `libs/core/src/core/ports/` - Repository and service protocols
- `libs/core/src/core/services/` - Business rule validation and calculation
- `libs/audio/src/audio/processing/` - Audio effect processing (Pedalboard)
- `sources/t3k/src/source_t3k/services/` - T3K sync orchestration

**Testing:**

- `tests/regression/conftest.py` - Regression test fixtures
- `tests/integration/webapp/conftest.py` - Integration test fixtures
- `tests/e2e/python/conftest.py` - Playwright E2E fixtures
- `tests/fixtures/factories.py` - Entity factory builders

## Naming Conventions

**Files:**

- Domain entities: `{entity_name}.py` (lowercase, singular)
  - Example: `user.py`, `signal_chain.py`, `shootout.py`
- Test files: `test_{module}.py` or `test_{feature}.py`
  - Example: `test_user_repository.py`, `test_signal_chain_validation.py`
- ORM models: Same name as domain entity (different namespace)
  - Example: `models/user.py` vs `domain/entities/user.py`
- Repositories: `{entity_name}_repository.py`
  - Example: `user_repository.py`, `job_repository.py`

**Directories:**

- Package directories: lowercase with underscores
  - Example: `signal_chain`, `user_identity`, `audio_processor`
- Test categories: `{test_type}` (unit, integration, e2e, regression)
- Module groups: Pluralized for collections
  - Example: `entities/`, `repositories/`, `services/`, `adapters/`

**Types and Classes:**

- Domain entities: PascalCase
  - Example: `User`, `SignalChain`, `DITrack`
- Value objects: PascalCase
  - Example: `JobStatus`, `AudioResult`, `ToneConfig`
- Exceptions: PascalCase with "Error" suffix
  - Example: `JobError`, `InvalidStateTransitionError`, `ProcessingError`
- Protocols: PascalCase
  - Example: `UserRepository`, `AudioProcessor`, `VideoComposer`

**Functions and Methods:**

- Functions/methods: snake_case
  - Example: `get_by_id()`, `create_job()`, `process_di_track()`
- Async methods: Same snake_case convention
  - Example: `async def get_by_id()`, `async def process_di_track()`

## Where to Add New Code

**New Feature (domain + API):**

1. Domain entity: `libs/core/src/core/domain/entities/{entity}.py`
2. Value objects: `libs/core/src/core/domain/value_objects/{vo}.py` (if needed)
3. Repository protocol: Add to `libs/core/src/core/ports/repositories.py`
4. ORM model: `apps/webapp/src/webapp/adapters/persistence/models/{entity}.py`
5. Repository implementation: `apps/webapp/src/webapp/adapters/persistence/repositories/{entity}_repository.py`
6. API routes: `apps/webapp/src/webapp/api/v1/{domain}.py`
7. Tests:
   - Unit: `tests/unit/core/test_{entity}.py`
   - Integration: `tests/integration/webapp/test_{entity}_repository.py`
   - E2E: `tests/e2e/python/tests/test_{feature}.py`

**New Component/Module:**

1. Assess dependencies: Does it depend on core only? Can it depend on audio?
2. Create directory: `libs/{name}/src/{name}/`
3. Add to `pyproject.toml` workspace members
4. Add import-linter contracts in root `pyproject.toml` if isolation needed
5. Implement ports and adapters within the module

**New Worker Job:**

1. Job definition: `apps/worker/src/worker/jobs/{job_type}.py`
2. Job handler/consumer: `apps/worker/src/worker/consumers/{job_type}.py`
3. Trigger from webapp: Publish message to pgmq
4. Tests: `tests/integration/worker/test_{job_type}.py`

**New HTMX Fragment:**

1. Template: `frontend/astro/src/pages/fragments/{domain}/{action}.html.ts`
2. Build: `just build-astro` generates `frontend/astro/dist/fragments/{domain}/{action}.html`
3. API endpoint: `apps/webapp/src/webapp/api/v1/html.py` route returns fragment
4. Tests: `tests/e2e/python/tests/test_{feature}.py` with Playwright

**New Static Page:**

1. Source: `frontend/astro/src/pages/{page}.astro`
2. Build: `just build-astro` generates `frontend/astro/dist/{page}.html`
3. Serve: nginx serves directly from `/static/`
4. No backend code needed (unless page has dynamic content)

**Utilities:**

- Shared helpers: `libs/{domain}/src/{domain}/lib/` or create new `libs/utils/`
- Standalone scripts: `scripts/{name}` or `worktree/{name}.py`

## Special Directories

**infrastructure/migrations/ (Alembic):**
- Purpose: Database schema versioning
- Generated: Yes (via `alembic revision -m "message"`)
- Committed: Yes
- Target database: gts_core only (T3K database not migrated via alembic)
- Run: Automatically at container startup
- Key files:
  - `versions/*.py` - Individual migration files (never edit by hand)
  - `env.py` - Migration runner configuration
  - `script.py.mako` - Template for new migrations

**.planning/codebase/ (GSD analysis):**
- Purpose: Architecture and codebase documentation for GSD tools
- Generated: Yes (via GSD map-codebase command)
- Committed: No (gitignored)
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md

**frontend/astro/dist/ (Pre-built frontend):**
- Purpose: Build output (runtime artifact)
- Generated: Yes (via `just build-astro`)
- Committed: Yes (critical for CI/production - no build step at runtime)
- Served by: nginx directly
- Must update when: `frontend/astro/src/` changes

**tests/e2e/python/ (Isolated E2E environment):**
- Purpose: End-to-end tests with Playwright
- Isolation: Own `pyproject.toml`, separate uv environment
- Depends on: No project dependencies (only pytest, playwright, httpx)
- Run: `just test-golden-path` (runs on host, hits Docker containers)
- Not tracked: `.venv/` directory in this folder

**.env.local (Development secrets):**
- Purpose: Local development secrets (gitignored)
- Contents: DB_PASSWORD, SECRET_KEY, OAUTH_ENCRYPTION_KEY, etc.
- Auto-generated: Yes (by `worktree.py setup`)
- Do NOT commit: Contains real secrets for worktree

---

*Structure analysis: 2026-02-05*


### ARCHITECTURE

# Architecture

**Analysis Date:** 2026-02-05

## Pattern Overview

**Overall:** Layered hexagonal architecture (ports and adapters) with strict dependency boundaries enforced by import-linter. The system separates domain logic from framework concerns through well-defined protocols.

**Key Characteristics:**
- Domain-driven design with zero-dependency core library
- Hexagonal architecture with ports (interfaces) and adapters (implementations)
- Strict module isolation via import-linter contracts in root `pyproject.toml`
- Dual database architecture: application database (gts_core) and source database (gts_t3k_source)
- Worker process acts as bridge between databases via pgmq message queues
- Event-driven background job processing using TaskIQ

## Layers

**Core Domain Library (`libs/core`):**
- Purpose: Framework-agnostic business logic and domain entities
- Location: `libs/core/src/core/`
- Contains: Domain entities, value objects, business rules, repository protocols
- Depends on: Nothing (pure Python)
- Used by: All other modules (audio, sources, apps)

**Audio Processing (`libs/audio`):**
- Purpose: Audio effect processing, loudness measurement, waveform extraction, video composition
- Location: `libs/audio/src/audio/`
- Contains: Pedalboard integration, PyLoudnorm loudness, NAM model loading, IR processing
- Depends on: core only
- Used by: worker (background job processing)

**Source Adapter - T3K (`sources/t3k`):**
- Purpose: Integration with Tone3000 source data (packs, models, presets)
- Location: `sources/t3k/src/source_t3k/`
- Contains: T3K API client, OAuth authentication, sync service, pgmq publisher
- Depends on: core only
- Used by: worker (via pgmq message routing)
- Critical Rule: webapp has NO dependency on sources; worker is the bridge

**Webapp - FastAPI (`apps/webapp`):**
- Purpose: Web application serving pages (Jinja2 SSR), REST API, session management
- Location: `apps/webapp/src/webapp/`
- Contains: HTTP handlers, ORM models, repository implementations, services, auth
- Depends on: core, audio
- Cannot depend on: sources (worker is the bridge)
- Serves: User pages and API routes on port 8000

**Worker - TaskIQ (`apps/worker`):**
- Purpose: Background job processing, pgmq consumer, T3K sync orchestration
- Location: `apps/worker/src/worker/`
- Contains: Job definitions, pgmq message consumers, tone processing pipeline
- Depends on: core, audio, sources
- Database access: Connects to both gts_core and gts_t3k_source
- Communication: Receives messages from webapp via pgmq queues

**Scheduler - TaskIQ (`apps/scheduler`):**
- Purpose: Cron job scheduling (T3K sync, cleanup tasks)
- Location: `apps/scheduler/src/scheduler/`
- Contains: Schedule definitions, broker configuration
- Depends on: core only
- Used by: worker (via TaskIQ broker)

**Frontend (`frontend/astro`):**
- Purpose: Static site generation with Astro, Tailwind styling
- Location: `frontend/astro/src/`
- Output: Pre-built HTML/CSS in `frontend/astro/dist/` (committed to git)
- Served by: nginx static file server (not FastAPI)
- No runtime dependency on backend

## Data Flow

**User HTTP Request → Response:**

1. HTTP request arrives at nginx (port 9000)
2. nginx routes to:
   - Static files from `/static` (bind-mounted `frontend/astro/dist/`) - served directly
   - SSR pages (Jinja2) to FastAPI webapp container (port 8000)
   - API routes to FastAPI webapp container
3. FastAPI handler executes:
   - Session auth validation (cookies)
   - Domain service logic (uses injected repositories)
   - Repository reads/writes to PostgreSQL gts_core database
   - HTML/JSON response back through nginx

**Background Job Processing:**

1. Webapp creates Job entity, saves to gts_core
2. Webapp publishes message to pgmq queue
3. Worker consumer polls pgmq, receives message
4. Worker creates JobProcessor, executes job:
   - Reads Job entity from gts_core
   - May read/write to gts_t3k_source (T3K sync)
   - Uses audio processor (Pedalboard) for tone processing
   - Updates Job status in gts_core
5. Job lifecycle: PENDING → RUNNING → COMPLETED/FAILED

**T3K Catalog Sync:**

1. Scheduler triggers sync cron job
2. Worker receives sync message from pgmq
3. Worker's T3K sync service:
   - Authenticates with T3K API (OAuth tokens)
   - Downloads packs/models/presets to gts_t3k_source
   - Publishes notifications back to gts_core via pgmq
   - Updates gts_core gear references if needed

**State Management:**

- **Domain state:** Aggregate roots (User, SignalChain, Shootout) managed by repositories
- **Job state:** State machine with validated transitions (PENDING → RUNNING → COMPLETED/FAILED)
- **Session state:** HTTP-only cookies (Starlette default)
- **Transaction boundaries:** Services own transactions using UnitOfWork pattern
  ```python
  async with UnitOfWork(session_factory) as uow:
      # Read/write to repositories via uow.session
      await uow.commit()  # Explicit commit
  ```
- **Database consistency:** SQLAlchemy ORM enforces constraints, migrations in `infrastructure/migrations/`

## Key Abstractions

**Domain Entities:**
- Purpose: Core business objects with identity and lifecycle
- Examples: `libs/core/src/core/domain/entities/{user.py, gear.py, shootout.py, signal_chain.py, job.py}`
- Pattern: Dataclasses with frozen value objects, explicit state transitions

**Value Objects:**
- Purpose: Immutable domain values (enums, IDs, results)
- Examples: `libs/core/src/core/domain/value_objects/{job_status.py, audio_result.py, signal_chain_enums.py}`
- Pattern: Frozen dataclasses, no mutable state

**Repository Protocols:**
- Purpose: Define persistence interface for domain layer
- Examples: `libs/core/src/core/ports/repositories.py` (UserRepository, JobRepository, GearRepository)
- Pattern: Python typing.Protocol - domain doesn't know about SQLAlchemy
- Implementation: `apps/webapp/src/webapp/adapters/persistence/repositories/{user_repository.py, job_repository.py, ...}`

**Audio Processor Protocol:**
- Purpose: Define audio effects interface for domain layer
- Location: `libs/core/src/core/ports/audio_processor.py`
- Methods: process_di_track(), extract_waveform(), measure_loudness(), normalize_loudness()
- Implementation: `libs/audio/src/audio/processing/processor.py` (PedalboardAudioProcessor)

**Video Composer Protocol:**
- Purpose: Define video generation interface
- Location: `libs/core/src/core/ports/video_composer.py`
- Used by: Job processing (tone comparison videos)

**Job and Signal Chain Grammar:**
- Purpose: Domain business rules encoded in entities
- SignalChain grammar: `[PrePedals*] -> AmpBlock -> [IRBlock?] -> [PostEffects*]`
- Validation: `libs/core/src/core/services/{signal_chain_validator.py, permutation_calculator.py}`
- Enforced at: Entity creation time, not in database constraints

## Entry Points

**FastAPI Application:**
- Location: `apps/webapp/src/webapp/main.py`
- Triggers: uvicorn container startup
- Responsibilities:
  - Creates FastAPI app instance
  - Registers middleware (CORS, auth, error handling)
  - Mounts routers (api/v1/*, pages/*)
  - Configures session store (Redis or in-memory)

**Worker Task Broker:**
- Location: `apps/worker/src/worker/main.py`
- Triggers: TaskIQ worker container startup
- Responsibilities:
  - Creates TaskIQ broker (Redis in production, in-memory in dev)
  - Registers job handlers and consumers
  - Polls pgmq queues for messages

**Scheduler:**
- Location: `apps/scheduler/src/scheduler/main.py`
- Triggers: TaskIQ scheduler container startup
- Responsibilities:
  - Creates TaskIQ scheduler instance
  - Registers cron schedule sources
  - Triggers periodic jobs (T3K sync, cleanup)

**nginx:**
- Location: `infrastructure/nginx/nginx.conf.template`
- Triggers: Container startup
- Responsibilities:
  - Serves static files from `/static` (Astro dist/)
  - Proxies SSR/API routes to webapp:8000
  - Sets security headers (CSP, X-Frame-Options, etc.)

**Frontend Build:**
- Location: `frontend/astro/` (TypeScript/Astro)
- Triggers: `just build-astro` command
- Output: `frontend/astro/dist/` (HTML, CSS, JS - committed to git)
- Served by: nginx (no build step at runtime)

## Error Handling

**Strategy:** Explicit error handling with domain-specific exceptions and HTTP status code mapping

**Patterns:**

- **Domain Errors:** Custom exceptions in entities/services
  ```python
  # libs/core/src/core/domain/entities/job.py
  class InvalidStateTransitionError(JobError):
      """Raised when an invalid state transition is attempted."""
  ```

- **Processing Errors:** Caught during job execution, status updated to FAILED
  ```python
  # Process DI track, catch ProcessingError, set job.status = FAILED
  ```

- **Validation Errors:** Pydantic raises ValidationError on input
  ```python
  # FastAPI catches Pydantic ValidationError → 422 Unprocessable Entity
  ```

- **Auth Errors:** Session validation, OAuth token refresh
  ```python
  # 401 Unauthorized if session invalid
  # 403 Forbidden if user doesn't own resource
  ```

- **HTTP Response Mapping:**
  - 200: Success
  - 302: Redirect (auth flow)
  - 400: Bad request (validation error)
  - 401: Unauthorized (missing/invalid session)
  - 403: Forbidden (user doesn't own resource)
  - 404: Not found (resource doesn't exist - 404 not 403 to avoid leaking existence)
  - 500: Server error (unhandled exception, logged)

## Cross-Cutting Concerns

**Logging:**

- Framework: Python standard library logging (if used) or stdout/stderr
- Patterns: Structured logs in JSON if applicable
- Error logging: Unhandled exceptions logged with traceback
- Authentication logging: Login/logout, token refresh events

**Validation:**

- Input validation: Pydantic schemas for all API endpoints
  ```python
  # apps/webapp/src/webapp/api/schemas.py
  class CreateShootoutRequest(BaseModel):
      title: str = Field(max_length=200)
      description: str | None = None
  ```
- Domain validation: Business rules enforced in entities/services
  ```python
  # Signal chain grammar validation in SignalChainValidator
  ```
- Database constraints: SQLAlchemy column constraints, foreign keys

**Authentication:**

- Method: Session cookies with HTTP-only flag
- Provider: T3K OAuth (passwordless email magic links)
- Storage: .gts-auth.json file shared across worktrees (600 permissions)
- Session duration: 7 days (extended from 30 min for worktree sharing)
- Refresh: Auto-refresh tokens at 24 hours remaining
- Endpoints: `/api/v1/auth/*` routes handle OAuth callback, session restore

**Authorization:**

- Pattern: CurrentUser dependency in FastAPI routes
- Check: Verify user owns resource before returning (404 not 403)
  ```python
  if shootout.user_id != current_user.id:
      raise HTTPException(status_code=404)  # Hide existence
  ```
- Admin routes: Separate admin API on worker (port 8001, no public exposure)

**Database Transactions:**

- Pattern: Services own transactions using UnitOfWork
  ```python
  async with UnitOfWork(session_factory) as uow:
      user = await user_repo.get_by_id(user_id)
      # Modifications
      await uow.commit()  # Explicit
  ```
- Rollback: Automatic if exception during context (ContextManager protocol)
- Isolation: SQLAlchemy default isolation level (READ COMMITTED)

---

*Architecture analysis: 2026-02-05*


### STACK

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


### CONVENTIONS

# Coding Conventions

**Analysis Date:** 2026-02-05

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `signal_chain_validator.py`)
- Test files: `test_{module_name}.py` (e.g., `test_user_model.py`)
- Config files: lowercase with underscores (e.g., `pyproject.toml`)
- Classes: `PascalCase` (e.g., `SignalChainValidator`, `UserRepository`)
- Domain exceptions: `DescriptivePascalCase` (e.g., `InvalidStateTransitionError`, `MaxChainsExceededError`)

**Functions:**
- All functions: `snake_case` (e.g., `validate`, `get_by_id`, `extract_waveform`)
- Private methods: `_snake_case` prefix (e.g., `_to_entity`, `_transition_to`)
- Class methods: `@classmethod def create_with_identity(...)` pattern
- Async functions: `async def function_name(...)` (no special prefix)

**Variables:**
- Module-level constants: `UPPER_CASE` (e.g., `_SUPPORTED_FORMATS`)
- Instance/local variables: `snake_case` (e.g., `user_id`, `db_session`)
- Loop variables: descriptive `snake_case` (e.g., `for identity in user.identities:`)
- Private attributes: prefix with underscore only if truly internal (rare)

**Types:**
- Domain entities: `ClassName` (e.g., `User`, `Job`, `SignalChain`)
- Value objects: `DescriptiveClassName` (e.g., `UserIdentity`, `ValidationError`, `JobStatus`)
- ORM models: `ClassName` (matching domain, e.g., `User` for ORM user model)
- Exception classes: `DescriptiveError` or `DescriptiveException` suffix (e.g., `JobError`, `ProcessingError`)
- Enums: `CapitalizedEnum` (e.g., `JobStatus`, `GearType`, `ValidationRule`)

## Code Style

**Formatting:**
- Tool: `ruff` (formatter and linter combined)
- Line length: 100 characters
- Quotes: Double quotes `"string"` (ruff default)
- Indentation: 4 spaces
- Type hints: Required on all function signatures (enforced by mypy strict mode)

**Linting:**
- Tool: `ruff` (Python linter)
- Config: `pyproject.toml` under `[tool.ruff]`
- Enabled rules: E (errors), W (warnings), F (Pyflakes), I (isort), B (bugbear), C4 (comprehensions), UP (pyupgrade), ARG (unused args), SIM (simplify), TCH (type checking), PTH (pathlib), RUF (ruff-specific)
- Ignored: E501 (handled by formatter), B008 (FastAPI Depends), B904 (raise from), ARG001 (unused args in protocols)

**Type Checking:**
- Tool: `mypy`
- Mode: Strict mode enabled
- Config: `pyproject.toml` under `[tool.mypy]`
- All functions must have explicit return types
- No implicit Optional types
- Untyped library overrides in `[[tool.mypy.overrides]]` for external packages (pedalboard, nam, torch, etc.)

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first for forward references)
2. Standard library (e.g., `from datetime import datetime`, `from pathlib import Path`)
3. Third-party (e.g., `from sqlalchemy import ...`, `from fastapi import ...`)
4. Local first-party (e.g., `from core.domain.entities.user import User`)
5. TYPE_CHECKING block with lazy imports (e.g., `if TYPE_CHECKING: from sqlalchemy.ext.asyncio import AsyncSession`)

**Path Aliases:**
- First-party packages configured in ruff isort: `["core", "audio", "source_t3k", "webapp", "worker", "scheduler"]`
- All imports use absolute paths from workspace root (e.g., `from core.domain.entities.user import User`, never relative imports)

**Example pattern:**
```python
"""Module docstring."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.domain.entities.user import User as UserEntity
from core.domain.entities.user import UserIdentity as UserIdentityVO
from webapp.adapters.persistence.models.user import User, UserIdentity

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
```

## Error Handling

**Patterns:**
- Domain exceptions are custom classes inheriting from base domain exception (e.g., `JobError`, `ShootoutError`)
- Custom exceptions include docstring explaining when they're raised
- Domain layer raises domain-specific exceptions (e.g., `InvalidStateTransitionError`)
- Repository/adapter layer propagates or wraps domain exceptions
- FastAPI/webapp layer catches exceptions and converts to HTTP responses
- All exceptions include descriptive messages with context (e.g., `f"Cannot transition from {self.status.value} to {new_status.value}"`)

**Exception hierarchy example:**
```python
class JobError(Exception):
    """Base exception for Job domain errors."""
    pass

class InvalidStateTransitionError(JobError):
    """Raised when an invalid state transition is attempted."""
    pass
```

**State validation pattern:**
```python
def _transition_to(self, new_status: JobStatus) -> None:
    """Validate and execute a status transition.

    Args:
        new_status: The status to transition to

    Raises:
        InvalidStateTransitionError: If the transition is not valid
    """
    if not self.status.can_transition_to(new_status):
        raise InvalidStateTransitionError(
            f"Cannot transition from {self.status.value} to {new_status.value}"
        )
```

## Logging

**Framework:** Standard library `logging` (not explicitly configured in codebase, uses defaults)

**Patterns:**
- Logging not heavily used in domain layer (pure functions preferred)
- Critical errors logged at adapter/application layer
- Structured logging deferred to future expansion
- No logging in unit tests unless debugging

## Comments

**When to Comment:**
- Complex business logic that isn't self-evident
- Grammar rules and validation constraints (e.g., signal chain grammar in `SignalChainValidator`)
- Workarounds or non-obvious decisions
- State machine transitions with validation rules
- Data transformation logic between domain and ORM models

**JSDoc/TSDoc/Docstrings:**
- All public classes: `"""Descriptive docstring with Attributes and usage."""`
- All public functions: `"""What it does. Args: ... Returns: ... Raises: ..."""`
- All methods: Include purpose, parameters, return type, exceptions
- Private methods: Docstring if logic is non-obvious
- Module-level: File-level docstring explaining module purpose
- No docstrings for trivial getters/setters unless adding significant value

**Example docstring:**
```python
class SignalChainValidator:
    """Service for validating signal chain compositions.

    Signal Chain Grammar:
        [PrePedals*] -> AmpBlock -> [IRBlock?] -> [PostEffects*]

    Validation rules:
        - NO_AMP: Chain must have exactly one amp block
        - MULTIPLE_AMPS: Only one amp allowed
        - IR_REQUIRED: Head amp requires IR block
    """

    def validate(self, chain: SignalChain) -> ValidationResult:
        """Validate a signal chain against grammar rules.

        Args:
            chain: The signal chain to validate

        Returns:
            ValidationResult with is_valid and any errors
        """
```

## Function Design

**Size:**
- Prefer functions under 50 lines
- Complex logic broken into helper functions with clear names
- Repository methods often longer due to query building (acceptable)

**Parameters:**
- Prefer explicit parameters over **kwargs
- Type hints required for all parameters
- Default arguments only for optional values
- Use keyword-only arguments for clarity when function has many parameters (`def method(self, required, *, optional=None)`)
- Async functions use same parameter conventions as sync

**Return Values:**
- All functions must declare return type (mypy strict)
- Return `X | None` instead of `Optional[X]`
- Domain methods return domain objects, repositories return entities
- Repository queries return `T | None` for single objects, `list[T]` for collections

**Example pattern:**
```python
async def get_by_id(self, user_id: UUID) -> UserEntity | None:
    """Get a user by their ID.

    Args:
        user_id: The user's UUID

    Returns:
        The User entity if found, None otherwise
    """
    stmt = select(User).where(User.id == user_id)
    result = await self.session.execute(stmt)
    user = result.scalar_one_or_none()
    return self._to_entity(user) if user else None
```

## Module Design

**Exports:**
- Modules export public classes and functions in `__init__.py`
- Private modules (starting with `_`) are implementation details
- Each layer has clear boundary: domain exports entities/value objects, adapters export implementations

**Barrel Files:**
- Use `__init__.py` for public API of packages
- Domain packages export entities: `from core.domain.entities.user import User, UserIdentity`
- Do not use star imports: always explicit `from X import Y`

**Example structure:**
```
libs/core/src/core/
├── domain/
│   ├── entities/
│   │   ├── __init__.py  # exports User, Job, SignalChain, etc.
│   │   ├── user.py
│   │   └── job.py
│   └── value_objects/
│       ├── __init__.py  # exports JobStatus, JobType, etc.
│       └── job_status.py
├── services/
│   ├── __init__.py  # exports validation/processing services
│   └── signal_chain_validator.py
└── ports/
    └── __init__.py  # exports protocols for dependency injection
```

## Dataclasses and Frozen Objects

**Patterns:**
- Domain entities: `@dataclass(eq=False, slots=True)` (identity-based equality, optimized)
- Value objects: `@dataclass(frozen=True, slots=True)` (immutable, hashable)
- ORM models: SQLAlchemy declarative, not dataclasses
- Attributes in dataclasses: declare with type hints and defaults

**Example:**
```python
@dataclass(frozen=True, slots=True)
class UserIdentity:
    """Value object representing an external identity link."""
    provider: str
    external_id: str
    username: str
    avatar_url: str | None = None
```

## Async Conventions

**All async patterns:**
- Repositories: All methods are `async def` even for simple lookups
- Type annotations: Use `AsyncSession`, `AsyncEngine` from `sqlalchemy.ext.asyncio`
- Session management: Use `async with session.begin():` for transactions
- No blocking I/O in async functions
- Fixtures marked with `@pytest.fixture` and return type `AsyncGenerator[T, None]`

**Repository transaction pattern:**
```python
async with session.begin():
    # Multiple operations in transaction
    await repo.save(entity)
    # Auto-rollback on exception, auto-commit on exit
```

## Dependency Injection and Protocols

**Ports/Adapters pattern:**
- Protocols defined in `core.ports` (not yet visible in codebase, follows hexagonal architecture)
- Implementations in `webapp.adapters` (SQLAlchemy, etc.)
- Services accept injected adapters via constructor
- FastAPI uses `Depends()` for injection

**Example (future pattern):**
```python
class UserService:
    def __init__(self, repo: UserRepository):  # Protocol type
        self.repo = repo

    async def create_user(self, identity: UserIdentity) -> User:
        user = User.create_with_identity(identity)
        await self.repo.save(user)
        return user
```

---

*Convention analysis: 2026-02-05*


### INTEGRATIONS

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


### TESTING

# Testing Patterns

**Analysis Date:** 2026-02-05

## Test Framework

**Runner:**
- `pytest` 8.3.0+
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`
- Async mode: `asyncio_mode = "auto"`
- Test paths: `tests/` directory

**Assertion Library:**
- pytest built-in assertions (no external assertion library)
- Format: `assert retrieved is not None, "Descriptive message"`

**Run Commands:**
```bash
just test-regression  # Stack connectivity tests (~0.2s, SQLite in-memory)
just test             # Unit + Integration tests (~30s)
just test-unit        # Unit tests only
just test-integration # Integration tests only
just test-golden-path         # E2E tests with Playwright (requires running containers)
just tdd <path>       # Single test during development (Docker, watches)
```

## Test File Organization

**Location:**
- Colocated with source code in `tests/` directory, mirroring source structure
- Pattern: `tests/{type}/{module}/test_{component}.py`

**Naming:**
- Test files: `test_{component}.py` (e.g., `test_user_model.py`, `test_stack.py`)
- Test classes: `Test{ComponentName}` (e.g., `TestUserRoundTrip`, `TestStackConnectivity`)
- Test functions: `test_{specific_behavior}` (e.g., `test_create_and_retrieve`, `test_user_identity_links_to_user`)

**Structure:**
```
tests/
├── regression/
│   ├── conftest.py          # Shared fixtures (db_engine, db_session)
│   └── test_stack.py        # Stack connectivity (ORM → Repo → DB)
├── unit/
│   ├── core/                # Domain entity tests
│   ├── audio/               # Audio processing tests
│   ├── webapp/              # ORM model and basic logic tests
│   └── worktree/            # Utility tests
├── integration/
│   ├── audio/               # Audio processing with real files
│   ├── webapp/              # Repository integration with real DB
│   │   └── conftest.py      # Shared fixtures
│   └── worker/              # Job processing integration
├── e2e/
│   └── python/
│       ├── pyproject.toml   # Standalone package
│       ├── conftest.py
│       └── tests/
├── fixtures/                # Shared test fixtures (empty, future use)
└── data/                    # Test data files (empty, future use)
```

## Test Structure

**Suite Organization:**
```python
"""Test module docstring explaining purpose."""

from __future__ import annotations

from typing import TYPE_CHECKING
import pytest

# Imports organized: stdlib, third-party, local

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def my_fixture() -> AsyncGenerator[T, None]:
    """Setup for tests."""
    yield value
    # Cleanup if needed


class TestStackConnectivity:
    """Group related tests in a class."""

    def test_orm_models_import(self) -> None:
        """Test something specific."""
        assert Base is not None


class TestUserRoundTrip:
    """Another test class."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
        """Test async behavior with fixture."""
        # Setup
        identity = UserIdentity(...)
        user = UserEntity.create_with_identity(identity=identity)

        # Act
        repo = SQLAlchemyUserRepository(db_session)
        await repo.save(user)
        await db_session.commit()
        retrieved = await repo.get_by_id(user.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == user.id
```

**Patterns:**
- Setup-Act-Assert pattern (comments optional but helpful)
- Fixtures injected as parameters
- `@pytest.mark.asyncio` on all async tests
- Type hints on all test functions
- Clear test names describing behavior, not implementation

## Mocking

**Framework:** `unittest.mock` (not currently heavily used)

**Patterns:**
- Avoid mocking internal services (test against real objects)
- Mock only external APIs and I/O-heavy operations
- For audio tests: create minimal test audio files instead of mocking audio libraries
- For model tests: use in-memory SQLite instead of mocking database

**What to Mock:**
- External APIs (Tone3000 API, email services, payment systems)
- File I/O in unit tests (not in integration tests)
- Time-dependent behavior (mock `datetime.now()` if needed)

**What NOT to Mock:**
- Domain entities and value objects
- Repositories (use real DB with SQLite in-memory)
- SQLAlchemy ORM (test with real models)
- Core business logic

**Example of correct pattern (test real, not mock):**
```python
@pytest.mark.asyncio
async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
    """Create user via repository, retrieve it - validates full stack."""
    # Real domain entity
    identity = UserIdentity(
        provider="t3k", external_id="test-001", username="test_user"
    )
    user = UserEntity.create_with_identity(identity=identity, email="test@gts.dev")

    # Real repository
    repo = SQLAlchemyUserRepository(db_session)
    await repo.save(user)  # Real database operation
    await db_session.commit()

    # Real query
    retrieved = await repo.get_by_id(user.id)

    # Assertion
    assert retrieved is not None
```

## Fixtures and Factories

**Test Data:**
- Fixtures created inline in test functions (small, simple data)
- Reusable fixtures defined at top of test file or in `conftest.py`

**Fixture pattern:**
```python
@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite engine with all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async with async_session() as session:
        yield session
```

**Location:**
- Shared fixtures: `tests/{type}/conftest.py` (e.g., `tests/regression/conftest.py`)
- Fixture scope: Function scope (default, isolated tests)
- No global fixtures unless truly needed

**Naming:**
- Fixture functions: `fixture_name` (e.g., `db_session`, `test_audio_dir`)
- Factory functions: `make_user()`, `create_job()` (not currently used, prefer inline)

## Coverage

**Requirements:** Not enforced by default, but configured

**View Coverage:**
```bash
# After running tests with pytest-cov
pytest --cov=libs --cov=sources --cov=apps --cov-report=html
# Then open htmlcov/index.html
```

**Configuration:** `pyproject.toml` under `[tool.coverage.run]` and `[tool.coverage.report]`
- Source: `libs`, `sources`, `apps`
- Branch coverage: enabled
- Exclusions: tests, pycache, abstract methods, TYPE_CHECKING blocks

## Test Types

**Unit Tests:**
- Location: `tests/unit/{module}/test_{component}.py`
- Scope: Pure logic, no I/O
- Database: None (test domain entities, value objects, validators)
- Examples: `tests/unit/core/`, `tests/unit/audio/test_ir_loader.py`
- Approach: Test domain entities, enums, value objects in isolation

**Regression Tests:**
- Location: `tests/regression/test_stack.py`
- Purpose: Verify ORM → Repository → Database stack works end-to-end
- Database: In-memory SQLite
- Run before commits to catch fundamental breaks
- Includes: User entity round-trip, Job state machine, query operations
- Speed: ~0.2 seconds

**Integration Tests:**
- Location: `tests/integration/{module}/test_{component}.py`
- Scope: Real database (in-memory SQLite), real services
- Database: In-memory SQLite with schema
- Examples: `tests/integration/webapp/` (repositories), `tests/integration/audio/` (processing)
- Approach: Test repository implementations, service interactions with real DB

**E2E Tests:**
- Location: `tests/e2e/python/tests/`
- Framework: pytest + Playwright
- Scope: Full user journeys through web UI
- Database: Docker PostgreSQL (running containers required)
- Approach: Browser automation, assert DOM state and database persistence
- Run: `just test-golden-path` (on host, not in Docker)
- Note: Standalone package (`tests/e2e/python/pyproject.toml`), isolated from main workspace

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_async_function(self, db_session: AsyncSession) -> None:
    """Test async behavior."""
    result = await some_async_function(db_session)
    assert result is not None
```

**Error Testing:**
```python
@pytest.mark.asyncio
async def test_invalid_state_transition(self) -> None:
    """Test that invalid state transition raises error."""
    job = JobEntity(job_type=JobType.AUDIO_PROCESSING)
    job.queue(task_id="test-123")

    # Cannot transition from QUEUED directly to COMPLETED
    with pytest.raises(InvalidStateTransitionError):
        job.complete(result_path="/path")
```

**Fixture Usage:**
```python
@pytest.mark.asyncio
async def test_user_email_index(self, db_session: AsyncSession) -> None:
    """Test email column has index for performance."""
    user1 = User(username="user1", email="user1@example.com")
    user2 = User(username="user2", email="user2@example.com")
    db_session.add_all([user1, user2])
    await db_session.commit()

    # Query by email
    result = await db_session.execute(
        select(User).where(User.email == "user1@example.com")
    )
    found = result.scalar_one()

    assert found.username == "user1"
```

**Fresh Session per Test:**
```python
@pytest.mark.asyncio
async def test_relationships_fresh_session(self, db_session: AsyncSession) -> None:
    """Test relationships load correctly with fresh query."""
    # Create data
    provider = OAuthProvider(name="t3k", enabled=True)
    db_session.add(provider)
    await db_session.commit()

    user = User(username="test_user", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Close session and create new one for fresh query
    await db_session.close()

    # New session
    async_session = async_sessionmaker(
        db_session.bind, class_=AsyncSession, expire_on_commit=False
    )
    new_session = async_session()

    # Query and verify
    result = await new_session.execute(select(User).where(User.id == user_id))
    loaded_user = result.scalar_one()

    assert loaded_user is not None
```

## Test Markers

**Available markers:**
```
@pytest.mark.slow           # Slow tests
@pytest.mark.integration    # Integration tests
@pytest.mark.e2e            # End-to-end tests
@pytest.mark.smoke          # Smoke tests
```

**Configuration:** Defined in `pyproject.toml` under `[tool.pytest.ini_options]` markers

## Special Considerations

**SQLite in-memory vs PostgreSQL:**
- Unit/regression/integration: Use in-memory SQLite for speed (~0.2s for regression, <30s for all)
- E2E: Uses Docker PostgreSQL (real production database)
- Rationale: Speed + isolation for most tests, real schema validation for E2E

**Async Fixtures:**
- All database fixtures are async: `async def fixture(...) -> AsyncGenerator[T, None]:`
- Marked with `@pytest.fixture` (asyncio_mode="auto" handles async automatically)

**Test Isolation:**
- Each test gets fresh in-memory SQLite database
- No test order dependencies
- No shared state between tests

---

*Testing analysis: 2026-02-05*


### CONCERNS

# Codebase Concerns

**Analysis Date:** 2026-02-05

## Tech Debt

**Missing Relationship in User Model:**
- Issue: User model has TODO comment for Gear relationship that hasn't been implemented
- Files: `apps/webapp/src/webapp/adapters/persistence/models/user.py:103`
- Impact: Foreign key relationships incomplete; queries for user gear will require joins or separate queries
- Fix approach: Add relationship definition once Gear model finalized, create migration to add FK if needed

**NAM Model Processing Performance:**
- Issue: NAM model processing uses sample-by-sample iteration instead of batched processing
- Files: `libs/audio/src/audio/processing/processor.py:236-271`
- Impact: Extremely slow for long audio files (real-time or longer); unsuitable for production
- Current state: Marked as "simplified implementation" with TODO-style comments about buffering
- Fix approach: Implement proper batch processing with PyTorch tensor operations; benchmark against expected processing times

**Incomplete FastAPI Endpoint Implementation:**
- Issue: Main application factory only implements health check endpoint; no API routes defined
- Files: `apps/webapp/src/webapp/main.py` (26 lines total)
- Impact: No user-facing API endpoints for jobs, shootouts, gear, or authentication exist yet
- Blocks: All client-side integration; frontend cannot fetch data
- Fix approach: Wire up API routers in main.py using separate route modules

## Known Gaps

**Missing API Endpoints:**
- What's not implemented: All `/api/v1/` endpoints for jobs, shootouts, gear, signal chains, user library
- Files: `apps/webapp/src/webapp/main.py`
- Impact: Frontend templates exist but cannot be populated with data
- Workaround: None - endpoints must be implemented for application to function
- Priority: Critical - blocks feature delivery

**Missing Authentication Endpoints:**
- What's not implemented: OAuth flow endpoints, session management
- Expected at: `apps/webapp/src/webapp/auth/` (exists but empty)
- Impact: Users cannot authenticate; all protected endpoints fail
- Priority: Critical - required before any authenticated features work

**Incomplete Repository Contract:**
- What's not implemented: Some repository methods may only have stubs
- Files: `libs/core/src/core/ports/repositories.py` (593 lines)
- Impact: Services depending on complete repository interface will fail at runtime
- Validation: Run all integration tests to find missing implementations

## Performance Bottlenecks

**Audio Processing - Sample-by-Sample NAM:**
- Problem: NAM model applies to audio one sample at a time with tensor creation overhead
- Files: `libs/audio/src/audio/processing/processor.py:261-266`
- Cause: Loop iterates `audio_tensor` with `model(sample.view(1,1))` - creates new tensor per sample
- Expected impact: 10-100x slower than batched processing depending on file length
- Improvement path:
  1. Buffer samples into chunks (e.g., 1024 per batch)
  2. Create single tensor per batch
  3. Stack outputs and concatenate results
  4. Benchmark: target <1s for 30s audio file

**Audio Analysis Waveform Extraction:**
- Problem: Extracting 200 peak values from full audio may load entire file into memory
- Files: `libs/audio/src/audio/processing/processor.py:72-88`
- Cause: Delegates to `_extract_waveform` without streaming mechanism
- Scaling concern: Large files (100MB+) could exhaust memory on container
- Improvement path: Implement streaming waveform extraction with fixed memory window

## Fragile Areas

**Dual Database Architecture Bridge (Worker):**
- Files: Worker container as message consumer
- Why fragile: Worker is the only connection between `gts_core` and `gts_t3k_source` databases; if worker fails, T3K sync cannot occur
- Safe modification: Always test pgmq message flow before deploying worker changes; include health checks for both database connections
- Test coverage: Check `tests/integration/` for worker-specific tests
- Impact of failure: T3K catalog won't update; users can't browse new models

**Signal Chain Validation:**
- Files: `libs/core/src/core/services/signal_chain_validator.py` (301 lines)
- Why fragile: Central point for all signal chain business logic; complex validation with many edge cases
- Safe modification: Add unit tests for each validation rule before changing logic; ensure test coverage >90%
- Current coverage: Check test files in `tests/unit/core/`

**Unit of Work Pattern:**
- Files: `apps/webapp/src/webapp/adapters/persistence/unit_of_work.py`
- Why fragile: Transaction boundaries must be correctly placed or data can be lost
- Safe modification: Always test with actual database transactions; use regression tests (`tests/regression/`)
- Risk: Incorrect transaction placement leaves partial updates committed

## Scaling Limits

**Audio Processing Container Resources:**
- Current capacity: Assumes files fit in memory after resampling
- Limit: Large audio files (>500MB uncompressed) may exhaust container memory
- Container memory: Likely 2-4GB based on standard Docker defaults
- Scaling path:
  1. Implement streaming audio processing
  2. Add memory limit monitoring
  3. Consider GPU acceleration for NAM inference

**Database Connection Pool:**
- Current capacity: Not explicitly configured; likely SQLAlchemy defaults
- Limit: If many concurrent requests hit database, connection pool exhaustion possible
- Scaling path:
  1. Configure explicit pool size in connection string
  2. Monitor active connections with postgres monitoring
  3. Adjust based on concurrent user count

**Message Queue Capacity (pgmq):**
- Current capacity: PostgreSQL-backed queue; limited by disk space
- Limit: If job processing slower than submission, queue backs up indefinitely
- Scaling path:
  1. Monitor queue depth with admin endpoint
  2. Implement backpressure (reject jobs if queue >N)
  3. Add circuit breaker if workers are down

## Dependencies at Risk

**PyTorch (torch):**
- Risk: Heavy dependency; large binary size; GPU support optional
- Impact: If torch incompatibilities arise, NAM processing breaks
- Current status: Only used in audio processing
- Migration plan: Could switch to ONNX runtime if performance issues arise

**Pedalboard:**
- Risk: External audio effects library; may have platform-specific issues
- Impact: HighpassFilter and other effects won't work if library breaks
- Current status: Used for highpass filtering only; could be replaced with scipy filters
- Alternative: `scipy.signal.iirfilter` for highpass implementation

**SQLAlchemy 2.0:**
- Risk: Major version; some projects report breaking changes
- Impact: ORM queries and relationship loading could break on upgrade
- Current status: Actively used throughout persistence layer
- Mitigation: Pin exact version in requirements; test carefully before upgrading

## Test Coverage Gaps

**API Endpoint Coverage:**
- What's not tested: No API integration tests exist (endpoints don't exist yet)
- Files: Covered once endpoints implemented
- Risk: API bugs won't be caught by tests
- Priority: High - add API tests before feature release

**Worker Message Processing:**
- What's not tested: pgmq consumer logic for T3K sync messages
- Files: `apps/worker/` - check for consumer tests
- Risk: Message corruption, lost messages, or incorrect processing undetected
- Priority: High - worker reliability critical for feature

**Authentication Flow:**
- What's not tested: OAuth flow, token refresh, session management
- Files: `apps/webapp/src/webapp/auth/` (currently empty)
- Risk: Auth bugs cause security issues
- Priority: Critical - must have >95% coverage

**Frontend Navigation (data-testid):**
- What's not tested: E2E tests for Astro navigation with `data-astro-reload`
- Files: Template files in `frontend/astro/src/pages/`
- Risk: Links to SSR pages silently fail in Astro's ClientRouter
- Priority: Medium - covered by E2E tests once implemented

## Architecture & Design Issues

**API Endpoint Location Not Finalized:**
- Issue: Unclear where API routers will be defined; no pattern established
- Files: `apps/webapp/src/webapp/main.py` is minimal stub
- Impact: Different developers may create endpoints inconsistently
- Fix approach: Create `apps/webapp/src/webapp/api/v1/` directory structure with route modules

**Missing Application Services Layer:**
- Issue: Services directory exists but unclear how business logic coordinates between repositories
- Files: `apps/webapp/src/webapp/services/` (likely empty)
- Impact: Business logic may end up in repositories or endpoints
- Fix approach: Define service classes for core workflows (create shootout, process job, etc.)

**Logging Not Configured:**
- Issue: Only 1 reference to logging in entire webapp codebase
- Files: Widespread across `apps/webapp/`
- Impact: Debugging production issues will be difficult; no audit trail
- Fix approach: Add structured logging with `structlog` or `loguru`; log at service boundaries

## Missing Critical Features

**Admin API Endpoints:**
- Problem: Admin API should serve jobs, sync status, auth status endpoints from worker
- Expected location: `apps/worker/src/worker/` (check if present)
- Blocks: Ability to monitor system health and manage jobs
- Priority: Medium - needed for operations

**Job Status Webhook Callbacks:**
- Problem: No mechanism for background jobs to notify external systems of completion
- Blocks: User notifications, downstream processing
- Priority: Low - can be added later if needed

**Error Recovery & Retry Logic:**
- Problem: No clear retry strategy for failed audio processing jobs
- Blocks: Resilience against transient failures
- Priority: Medium - should implement before production

## Security Concerns

**OAuth Token Storage Security:**
- Issue: `.gts-auth.json` permissions checked, but no encryption at rest
- Files: `worktree/auth.py`
- Risk: Token file readable by any process on system with user permissions
- Current mitigation: File permissions (600) prevent other users accessing
- Recommendation: Consider OS keychain integration for production; document security model

**Missing CORS Configuration:**
- Issue: FastAPI app created but CORS not explicitly configured
- Files: `apps/webapp/src/webapp/main.py`
- Risk: Browser-based clients may be blocked or incorrectly configured
- Fix approach: Add `fastapi.middleware.cors.CORSMiddleware` with explicit origin list

**No Rate Limiting:**
- Issue: Audio processing is resource-intensive but no rate limiting implemented
- Files: `apps/webapp/` (API endpoints not yet built)
- Risk: Users could submit unlimited processing jobs, exhausting resources
- Fix approach: Implement rate limiting per user once auth is complete

**Missing Input Validation on File Uploads:**
- Issue: Audio processor checks format but file size not validated
- Files: `libs/audio/src/audio/processing/processor.py`
- Risk: Large files could exhaust container memory before processing
- Fix approach: Add maximum file size check before loading

## Deployment & Maintenance Concerns

**Astro Build Sync Between Source & Dist:**
- Issue: `frontend/astro/dist/` must stay in sync with `frontend/astro/src/`
- Files: Both `src/` and `dist/` directories
- Risk: Out-of-sync dist/ means production differs from development
- Mitigation: CI check enforces sync; `just verify-astro-sync` prevents commits
- Process: Always run `just build-astro` after template changes

**Database Migration Management:**
- Issue: Only one migration file exists; unclear how future migrations will be organized
- Files: `infrastructure/migrations/versions/b4a1fd310cb9_initial_schema.py` (932 lines - very large)
- Risk: Single large migration is difficult to debug if it fails partially
- Recommendation: Break future migrations into smaller, more focused changes

**Docker Compose Override Files Generated:**
- Issue: `docker-compose.override.yml` is auto-generated and should not be manually edited
- Files: Generated by `worktree.py setup`
- Risk: Manual edits get overwritten on next setup
- Mitigation: Enforced by infrastructure protection rules

## Recommendations (Priority Order)

| Area | Action | Priority | Effort |
|------|--------|----------|--------|
| API Endpoints | Implement missing `/api/v1/*` endpoints | Critical | High |
| Authentication | Build OAuth flow and session management | Critical | High |
| NAM Processing | Optimize sample-by-sample to batched processing | High | Medium |
| Logging | Add structured logging throughout webapp | High | Medium |
| API Tests | Create comprehensive API integration tests | High | Medium |
| CORS Configuration | Explicit CORS setup with allowed origins | High | Low |
| Rate Limiting | Per-user rate limiting on audio processing | High | Medium |
| Services Layer | Define application service classes | Medium | Medium |
| File Upload Validation | Add file size and format validation | Medium | Low |
| Keychain Integration | OS-specific credential storage for production | Medium | High |

---

*Concerns audit: 2026-02-05*


---

## Architecture Documentation

The following sections are from the project wiki:


### GTS-Technical-Architecture

# GTS Technical Architecture

Implementation architecture for Guitar Tone Shootout. For the implementation-agnostic reference, see [[REFERENCE-ARCHITECTURE]].

> **Status:** Approved — Audited and updated 2026-02-05.

---

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

## Architecture Layers

Hexagonal architecture with domain at centre. Dependencies point inward — adapters depend on domain, never reverse.

### Layer Diagram

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

### Workspace to Layer Mapping

| Layer | Location | Contents |
|-------|----------|----------|
| **Domain** | `libs/core/src/core/domain/` | Entities, aggregates, value objects |
| | `libs/core/src/core/ports/` | Protocol interfaces (repository contracts) |
| | `libs/core/src/core/services/` | Domain services (pure business logic) |
| | `libs/core/src/core/records/` | Sync record schemas (DTOs owned by core) |
| **Application** | `libs/audio/src/audio/` | Audio processing (standalone library) |
| | `libs/video/src/video/` | Video composition BC (Remotion + Python) |
| | `apps/webapp/src/webapp/services/` | Use case orchestration |
| | `apps/worker/src/worker/jobs/` | Job implementations |
| **Adapters** | `apps/webapp/src/webapp/api/` | HTTP endpoints (inbound) |
| | `apps/webapp/src/webapp/adapters/` | Persistence, file storage (outbound) |
| | `apps/webapp/src/webapp/auth/` | OAuth handlers (inbound) |
| | `sources/*/src/source_*/adapters/inbound/` | External API clients |
| | `sources/*/src/source_*/adapters/outbound/` | Queue publishers |

### Layer Responsibilities

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

### Shared Libraries Are Decoupled

`libs/` are shared libraries, not tied to any application. They can be called from:
- Web application services
- Background worker jobs
- CLI scripts
- Bulk import scripts
- Tests
- Cron jobs

This is enforced by dependency rules — `libs/audio/` depends only on `libs/core/`, never on `apps/` or `sources/`.

---

## Context Map

DDD context map showing bounded context relationships. See [[REFERENCE-ARCHITECTURE]] for the full implementation-agnostic rationale.

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
| Sources → Core | Conformist | Sources conform to core's schema. Core does not adapt to sources. |
| Webapp → Core | Customer/Supplier | Webapp consumes core's domain model. Core may evolve to serve webapp needs. |
| Sources ↔ Sources | None | Sources are isolated from each other. No direct dependencies. |

### Schema Ownership

Core owns all synchronisation record schemas (`libs/core/src/core/records/`). Source adapters import and conform to these schemas. Schema changes are validated in CI — all source adapters must pass against the current core schema before merge.

---

## Design Patterns

Persistence and domain patterns used throughout GTS. These implement the patterns defined in [[REFERENCE-ARCHITECTURE]] with GTS-specific technology choices.

### Persistence Pattern Summary

| Pattern | Purpose | Location |
|---------|---------|----------|
| **Repository (DDD)** | Aggregate-oriented data access behind protocol interfaces | `core/ports/` → `webapp/adapters/persistence/repositories/` |
| **DataMapper** | Separate ORM models from domain entities; repositories translate between them | `webapp/adapters/persistence/repositories/*` (`_to_entity()` methods) |
| **Unit of Work** | Transaction boundaries managed by session; explicit commit semantics | `webapp/adapters/persistence/unit_of_work.py` |
| **DTO** | Models for data crossing boundaries (sync records, API payloads) | `core/records/`, `webapp/schemas/` |

### Repository Pattern

Aggregate-oriented data access behind protocol interfaces. Presents collection semantics ("in-memory collection of aggregates"). One repository per aggregate root.

**Ports (Domain Layer):** `libs/core/src/core/ports/repositories.py`

| Repository | Aggregate | Purpose |
|------------|-----------|---------|
| `UserRepository` | User | User identity and profile operations |
| `GearRepository` | Gear | Unified gear model across all sources |
| `DITrackRepository` | DITrack | DI track persistence |
| `SignalChainRepository` | SignalChain | Signal chain and block persistence |
| `SignalChainGroupRepository` | SignalChainGroup | Chain group persistence |
| `ShootoutRepository` | Shootout | Shootout with chains |
| `JobRepository` | Job | Background job tracking |
| `AuditRepository` | — | Audit logging |

**Implementations (Adapter Layer):** `apps/webapp/src/webapp/adapters/persistence/repositories/`

**Key Characteristics:**
- Protocol-based (dependency inversion — domain depends on protocol, not implementation)
- Aggregate-oriented queries (business-focused, not table-oriented)
- Eager loading with `selectinload()` to prevent N+1 queries
- Full CRUD operations with complex queries
- Hides all persistence details from domain layer

### DataMapper Pattern

Domain entities are persistence-ignorant. ORM models and domain entities are **always separate classes**. Repositories handle translation between them.

**Domain entities** (`libs/core/src/core/domain/entities/`):
- Pure Python dataclasses, no framework imports
- Identity-based equality (`__eq__` compares IDs)
- Business methods that enforce invariants
- No `save()`, `load()`, or any persistence awareness

**ORM models** (`apps/webapp/src/webapp/adapters/persistence/models/`):
- SQLAlchemy 2.0 mapped classes
- Relationships, foreign keys, indexes
- Concern: storage schema only

**Mapping** (`apps/webapp/src/webapp/adapters/persistence/repositories/`):
- Each repository has `_to_entity()` for ORM → domain conversion
- `save()` methods handle domain → ORM conversion
- Mapping logic lives in repositories, not in a separate mapper class

```python
# Repository maps between ORM and domain
class SQLAlchemyUserRepository:
    def _to_entity(self, orm_user: UserModel) -> UserEntity:
        """ORM → Domain: construct domain entity from ORM model."""
        identities = [
            UserIdentityVO(
                provider=identity.provider.name,
                external_id=identity.external_id,
            )
            for identity in orm_user.identities
        ]
        return UserEntity(
            id=orm_user.id,
            username=orm_user.username,
            identities=identities,
        )

    async def save(self, user: UserEntity) -> None:
        """Domain → ORM: persist domain entity via ORM model."""
        existing = await self.session.get(UserModel, user.id)
        if existing:
            existing.username = user.username
            # ... update fields
        else:
            self.session.add(UserModel(id=user.id, ...))
```

### Unit of Work

Manages database transaction boundaries with explicit commit semantics.

**Location:** `apps/webapp/src/webapp/adapters/persistence/unit_of_work.py`

**Usage:**
```python
async with UnitOfWork(session_factory) as uow:
    user = await user_repository.get_by_id(user_id)
    user.email = "new@example.com"
    await user_repository.save(user)
    await uow.commit()  # Explicit commit required
```

**Key Characteristics:**
- Async context manager protocol (`__aenter__`/`__aexit__`)
- Explicit `commit()` required for changes to persist
- Automatic rollback on exception
- Default rollback if not committed (fail-safe)
- Session lifecycle managed by UoW, not repositories

**Transaction Rule:** Services own transactions. Repositories receive sessions but don't create or commit them.

### DTO (Data Transfer Object)

Models for data crossing system boundaries. Validated at the edge, immutable in transit.

| DTO Type | Location | Purpose |
|----------|----------|---------|
| Sync records | `libs/core/src/core/records/` | Gear sync messages between source adapters and core consumer |
| API schemas | `apps/webapp/src/webapp/schemas/` | HTTP request/response validation (Pydantic) |
| Value objects | `libs/core/src/core/domain/value_objects/` | Immutable domain concepts (AudioResult, ToneConfig, etc.) |

**Sync records** are owned by core and imported by source adapters (Conformist pattern). Source adapters must construct valid `GearSyncRecord` instances — core rejects invalid records.

### Aggregate Identity

Each aggregate instance in the sync pipeline is owned by exactly one source. Aggregate identity is source-scoped.

**Composite key:** `(source_name, source_record_id)`

Core persists source identity for traceability and audit. Cross-source merging is **not performed in the ingestion pipeline**. If multiple sources describe the same real-world entity (e.g., two sources both provide data about "Fender Twin Reverb"), they are treated as separate aggregate instances. Entity resolution, if required, is a downstream concern handled by read models.

### Domain Services

Pure business logic with zero framework dependencies.

**Location:** `libs/core/src/core/services/`

| Service | Purpose |
|---------|---------|
| `SignalChainValidator` | Validates signal chain grammar (amp placement, IR requirements) |
| `PermutationCalculator` | Calculates gear permutations for comparisons |

**Key Characteristics:**
- Stateless services
- No database access — pure calculations
- Returns value objects, not ORM models
- Testable without infrastructure

### Anti-Patterns to Avoid

These patterns are explicitly prohibited. See [[REFERENCE-ARCHITECTURE]] §Persistence Patterns for rationale.

| Anti-Pattern | Description | Violation Example |
|--------------|-------------|-------------------|
| **DAO masquerading as Repository** | Table-oriented CRUD instead of aggregate-oriented access | `get_all_rows()`, `find_by_column()` without aggregate context |
| **Active Record** | Domain entities coupled to persistence (`entity.save()`) | Adding SQLAlchemy imports to `libs/core/` |
| **Exposing ORM outside service layer** | ORM models leaked to API routes or templates | Returning `UserModel` from a route handler instead of a schema |
| **Business logic in persistence** | Validation or rules in repository or ORM model | Computing signal chain validity inside a repository query |

### Docker-First Development

All project code executes in Docker containers. The host environment is only for E2E tests and host tooling.

**Execution Matrix:**

| Code Type | Runs In | Command |
|-----------|---------|---------|
| Lint, type check | Docker | `just check` |
| Unit tests | Docker | `just test-unit` |
| Integration tests | Docker | `just test-integration` |
| Migrations | Docker | `just migrate` |
| Python REPL | Docker | `just repl` |
| E2E tests | **Host** | `just test-golden-path` |
| Git, GitHub CLI | Host | `git`, `gh` |
| Worktree management | Host | `./worktree.py` |

**Why Docker-First:**
- Consistent environment across all machines
- Exact dependency versions controlled
- CI parity — same commands work in GitHub Actions
- No local Python/Node version conflicts

**NEVER run on host:**
```bash
# WRONG
uv run pytest tests/unit/
uv run ruff check
pytest tests/

# RIGHT
just test-unit
just check
just tdd tests/unit/path/test.py
```

The only `uv run` on host is for E2E tests in `tests/e2e/python/`.

---

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

## File Storage

Docker volume (`gts-storage`) — existing from archive with synced T3K files.

### Storage Layout

```
/app/storage/
├── models/          # Downloaded gear models (NAM, IR files)
├── uploads/
│   ├── di_tracks/   # User-uploaded guitar recordings
│   └── irs/         # User-uploaded impulse responses
├── audio/           # Processed audio segments
└── videos/          # Generated shootout comparison videos
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

## Video Generation

Video composition combines audio segments into comparison videos. Implemented in `libs/video/` as a separate bounded context (see [[GTS-Remotion-Architecture]]).

### Purpose

Videos enable side-by-side tone comparisons:
- Sequential playback of each tone
- Visual waveforms for each segment
- Labels identifying gear used
- YouTube chapter markers for navigation

### Composition Pipeline

```
Audio Segments + Metadata
    ↓
Generate waveform visualizations (per segment)
    ↓
Render title card (gear list, DI track info)
    ↓
Compose video frames (waveform + labels)
    ↓
Concatenate segments with transitions
    ↓
Encode final video (MP4)
    ↓
Generate chapter data (for YouTube)
```

### Remotion

Video composition uses Remotion (React-based) for:
- Programmable video layout with React components
- Signal chain segment visualisation with gear images
- Slide transitions between segments (3-frame / 100ms)
- Metadata overlays (gear labels, chapter markers)

Server-side rendering via `@remotion/renderer` in a Docker container (Node.js + Chromium). Worker communicates via HTTP (`POST /render` + poll).

**Output format:** MP4 (H.264 video, AAC 256-320kbps) — YouTube optimised, 1920×1080 @ 30fps.

### Segment Metadata

Each audio segment carries metadata for video composition:

| Field | Purpose |
|-------|---------|
| `segment_id` | Unique identifier |
| `label` | Display name (e.g., "Amp₁ + IR₂") |
| `start_time` | Position in final video |
| `duration` | Segment length |
| `gear_info` | Amp, IR, effects used |

### Job Hierarchy

Video generation is a child job of SHOOTOUT:

```
SHOOTOUT (parent)
├── SHOOTOUT_AUDIO (tone A)
├── SHOOTOUT_AUDIO (tone B)
├── SHOOTOUT_AUDIO (tone C)
└── VIDEO_COMPOSE (after all audio complete)
```

VIDEO_COMPOSE waits for all SHOOTOUT_AUDIO jobs to complete before starting.

### Current State

| Feature | Status |
|---------|--------|
| Waveform visualization | Exists |
| Gear labels | Exists |
| Gear images | Exists |
| Video layout | Exists (basic) |
| Chapter markers | Exists |

### Implementation Notes

Layout and visual refinements will be done interactively during implementation. The foundation works — aesthetic improvements are iterative.

---

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

## Testing Strategy

Testing uses pytest with Playwright for browser automation. The suite is structured in layers, with regression tests providing fast stack validation and E2E tests validating user journeys.

### Test Levels

| Level | Purpose | Infrastructure | Location |
|-------|---------|----------------|----------|
| Regression | Stack connectivity (ORM → Repo → DB) | SQLite in-memory | `tests/regression/` |
| Unit | Domain logic, validators | None | `tests/unit/` |
| Integration | Repository operations, services | Real PostgreSQL/Redis | `tests/integration/` |
| E2E | User journeys, UI flows | Browser + full stack | `tests/e2e/python/` |

### Regression Tests

Fast validation that the ORM → Repository → Database stack works correctly:

- **User round-trip** — Create, save, retrieve by ID/email/identity
- **Job round-trip** — Create, save, state transitions, retrieve
- Uses SQLite in-memory for speed (~0.2s)
- Run before commits to catch fundamental breaks

```bash
just test-regression  # Stack connectivity (< 1s)
```

### Three-Layer E2E Validation

E2E tests validate each interaction at three levels:

1. **UI Action** — Navigate and interact like a real user
2. **DOM Update** — Assert visible state changes
3. **Database State** — Verify data persistence

This pattern catches issues at any layer: frontend rendering, API communication, or data persistence.

### Mocking Policy

**No mocking.** Tests use real services — real databases, real Redis, real T3K API, real pgmq. The `test_quality_check.py` gate bans all `unittest.mock` imports with zero exceptions.

| Category | Approach |
|----------|----------|
| PostgreSQL | Real database (SQLite in-memory for unit/regression, PostgreSQL for integration) |
| Redis | Real Redis instance in Docker |
| T3K API | Real T3K API with auth tokens |
| pgmq | Real pgmq extension in PostgreSQL |

**Rationale:** Mocking hides integration bugs. Real services catch schema mismatches, connection problems, auth failures, and timing issues that mocks would mask. All GTS services are available in the Docker test environment.

### Running Tests

```bash
just test-regression  # Stack connectivity (< 1s) - before commits
just test             # Unit + Integration (< 30s) - before PRs
just tdd <path>       # Single test during development
just test-golden-path         # E2E (when frontend works)
```

### Contract Tests

Core schemas (`libs/core/records/`) are treated as contracts between bounded contexts:

- All source adapters validate output against current core schemas in CI.
- Compatibility checks ensure new schema versions meet backward-compatibility requirements.
- Breaking changes fail source adapter tests immediately, preventing deployment of incompatible adapters.

**Example:** `GearSyncRecord` is the contract between source adapters and core. If a required field is added, source adapter tests break until the adapter populates it.

### Data Quality Tests

Automated data quality validation at the persistence boundary:

| Expectation | What It Checks |
|-------------|----------------|
| Schema | Required columns exist, types correct |
| Completeness | Non-null constraints on mandatory fields |
| Uniqueness | Composite key uniqueness (`source_name` + `source_record_id`) |
| Distribution drift | Key field value distributions remain within expected ranges |

Quality test failures increment the `data_quality_quarantine_total` metric and prevent bad data from reaching consumers.

### Replay Tests

Replay and recovery workflows are exercised with realistic data volumes:

- **Reingest workflows** — Bulk reingest exercised with full pack catalogs to verify idempotent upserts produce identical state.
- **Checkpoint resume** — Simulated failures mid-sync verify that checkpoint recovery resumes from the correct position without data loss or duplication.
- **DLQ replay** — Partial failure recovery tested: poison messages isolated, remaining messages redriven and processed successfully.

### E2E Canary Tests

Synthetic validation of the complete ingestion pipeline:

- **Canary Source** — Generates predictable data patterns (known pack counts, model names, checksums).
- **Critical path verification** — Validates fetch → transform → enqueue → consume → persist in staging.
- **Scheduled verification** — Core database queried on schedule to confirm canary data arrived within SLO freshness target.

Canary test failures trigger P2 alerts (significant degradation).

**Forbidden Patterns (enforced by `.claude/rules/testing-policy.md`):**

```python
@patch('app.repositories.signal_chain_repo')  # NEVER mock internal services
mock_service = Mock(spec=SignalChainService)   # NEVER mock internal services
page.route('**/api/**', ...)                   # NEVER mock API in E2E tests
```

Mock ONLY external network APIs (Tone3000, email, payment).

**Reference:**
- Markers defined in `tests/conftest.py`
- Fixtures in `tests/fixtures/`
- Structure documented in `tests/AGENTS.md`
- TDD workflow documented in [[TDD-Workflow]] wiki page

---

## Observability

### Logging (structlog)

Structured logging via structlog with JSON output:
- Context binding (`logger.bind(user_id=123)`)
- OpenTelemetry correlation (trace_id, span_id)
- Sensitive data filtering (passwords, tokens, credentials redacted)

**Mandatory context:** request_id, user_id, trace_id (where applicable).

structlog bridges to OpenTelemetry via stdlib integration for unified log export.

### Tracing (OpenTelemetry)

Distributed tracing with OTLP export:

| Auto-instrumented | Attributes |
|-------------------|------------|
| FastAPI requests | http.method, http.route, http.status_code |
| SQLAlchemy queries | db.system, db.statement, db.operation |
| HTTPX outbound | http.url, http.status_code |
| Redis commands | db.system, db.statement |

Trace context propagation to background workers via inject/extract.

### Metrics (OpenTelemetry → Prometheus)

OpenTelemetry SDK for instrumentation, exported to Prometheus for storage and PromQL querying.

| Category | Examples |
|----------|----------|
| **HTTP** | Request count, latency, in-progress by method/route/status |
| **Business** | Shootouts created/processed, signal chains, gear items |
| **Jobs** | Queue depth, in-progress count |
| **External APIs** | T3K request count, latency, error rates |
| **Infrastructure** | DB connection pool, circuit breaker state |

### Health Checks

| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `/health` | Liveness probe | Process alive |
| `/health/ready` | Readiness probe | Database, external APIs |

**Graceful shutdown:** Returns 503 during shutdown for load balancer draining.

**Status levels:** HEALTHY, DEGRADED, UNHEALTHY.

### SLIs and SLOs

Service Level Indicators and Objectives for the ingestion pipeline. Each aggregate or source declares its freshness and completeness SLO targets.

| Category | SLI | Target | Measurement |
|----------|-----|--------|-------------|
| **Freshness** | Time from source change detection to core persistence | 99% of sources within 15 minutes | `data_freshness_seconds` gauge |
| **Completeness** | Record counts per source/interval against expected bands | Anomaly-based | `ingest_completion_rate` |
| **Reliability** | Sync attempts that succeed | 99.9% | `sync_records_total{status="success"}` / total |
| **Quality** | Records passing validation | > 99% | `validation_failure_rate` |

Alerts are based on SLO breach and error budgets.

### Alerting Strategy

- Multi-window burn-rate alerting to prevent fatigue
- Error budget consumption alerts
- Stale source detection (no updates in N minutes, configurable per source)
- Queue depth warnings

### Dashboards

**Pipeline Overview:**
- Total throughput (records/min)
- Error rate trend
- Source status summary (healthy/degraded/stale)

**Source Health:**
- Per-source latency distribution
- Per-source error rates
- Last sync timestamps

**Queue Health:**
- Queue depth over time
- Consumer lag trends
- DLQ accumulation

---

## Configuration

Configuration follows 12-Factor methodology. All settings come from environment variables, with Pydantic Settings handling validation and type coercion.

### Environment Variables

| Category | Variables | Required |
|----------|-----------|----------|
| **Application** | `DEBUG`, `APP_NAME`, `APP_URL`, `FRONTEND_URL` | No (defaults) |
| **Database** | `DATABASE_URL` or `DB_PASSWORD` + components | Yes |
| **Redis** | `REDIS_URL` | No (default: `redis://redis:6379`) |
| **Security** | `SECRET_KEY`, `OAUTH_ENCRYPTION_KEY` | Production only |
| **OAuth** | `{PROVIDER}_CLIENT_ID`, `{PROVIDER}_CLIENT_SECRET` | Per-provider |
| **Storage** | `STORAGE_ROOT`, `MODEL_CACHE_DIR`, `UPLOAD_DIR`, `SEGMENTS_DIR`, `VIDEOS_DIR` | No (defaults) |
| **Observability** | `OTLP_ENDPOINT`, `LOG_LEVEL`, `LOG_FORMAT`, `METRICS_ENABLED` | No |
| **Sources** | Per-source API credentials, rate limits, sync schedules | Per-source |

### Secrets Management

| Environment | Mechanism |
|-------------|-----------|
| Development | `.env` file (gitignored) |
| Production | Platform secrets (injected at runtime) |
| Docker | `{NAME}_FILE` pattern (reads from `/run/secrets/`) |

**Supported Docker secrets:** `SECRET_KEY_FILE`, `DB_PASSWORD_FILE`, `OAUTH_ENCRYPTION_KEY_FILE`

**Token encryption:** Fernet symmetric encryption for OAuth tokens at rest.

### Production Validation

Production mode (`DEBUG=false`) enforces:
- `SECRET_KEY` must not be default value
- `OAUTH_ENCRYPTION_KEY` must be set
- `DATABASE_URL` or `DB_PASSWORD` must be set

Development mode logs warnings but continues with defaults.

### Per-Source Configuration

Each source adapter has independent configuration:

| Setting | Purpose |
|---------|---------|
| API endpoint | External API URL |
| API credentials | Injected via secrets (not in code) |
| Sync schedule | Cron expression for incremental sync |
| Batch size | Records per bulk operation |
| Rate limits | Requests per window |
| Retry limits | Max attempts before failure |
| Timeouts | Connection and operation limits |

### Configuration Precedence

1. Environment variable (highest)
2. Docker secret file (`{NAME}_FILE`)
3. `.env` file
4. Default value (lowest)

---

## Error Handling & Resilience

### Retry Strategies

External API calls use bounded retries with exponential backoff and full jitter to prevent thundering herd.

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max attempts | 5 | Sufficient for transient failures |
| Base delay | 60s | Allows temporary issues to resolve |
| Backoff formula | `base × 2^(attempt-1)` + jitter | Exponential spacing with randomisation |
| Jitter | Full (0 to delay) | Distributes retry load |

**Retry only transient errors:**
- Network failures (timeout, connection refused)
- Rate limits (429)
- Server errors (5xx)

**Do not retry:**
- Client errors (4xx except 429)
- Authentication failures (401 after token refresh attempt)
- Validation errors

### Circuit Breaker

Circuit breakers protect against cascading failures when external services are unavailable.

| State | Behaviour |
|-------|-----------|
| **Closed** | Requests pass through; failures counted |
| **Open** | Requests rejected immediately; return cached/degraded response |
| **Half-open** | Single probe request allowed; success closes, failure reopens |

**Configuration:**
- Failure threshold: 5 consecutive failures to open
- Recovery timeout: 30 seconds before half-open probe
- Scope: Per external source (not global)

Circuit breakers wrap retry logic—when open, retries are skipped entirely.

### Rate Limiting

**External APIs:**
- Respect rate limit headers (`X-RateLimit-*`, `Retry-After`)
- Adaptive throttling on 429 responses
- Token bucket algorithm for smooth request distribution
- Redis-backed for coordination across processes

**Source Ingestion:**
- Source sync jobs respect configured rate limits per source
- Adaptive throttling when approaching limits
- Metrics emitted for rate limit events (`source_rate_limit_total`)

**Internal APIs:**
- Bulk ingest endpoints rate-limited per source
- Batch size limits per request
- Payload size limits enforced

### Backpressure

Backpressure prevents sources from overwhelming the core consumer:

- **Bounded queue size** — pgmq queue depth monitored; sources pause publishing when depth exceeds threshold.
- **Adaptive batch sizing** — Consumer batch size decreases when processing latency increases.
- **Metrics emitted** — `queue_backpressure_applied_total` incremented when backpressure engages, enabling alerting and capacity planning.

### Job Failure Handling

Background jobs follow a defined failure lifecycle:

```
RUNNING → FAILED → [retry if attempts remain] → PENDING
                → [max attempts reached] → DEAD_LETTERED
```

**Retry scheduling:**
- Jobs marked FAILED with `next_retry_at` timestamp
- Scheduler polls for jobs ready for retry
- Exponential backoff between attempts

**Dead-letter handling:**
- Jobs exceeding max attempts enter DEAD_LETTERED state
- Require manual investigation via admin tooling
- Can be reset for retry after root cause resolution

### Heartbeat Monitoring

Long-running jobs emit heartbeats to detect worker crashes:

| Parameter | Value |
|-----------|-------|
| Heartbeat interval | 30 seconds |
| Stale threshold | 5 minutes |
| Detection frequency | 2 minutes |

Jobs with stale heartbeats are marked FAILED and scheduled for retry.

### Partial Failure Handling

Batch operations handle partial failures gracefully:

- Per-item errors logged with context (record ID, error type, message)
- Successful items committed; failed items tracked
- Configurable: retry failed subset vs full batch retry
- Alerting when failure rate exceeds threshold

### Graceful Degradation

When external services are unavailable:

| Component | Degradation Strategy |
|-----------|----------------------|
| T3K API unavailable | Serve cached gear data; disable sync |
| Job queue full | Apply backpressure; return 503 to new requests |
| Database read replica lag | Route to primary for consistency-critical reads |

### Error Classification

Errors are classified for appropriate handling:

| Category | Examples | Action |
|----------|----------|--------|
| **Transient** | Network timeout, rate limit | Retry with backoff |
| **Permanent** | Validation error, not found | Fail immediately |
| **Auth** | Token expired | Attempt refresh, then fail |
| **System** | Out of memory, disk full | Alert; manual intervention |

---

## Security

Security architecture following OWASP guidelines.

### Authentication

Delegated to external identity providers via OAuth 2.1:

| Aspect | Approach |
|--------|----------|
| **Flow** | Authorization code + PKCE (S256) |
| **Credential storage** | None — IdP manages all credentials |
| **GTS responsibility** | Validate OAuth callback, issue token |
| **Providers** | Configurable (T3K, Google, GitHub, etc.) |

Token-based authentication (stateless):

| Aspect | Approach |
|--------|----------|
| **Token storage** | `.gts-auth.json` file (shared across worktrees) |
| **Token transfer** | Browser login, token copied to server via scp |
| **Validation** | Stateless token validation on each request |
| **No sessions** | No server-side session state, no Redis for webapp |

GTS stores only the user's identity (ID, email, display name) and encrypted OAuth tokens in the auth file.

### Authorisation

Write-path protection — users can only modify their own resources:

| Resource | Read Access | Write Access |
|----------|-------------|--------------|
| Shootouts | Public | Owner only |
| Audio segments | Public | Owner only |
| Signal chains | Public | Owner only |
| DI tracks | Public or private (user choice) | Owner only |

Implementation:
- Write operations filter by `user_id`
- Error responses return 404 for unauthorised writes (no existence leakage)
- Admin APIs network-isolated (no authentication layer)

### Transport Security

| Layer | Requirement |
|-------|-------------|
| TLS | 1.2 minimum, 1.3 preferred |
| HSTS | Enabled in production |
| Certificate | Managed by reverse proxy |

### Input Validation

All user input validated at API boundaries:

| Layer | Mechanism |
|-------|-----------|
| **API schemas** | Pydantic models with constraints |
| **Database** | SQLAlchemy ORM (parameterised queries) |
| **File uploads** | Type validation, size limits, sanitised names |

### Output Encoding

XSS prevention via auto-escaping:

| Template engine | Auto-escaping | Avoid |
|-----------------|---------------|-------|
| Jinja2 | Enabled | `| safe` filter |
| Astro | Enabled | `set:html` |
| React | Enabled | `dangerouslySetInnerHTML` |

### Security Headers

Configured at reverse proxy:

| Header | Value |
|--------|-------|
| `Content-Security-Policy` | Restrictive policy |
| `X-Frame-Options` | DENY |
| `X-Content-Type-Options` | nosniff |
| `Referrer-Policy` | strict-origin-when-cross-origin |
| `Strict-Transport-Security` | max-age=31536000; includeSubDomains |

### Secret Management

| Category | Storage |
|----------|---------|
| Database credentials | Environment variables |
| Session secret | Environment variables |
| OAuth client ID/secret | Environment variables |

Rules:
- No secrets in source control or logs
- Environment-specific configuration

### Dependency Security

| Tool | Scope | Frequency |
|------|-------|-----------|
| `pip-audit` | Python dependencies | CI + weekly |
| `npm audit` | Node dependencies | CI + weekly |
| `gitleaks` | Secret detection | Pre-commit + CI |

### Audit Trail

Security events logged:

| Event | Logged Data |
|-------|-------------|
| Authentication success/failure | Provider, timestamp |
| Authorisation failure | User ID, resource, action |

---

## Consistency & Concurrency

### Data-Level Concurrency

Idempotent upsert with timestamp handles concurrent writes safely. Last-write-wins by source timestamp. No optimistic locking required for sync records because source timestamps provide natural ordering.

For user-created entities (signal chains, shootouts), standard database-level isolation (READ COMMITTED) provides sufficient concurrency control.

### Job-Level Concurrency

Single job per source. Scheduler configuration prevents overlapping runs via Redis distributed locks.

**Future optimisation path:** For high-volume backfills, internal parallelism (concurrent processing within a single job) or source partitioning into multiple jobs can increase throughput without sacrificing ordering guarantees.

### Orchestration Control

Both sides of ingestion are managed internally. Complex operations (migrations, recovery) follow defined sequences documented in [[#Operations & Runbooks]].

---

## Data Quality & Validation

### Source Validation

Source adapters validate required fields before emitting sync records:
- Required fields present and non-null
- Field types and ranges correct
- File integrity verified (checksums match)

Invalid records are rejected or quarantined with reason before reaching the queue.

### Core Validation

Core enforces schema validation on ingest:
- `GearSyncRecord` validated against Pydantic schema
- Required fields enforced
- Referential integrity checked

### Quality Metrics

Data quality metrics tracked per source:

| Metric | Purpose |
|--------|---------|
| Null rates on required fields | Detect source data degradation |
| Range checks on numeric fields | Catch invalid values |
| Distribution drift detection | Alert on unexpected data patterns |
| Pass/fail ratios on validation rules | Track overall quality trend |

### Quarantine

Records failing validation are quarantined for investigation:
- Quarantine includes original payload and failure reason
- Reprocessing workflow for fixed records
- Dead-letter queue for messages that fail after max retries (see [[#Message Queue (pgmq)]])

---

## Retention & Lifecycle

### Retention Policies

| Data | Retention | Rationale |
|------|-----------|-----------|
| Source staging data | 90 days | Debugging, reingest capability |
| Core domain data | Indefinite | Primary application data |
| Sync audit logs | 1 year | Compliance, debugging |
| Queue messages | Until consumed + 7 days archive | Recovery capability |
| Checkpoints | 30 days | Sufficient for recovery |
| DLQ messages | 30 days | Investigation window |

### Archival

- Completed sync records archived to cold storage after retention period
- Archived data queryable but not in hot path
- Queue archives retained for bounded period aligned with recovery requirements

### Deletion Workflows

- Core records follow lifecycle policies
- Support deletion workflows where required (e.g., GDPR requests)
- PII handling follows explicit classification and retention rules

---

## Operations & Runbooks

### Graceful Shutdown

**Consumer shutdown sequence:**
1. **Receive SIGTERM** — Stop accepting new messages
2. **Drain in-flight** — Complete processing of active messages
3. **Commit checkpoints** — Persist final offsets before exit
4. **Close connections** — Release database and queue connections
5. **Exit cleanly** — Return exit code 0

**Job scheduler shutdown:**
1. Stop scheduling new jobs
2. Wait for running jobs to complete (or timeout)
3. Persist scheduler state
4. Exit cleanly

### Failure Scenarios

| Scenario | Detection | Response |
|----------|-----------|----------|
| Consumer crash | Missing heartbeat, lag growth | Auto-restart, verify checkpoint resume |
| External API down | Circuit breaker open | Wait for recovery, catchup sync |
| Queue overflow | Depth metric spike | Scale consumers or pause sources |
| Poison message | Repeated DLQ entries | Isolate message, fix or archive |
| Schema mismatch | Validation errors spike | Deploy compatible consumers, drain |
| Database unavailable | Connection errors | Failover or wait for recovery |

### DLQ Processing

1. Monitor DLQ depth (alert if > threshold)
2. Sample messages, classify failure type
3. **Transient:** Wait for recovery, then redrive
4. **Permanent:** Fix data or archive with reason
5. **System bug:** Deploy fix first, then redrive
6. Verify DLQ emptying, main processing succeeding

### Incident Classification

| Severity | Impact | Response Time |
|----------|--------|---------------|
| P1 | Complete pipeline failure | < 15 minutes |
| P2 | Significant degradation, SLA breach | < 1 hour |
| P3 | Minor impact, single consumer issue | < 4 hours |
| P4 | Low impact, non-critical | Next business day |

### Disaster Recovery

**Recovery Targets:**

| Tier | Data | RTO | RPO |
|------|------|-----|-----|
| Critical | Core database (users, shootouts, chains) | < 1 hour | < 15 minutes (checkpoint frequency) |
| High | Source staging data (T3K packs, models) | < 4 hours | Last successful sync checkpoint |
| Normal | Queue state, job history | < 8 hours | Replay from source checkpoints |

**Recovery Strategy:**
1. Restore core database from latest backup
2. Restore queue state or replay from source checkpoints
3. Reingest from source staging data if needed
4. Verify data consistency post-recovery (canary tests + quality checks)

**Backup Requirements:**
- Regular database backups with tested restore procedures
- Checkpoint data retained for the full recovery window
- Source staging data retained for reingest capability
- Restore procedures exercised quarterly (at minimum)

---

## References

- [[REFERENCE-ARCHITECTURE]] - Implementation-agnostic patterns
- [Archive Wiki](https://github.com/krazyuniks/guitar-tone-shootout-archive/wiki) - Previous implementation
- Archive codebase: `guitar-tone-worktrees-archive-20260202/main/`


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
