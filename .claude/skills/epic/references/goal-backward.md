# Goal-Backward Planning Guide

Transform user stories into observable truths, required artefacts, user journeys, and validation checkpoints.

## Philosophy

```
Forward planning asks: "What should we build?"
Goal-backward planning asks: "What must be TRUE for the goal to be achieved?"
```

The gate is not "do tests pass?" but "does the thing work?" -- verified by type-appropriate checks at validation checkpoints.

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
- These are observable behaviours
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

## Step 3: Derive User Journeys

Connect observable truths into coherent end-to-end narratives. Not isolated assertions ("GET /gear returns 200") but connected walks ("user clicks Gear in nav, sees list, clicks item, sees detail").

Every truth must appear in at least one journey. Journeys include critical transitions with `{from, to, mechanism}`.

**Example:**
```
Journey: "Build and save a signal chain"
Persona: authenticated user
Entry point: /library/chains

1. User navigates to chain builder page (Truth 1)
2. User adds amp block from gear library (Truth 2)
3. System shows IR requirement for HEAD amp (Truth 3)
4. User adds IR block
5. Chain validation passes (Truth 4)
6. User saves chain to library (Truth 5)
7. Chain appears in user's chain list

Critical transitions:
  - /library/chains -> /library/chains/build (click "New Chain" button)
  - /library/chains/build -> /library/chains (save and redirect)
```

---

## Step 4: Derive Required Artefacts

For each truth, ask: "What must EXIST for this to be true?"

**Example:**
```
Truth: "User can add amp block from gear library"
Artefacts:
- SignalChainBuilder React component (frontend/astro/src/components/)
- UserGear query endpoint (apps/webapp/src/webapp/api/v1/)
- SignalChainBlock model (apps/webapp/src/webapp/adapters/persistence/models/)
- Add block API endpoint

Truth: "Chain validates block ordering and requirements"
Artefacts:
- SignalChainValidator domain service (libs/core/src/core/services/)
- Validation rules (HEAD requires IR, FULL_RIG forbids IR, etc.)
- Error response schemas
```

### GTS Artefact Mapping

| Artefact Type | GTS Location | Pattern |
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

## Step 5: Derive Required Wiring

For each artefact, ask: "What must be CONNECTED for this to function?"

**Example:**
```
Artefact: POST /api/v1/chains endpoint
Wiring:
- FastAPI route registered in apps/webapp/src/webapp/api/v1/__init__.py
- Pydantic request validation (SignalChainCreate schema)
- SignalChainService transaction (service owns transaction)
- SignalChainRepository persistence
- SignalChainValidator domain validation
- Response serialisation (SignalChainResponse schema)
```

---

## Step 6: Define Validation Checkpoints

For each truth (or group of truths), define how the orchestrator will verify the product works. Checkpoints use type-aware validation -- not tests, but direct evidence collection.

### Checkpoint Types

| Check Type | What It Verifies | Evidence Fields |
|------------|-----------------|-----------------|
| `http` | Endpoint responds correctly | `status_code`, `url`, `response_excerpt` |
| `http+dom` | Page renders with expected content | `status_code`, `url`, `dom_selector`, `element_text` |
| `browser+db` | UI action persists to database | `action_performed`, `sql_query`, `row_count`, `sample_row` |
| `api+response` | API returns correct data | `status_code`, `url`, `method`, `response_body_excerpt` |
| `process` | Service is running | `process_name`, `pid_or_status`, `log_excerpt` |
| `screenshot` | Visual correctness | `screenshot_path`, `observations` |
| `regression` | Existing tests still pass | `test_command`, `exit_code`, `test_count`, `failure_count` |
| `quality` | Lint/type checks pass | `commands_run`, `exit_code`, `error_count` |

**Example:**
```
After story "02-ui-scaffold":
  check_type: http+dom
  checks:
    - criterion: "Gear list page renders with gear items"
      evidence_fields: [status_code, url, dom_selector, element_text]
    - criterion: "Gear detail page shows gear attributes"
      evidence_fields: [status_code, url, dom_selector, element_text]

After story "03-crud-features":
  check_type: browser+db
  checks:
    - criterion: "Creating a chain persists to database"
      evidence_fields: [action_performed, sql_query, row_count, sample_row]
```

Place checkpoints strategically: after scaffolding, after CRUD, before and after regression tests. Not after every story -- backend-only stories may wait for the UI story that exposes them.

---

## Step 7: Organise into Stories

Group artefacts into stories (2-5 per epic, each 3-8 files). Each story specifies:
- `story_id`, `name`, `purpose`
- `agent` config: model, skills, tools, MCP, max_turns, max_budget_usd
- `scope`: files to create and modify
- `state_assumption`: `cumulative` (default) or `clean`
- `implementation_notes`: domain-specific hints
- `truths_addressed`: which observable truths this story delivers

---

## Output Format

The planner produces two files:

### PLAN.md (narrative, human-readable)

```markdown
# Plan: {Epic Title}

## Goal
{Outcome-shaped goal statement}

## Observable Truths
1. {Truth 1 - user perspective}
2. {Truth 2}
...

## User Journeys

### Journey 1: {Title}
{Connected narrative with entry point, steps, and critical transitions}

## Stories

### Story 01: {Name}
{Purpose, scope summary, validation approach}

### Story 02: {Name}
...

## Validation Checkpoints
{When and how each checkpoint verifies the product works}

## Artefact Summary
{All files created/modified, grouped by story}
```

### plan.json (machine-readable)

Conforms to `scripts/schemas/plan.schema.json`. Contains all stories, observable truths, user journeys, and validation checkpoints as structured data for the orchestrator.

---

## Layer-Boundary Examples

**Good (single boundary):**
- Story: "Architecture -- models, repos, services" -- touches persistence + service layer
- Story: "API + Schemas" -- touches API routes + Pydantic schemas
- Story: "UI Scaffolding" -- touches templates + page routes

**Bad (too granular):**
- Story: "Add GearModel" -- single file, not enough for a story
- Story: "Everything" -- all layers, too large

### Breaking Change Blast Radius Analysis

For refactor epics, the goal-backward phase MUST identify breaking changes and their blast radius:

1. **Identify breaking changes** -- any change to model attributes, relationship loading, public APIs, or column types
2. **Enumerate ALL downstream consumers** -- grep the codebase for every usage
3. **Group consumers into the same story** as the breaking change, or place the fix in the immediately following story
4. **List every affected file** in the story scope
