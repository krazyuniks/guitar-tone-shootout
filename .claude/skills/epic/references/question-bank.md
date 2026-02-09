# Epic Builder Question Bank

GTS-specific questions for structured epic planning.

## Core Understanding Questions

### Vision
- What feature are you building? (one sentence)
- What problem does this solve?

### User Stories
- Who benefits from this feature?
- What can they do that they couldn't before?
- Are there secondary users or personas?

### Core Priority
- What's the ONE thing that must work?
- If you could only ship one capability, what would it be?

### Boundaries
- What's explicitly out of scope?
- What might people assume is included but isn't?
- Are there future enhancements to defer?

### Constraints
- Any technical constraints? (existing systems, performance)
- Any business constraints? (timeline, budget, compliance)
- Any dependencies on other teams or systems?

---

## GTS-Specific Gray Area Questions

### Signal Chain
- Does this feature involve signal chains?
- Which block types are affected? (amp, IR, pedal, built-in)
- HEAD vs FULL_RIG considerations? (IR required vs forbidden)
- Loop effects allowed? (not with FULL_RIG)
- Block ordering constraints?
- Permutation support needed? (SignalChainGroup)

### Gear Model
- Does this feature involve gear?
- Unified Gear model or source-specific?
- GearModel files involved? (NAM, IR)
- Source attribution needed?
- User-uploaded (community) or synced from source?
- UserGear library implications?

### Dual Database
- Which database is this for? (gts_core or gts_t3k_source)
- If source data, is worker the access point?
- pgmq messages involved?
- Sync records needed?
- Cross-database implications?

### Frontend Layers
- Is this a static page (Astro SSG)?
- Is this a dynamic page (Jinja2 SSR)?
- Does it need HTMX fragments?
- Is it the SignalChainBuilder (React)?
- Navigation: Astro page to SSR page? (needs data-astro-reload)
- Design tokens from Astro CSS?

### Job Processing
- Does this trigger background jobs?
- TaskIQ job or pgmq consumer?
- Parent/child job hierarchy? (like SHOOTOUT)
- Retry strategy and max attempts?
- Progress reporting (WebSocket for user jobs)?
- Redis locks needed?

### Audio Processing
- Does this involve audio processing?
- NAM model loading?
- IR convolution?
- Loudness normalization?
- libs/audio or apps/worker?

---

## Standard Gray Area Questions

### Data Model
- What's the primary entity?
- What fields are required vs optional?
- What's the status/lifecycle?
- Relations to existing tables in gts_core?
- Indexes or constraints needed?
- Soft delete or hard delete?

### ORM Patterns
- Follow existing repository pattern?
- Which existing repository to reference?
- Eager or lazy loading for relations?
- Transaction boundaries (service owns)?

### API Contract
- REST endpoint path? (/api/v1/...)
- HTML endpoint path? (/api/v1/html/...)
- Pydantic request/response schemas?
- Validation error format?
- Pagination approach (offset or cursor)?

### Security
- Does endpoint require authentication?
- CurrentUser dependency?
- Ownership check (user_id match)?
- Return 404 for unauthorised (not 403)?
- Rate limiting?

---

## Testing Strategy Questions

### Unit Tests
- What pure functions need testing? (tests/unit/)
- Domain logic in libs/core?
- Runs in Docker via `just test-unit`

### Integration Tests
- What API flows need testing? (tests/integration/)
- What repository operations?
- What job enqueue/consume flows?
- Runs in Docker via `just test-integration`

### E2E Tests
- What user journeys are critical? (tests/e2e/python/)
- Playwright page interactions?
- Three-layer validation (UI > DOM > Database)?
- Runs on HOST via `just test-golden-path`

### Mocking
- Mock: T3K API, email services, external APIs
- Real: PostgreSQL, Redis (Docker containers)
- Never mock internal services or repositories
