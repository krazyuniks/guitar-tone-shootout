# Epic Workflow Reference

The epic workflow transforms a GitHub issue into committed, validated code through a 4-stage pipeline. Every stage exists to produce one thing: the **agent prompt**. The prompt is the only interface between planning and execution — it is the culmination of ingestion, context assembly, scope decisions, and plan decomposition. A well-constructed prompt is the single highest-leverage artefact in the pipeline.

The orchestrator (`workflow/orchestrator.py`) is stateless: it reads JSONL logs, determines the next step, runs it (Python function call for Stages 1–2, agent dispatch for Stages 3–4), and loops. No AI tokens are spent on orchestration.

The workflow is a standalone program invoked via `./wf` from the project root.

## Pipeline

```
                   ┌───────────┐               ┌──────────────────┐
  GitHub Issue ──► │  Stage 1  │ ──► EPIC.md ─►│     Stage 2      │
                   │  Ingest   │               │ Context Assembly │
                   └───────────┘               └────────┬─────────┘
                                                        │
                                                    CONTEXT.md
                                                        │
                                               ┌────────▼─────────┐
                                               │     Stage 3      │
                                               │    Planning      │
                                               └────────┬─────────┘
                                                        │
                                          plan.json + PLAN.md
                                          + user-decisions.json
                                                        │
                   ┌───────────┐               ┌────────▼─────────┐
  Committed Code ◄─│  Stage 4  │ ◄── PROMPT ◄──│ Prompt Assembly  │
  JSONL Logs       │ Execution │               │  (per story)     │
  SUMMARY.md       └───────────┘               └──────────────────┘
```

Stage 3 encompasses 7 sub-steps: ingest, context assembly, scope discussion, plan generation, verification (deterministic + agent), decision gate, and commit + push. Each stage is idempotent — re-running overwrites previous output. The planning agent is invoked at most 3 times: the initial attempt, plus up to one revision after each verification phase.

## Stage 1: Ingestion

**Input:** GitHub issue number.

**Process:** `gh issue view` fetches title, state, labels, and body. Writes `EPIC.md` with YAML frontmatter (`github_issue`, `title`, `state`, `labels`, `fetched`) followed by the verbatim issue body. Creates the `.planning/epics/E{N}/stories/` directory for downstream use.

The expected issue format is described in Stage 3 (Epic Issue Requirements). Stage 1 does not validate format — it captures the issue body as-is.

If `gh` fails (network error, issue not found, auth failure), the stage exits with a clear error. No partial output is written.

**Output:** `.planning/epics/E{N}/EPIC.md`

**Module:** `workflow/epic_ingest.py`

**Command:** Invoked as Step 1 of `./wf epic N`. No standalone command.

## Stage 2: Context Assembly

**Input:** `EPIC.md` (must exist).

**Process:** Pure Python I/O, zero AI tokens:
1. Read `EPIC.md` body.
2. Keyword-scan against hardcoded area mapping tables in `context_assembler.py` to detect relevant architecture areas. The 11 areas are: `signal_chain`, `gear_model`, `dual_database`, `frontend_layers`, `job_processing`, `audio_processing`, `data_model`, `orm_patterns`, `api_contract`, `security`, `testing`. The epic issue may also declare areas (see Stage 3, Epic Issue Requirements) — these are advisory hints. Stage 2's detection is authoritative. If declared and detected areas diverge, Stage 2 logs a warning.
3. Extract matching sections from `GTS-Technical-Architecture.md` using `<!-- CONTEXT:X -->` markers. The `architecture-layers` section is always included. Domain-specific wiki files are loaded conditionally: `Frontend-Architecture.md` when `frontend_layers` detected, `Audio-Processing.md` when `audio_processing` detected, `GTS-Remotion-Architecture.md` when `job_processing` detected.
4. Load selected codebase files from `.planning/codebase/`. `STRUCTURE.md` is always included. `SCHEMA.md`, `ENDPOINTS.md`, `IMPORTS.md`, `TESTS.md` are loaded conditionally based on detected areas (e.g. `SCHEMA.md` for `data_model` or `orm_patterns`, `ENDPOINTS.md` for `api_contract`).
5. Assemble into `CONTEXT.md` with sections: **Detected Areas** (area list with rationale), **Architecture** (selected wiki sections), **Codebase Structure** (selected codebase files), **Scope Discussion Questions** (area-specific questions, hardcoded per area in `context_assembler.py`).
6. Freshness check: warn if `.planning/codebase/` files are older than source files. Suggest `just map-codebase` to regenerate.

