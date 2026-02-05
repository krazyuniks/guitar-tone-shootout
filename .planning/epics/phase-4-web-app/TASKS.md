# Task Breakdown: Phase 4 - Web Application Implementation

**Source:** `../wiki/IMPLEMENTATION.md` lines 644-754
**Domain Model:** `../wiki/GTS-Technical-Architecture.md` lines 245-390

## Task Groups

| Group | Focus | Tasks |
|-------|-------|-------|
| A | FastAPI Core | A1-A2 |
| B | User & Auth Models | B1-B3 |
| C | Auth Services & API | C1-C3 |
| D | Gear Models | D1-D2 |
| E | Gear API & Pages | E1-E3 |
| F | User Library | F1-F2 |
| G | Signal Chain Models | G1-G2 |
| H | Signal Chain Services & API | H1-H3 |
| I | React SignalChainBuilder | I1-I2 |
| J | Shootout & Job | J1-J3 |
| K | SSR Pages & Fragments | K1-K3 |

---

## Group A: FastAPI Core

### A1: FastAPI Application Skeleton

**Objective:** Create FastAPI application with middleware, exception handlers, and template configuration.

**Citation:** IMPL:654-659

**Acceptance Criteria:**
- [ ] FastAPI app in `apps/webapp/src/webapp/main.py`
- [ ] CORS configuration
- [ ] Exception handlers (HTTPException mapping)
- [ ] Request ID middleware
- [ ] Timing middleware
- [ ] Jinja2 templates from `frontend/astro/dist/`
- [ ] Regression test updated (`just test-regression` passes)

**Scope:**
- Create: `apps/webapp/src/webapp/main.py`
- Create: `apps/webapp/src/webapp/middleware/`
- Create: `apps/webapp/src/webapp/templates.py`

**Dependencies:** None

**Labels:** `task`, `project:webapp`

---

### A2: Health Endpoints

**Objective:** Implement health check endpoints for liveness and readiness.

**Citation:** IMPL:703-705

**Acceptance Criteria:**
- [ ] GET `/health` returns process alive
- [ ] GET `/health/ready` returns database connectivity status
- [ ] `just test-integration` passes for health endpoints
- [ ] Regression test updated with health check

**Scope:**
- Create: `apps/webapp/src/webapp/api/v1/health.py`

**Dependencies:** Blocked by: A1

**Labels:** `task`, `project:webapp`

---

## Group B: User & Auth Models

### B1: User ORM Model

**Objective:** Create User aggregate root ORM model.

**Citation:** wiki:264

**Acceptance Criteria:**
- [ ] User model in `apps/webapp/src/webapp/adapters/persistence/models/`
- [ ] Fields as defined in domain model (id, created_at, updated_at)
- [ ] NO source-specific fields (no t3k_id, etc.)
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/user.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/models/base.py`

**Dependencies:** Blocked by: A1

**Labels:** `task`, `project:webapp`

---

### B2: UserIdentity ORM Model

**Objective:** Create UserIdentity model for OAuth provider links.

**Citation:** wiki:265

**Acceptance Criteria:**
- [ ] UserIdentity model with user_id, provider_id, external_id
- [ ] Supports multiple providers per user
- [ ] Foreign key to User
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/user_identity.py`

**Dependencies:** Blocked by: B1

**Labels:** `task`, `project:webapp`

---

### B3: OAuthProvider ORM Model

**Objective:** Create OAuthProvider configuration model.

**Citation:** wiki:266

**Acceptance Criteria:**
- [ ] OAuthProvider model with name, client_id, enabled, etc.
- [ ] Supports T3K, Google, GitHub, Facebook (stubs)
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/oauth_provider.py`

**Dependencies:** Blocked by: A1

**Labels:** `task`, `project:webapp`

---

## Group C: Auth Services & API

### C1: Generic OAuth Handler

**Objective:** Implement generic OAuth handler supporting multiple providers.

**Citation:** IMPL:662

**Acceptance Criteria:**
- [ ] Generic OAuth flow in `apps/webapp/src/webapp/auth/`
- [ ] Provider-agnostic callback handling
- [ ] Token exchange logic
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/auth/__init__.py`
- Create: `apps/webapp/src/webapp/auth/oauth.py`
- Create: `apps/webapp/src/webapp/auth/token.py`

