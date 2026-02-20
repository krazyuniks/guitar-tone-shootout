# Epic Question Bank

Questions for the scope discussion phase of epic planning. Organised by architecture layer, following the GTS codebase structure. The orchestrator presents only the sections relevant to detected areas.

---

## 1. Scope & Intent

- What feature are you building? (one sentence)
- What problem does this solve?
- Who benefits from this feature?
- What can they do that they couldn't before?
- What does DONE look like? List every capability.
- Any dependencies on other epics or systems?

---

## 2. Architecture

Which layers of the stack does this epic touch?

### Bounded Contexts

- Which BCs are involved? (core, audio, video, source_t3k)
- Does this cross BC boundaries? If so, what messages flow between them?
- Are new pgmq queues needed, or do existing queues carry the messages?

### Database

- Which BC's tables are involved? (core_*, t3k_*, audio_*, video_*)
- Any new tables or columns?
- Cross-BC joins forbidden — is messaging needed instead?

### Messaging

- Does this involve pgmq commands (point-to-point) or events (multi-consumer)?
- Which queue(s)? Existing or new?
- Transactional outbox — does the publish happen in the same transaction as the state change?

---

## 3. Domain Model (`libs/core`)

Core domain entities, value objects, and business rules.

### Entities & Relationships

- What's the primary entity?
- What fields are required vs optional?
- What's the status/lifecycle?
- Relations to existing tables?
- Indexes or constraints needed?
- Soft delete or hard delete?

### Gear Model

- Unified Gear model or source-specific?
- GearModel files involved? (NAM, IR)
- Source attribution needed?
- User-uploaded (community) or synced from source?
- UserGear library implications?

### Signal Chain

- Which block types are affected? (amp, IR, pedal, built-in)
- HEAD vs FULL_RIG considerations? (IR required vs forbidden)
- Loop effects allowed? (not with FULL_RIG)
- Block ordering constraints?
- Permutation support needed? (SignalChainGroup)

---

## 4. Libraries

### Audio (`libs/audio`)

- NAM model loading?
- IR convolution?
- Loudness normalisation?
- Processing pipeline stages?

### Video (`libs/video`)

- Remotion composition involved?
- Image preparation (waveform, spectrogram)?
- Video rendering pipeline?

---

## 5. Applications

### Webapp (`apps/webapp`)

The user-facing web application: FastAPI + Jinja2 SSR + HTMX.

#### Persistence (ORM)

- Follow existing repository pattern?
- Which existing repository to reference?
- Eager loading with joinedload? (lazy="raise" is mandatory)
- Transaction boundaries (service owns)?

#### Services

- New service or extend existing?
- What business logic beyond CRUD?
- Transaction scope — what must be atomic?

#### API

- REST endpoint path? (`/api/v1/...`)
- HTML endpoint path? (`/api/v1/html/...`)
- Pydantic request/response schemas?
- Validation error format?
- Pagination approach (offset or cursor)?

#### Frontend

- Is this a static page (Astro SSG)?
- Is this a dynamic page (Jinja2 SSR)?
- Does it need HTMX fragments?
- Is it the SignalChainBuilder (React island)?
- Navigation: standard `<a href>` links?
- Design tokens from `astro/src/styles/global.css`?

#### Security

- Does endpoint require authentication?
- CurrentUser dependency?
- Ownership check (user_id match)?
- Return 404 for unauthorised (not 403)?

### T3K Sync Worker (`apps/t3k_sync`)

- New sync entity or extending existing?
- T3K API endpoints involved?
- Sync record lifecycle (pending → synced → failed)?
- pgmq command consumption pattern?

### Audio Worker (`apps/audio_worker`)

- Which processing pipeline? (NAM, IR, loudness)
- Input/output file formats?
- pgmq command consumption pattern?
- Error handling for processing failures?

### Video Worker (`apps/video_worker`)

- Remotion composition template?
- Input assets (images, audio, metadata)?
- pgmq command consumption pattern?
- Rendering output format and storage?

---

## 6. Testing Strategy

### Unit Tests (`tests/unit/`)

- What pure functions need testing?
- Domain logic in libs/core?

### Integration Tests (`tests/integration/`)

- What API flows need testing?
- What repository operations?
- What message enqueue/consume flows?

### E2E Tests (`tests/e2e/python/`)

- What user journeys are critical?
- Playwright page interactions?
- Three-layer validation (UI > DOM > Database)?

No mocking — all tests use real services (PostgreSQL, pgmq, Docker containers).
