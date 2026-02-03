---
created: 2026-02-03T03:15:00Z
github_issue: null
source: https://github.com/krazyuniks/guitar-tone-shootout/wiki/IMPLEMENTATION
---

# Phase 3: Adapter Implementation

Implementation of three parallel adapter sub-phases that build on the core domain (Phase 2).

## Problem Statement

The core domain layer (`libs/core/`) defines entities, value objects, and port protocols but has no concrete implementations. Phase 3 delivers the adapter layer:

- **3A (Persistence):** SQLAlchemy ORM models and repository implementations for `gts_core` database
- **3B (Audio):** Audio processing library implementing the `AudioProcessor` protocol
- **3C (Frontend):** Astro build system for templates and static assets

These three sub-phases modify distinct directories and can execute in parallel:
- 3A: `apps/webapp/src/webapp/adapters/persistence/` and `infrastructure/migrations/`
- 3B: `libs/audio/src/audio/`
- 3C: `frontend/astro/`

## Success Criteria

- [ ] All ORM models with relationships pass protocol compliance tests
- [ ] Repositories implement all methods from `libs/core/ports/repositories.py`
- [ ] Alembic migrations create complete `gts_core` schema
- [ ] Audio processor implements `AudioProcessor` protocol with async support
- [ ] NAM model loading with LRU caching functional
- [ ] Loudness normalization (EBU R128) operational
- [ ] Astro builds successfully to `frontend/astro/dist/`
- [ ] Tailwind CSS compiles with design tokens
- [ ] Base Jinja2 wrapper generates valid HTML
- [ ] Static pages (index, about, login) render correctly
- [ ] `just check` passes (lint, types, tests)
- [ ] Wiki documentation updated for all three sub-phases

## Execution Guidelines

### Test-Driven Development (MANDATORY)

**Every story MUST follow Red-Green-Refactor:**