**Error handling:** If `EPIC.md` does not exist, the stage exits with an error (Stage 1 must run first). Missing wiki files or codebase structure files are logged as warnings and skipped — a partial `CONTEXT.md` is still produced. This allows the pipeline to proceed even if `just map-codebase` has not been run, though the resulting context will be less complete.

**Output:** `.planning/epics/E{N}/CONTEXT.md`

**Module:** `workflow/context_assembler.py`

**Command:** Stage 2 has no standalone command; invoked as part of `./wf epic N` or `just epic-plan N`.

**Note:** Stage 2 context supplements the compressed `AGENTS.md` (~1,500 tokens) with epic-specific wiki sections and codebase structure that are not auto-loaded. `AGENTS.md` provides general project conventions; Stage 2 provides the targeted architectural context needed for planning a specific epic.

> **Research history:** The wiki architecture, codebase mapping approach, and documentation compression strategy were evaluated in detail. See `Epic-Workflow-Research.md` for the full research log and decision rationale.

## Stage 3: Planning

**Input:** Epic number `N`.

**Process:** `./wf epic N` runs the full pipeline. At each step, if the output artefact already exists, the orchestrator prompts the user to skip or re-run. Steps 4–7 always re-run unless the plan was already committed (detectable via a `plan_committed` JSONL event, in which case the orchestrator skips directly to Stage 4).

### Epic Issue Requirements

Every epic GitHub issue must contain the sections below for the pipeline to produce a good plan. The pipeline does not validate issue structure — a malformed or incomplete issue produces a poor plan. The issue author is responsible for conformance.

**Background** — What exists in the codebase and what is missing. Describes the current state the epic builds upon.
→ Embedded in the planner prompt (Step 4) as background for plan generation.

**Scope** — Prose overview of which system areas the epic affects and what gaps exist. Describes the shape of the work at a high level — not individual files (see Key Files for concrete paths).
→ Embedded in the planner prompt (Step 4) to inform story scoping.

**Observable Truths** — User-perspective, verifiable-by-a-human statements that define "done". Not technical requirements — describe what a user can see or do. Good: "A user can visit /gear and see a list of their gear items." Bad: "GearRepository has a get_by_id method."
→ The planner (Step 4) maps each truth to stories. Phase B verification (Step 5) checks every truth is addressed. Stage 4 completion comments present truths as a human validation checklist.

**User Journeys** — Connected end-to-end narratives, not isolated assertions. Each journey includes an entry point, critical transitions (`{from, to, mechanism}`), and which observable truths the journey covers.
→ The planner (Step 4) maps journeys to stories and checkpoints. Phase B verification (Step 5) checks journey completeness and transition coverage.

**Verification Criteria** — Specific, testable statements with expected outcomes. Not vanity metrics ("page loads"). Example: "POST /api/gear returns 201 and the response body includes the created gear's ID."
→ The planner maps criteria to validation checkpoints in `plan.json`. Stage 4 validation agents use these to verify story output.

**Key Files** — Create vs Modify table listing concrete file paths. Files to create must have existing parent directories. Files to modify must exist on disk.
→ The planner uses this as input for story file scopes. Phase A verification (Step 5) validates file existence (checks 5–6).

**Dependency Graph** — Story ordering constraints ("X must complete before Y"). These are hints — the planner may refine ordering based on its own analysis of artefact dependencies.
→ Informs the planner's story ordering (Step 4). Phase A check 6 validates the planner's final ordering.

**Architecture Areas** — Which system areas the epic affects, from the area definitions (signal_chain, gear_model, dual_database, frontend_layers, job_processing, audio_processing, data_model, orm_patterns, api_contract, security, testing). These are hints — Stage 2's keyword scanner detects areas independently. If declared and detected areas diverge, Stage 2 logs a warning and uses its own detection as authoritative.
→ Stage 2 context assembly uses detected areas to select wiki sections and scope discussion questions.

### Step 1: Ingest (skip if `EPIC.md` exists)
The orchestrator runs Stage 1 ingestion to fetch the epic from GitHub. See Stage 1.

### Step 2: Context Assembly (skip if `CONTEXT.md` exists)
The orchestrator runs Stage 2 context assembly to produce `CONTEXT.md`. See Stage 2. The resulting `CONTEXT.md` contains selective wiki sections and codebase files based on detected areas, not wholesale dumps of all documentation.

### Step 3: Scope Discussion (skip if `user-decisions.json` exists)
The orchestrator presents scope discussion questions (extracted from `CONTEXT.md`) as an interactive Q&A session. The user answers each question to lock scope decisions. The orchestrator writes answers to `user-decisions.json` as key/value pairs (question string → answer string).