**Dependencies:** Blocked by: B2, B3

**Labels:** `task`, `project:webapp`

---

### C2: T3K Provider Implementation

**Objective:** Implement T3K as primary OAuth provider.

**Citation:** IMPL:663

**Acceptance Criteria:**
- [ ] T3K provider in `apps/webapp/src/webapp/auth/providers/`
- [ ] OAuth2 authorization URL generation
- [ ] Token exchange with T3K API
- [ ] User info retrieval
- [ ] `just test-integration` passes

**Scope:**
- Create: `apps/webapp/src/webapp/auth/providers/__init__.py`
- Create: `apps/webapp/src/webapp/auth/providers/t3k.py`

**Dependencies:** Blocked by: C1

**Labels:** `task`, `project:webapp`

---

### C3: IdentityService and Auth API

**Objective:** Implement IdentityService and auth API endpoints.

**Citation:** IMPL:678, IMPL:681

**Acceptance Criteria:**
- [ ] IdentityService handles user creation/linking
- [ ] GET `/api/v1/auth/login` redirects to provider
- [ ] GET `/api/v1/auth/callback` handles OAuth callback
- [ ] Token authentication (stateless)
- [ ] Auth file save/restore for `.gts-auth.json`
- [ ] Token encryption at rest (Fernet)
- [ ] `just test-integration` passes
- [ ] Regression test updated with auth flow

**Scope:**
- Create: `apps/webapp/src/webapp/services/identity_service.py`
- Create: `apps/webapp/src/webapp/api/v1/auth.py`
- Create: `apps/webapp/src/webapp/auth/persistence.py`
- Create: `apps/webapp/src/webapp/auth/encryption.py`

**Dependencies:** Blocked by: C2

**Labels:** `task`, `project:webapp`

---

## Group D: Gear Models

### D1: Gear and GearModel ORM Models

**Objective:** Create unified Gear and GearModel ORM models.

**Citation:** wiki:271, wiki:272

**Acceptance Criteria:**
- [ ] Gear model (unified across all sources)
- [ ] GearModel model (specific model file)
- [ ] GearType enum (AMP, FULL_RIG, PEDAL, OUTBOARD, IR) - wiki:304-312
- [ ] Platform enum (NAM, IR, AIDA_X, etc.) - wiki:314-322
- [ ] NO source-specific fields in Gear
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/gear.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/models/gear_model.py`
- Create: `libs/core/src/core/domain/value_objects/gear_type.py`
- Create: `libs/core/src/core/domain/value_objects/platform.py`

**Dependencies:** Blocked by: B1

**Labels:** `task`, `project:webapp`, `project:core`

---

### D2: GearSource ORM Model

**Objective:** Create GearSource model for source attribution.

**Citation:** wiki:273

**Acceptance Criteria:**
- [ ] GearSource model (t3k, community, etc.)
- [ ] Foreign key from Gear to GearSource
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/gear_source.py`

**Dependencies:** Blocked by: D1

**Labels:** `task`, `project:webapp`

---

## Group E: Gear API & Pages

### E1: Gear Repository

**Objective:** Implement repository for Gear queries.

**Acceptance Criteria:**
- [ ] GearRepository protocol and implementation
- [ ] List with pagination and filtering
- [ ] Get by ID/slug
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/repositories/gear_repository.py`

**Dependencies:** Blocked by: D2

**Labels:** `task`, `project:webapp`

---

### E2: Gear API Endpoints

**Objective:** Implement gear browse and detail API.

**Citation:** IMPL:682

**Acceptance Criteria:**
- [ ] GET `/api/v1/gear/` returns gear list
- [ ] GET `/api/v1/gear/{id}` returns gear detail
- [ ] Pagination support
- [ ] `just test-integration` passes

**Scope:**
- Create: `apps/webapp/src/webapp/api/v1/gear.py`
- Create: `apps/webapp/src/webapp/api/v1/schemas/gear.py`

**Dependencies:** Blocked by: E1

**Labels:** `task`, `project:webapp`

---

### E3: Gear Browse and Detail Pages

**Objective:** Implement gear SSR pages.

**Citation:** IMPL:690

**Acceptance Criteria:**
- [ ] GET `/gear` renders browse page
- [ ] GET `/gear/{slug}` renders detail page
- [ ] HTMX fragments for list updates
- [ ] `just test-e2e` passes
- [ ] Regression test updated with gear browse

**Scope:**
- Create: `frontend/astro/src/pages/pages/gear_browse.html.ts`
- Create: `frontend/astro/src/pages/pages/gear_detail.html.ts`
- Create: `frontend/astro/src/pages/fragments/gear/`
- Run: `just build-astro`

**Dependencies:** Blocked by: E2

**Labels:** `task`, `project:webapp`

---

## Group F: User Library

### F1: UserGear Model and Repository

**Objective:** Create UserGear model and repository for user's gear library.

**Citation:** wiki:276

**Acceptance Criteria:**
- [ ] UserGear model (user_id, gear_id)
- [ ] Unique constraint (user can't add same gear twice)
- [ ] UserGearRepository with add/remove/list
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/user_gear.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/repositories/user_gear_repository.py`

