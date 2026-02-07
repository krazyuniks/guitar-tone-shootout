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