In non-interactive mode, the orchestrator loads decisions from an existing `user-decisions.json`. If the file does not exist in non-interactive mode, the orchestrator exits with an error.

Schema: `workflow/schemas/user-decisions.schema.json`

### Step 4: Plan Generation
The orchestrator assembles a planner prompt from `CONTEXT.md` and `user-decisions.json` using the planner prompt template (`workflow/templates/planner.md`), then dispatches a single planning agent invocation. The planner receives a lean `CONTEXT.md` (~30K tokens) containing only the wiki sections and codebase files relevant to the epic's detected areas. The planner prompt instructs the planning agent to:
1. Define observable truths (user-perspective, verifiable).
2. Derive required artefacts for each truth (full-stack walk).
3. Organise artefacts into stories (2–5 per epic, 3–8 files each).
4. Define user journeys (connected end-to-end narratives).
5. Place validation checkpoints strategically.
6. Specify `wiki_sections` per story in `plan.json` for Stage 4 prompt builder consumption.
7. Emit `PLAN.md` (human-readable) and `plan.json` (machine-readable) separated by `---PLAN_JSON_START---` / `---PLAN_JSON_END---` delimiters.

**What the planner does:**
- Goal-backward analysis: truths → artefacts → stories.
- Story sizing, agent config (skills, tools, MCP, budget).
- Checkpoint placement with check types and evidence fields.

**What the planner does NOT do:**
- Read or explore the codebase (the planner receives all context in the prompt).
- Make implementation decisions deferred to execution agents.
- Determine runtime behaviour (execution agents discover this).

### Step 5: Verification

**Phase A — Deterministic:** 7 structural checks on `plan.json`:
1. Schema conformance against `plan.schema.json`.
2. Referential integrity (truth IDs, story IDs, checkpoint references).
3. Truth coverage (every truth addressed by at least one story).
4. Journey coverage (every truth covered by at least one journey).
5. Scope coherence (files to modify exist on disk, parent directories for files to create exist).
6. Dependency ordering (stories that modify files appear after the story that creates them).
7. Budget sanity (total budget positive and within configured limit).

If Phase A fails, the orchestrator re-invokes the planning agent with the validation errors appended to the original prompt (attempt 2 of 3).

**Phase B — Agent verification:** 5 holistic dimensions scored by a verification agent:
1. Journey completeness (every journey step has a corresponding story and checkpoint).
2. Transition coverage (critical transitions between stories verified by checkpoints).
3. Intent alignment (no unaddressed requirements from `EPIC.md`, no scope creep beyond it).
4. Gap detection (no missing links in the full-stack chain from data model through to UI).
5. Validation sufficiency (checkpoints test observable behaviour, not just file existence).

Phase B only runs on a plan that passes Phase A. If Phase B fails, the orchestrator feeds verifier feedback back to the planning agent for one final revision (attempt 3 of 3). If the third attempt fails either phase, the orchestrator exits to human review.

**Revision budget:** The planning agent is invoked at most 3 times: the initial attempt, one Phase A revision, and one Phase B revision. Phases run sequentially — Phase B only runs on a plan that passes Phase A.

### Step 6: Decision Gate
Interactive human review of `PLAN.md` and `plan.json`. Three outcomes:
- **Approve:** The orchestrator proceeds to Step 7 (commit + push), then continues to Stage 4 execution.
- **Revise:** The human edits `plan.json` and/or `PLAN.md` directly. The orchestrator re-runs verification (Phase A then Phase B). Returns to the decision gate. This loop repeats until the human approves or rejects. The `./wf epic validate-plan N` command can be used to run Phase A independently during manual editing.
- **Reject:** The orchestrator exits. Planning artefacts remain on disk uncommitted. A subsequent `--resume` or re-run overwrites them (stages are idempotent).

### Step 7: Commit + Push
The orchestrator commits all planning artefacts (`EPIC.md`, `CONTEXT.md`, `user-decisions.json`, `plan.json`, `PLAN.md`) and pushes to remote. The orchestrator posts a GitHub comment on the epic issue summarising the approved plan (story count, truth count, estimated budget).

**Output:** `plan.json`, `PLAN.md`, `user-decisions.json`. Step 7 commits these alongside `EPIC.md` and `CONTEXT.md` (produced by Stages 1–2).

**Modules:** `workflow/scope_discussion.py`, `workflow/plan_generator.py`, `workflow/plan_validator.py`, `workflow/plan_verifier.py`

**Command:** `./wf epic N` (single entry point for the full pipeline).