**Dependencies:** Blocked by: D1, B1

**Labels:** `task`, `project:webapp`

---

### F2: User Library API and Page

**Objective:** Implement user gear library API and page.

**Citation:** IMPL:691

**Acceptance Criteria:**
- [ ] GET `/api/v1/library/gear` returns user's gear (requires auth)
- [ ] POST `/api/v1/library/gear` adds gear (requires auth)
- [ ] DELETE `/api/v1/library/gear/{id}` removes gear
- [ ] GET `/library/my-gear` renders page
- [ ] HTMX fragments for add/remove
- [ ] `just test-e2e` passes
- [ ] Regression test updated with library test

**Scope:**
- Create: `apps/webapp/src/webapp/api/v1/library.py`
- Create: `frontend/astro/src/pages/pages/library/my_gear.html.ts`
- Create: `frontend/astro/src/pages/fragments/library/`
- Run: `just build-astro`

**Dependencies:** Blocked by: F1, C3

**Labels:** `task`, `project:webapp`

---

## Group G: Signal Chain Models

### G1: SignalChain and SignalChainBlock Models

**Objective:** Create SignalChain aggregate and block models.

**Citation:** wiki:281, wiki:282

**Acceptance Criteria:**
- [ ] SignalChain model (user_id, name, description)
- [ ] SignalChainBlock model (chain_id, position, gear_model_id or block_type_id)
- [ ] BlockPosition enum (pre, loop, post) - wiki:388
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/signal_chain.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/models/signal_chain_block.py`
- Create: `libs/core/src/core/domain/value_objects/block_position.py`

**Dependencies:** Blocked by: D1, B1

**Labels:** `task`, `project:webapp`, `project:core`

---

### G2: BlockType and Preset Models

**Objective:** Create BlockType (built-in processors) and Preset models.

**Citation:** wiki:286, wiki:287

**Acceptance Criteria:**
- [ ] BlockType model (name, category, parameters schema)
- [ ] BlockCategory enum (utility, eq, dynamics, filter, delay, reverb, modulation) - wiki:334-342
- [ ] Preset model (chain_id, parameter values)
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/block_type.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/models/preset.py`
- Create: `libs/core/src/core/domain/value_objects/block_category.py`

**Dependencies:** Blocked by: G1

**Labels:** `task`, `project:webapp`, `project:core`

---

## Group H: Signal Chain Services & API

### H1: Chain Validator Domain Service

**Objective:** Implement domain validation rules for signal chains.

**Citation:** wiki:360-368

**Acceptance Criteria:**
- [ ] Validates NO_AMP (no amp block)
- [ ] Validates MULTIPLE_AMPS (more than one amp)
- [ ] Validates IR_REQUIRED (HEAD amp, no IR)
- [ ] Validates IR_FORBIDDEN (FULL_RIG amp with IR)
- [ ] Validates LOOP_FORBIDDEN (loop effects with FULL_RIG)
- [ ] Validates INVALID_ORDER (blocks in wrong position)
- [ ] Returns detailed validation errors
- [ ] `just test-unit` passes

**Scope:**
- Create: `libs/core/src/core/services/chain_validator.py`

**Dependencies:** Blocked by: G1

**Labels:** `task`, `project:core`

---

### H2: SignalChainService and API

