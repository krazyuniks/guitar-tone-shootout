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