### Todo

- [ ] Define planner prompt template (`workflow/templates/planner.md`) — sections, token budget, how `CONTEXT.md` and `user-decisions.json` are embedded
- [ ] Define `user-decisions.json` schema (`workflow/schemas/user-decisions.schema.json`)
- [ ] Define `scope_discussion.py` module — how questions are extracted from `CONTEXT.md`, interactive vs non-interactive mode, question format
- [ ] Add example of a well-formed epic issue (or link to one) in Epic Issue Requirements
- [ ] Decide whether the pipeline should validate issue structure (in Stage 1 or Stage 2) rather than relying on the issue author

## Stage 4: Execution

**Input:** `plan.json` (primary). The orchestrator also references `EPIC.md` for the epic goal and the story directory structure for prompt assembly.

**Process:** The orchestrator executes stories sequentially. On re-invocation, the orchestrator reads story JSONL logs to determine which stories are complete and resumes from the first incomplete story. For each story:

### 1. Pre-flight Checks
The orchestrator verifies inputs before dispatching the story's agent:
- Files that earlier stories should have created exist.
- Files the current story will modify exist.
- Parent directories for files the current story will create exist.

If all checks pass, the orchestrator proceeds to dispatch. If 1–2 files to modify are missing but the current story also creates them, the orchestrator logs a warning and proceeds. If any other check fails (upstream files missing, parent directories absent), the orchestrator classifies the failure as `upstream` and exits to human review.

### 2. State Assumption
If the story's `state_assumption` field in `plan.json` is `"clean"`, the orchestrator runs the configured database reset command before dispatch. The default is `"cumulative"` (no action — the story builds on the state left by previous stories).

### 3. Prompt Construction
The prompt builder (`workflow/prompt_builder.py`) assembles the agent prompt from 7 sections:

| Section | Source | Content |
|---------|--------|---------|
| 1. Role | `workflow/templates/role_{type}.md` | Agent type template (implementation, validation, regression) |
| 2. Context | `EPIC.md`, `plan.json`, wiki indexes | Epic goal, story purpose, observable truths addressed, compressed doc index (epilot pattern) |
| 3. Scope | `plan.json` | Files to create and modify |
| 4. Implementation Notes | `plan.json` | Domain-specific hints from the planner |
| 5. Verification | `plan.json` | Criteria from the story's validation checkpoint |
| 6. Failure Feedback | `story.jsonl` | Error description, files modified, JSONL excerpt (retry attempts only) |
| 7. Constraints | `workflow/templates/role_{type}.md` | What NOT to do (role-specific) |

The prompt body targets <2,000 tokens. With per-story documentation segmentation, total documentation overhead is ≤650 tokens. Domain-tagged rules files (`.claude/rules/`) are loaded selectively per story based on checkpoint type and file paths. The `wiki_sections` field from `plan.json` feeds the prompt builder for targeted wiki section loading via header indexes in `.planning/wiki-indexes/`. Domain knowledge also comes from skills listed in the story's agent config in `plan.json`, injected by `dispatch.py` at dispatch time. The prompt body contains only story-specific instructions.

### 4. Agent Dispatch
The dispatch module (`workflow/dispatch.py`) sends the assembled prompt to a Claude Code agent:
- CLI: `claude -p - --max-turns N --max-budget-usd B --no-session-persistence --output-format json --dangerously-skip-permissions`
- The prompt is piped via stdin to avoid OS argument length limits.
- The `CLAUDECODE` env var is cleared before dispatch to prevent infinite recursion if an agent attempts to spawn sub-agents.
- `--dangerously-skip-permissions` is required because agents run non-interactively. Safety is enforced through scoped tool restrictions (see table below) and story-level scope constraints in the prompt.

**Capability tiers:**

The dispatch module uses three capability tiers to abstract model selection. Tier-to-model mapping is configured in `dispatch.py` and can change without affecting the pipeline.

| Tier | Purpose |
|------|---------|
| high | Complex reasoning: planning, multi-file architecture decisions |
| standard | Implementation, code review, regression testing |
| light | Simple validation: HTTP checks, process status, evidence collection |

On transient failures (HTTP 529, network errors, 5xx), the dispatch module retries with the next lower tier without consuming the story retry budget. Fallback chain: high → standard → light → light (no cheaper fallback).

**Budget defaults per agent type:**

| Agent Type | Tier | Max Turns | Max Budget |
|------------|------|-----------|------------|
| Implementation | standard | 40 | $4.00 |
| Validation | light | 15 | $0.50 |
| Regression | standard | 30 | $3.00 |