**Objective:** Implement SignalChainService and REST API.

**Citation:** IMPL:672, IMPL:683

**Acceptance Criteria:**
- [ ] SignalChainService with CRUD + validation
- [ ] GET `/api/v1/signal-chains/` returns user's chains
- [ ] POST `/api/v1/signal-chains/` creates chain (validates)
- [ ] PUT `/api/v1/signal-chains/{id}` updates chain
- [ ] DELETE `/api/v1/signal-chains/{id}` deletes chain
- [ ] Returns 422 with validation errors
- [ ] `just test-integration` passes

**Scope:**
- Create: `apps/webapp/src/webapp/services/signal_chain_service.py`
- Create: `apps/webapp/src/webapp/api/v1/signal_chains.py`
- Create: `apps/webapp/src/webapp/api/v1/schemas/signal_chain.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/repositories/signal_chain_repository.py`

**Dependencies:** Blocked by: H1, G2

**Labels:** `task`, `project:webapp`

---

### H3: BlockTypeRegistry and PresetService

**Objective:** Implement BlockTypeRegistry and PresetService.

**Citation:** IMPL:677, IMPL:673

**Acceptance Criteria:**
- [ ] BlockTypeRegistry loads built-in processor templates
- [ ] PresetService manages parameter values for chains
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/services/block_type_registry.py`
- Create: `apps/webapp/src/webapp/services/preset_service.py`

**Dependencies:** Blocked by: G2

**Labels:** `task`, `project:webapp`

---

## Group I: React SignalChainBuilder

### I1: React SignalChainBuilder Refactor

**Objective:** Refactor and move React SignalChainBuilder from archive.

**Citation:** IMPL:696-701, IMPL:725

**Acceptance Criteria:**
- [ ] Component in `frontend/astro/src/components/SignalChainBuilder/`
- [ ] Block drag-and-drop
- [ ] Gear selection from user library
- [ ] Single chain mode
- [ ] Permutation mode (multiple gear per slot)
- [ ] `just build-astro` succeeds
- [ ] `just check-astro` passes

**Scope:**
- Create: `frontend/astro/src/components/SignalChainBuilder/`
- Modify: `frontend/astro/astro.config.mjs` (if needed)

**Dependencies:** Blocked by: H2

**Labels:** `task`, `project:webapp`

---

### I2: Chain Builder Page

**Objective:** Create page that mounts React SignalChainBuilder.

**Citation:** IMPL:693

**Acceptance Criteria:**
- [ ] GET `/library/chains/build` renders builder page
- [ ] React component mounts and functions
- [ ] Integration with chain API
- [ ] `just test-e2e` passes
- [ ] Regression test updated with builder test

**Scope:**
- Create: `frontend/astro/src/pages/pages/library/chains_build.html.ts`
- Run: `just build-astro`

**Dependencies:** Blocked by: I1

**Labels:** `task`, `project:webapp`

---

## Group J: Shootout & Job

### J1: Shootout and ShootoutChain Models

**Objective:** Create Shootout aggregate and ShootoutChain join model.

**Citation:** wiki:293, wiki:294

**Acceptance Criteria:**
- [ ] Shootout model (user_id, name, status)
- [ ] ShootoutChain model (shootout_id, chain_id)
- [ ] ShootoutRepository with CRUD
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/models/shootout_chain.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py`

**Dependencies:** Blocked by: G1, B1

**Labels:** `task`, `project:webapp`

---

### J2: DITrack Model and Service

**Objective:** Create DITrack model and upload service.

**Citation:** wiki:292, IMPL:675