1. **RED - Write failing tests FIRST**
   - Before writing ANY implementation code, write tests for the story's acceptance criteria
   - Run the tests - they MUST fail (if they pass, you're not testing new behaviour)

2. **GREEN - Implement to pass**
   - Write the minimum code to make your tests pass
   - Run tests frequently during implementation

3. **REFACTOR - Clean up (if needed)**
   - Improve code quality while keeping tests green

### Archive Reference

Archive code at `../../guitar-tone-worktrees-archive-20260202/main/` provides reference implementations:

| Archive Path | Target | Classification |
|--------------|--------|----------------|
| `backend/app/models/*.py` | `apps/webapp/src/webapp/adapters/persistence/models/` | REFACTOR |
| `backend/app/adapters/persistence/*.py` | `apps/webapp/src/webapp/adapters/persistence/` | REFACTOR |
| `backend/app/adapters/processing/pedalboard_audio.py` | `libs/audio/src/audio/processing/` | REFACTOR |
| `backend/app/adapters/processing/nam_loader.py` | `libs/audio/src/audio/processing/` | REFACTOR |
| `backend/app/adapters/processing/ir_loader.py` | `libs/audio/src/audio/processing/` | REFACTOR |
| `astro/astro.config.mjs` | `frontend/astro/` | REFACTOR |
| `astro/src/styles/global.css` | `frontend/astro/src/styles/` | REFACTOR |
| `astro/src/layouts/` | `frontend/astro/src/layouts/` | REFACTOR |
| `astro/src/pages/*.astro` | `frontend/astro/src/pages/` | REFACTOR |

### Container Execution

All commands run in containers via `just`:
- Backend: `docker compose exec backend <command>`
- Astro: `just build-astro` or `just watch-astro`
- Tests: `just tdd <path>`

### Background Agents

Use `Task` tool with `run_in_background: true` for parallel work:
- `Explore` agent for codebase research
- `Bash` agent for running tests in background

---

## User Stories

### STORY-001: ORM Base Infrastructure

**As a** developer
**I want** SQLAlchemy base classes and type utilities
**So that** all ORM models have consistent patterns

**Acceptance Criteria:**
- [ ] `Base` declarative base class with naming conventions
- [ ] `UUIDMixin` for UUIDv7 primary keys
- [ ] `TimestampMixin` for `created_at`/`updated_at`
- [ ] `EnumByValue` type for enum storage by value
- [ ] Session factory with async support
- [ ] Typecheck passes
- [ ] Unit tests pass

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/base.py`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/types.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/models/base.py`
- Use SQLAlchemy 2.0 mapped_column syntax

---

### STORY-002: Astro Project Configuration

**As a** developer
**I want** Astro configured with TypeScript and Tailwind
**So that** the frontend build system is operational

**Acceptance Criteria:**
- [ ] `astro.config.mjs` with static output mode
- [ ] TypeScript configuration (`tsconfig.json`)
- [ ] Tailwind integration configured
- [ ] `package.json` with build scripts
- [ ] Output directory set to `frontend/astro/dist/`
- [ ] `just build-astro` succeeds
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/astro/astro.config.mjs`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/astro/package.json`
- Target: `frontend/astro/`
- Docker container runs astro via `--profile build`

---

### STORY-003: Tailwind Design System

**As a** developer
**I want** Tailwind CSS with GTS design tokens
**So that** consistent styling is available across all pages

**Acceptance Criteria:**
- [ ] `global.css` with CSS custom properties (design tokens)
- [ ] Background colors: `--color-bg-base`, `--color-bg-surface`, `--color-bg-elevated`
- [ ] Text colors: `--color-text-primary`, `--color-text-secondary`, `--color-text-muted`
- [ ] Accent colors: `--color-accent-primary`, `--color-accent-success`, etc.
- [ ] Block type colors: `--color-block-amp`, `--color-block-pedal`, etc.
- [ ] `tailwind.config.mjs` extends theme with tokens
- [ ] CSS compiles without errors
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/astro/src/styles/global.css`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/astro/tailwind.config.mjs`
- Target: `frontend/astro/src/styles/global.css`

---

### STORY-004: NAM Model Loader with Caching

**As a** developer
**I want** NAM model loading with LRU caching
**So that** repeated processing uses cached models efficiently

**Acceptance Criteria:**
- [ ] `load_nam_model(path)` function loads .nam files
- [ ] LRU cache (configurable size, default 10 models)
- [ ] Cache key based on file path
- [ ] `NAMLoadError` exception for invalid models
- [ ] Sample rate detection from model metadata
- [ ] Unit tests with mock model files pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/adapters/processing/nam_loader.py`
- Target: `libs/audio/src/audio/processing/nam_loader.py`
- Use `functools.lru_cache` or custom cache implementation
- NAM uses `nam.models.init_from_nam()` for loading

---

### STORY-005: IR Loader

**As a** developer
**I want** impulse response loading and validation
**So that** cabinet simulation can be applied to processed audio

**Acceptance Criteria:**
- [ ] `load_ir(path)` function loads IR files (.wav, .flac)
- [ ] Returns Pedalboard `Convolution` effect
- [ ] `IRLoadError` exception for invalid files
- [ ] Validates file exists and is readable
- [ ] Unit tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/adapters/processing/ir_loader.py`
- Target: `libs/audio/src/audio/processing/ir_loader.py`
- Use `pedalboard.Convolution` for IR application

---

### STORY-006: User ORM Model

**As a** developer
**I want** User and UserIdentity ORM models
**So that** user data can be persisted

**Acceptance Criteria:**
- [ ] `User` model with id, email, display_name, avatar_url, timestamps
- [ ] `UserIdentity` model for OAuth provider links
- [ ] `OAuthProvider` model (id, name, enabled)
- [ ] Relationships: User has many UserIdentities
- [ ] Indexes on email, provider lookups
- [ ] Unit tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/user.py`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/user_identity.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/models/user.py`

---

### STORY-007: Gear ORM Models

**As a** developer
**I want** Gear and related ORM models
**So that** gear data can be persisted

**Acceptance Criteria:**
- [ ] `Gear` model (aggregate root) with all fields from domain entity
- [ ] `GearModel` for downloadable model files
- [ ] `GearSource` for source tracking (t3k, community)
- [ ] `GearTag`, `GearMake` for categorization
- [ ] Junction tables for many-to-many relationships
- [ ] Indexes for common query patterns (gear_type, platform, source)
- [ ] Unit tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/gear.py`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/gear_model.py`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/gear_related.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/models/gear.py`

---

### STORY-008: Base Layout Template

**As a** developer
**I want** a Jinja2-compatible base layout wrapper
**So that** SSR pages can extend a consistent HTML structure

**Acceptance Criteria:**
- [ ] `BaseWrapper.astro` generates `layouts/base.html`
- [ ] HTML structure with `<head>` containing CSS links
- [ ] HTMX script tag (unpkg CDN)
- [ ] Alpine.js script tag
- [ ] Jinja2 blocks: `{% block title %}`, `{% block content %}`, `{% block scripts %}`
- [ ] CSS links to `/_astro/*.css` (compiled Tailwind)
- [ ] `just build-astro` produces valid wrapper
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/astro/src/layouts/`
- Target: `frontend/astro/src/layouts/BaseWrapper.astro`
- Output: `frontend/astro/dist/layouts/base.html`

---

### STORY-009: Audio Processor Implementation

**As a** developer
**I want** an AudioProcessor that implements the core protocol
**So that** the domain layer can process audio through adapters

**Acceptance Criteria:**
- [ ] `PedalboardAudioProcessor` class in `libs/audio/`
- [ ] Implements `AudioProcessor` protocol from `libs/core/ports/`
- [ ] `async def process_di_track()` - process DI through tone config
- [ ] `async def extract_waveform()` - generate visualization data
- [ ] `async def measure_loudness()` - EBU R128 measurement
- [ ] `async def normalize_loudness()` - normalize to target LUFS
- [ ] `get_supported_formats()` and `is_format_supported()`
- [ ] All methods are async (wrap sync pedalboard calls)
- [ ] Integration tests with real audio files pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/adapters/processing/pedalboard_audio.py`
- Protocol: `libs/core/src/core/ports/audio_processor.py`
- Target: `libs/audio/src/audio/processing/processor.py`
- Archive is sync; must convert to async

---

### STORY-010: SignalChain ORM Models

**As a** developer
**I want** SignalChain and related ORM models
**So that** signal chain data can be persisted

**Acceptance Criteria:**
- [ ] `SignalChain` model with user_id, name, description, timestamps
- [ ] `SignalChainBlock` model for individual blocks in chain
- [ ] `SignalChainGroup` model for permutation groups
- [ ] `BlockType` model for built-in processor definitions
- [ ] `Preset` model for parameter values
- [ ] Relationships with proper cascade delete
- [ ] Indexes on user_id, block positions
- [ ] Unit tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/signal_chain.py`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/signal_chain_group.py`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/block_type.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py`

---

### STORY-011: Static Pages (Index, About, Login)

**As a** developer
**I want** static Astro pages for public routes
**So that** visitors can access the home, about, and login pages

**Acceptance Criteria:**
- [ ] `index.astro` - Home page with hero section
- [ ] `about.astro` - About page with project info
- [ ] `login.astro` - Login page with OAuth buttons
- [ ] All pages use design tokens from Tailwind
- [ ] All pages render without errors
- [ ] `just build-astro` produces HTML files
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/astro/src/pages/`
- Target: `frontend/astro/src/pages/`
- Output: `frontend/astro/dist/*.html`

---

### STORY-012: Shootout and DITrack ORM Models

**As a** developer
**I want** Shootout and DITrack ORM models
**So that** shootout and audio track data can be persisted

**Acceptance Criteria:**
- [ ] `Shootout` model with user_id, title, status, video_path, timestamps
- [ ] `ShootoutChain` junction model linking shootouts to signal chains
- [ ] `DITrack` model with user_id, name, file_path, duration, checksum
- [ ] `AudioSegment` model for processed segments
- [ ] Relationships with proper cascade
- [ ] Indexes on user_id, status
- [ ] Unit tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/shootout.py`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/di_track.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`

---

### STORY-013: Job and Audit ORM Models

**As a** developer
**I want** Job and Audit ORM models
**So that** background job and audit data can be persisted

**Acceptance Criteria:**
- [ ] `Job` model with all fields from domain entity
- [ ] Parent/child job relationships (parent_job_id)
- [ ] `Audit` model for event logging
- [ ] Job status enum stored by value
- [ ] Indexes on user_id, status, entity_id, task_id
- [ ] Unit tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/job.py`
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/models/audit.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/models/job.py`

---

### STORY-014: User Repository Implementation

**As a** developer
**I want** SQLAlchemy UserRepository
**So that** user persistence operations are available

**Acceptance Criteria:**
- [ ] `SQLAlchemyUserRepository` implements `UserRepository` protocol
- [ ] `get_by_id()`, `get_by_email()`, `get_by_identity()`
- [ ] `save()` handles create and update
- [ ] `delete()` removes user
- [ ] All methods are async
- [ ] Domain entity mapping (ORM ↔ Entity)
- [ ] Integration tests against PostgreSQL pass
- [ ] Typecheck passes

**Technical Notes:**
- Protocol: `libs/core/src/core/ports/repositories.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/repositories/user_repository.py`
- Use async SQLAlchemy session

---

### STORY-015: Gear Repository Implementation

**As a** developer
**I want** SQLAlchemy GearRepository
**So that** gear persistence operations are available

**Acceptance Criteria:**
- [ ] `SQLAlchemyGearRepository` implements `GearRepository` protocol
- [ ] `get_by_id()`, `get_by_source()`
- [ ] `search()` with filters (query, gear_type, manufacturer, tags)
- [ ] `count()` for pagination
- [ ] `save()` and `delete()`
- [ ] All methods are async
- [ ] Integration tests against PostgreSQL pass
- [ ] Typecheck passes

**Technical Notes:**
- Protocol: `libs/core/src/core/ports/repositories.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/repositories/gear_repository.py`

---

### STORY-016: SignalChain Repository Implementation

**As a** developer
**I want** SQLAlchemy SignalChainRepository
**So that** signal chain persistence operations are available

**Acceptance Criteria:**
- [ ] `SQLAlchemySignalChainRepository` implements `SignalChainRepository` protocol
- [ ] `get_by_id()` loads chain with all blocks
- [ ] `get_by_user_id()` with pagination
- [ ] `count_by_user_id()`
- [ ] `save()` handles chain and blocks together
- [ ] `delete()` cascades to blocks
- [ ] All methods are async
- [ ] Integration tests against PostgreSQL pass
- [ ] Typecheck passes

**Technical Notes:**
- Protocol: `libs/core/src/core/ports/repositories.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/repositories/signal_chain_repository.py`

---

### STORY-017: Template Structure (Pages, Fragments, Partials)

**As a** developer
**I want** organized template directories
**So that** SSR pages and HTMX fragments follow conventions

**Acceptance Criteria:**
- [ ] `src/pages/pages/` directory for full page templates
- [ ] `src/pages/fragments/` directory for HTMX responses
- [ ] `src/pages/partials/` directory for header/footer
- [ ] Sample `.html.ts` file demonstrating pattern
- [ ] Build outputs to correct locations in `dist/`
- [ ] `just build-astro` succeeds
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/astro/src/pages/`
- Target: `frontend/astro/src/pages/`
- Templates use `.html.ts` extension for Jinja2 output

---

### STORY-018: Remaining Repository Implementations

**As a** developer
**I want** all remaining repository implementations
**So that** the full persistence layer is complete

**Acceptance Criteria:**
- [ ] `SQLAlchemyDITrackRepository` implements protocol
- [ ] `SQLAlchemyShootoutRepository` implements protocol
- [ ] `SQLAlchemyJobRepository` implements protocol
- [ ] `SQLAlchemyAuditRepository` implements protocol
- [ ] `SQLAlchemySignalChainGroupRepository` implements protocol
- [ ] All methods are async
- [ ] Integration tests against PostgreSQL pass
- [ ] Typecheck passes

**Technical Notes:**
- Protocol: `libs/core/src/core/ports/repositories.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/repositories/`

---

### STORY-019: Unit of Work Pattern

**As a** developer
**I want** Unit of Work for transaction management
**So that** services can manage transaction boundaries

**Acceptance Criteria:**
- [ ] `UnitOfWork` class with async context manager
- [ ] `commit()` and `rollback()` methods
- [ ] Session factory configuration
- [ ] Separate factory for worker (dual-database)
- [ ] Transaction scoping works correctly
- [ ] Integration tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/app/core/database.py`
- Target: `apps/webapp/src/webapp/adapters/persistence/unit_of_work.py`

---

### STORY-020: Alembic Migrations

**As a** developer
**I want** Alembic migrations for gts_core schema
**So that** database tables are created correctly

**Acceptance Criteria:**
- [ ] Alembic configuration for `gts_core` database
- [ ] Initial migration creates all tables
- [ ] Indexes and constraints included
- [ ] Seed data for BlockType and OAuthProvider
- [ ] `just migrate` runs successfully
- [ ] Fresh database starts correctly
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/alembic/`
- Target: `infrastructure/migrations/`
- Use async Alembic with SQLAlchemy 2.0

---

### STORY-021: Error Pages (404, 500)

**As a** developer
**I want** error page templates
**So that** users see friendly error messages

**Acceptance Criteria:**
- [ ] `404.astro` - Not found page
- [ ] `500.astro` - Server error page
- [ ] Consistent styling with design system
- [ ] Helpful messaging and navigation back
- [ ] `just build-astro` produces HTML files
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/astro/src/pages/`
- Target: `frontend/astro/src/pages/`

---

### STORY-022: Loudness Normalization

**As a** developer
**I want** EBU R128 loudness normalization
**So that** processed audio has consistent levels

**Acceptance Criteria:**
- [ ] `measure_loudness()` returns (integrated_lufs, peak_dbfs)
- [ ] `normalize_loudness()` adjusts to target LUFS
- [ ] Default target: -14.0 LUFS
- [ ] Silent audio detection (returns error, not normalized)
- [ ] Uses pyloudnorm library
- [ ] Integration tests with real audio pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: Archive `pedalboard_audio.py` `_normalize_lufs()` method
- Target: `libs/audio/src/audio/processing/loudness.py`

---

### STORY-023: Signal Chain Execution

**As a** developer
**I want** signal chain block execution
**So that** audio can be processed through complete chains

**Acceptance Criteria:**
- [ ] Block-by-block sequential execution
- [ ] Position-based ordering (PRE → AMP → LOOP → IR → POST)
- [ ] FULL_RIG constraint enforcement (no loop blocks, no IR)
- [ ] HEAD constraint enforcement (IR required)
- [ ] Uses NAM loader and IR loader
- [ ] Integration tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: Archive `pedalboard_audio.py` and domain `SignalChainValidator`
- Target: `libs/audio/src/audio/processing/chain_executor.py`

---

### STORY-024: Permutation Processing

**As a** developer
**I want** signal chain group permutation expansion
**So that** A/B comparisons can be generated

**Acceptance Criteria:**
- [ ] Cartesian product generation from SignalChainGroup
- [ ] Null gear handling (with/without effect comparisons)
- [ ] Limit enforcement (max 27 permutations, max 3 options per block)
- [ ] Uses domain `PermutationCalculator`
- [ ] Integration tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Reference: Archive `permutation_service.py`
- Target: `libs/audio/src/audio/processing/permutation.py`
- Domain service in `libs/core/src/core/services/permutation_calculator.py`

---

### STORY-025: Waveform Extraction

**As a** developer
**I want** waveform visualization data extraction
**So that** audio can be displayed visually

**Acceptance Criteria:**
- [ ] `extract_waveform()` returns `WaveformData`
- [ ] Configurable number of peaks (default 200)
- [ ] Works with various audio formats
- [ ] Uses numpy for peak calculation
- [ ] Integration tests pass
- [ ] Typecheck passes

**Technical Notes:**
- Protocol: `libs/core/src/core/ports/audio_processor.py`
- Target: `libs/audio/src/audio/analysis/waveform.py`

---

### STORY-026: Build Pipeline Integration

**As a** developer
**I want** just commands for Astro build pipeline
**So that** frontend builds are integrated with project tooling

**Acceptance Criteria:**
- [ ] `just build-astro` triggers production build
- [ ] `just watch-astro` enables development mode
- [ ] `just verify-astro-sync` checks dist/ is in sync
- [ ] `just check-astro` runs lint and type check
- [ ] Commands use Docker with `--profile build`
- [ ] All commands documented in justfile
- [ ] Commands work from project root

**Technical Notes:**
- Reference: Archive `justfile`
- Target: Update existing `justfile`
- Astro container uses `--profile build`

---

### STORY-027: Integration Tests - Persistence

**As a** developer
**I want** integration tests for persistence layer
**So that** repositories are verified against real PostgreSQL

**Acceptance Criteria:**
- [ ] Test fixtures for database setup/teardown
- [ ] Tests for each repository implementation
- [ ] Tests verify CRUD operations
- [ ] Tests verify relationship loading
- [ ] Tests run against real PostgreSQL (via Docker)
- [ ] `just tdd tests/integration/webapp/` passes
- [ ] Typecheck passes

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/backend/tests/`
- Target: `tests/integration/webapp/test_repositories.py`

---

### STORY-028: Integration Tests - Audio

**As a** developer
**I want** integration tests for audio processing
**So that** the audio library is verified with real files

**Acceptance Criteria:**
- [ ] Test audio files in `tests/data/`
- [ ] Tests for NAM model loading
- [ ] Tests for IR loading
- [ ] Tests for full processing pipeline
- [ ] Tests for loudness measurement
- [ ] `just tdd tests/integration/audio/` passes
- [ ] Typecheck passes

**Technical Notes:**
- Reference: Archive test patterns
- Target: `tests/integration/audio/`
- May need sample .nam and .wav files

---

### STORY-029: nginx Static File Serving

**As a** developer
**I want** nginx configured to serve Astro static files
**So that** the frontend is accessible via HTTP

**Acceptance Criteria:**
- [ ] nginx serves files from `frontend/astro/dist/`
- [ ] Static routes (`/`, `/about`, `/login`) serve HTML
- [ ] CSS/JS assets served from `/_astro/`
- [ ] SSR routes proxy to backend
- [ ] Security headers configured
- [ ] `just up-d` starts nginx correctly
- [ ] Pages load in browser

**Technical Notes:**
- Reference: `../../guitar-tone-worktrees-archive-20260202/main/deploy/nginx/`
- Target: `infrastructure/nginx/nginx.conf.template`
- Uses envsubst for environment variables

---

### STORY-030: Documentation Updates

**As a** developer
**I want** wiki and AGENTS.md updated
**So that** documentation reflects the implemented Phase 3

**Acceptance Criteria:**
- [ ] Wiki [[GTS-Technical-Architecture]] updated with actual paths
- [ ] Wiki [[Frontend-Architecture]] created/updated
- [ ] Wiki [[Audio-Processing]] guide created
- [ ] AGENTS.md updated if patterns changed
- [ ] All documentation accurate to implementation
- [ ] No stale documentation

**Technical Notes:**
- Wiki location: `../wiki/`
- AGENTS.md in project root
- Follow documentation style rules (declarative, not historical)

---

## Out of Scope

- Webapp application (Phase 4)
- Worker/Scheduler (Phase 5A)
- T3K source adapter (Phase 5B)
- Video composition (Phase 5C)
- E2E tests (Phase 6)
- React SignalChainBuilder component (Phase 4)
- SSR page routes (Phase 4)
- HTMX fragment endpoints (Phase 4)

## Open Questions

None - all clarified via implementation plan and reference architecture.

## Must-Haves (Derived from Goals)

### Observable Truths

- Developer can run `just migrate` and database tables are created
- Developer can instantiate repositories and perform CRUD operations
- Developer can process a DI track through the audio processor
- Developer can run `just build-astro` and static files are generated
- Developer can access static pages via nginx

### Required Artifacts

| Artifact | Purpose | Min Lines |
|----------|---------|-----------|
| `apps/webapp/src/webapp/adapters/persistence/models/base.py` | ORM base classes | 30 |
| `apps/webapp/src/webapp/adapters/persistence/models/user.py` | User ORM | 50 |
| `apps/webapp/src/webapp/adapters/persistence/models/gear.py` | Gear ORM | 100 |
| `apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py` | SignalChain ORM | 100 |
| `apps/webapp/src/webapp/adapters/persistence/models/shootout.py` | Shootout ORM | 80 |
| `apps/webapp/src/webapp/adapters/persistence/models/job.py` | Job ORM | 60 |
| `apps/webapp/src/webapp/adapters/persistence/repositories/user_repository.py` | User repo | 50 |
| `apps/webapp/src/webapp/adapters/persistence/repositories/gear_repository.py` | Gear repo | 80 |
| `apps/webapp/src/webapp/adapters/persistence/repositories/signal_chain_repository.py` | Chain repo | 70 |
| `libs/audio/src/audio/processing/nam_loader.py` | NAM loading | 50 |
| `libs/audio/src/audio/processing/ir_loader.py` | IR loading | 30 |
| `libs/audio/src/audio/processing/processor.py` | Audio processor | 150 |
| `frontend/astro/astro.config.mjs` | Astro config | 20 |
| `frontend/astro/src/styles/global.css` | Design tokens | 100 |
| `frontend/astro/src/layouts/BaseWrapper.astro` | Base layout | 50 |
| `infrastructure/migrations/versions/001_initial.py` | Initial migration | 200 |
| `tests/integration/webapp/test_repositories.py` | Repo tests | 100 |
| `tests/integration/audio/test_processor.py` | Audio tests | 80 |

### Key Wiring

| From | To | Via |
|------|----|-----|
| Repositories | Core protocols | Implement `UserRepository`, `GearRepository`, etc. |
| Audio processor | Core protocol | Implement `AudioProcessor` |
| ORM models | Domain entities | Mapper functions in repositories |
| Astro build | nginx | `frontend/astro/dist/` bind mount |
| Base layout | SSR pages | Jinja2 `{% extends "layouts/base.html" %}` |