The planning agent (high tier, 50 turns, $5.00 budget) and verification agent (standard tier) are dispatched in Stage 3. See Stage 3 Steps 4–5.

**Tool restrictions per agent role:**

| Agent Role | Allowed | Denied |
|------------|---------|--------|
| Implementation | Read, Edit, Write, Bash, Glob, Grep | Task |
| Validation (browser) | Read, Bash, Glob, Grep + MCP | Edit, Write |
| Validation (API/DB) | Bash, Read, Glob, Grep | Edit, Write |
| Regression test | Read, Edit, Write, Bash, Glob, Grep | Task |

### 5. Validation Checkpoint
If a checkpoint exists after this story, the orchestrator runs the corresponding check:

| Check Type | Tier | MCP | Evidence Fields |
|------------|------|-----|-----------------|
| `http` | light | none | status_code, url, response_excerpt |
| `http+dom` | light | chrome-devtools | status_code, url, dom_selector, element_text |
| `browser+db` | standard | chrome-devtools | action_performed, sql_query, row_count, sample_row |
| `api+response` | light | none | status_code, url, method, response_body_excerpt |
| `process` | light | none | process_name, pid_or_status, log_excerpt |
| `screenshot` | standard | chrome-devtools | screenshot_path, observations |
| `regression` | — | none | test_command, exit_code, test_count, failure_count |
| `quality` | — | none | commands_run[], exit_code, error_count |

`regression` and `quality` checks run configured test commands directly via subprocess (deterministic, no agent). Criterion strings in `plan.json` are mapped to shell commands via project-level test configuration. Other check types dispatch a read-only validation agent with `--json-schema` for structured output against `workflow/schemas/validation-result.schema.json`. The orchestrator validates evidence fields to reject empty or generic responses ("looks good", "seems fine"); rejected evidence counts as a validation failure.

### 6. Failure Model

5-category classification with category-aware retry policy:

| Category | Retry Budget | Action |
|----------|-------------|--------|
| `env` | 0 | The orchestrator exits immediately (infrastructure problem). |
| `upstream` | 0 | The orchestrator exits to human review (earlier story produced incorrect output). |
| `scope` | 2 | The orchestrator retries with failure feedback in prompt section 6. |
| `implementation` | 2 | The orchestrator retries with failure feedback in prompt section 6. |
| `unknown` | 2 | The orchestrator retries with failure feedback in prompt section 6. |