**Acceptance Criteria:**
- [ ] DITrack model (user_id, filename, checksum, duration)
- [ ] DITrackService handles upload and validation
- [ ] `just test-unit` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/di_track.py`
- Create: `apps/webapp/src/webapp/services/di_track_service.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/repositories/di_track_repository.py`

**Dependencies:** Blocked by: B1

**Labels:** `task`, `project:webapp`

---

### J3: ShootoutService, JobService, and APIs

**Objective:** Implement ShootoutService, JobService, and API endpoints.

**Citation:** IMPL:671, IMPL:674, IMPL:684, IMPL:685, wiki:299

**Acceptance Criteria:**
- [ ] Job model (user_id, status, type, payload)
- [ ] ShootoutService with CRUD + lifecycle
- [ ] JobService with status queries (user's own jobs)
- [ ] GET `/api/v1/shootouts/` returns user's shootouts
- [ ] POST `/api/v1/shootouts/` creates shootout
- [ ] GET `/api/v1/jobs/{id}` returns job status
- [ ] `just test-integration` passes

**Scope:**
- Create: `apps/webapp/src/webapp/adapters/persistence/models/job.py`
- Create: `apps/webapp/src/webapp/services/shootout_service.py`
- Create: `apps/webapp/src/webapp/services/job_service.py`
- Create: `apps/webapp/src/webapp/api/v1/shootouts.py`
- Create: `apps/webapp/src/webapp/api/v1/jobs.py`
- Create: `apps/webapp/src/webapp/api/v1/schemas/shootout.py`
- Create: `apps/webapp/src/webapp/api/v1/schemas/job.py`
- Create: `apps/webapp/src/webapp/adapters/persistence/repositories/job_repository.py`

**Dependencies:** Blocked by: J1, J2

**Labels:** `task`, `project:webapp`

---

## Group K: SSR Pages & Fragments

### K1: Shootout Pages

**Objective:** Implement shootout list and detail SSR pages.

**Citation:** IMPL:691, IMPL:692

**Acceptance Criteria:**
- [ ] GET `/library/shootouts` renders shootout list
- [ ] GET `/shootout/{id}` renders shootout detail
- [ ] HTMX fragments for CRUD operations
- [ ] `just test-e2e` passes

**Scope:**
- Create: `frontend/astro/src/pages/pages/library/shootouts.html.ts`
- Create: `frontend/astro/src/pages/pages/shootout_detail.html.ts`
- Create: `frontend/astro/src/pages/fragments/shootouts/`
- Run: `just build-astro`

**Dependencies:** Blocked by: J3

**Labels:** `task`, `project:webapp`

---

### K2: Chain List Page

**Objective:** Implement signal chain list page.

**Citation:** IMPL:691

**Acceptance Criteria:**
- [ ] GET `/library/chains` renders chain list
- [ ] HTMX fragments for list operations
- [ ] `just test-e2e` passes

**Scope:**
- Create: `frontend/astro/src/pages/pages/library/chains.html.ts`
- Create: `frontend/astro/src/pages/fragments/chains/`
- Run: `just build-astro`

**Dependencies:** Blocked by: H2

**Labels:** `task`, `project:webapp`

---

### K3: HTMX Fragment Endpoints

**Objective:** Implement HTMX fragment API endpoints.

**Citation:** IMPL:686

**Acceptance Criteria:**
- [ ] `/api/v1/html/` namespace for fragment endpoints
- [ ] Gear browse fragments
- [ ] Library fragments (my-gear, chains, shootouts)
- [ ] `just test-integration` passes

**Scope:**
- Create: `apps/webapp/src/webapp/api/v1/html.py`

**Dependencies:** Blocked by: E2, F2, H2, J3

**Labels:** `task`, `project:webapp`

---

## Dependency Graph

```
A1 ─── A2
 │
 ├─── B1 ─── B2 ─── C1 ─── C2 ─── C3
 │     │
 │     └─── D1 ─── D2 ─── E1 ─── E2 ─── E3
 │           │
 │           ├─── F1 ─────────────────── F2
 │           │
 │           └─── G1 ─── G2 ─── H1 ─── H2 ─── I1 ─── I2
 │                 │            │       │
 │                 │            └─── H3 └─── K2
 │                 │
 │                 └─── J1 ─────────────────── J3 ─── K1
 │
 └─── B3
       │
       └─── J2
```

## Execution Order (Waves)

| Wave | Tasks | Parallel |
|------|-------|----------|
| 1 | A1 | - |
| 2 | A2, B1, B3 | Yes |
| 3 | B2, D1, J2 | Yes |
| 4 | C1, D2, F1, G1 | Yes |
| 5 | C2, E1, G2, J1 | Yes |
| 6 | C3, E2, H1, H3 | Yes |
| 7 | E3, F2, H2, J3 | Yes |
| 8 | I1, K2, K3 | Yes |
| 9 | I2, K1 | Yes |
