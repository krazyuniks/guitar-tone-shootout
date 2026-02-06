# Goal-Backward Planning Guide

Transform user stories into testable truths, required artifacts, and test specifications.

## Philosophy

```
Forward planning asks: "What should we build?"
Goal-backward planning asks: "What must be TRUE for the goal to be achieved?"
```

---

## Step 1: State the Goal

Take the user story and reframe as outcome:

```
User Story: "As a user, I want to build a signal chain"
Goal: Users can compose signal chains from their gear library
```

**Rule:** If goal is task-shaped ("implement X"), reframe as outcome-shaped ("users can X").

---

## Step 2: Derive Observable Truths

Ask: "What must be TRUE for this goal to be achieved?"

List 3-7 truths from the USER's perspective:
- These are observable behaviors
- Each must be verifiable by a human using the application
- Focus on what user sees/experiences, not implementation

**Example (GTS signal chain):**
1. User can navigate to chain builder page
2. User can add amp block from gear library
3. User can add IR block (required if amp is HEAD)
4. Chain validates block ordering and requirements
5. User can save chain to library
6. User can process chain with DI track

---

## Step 3: Derive Required Artifacts

For each truth, ask: "What must EXIST for this to be true?"

**Example:**
```
Truth: "User can add amp block from gear library"
Artifacts:
- SignalChainBuilder React component (frontend/astro/src/components/)
- UserGear query endpoint (apps/webapp/src/webapp/api/v1/)
- SignalChainBlock model (apps/webapp/src/webapp/adapters/persistence/models/)
- Add block API endpoint

Truth: "Chain validates block ordering and requirements"
Artifacts:
- SignalChainValidator domain service (libs/core/src/core/services/)
- Validation rules (HEAD requires IR, FULL_RIG forbids IR, etc.)
- Error response schemas
```

### GTS Artifact Mapping

| Artifact Type | GTS Location | Pattern |
|---------------|--------------|---------|
| ORM Model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy |
| Repository | `apps/webapp/src/webapp/adapters/persistence/repositories/` | Protocol impl |
| Service | `apps/webapp/src/webapp/services/` | Transaction owner |
| API Route | `apps/webapp/src/webapp/api/v1/` | FastAPI router |
| Pydantic Schema | `apps/webapp/src/webapp/api/v1/schemas/` | Request/response |
| Job | `apps/worker/src/worker/jobs/` | TaskIQ job |
| Jinja2 Template | `frontend/astro/src/pages/` (source) | `.html.ts` files |
| HTMX Fragment | `frontend/astro/src/pages/fragments/` | HTML partials |
| Domain Logic | `libs/core/src/core/` | No framework deps |
| Audio Processing | `libs/audio/src/audio/` | NAM, IR, pedalboard |

---

## Step 4: Derive Required Wiring

For each artifact, ask: "What must be CONNECTED for this to function?"

**Example:**
```
Artifact: POST /api/v1/chains endpoint
Wiring:
- FastAPI route registered in apps/webapp/src/webapp/api/v1/__init__.py
- Pydantic request validation (SignalChainCreate schema)
- SignalChainService transaction (service owns transaction)
- SignalChainRepository persistence
- SignalChainValidator domain validation
- Response serialization (SignalChainResponse schema)
```

---

## Step 5: Derive Test Specifications

For each truth, ask: "What test VERIFIES this is true?"

**Example:**
```
Truth: "Chain validates block ordering and requirements"
Tests:
- Unit (tests/unit/core/): test_validator_rejects_head_without_ir
- Unit: test_validator_rejects_full_rig_with_ir
- Integration (tests/integration/webapp/): test_create_chain_validates
- E2E (tests/e2e/python/): test_builder_shows_validation_errors
```

### GTS Test Mapping

| Truth Type | Test Level | Location | Execution |
|------------|------------|----------|-----------|
| Pure logic | Unit | `tests/unit/` | Docker |
| DB/service | Integration | `tests/integration/` | Docker |
| User journey | E2E | `tests/e2e/python/` | Host |

### Test Commands (ONLY `just` commands allowed)

| Test Type | Command | Purpose |
|-----------|---------|---------|
| Regression | `just test-regression` | **Quality gate** - E2E test exercising all endpoints + stack connectivity |
| Unit | `just test-unit` | Isolated logic, no I/O |
| Integration | `just test-integration` | Real DB/Redis |
| E2E | `just test-golden-path` | Full user journeys |
| TDD single | `just tdd <path>` | Single test during development |

**NEVER use raw `docker compose exec`, `pytest`, or `python` commands in acceptance criteria.** The `just` commands wrap the underlying execution - implementation details are hidden.

### Three-Layer E2E Validation (MANDATORY)

All E2E tests (including regression) must verify the full code path:

1. **UI Action** - User interaction succeeds (click, submit)
2. **DOM Update** - Page reflects expected state change
3. **Database State** - Data persisted correctly (or page content reflects DB query)

This ensures the entire stack is wired correctly: UI → Domain Model → Database.

**Regression test note:** `test-regression` is a Playwright E2E test that serves dual purposes:
1. **Stack connectivity** - Exercises ORM → Repository → Database through the webapp
2. **Endpoint validation** - All web endpoints respond correctly with expected content

When adding new endpoints, update `tests/e2e/python/tests/test_regression.py` with specific validation criteria (expected content, UI elements, data counts).

### Layer-Boundary Examples

**Good (single boundary):**
- Task: "Gear repository + service" — touches `repositories/gear.py` + `services/gear.py`
- Task: "Gear API endpoints" — touches `api/gear.py` + `schemas/gear.py`
- Task: "Gear library page" — touches `pages/gear.html.ts` + template

**Bad (crosses boundaries):**
- Task: "Full gear CRUD" — touches repository + service + API + schemas + template
- Task: "Implement shootouts and jobs" — crosses entity boundaries

---

## Output Format

Save to `.planning/epics/{slug}/GOALS.md`:

```markdown
# Goal-Backward Analysis: {Epic Title}

## Goal
{Outcome-shaped goal statement}

## Observable Truths

1. {Truth 1 - user perspective}
2. {Truth 2}
3. {Truth 3}
...

## Required Artifacts

### Truth 1: {Truth statement}
| Artifact | Location | Pattern |
|----------|----------|---------|
| {Name} | {Path} | {Pattern} |

### Truth 2: {Truth statement}
...

## Required Wiring

### {Artifact 1}
- Connection 1
- Connection 2

### {Artifact 2}
...

## Test Specifications

| Truth | Test Level | Test Name | Location |
|-------|------------|-----------|----------|
| Truth 1 | E2E | test_user_can_navigate_to_builder | tests/e2e/python/ |
| Truth 2 | Integration | test_add_amp_block_to_chain | tests/integration/ |
...
```