Classification uses explicit pattern tables (`ENV_PATTERNS`, `SCOPE_PATTERNS`, `IMPLEMENTATION_PATTERNS` in `story_executor.py`) and a file-ownership map derived from `plan.json` (which story's scope includes which files) for upstream detection.

Total attempts per story: 1 initial + 2 retries = 3 maximum. If all 3 attempts fail for a retryable category, the orchestrator exits to human review with the failure category and context.

### 7. GitHub Integration
After each story, the orchestrator:
- Posts a story completion or failure comment on the epic issue (story ID, attempt count, files changed, cost).
- Syncs the local branch with remote via `git_sync()` (fetch, merge, push with `--force-with-lease`). If a merge conflict occurs, `git_sync()` raises `GitConflictError` and the orchestrator exits to human review.

After all stories complete, the orchestrator:
- Posts an epic completion comment on the issue.
- Posts a human validation prompt: observable truths as a checklist, user journeys to walk through manually.
- Adds the `workflow-complete` label to the issue.
- Generates `SUMMARY.md` in the epic directory.

**Output:** Committed code, JSONL logs, `SUMMARY.md`.

**Modules:** `workflow/story_executor.py`, `workflow/prompt_builder.py`, `workflow/dispatch.py`, `workflow/validation.py`

**Command:** `./wf epic N` (single entry point). Stage 4 is reached when the decision gate approves, or on re-invocation when the orchestrator detects a committed plan. Within Stage 4, the orchestrator reads story JSONL logs to determine progress and resumes from the first incomplete story.

### Todo

- [ ] Define `SUMMARY.md` structure — sections, data fields (per-story results, total cost, observable truth status, links to JSONL)
- [ ] Define story comment template — what fields appear in GitHub issue comments per story
- [ ] Define test command configuration format — how criterion strings in `plan.json` map to shell commands per project
- [ ] Decide where capability tiers are formally defined — currently inline in Stage 4 Step 4; consider a dedicated section or the dispatch module description in Program Structure

## Observability

### Structured JSONL Event Log

Every event is a single JSON line with universal fields:

```json
{
  "schema_v": 1,
  "run_id": "uuid4",
  "ts": "ISO 8601",
  "event": "event_type",
  ...event-specific fields
}
```

The `level` column determines which JSONL file receives the event: `epic` events are written to `epic.jsonl`, `story` events to `stories/{story_id}/story.jsonl`.

Agent dispatch events log both `tier` (the capability abstraction: high, standard, light) and `model` (the resolved model identifier). The document refers to tiers; the model is captured for cost auditing and debugging.

**Stage 3 events (planning):**

| Event | Level | Key Fields |
|-------|-------|------------|
| `planner_dispatched` | epic | epic, attempt, tier, model, prompt_hash, prompt_tokens |
| `planner_complete` | epic | epic, attempt, turns, cost_usd, response_path |
| `planner_failed` | epic | epic, attempt, error, turns, cost_usd, response_path |
| `phase_a_pass` | epic | epic, attempt |
| `phase_a_fail` | epic | epic, attempt, checks_failed[] |
| `verifier_dispatched` | epic | epic, attempt, tier, model, prompt_hash, prompt_tokens |
| `phase_b_pass` | epic | epic, attempt, scores{} |
| `phase_b_fail` | epic | epic, attempt, scores{}, feedback |
| `plan_approved` | epic | epic |
| `plan_revised` | epic | epic |
| `plan_rejected` | epic | epic |
| `plan_committed` | epic | epic, commit |

**Stage 4 events (execution):**

| Event | Level | Key Fields |
|-------|-------|------------|
| `epic_started` | epic | epic, stories |
| `story_started` | story | story_id, attempt, index |
| `preflight_pass` | story | story_id, attempt |
| `preflight_fail` | story | story_id, attempt, failure_category, description |
| `agent_dispatched` | story | story_id, attempt, tier, model, prompt_hash, prompt_tokens |
| `agent_complete` | story | story_id, attempt, commit, turns, cost_usd, response_path |
| `agent_failed` | story | story_id, attempt, error, turns, cost_usd, response_path |
| `validation_pass` | story | story_id, check_type, results[] |
| `validation_fail` | story | story_id, check_type, results[], failure_category |
| `story_complete` | story | story_id, attempt, commit |
| `story_failed` | story | story_id, attempt, reason |
| `exit_to_human` | story | story_id, reason, failure_category, context{} |
| `github_comment` | epic | epic, comment_url |
| `epic_complete` | epic | epic, stories_completed, total_cost_usd |
| `epic_failed` | epic | epic, reason, stories_completed, stories_failed |

Schema: `workflow/schemas/jsonl-events.schema.json`

### Prompt Persistence

Every prompt is written to disk before dispatch.

**Stage 3 (planning):**
- Planner prompt: `.planning/epics/E{N}/planner-prompt-attempt-{A}.md`
- Verifier prompt: `.planning/epics/E{N}/verifier-prompt-attempt-{A}.md`

**Stage 4 (execution):**
- Implementation prompt: `.planning/epics/E{N}/stories/{story_id}/prompt-attempt-{A}.md`
- Validation prompt: `.planning/epics/E{N}/stories/{story_id}/validation-prompt-attempt-{A}.md`

**All stages:**
- Dispatch log: `.planning/logs/dispatch-{tier}-{hash}-{timestamp}.txt`

The dispatch log filename uses the capability tier (high, standard, light). The resolved model name is recorded inside the file and in the corresponding JSONL event.

### Agent Output Capture

Full agent responses are written to separate JSON files alongside their prompts. The corresponding JSONL event (`planner_complete`, `agent_complete`, etc.) includes a `response_path` field pointing to the file. Claude Code's `--output-format json` provides a structured envelope with `num_turns`, `cost_usd`, and `result` text.

**Stage 3:** `.planning/epics/E{N}/planner-response-attempt-{A}.json`, `.planning/epics/E{N}/verifier-response-attempt-{A}.json`
**Stage 4:** `.planning/epics/E{N}/stories/{story_id}/response-attempt-{A}.json`

### Validation Evidence

Each validation result includes per-criterion `{criterion, status, evidence{}}`. Evidence is validated against check-type-specific required fields defined in `workflow/schemas/validation-result.schema.json`. The orchestrator pattern-matches evidence text against a reject list of generic phrases ("looks good", "seems fine") and treats matches as validation failures.

### Log Locations

```
.planning/epics/E{N}/
├── epic.jsonl                                  # Epic-level events (Stages 3–4)
├── planner-prompt-attempt-{A}.md               # Planner prompt per attempt
├── planner-response-attempt-{A}.json           # Planner response per attempt
├── verifier-prompt-attempt-{A}.md              # Phase B verifier prompt per attempt
├── verifier-response-attempt-{A}.json          # Phase B verifier response per attempt
├── SUMMARY.md                                  # Generated on completion or failure
└── stories/
    └── {story_id}/
        ├── story.jsonl                         # Story-level events
        ├── prompt-attempt-{A}.md               # Implementation prompt per attempt
        ├── response-attempt-{A}.json           # Agent response per attempt
        ├── validation-prompt-attempt-{A}.md    # Validation prompt per attempt
        └── validation-response-attempt-{A}.json # Validation response per attempt

.planning/logs/
└── dispatch-{tier}-{hash}-{ts}.txt             # All dispatched prompts (all tiers)
```

### Inspection

`./wf epic status N` reads JSONL logs and reports:

- **Pipeline stage:** Current stage (planning, execution, complete, failed).
- **Planning status:** Planner attempts, Phase A/B results, decision gate outcome.
- **Per-story table:** Story ID, status (pending/running/complete/failed), attempt count, files changed, cost.
- **Totals:** Stories completed/failed/remaining, total cost, total turns.
- **Failures:** Most recent failure category and context for any failed story.

Direct JSONL reads with `jq` for ad-hoc filtering: e.g. `jq 'select(.event == "agent_dispatched")' .planning/epics/E1/stories/S1/story.jsonl`.

### Todo

- [ ] Define `wf epic status N` output format precisely (table layout, column widths, colour coding)
- [ ] Decide maximum response file size before truncation (or whether to truncate at all)

## Artefact Map

| Artefact | Created By | Consumed By | Location |
|----------|-----------|-------------|----------|
| `EPIC.md` | `epic_ingest.py` | `context_assembler.py`, `prompt_builder.py` | `.planning/epics/E{N}/` |
| `CONTEXT.md` | `context_assembler.py` | `scope_discussion.py`, `plan_generator.py`, `plan_verifier.py` | `.planning/epics/E{N}/` |
| `user-decisions.json` | `scope_discussion.py` | `plan_generator.py` | `.planning/epics/E{N}/` |
| `plan.json` | `plan_generator.py` | `orchestrator.py`, `story_executor.py`, `prompt_builder.py`, `plan_validator.py`, `plan_verifier.py` | `.planning/epics/E{N}/` |
| `PLAN.md` | `plan_generator.py` | Human review (Decision Gate) | `.planning/epics/E{N}/` |
| `epic.jsonl` | `orchestrator.py` | `orchestrator.py` (resume, stage detection), `wf epic status` | `.planning/epics/E{N}/` |
| `story.jsonl` | `story_executor.py` | `prompt_builder.py` (failure feedback), `orchestrator.py` (comments, summary) | `.planning/epics/E{N}/stories/{id}/` |
| `STRUCTURE.md` | `codebase_mapper.py` | `context_assembler.py` | `.planning/codebase/` |
| `SCHEMA.md` | `codebase_mapper.py` | `context_assembler.py` | `.planning/codebase/` |
| `ENDPOINTS.md` | `codebase_mapper.py` | `context_assembler.py` | `.planning/codebase/` |
| `IMPORTS.md` | `codebase_mapper.py` | `context_assembler.py` | `.planning/codebase/` |
| `TESTS.md` | `codebase_mapper.py` | `context_assembler.py` | `.planning/codebase/` |
| `*.md` (wiki indexes) | `wiki_indexer.py` | `prompt_builder.py` | `.planning/wiki-indexes/` |
| `planner-prompt-attempt-{A}.md` | `plan_generator.py` | Debugging (post-mortem) | `.planning/epics/E{N}/` |
| `planner-response-attempt-{A}.json` | `plan_generator.py` | Debugging (post-mortem) | `.planning/epics/E{N}/` |
| `verifier-prompt-attempt-{A}.md` | `plan_verifier.py` | Debugging (post-mortem) | `.planning/epics/E{N}/` |
| `verifier-response-attempt-{A}.json` | `plan_verifier.py` | Debugging (post-mortem) | `.planning/epics/E{N}/` |
| `prompt-attempt-{A}.md` | `prompt_builder.py` | Debugging (post-mortem) | `.planning/epics/E{N}/stories/{id}/` |
| `response-attempt-{A}.json` | `story_executor.py` | Debugging (post-mortem) | `.planning/epics/E{N}/stories/{id}/` |
| `validation-prompt-attempt-{A}.md` | `validation.py` | Debugging (post-mortem) | `.planning/epics/E{N}/stories/{id}/` |
| `validation-response-attempt-{A}.json` | `validation.py` | Debugging (post-mortem) | `.planning/epics/E{N}/stories/{id}/` |
| `dispatch-{tier}-*.txt` | `dispatch.py` | Debugging (post-mortem) | `.planning/logs/` |
| `SUMMARY.md` | `orchestrator.py` | Human review, GitHub | `.planning/epics/E{N}/` |

## Commands

```bash
./wf epic N                 # Full pipeline: ingest -> context -> scope -> plan -> verify -> gate -> execute
./wf epic status N          # Show progress from JSONL logs (read-only)
./wf epic validate-plan N   # Run Phase A deterministic validation only (read-only)
./wf map codebase           # Regenerate .planning/codebase/ files (deterministic, <10s)
./wf map wiki               # Regenerate .planning/wiki-indexes/ (deterministic, <5s)
./wf map all                # Both of the above
```

Equivalent `just` aliases:

```bash
just map-codebase           # Regenerate .planning/codebase/
just index-wiki             # Regenerate .planning/wiki-indexes/
just map-context            # Both
```

`./wf epic N` is the single entry point. On re-invocation, the orchestrator detects completed stages via artefacts and JSONL events, prompting the user to skip or re-run each. There are no separate commands for individual stages or crash recovery — the orchestrator handles resumption automatically.

`./wf epic status N` output format is defined in Observability → Inspection.

## Program Structure

The workflow follows the same pattern as `worktree.py`: a thin `uv run --script` entry point at the project root with PEP 723 inline dependency metadata, backed by a package directory.

```
project-root/
├── wf                              # Entry point (uv run --script, chmod +x)
└── workflow/
    ├── __init__.py
    ├── cli.py                      # Typer CLI, subcommand routing
    ├── orchestrator.py             # Outer loop, GitHub integration, SUMMARY.md generation
    ├── epic_ingest.py              # Fetch GitHub issue -> EPIC.md
    ├── context_assembler.py        # Keyword scanning, wiki/codebase reading -> CONTEXT.md
    ├── codebase_mapper.py          # Deterministic codebase mapping via ast.parse() -> .planning/codebase/
    ├── wiki_indexer.py             # Wiki header index generation -> .planning/wiki-indexes/
    ├── scope_discussion.py         # Interactive Q&A, user-decisions.json generation
    ├── plan_generator.py           # Planning agent dispatch -> PLAN.md + plan.json
    ├── plan_validator.py           # Phase A: 7 deterministic checks
    ├── plan_verifier.py            # Phase B: 5-dimension agent verification, Decision Gate
    ├── story_executor.py           # Inner loop: preflight -> dispatch -> validate -> retry
    ├── prompt_builder.py           # 7-section prompt assembly (<2,000 tokens), domain-filtered rules, compressed doc index
    ├── dispatch.py                 # Claude Code CLI adapter, tier resolution, MCP config, transient failure detection
    ├── validation.py               # Type-aware validation checkpoints, evidence validation
    ├── jsonl_logger.py             # Append-only JSONL with crash safety, resumption logic
    ├── git_helpers.py              # Robust commit (GitCommitError), sync (GitConflictError), push (GitPushError)
    ├── schemas/
    │   ├── plan.schema.json                # Validates plan.json structure (Phase A Check 1)
    │   ├── user-decisions.schema.json      # Validates user-decisions.json structure
    │   ├── jsonl-events.schema.json        # Documents all JSONL event types and fields
    │   ├── validation-result.schema.json   # Structured output schema for validation agents
    │   └── verifier-result.schema.json     # Structured output schema for plan verifier
    └── templates/
        ├── planner.md              # Planner prompt template (Stage 3 Step 4)
        ├── role_implementation.md  # Role template for implementation agents
        ├── role_validation.md      # Role template for validation agents
        └── role_regression.md      # Role template for regression test agents
```

`wf` is a thin entry point with `#!/usr/bin/env -S uv run --script` shebang and PEP 723 inline script metadata declaring dependencies (typer, rich, jsonschema, pyyaml). It adds the project root to `sys.path` and calls `workflow.cli.main()`. Dependencies are auto-installed by `uv` — no venv setup required.

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer>=0.9.0",
#     "rich>=13.0",
#     "jsonschema>=4.0",
#     "pyyaml>=6.0",
# ]
# ///
"""Epic workflow CLI. All logic is in the workflow package."""
import sys
from pathlib import Path

current = Path(__file__).resolve().parent
if str(current) not in sys.path:
    sys.path.insert(0, str(current))

from workflow.cli import main

if __name__ == "__main__":
    main()
```
