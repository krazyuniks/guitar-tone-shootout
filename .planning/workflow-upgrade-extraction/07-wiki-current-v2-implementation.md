# Epic Workflow V2 — Implementation Plan

Sequential implementation steps for the V2 behavioural-validation epic
workflow. Each step executes in a fresh session. The research document
(`Epic-Workflow-V2-Behavioural-Validation.md`) is the authoritative
reference — this plan operationalises every decision within it.

**Scope boundary:** V2 is Claude-only. Multi-provider adapters (Codex,
Gemini), cross-tool skill sync, JSONL analytics, parallel story
execution, and local model routing are explicitly deferred to V2.1
(research doc Section 9).

**Working branch:** Create a new branch from `main` for V2
implementation. All steps commit to this branch.

---

## Step 1: Define Foundational JSON Schemas — [x]

**Goal:** Create the 4 canonical schema files that govern every
interface in V2. These are the contracts — everything downstream
references them.

**Parallel work (Task):** Draft all 4 schemas in parallel. Each schema
is independent.

### Files to Create

| File | Governs | Reference |
|------|---------|-----------|
| `scripts/schemas/plan.schema.json` | `plan.json` structure | Section 8.4 Decision 3 |
| `scripts/schemas/jsonl-events.schema.json` | All JSONL event types | Section 2 (JSONL Log) |
| `scripts/schemas/validation-result.schema.json` | `--json-schema` for validation agents | Section 8.4 Decision 4 |
| `scripts/schemas/verifier-result.schema.json` | `--json-schema` for plan verifier agent | Section 8.4 Decision 8 |

### Schema 1: `plan.schema.json`

Must capture the full `plan.json` structure from Section 8.4 Decision 3:

- **Top-level:** `schema_v` (int, currently `1`), `epic_number` (int),
  `goal` (string)
- **`observable_truths`:** Array of `{id: int, statement: string}`
- **`user_journeys`:** Array of journey objects, each containing:
  - `journey_id` (string, e.g. `"J1"`)
  - `persona` (string, e.g. `"authenticated user"`)
  - `narrative` (string — connected end-to-end walkthrough in plain
    English, present tense, covering happy path from entry point through
    all critical transitions)
  - `truths_covered` (array of int — references to observable_truths IDs)
  - `entry_point` (string — URL path)
  - `critical_transitions` (array of `{from, to, mechanism}`)
- **`stories`:** Array of story objects, each containing:
  - `story_id` (string, e.g. `"01-architecture"`)
  - `name` (string)
  - `purpose` (string)
  - `agent` object: `model` (enum: opus/sonnet/haiku), `skills` (array
    of string), `tools` (array of string), `mcp` (array of string),
    `max_turns` (int), `max_budget_usd` (number)
  - `scope` object: `create` (array of file paths), `modify` (array of
    file paths)
  - `state_assumption` (enum: `"cumulative"` | `"clean"`, default
    `"cumulative"`) — `cumulative` means story expects data from all
    previous stories; `clean` means orchestrator runs `just db-reset`
    before dispatch (Section 8.4 Decision 7)
  - `implementation_notes` (array of string)
  - `truths_addressed` (array of int — references to observable_truths IDs)
- **`validation_checkpoints`:** Array of checkpoint objects, each
  containing:
  - `after_story` (string — references a story_id)
  - `check_type` (enum: `http`, `http+dom`, `browser+db`, `api+response`,
    `process`, `screenshot`, `regression`, `quality`)
  - `checks` array of `{criterion: string, evidence_fields: [string]}`

**Validation rules to encode in the schema or document alongside:**
These are checked by the Phase A deterministic validator (Step 8), not
by JSON Schema alone:
1. Every `truths_addressed` ID must exist in `observable_truths`
2. Every checkpoint `after_story` must reference a valid `story_id`
3. Every journey `truths_covered` ID must exist in `observable_truths`
4. Every observable truth must be addressed by at least one story
5. Every observable truth must appear in at least one journey's
   `truths_covered` (no orphan truths)
6. Files in `scope.modify` must exist on disk
7. Files in `scope.create` must have existing parent directories
8. Stories referencing files created by earlier stories must appear
   after those stories
9. Total estimated budget (sum of `max_budget_usd`) within reason

### Schema 2: `jsonl-events.schema.json`

Must capture all event types from Section 2 (JSONL Log as Source of
Truth).

**Universal fields (present on every event):**
- `schema_v` (int, currently `1`)
- `run_id` (UUID string)
- `ts` (ISO 8601 datetime with timezone, monotonically increasing)
- `event` (enum of known event types)

**Story-scoped fields (present on story-level events, absent on
epic-level events):**
- `story_id` (string)
- `attempt` (int, 1-based, increments on retry)

**Epic-level event types** (no `story_id` or `attempt`):
`epic_started`, `github_comment`, `epic_complete`

**Story-level event types** (include `story_id` + `attempt`):
`story_started`, `agent_dispatched`, `preflight_pass`, `preflight_fail`,
`agent_complete`, `agent_failed`, `validation_pass`, `validation_fail`,
`story_complete`, `story_failed`, `exit_to_human`

**Event-specific fields:**
- `agent_dispatched`: `model`, `prompt_hash`, `prompt_tokens`,
  `skill_tokens`
- `agent_complete`: `commit` (git hash), `turns`, `cost_usd`
- `agent_failed`: `error`, `turns`, `cost_usd`
- `validation_pass`/`validation_fail`: `check_type`, `results` (array
  of `{criterion, status, evidence}`), `failure_category` (on fail only)
- `preflight_fail`: `failure_category`, `description`
- `exit_to_human`: `reason` (short description), `failure_category`,
  `context` (rich object: `{story_id, attempt, last_error, files_affected,
  jsonl_excerpt}` — enough info for a human to diagnose without reading
  the full JSONL log)
- `github_comment`: `epic` (int), `comment_url`
- `epic_started`: `epic` (int), `stories` (int — count)
- `epic_complete`: `epic` (int), `stories_completed` (int),
  `total_cost_usd` (number)
- `story_started`: `index` (int — position in story order)
- `story_complete`: `commit` (git hash)
- `story_failed`: `reason`

**`failure_category` enum:** `env`, `scope`, `implementation`,
`unknown`, `upstream`

### Schema 3: `validation-result.schema.json`

Must capture structured validation output per Section 8.4 Decision 4
and Section 8.5 Decision 5. This is the `--json-schema` passed to
validation agents.

```json
{
  "type": "object",
  "properties": {
    "status": {"enum": ["pass", "fail"]},
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "criterion": {"type": "string"},
          "status": {"enum": ["pass", "fail"]},
          "evidence": {"type": "object"}
        },
        "required": ["criterion", "status", "evidence"]
      }
    }
  },
  "required": ["status", "results"]
}
```

The `evidence` object's required fields vary by check type. Document
the per-type evidence requirements from Section 8.4 Decision 4:

| Check Type | Required Evidence Fields |
|------------|------------------------|
| `http` | `status_code`, `url`, `response_excerpt` |
| `http+dom` | `status_code`, `url`, `dom_selector`, `element_text` |
| `browser+db` | `action_performed`, `sql_query`, `row_count`, `sample_row` |
| `api+response` | `status_code`, `url`, `method`, `response_body_excerpt` |
| `process` | `process_name`, `pid_or_status`, `log_excerpt` |
| `screenshot` | `screenshot_path`, `observations` |
| `regression` | `test_command`, `exit_code`, `test_count`, `failure_count` |
| `quality` | `commands_run`, `exit_code`, `error_count` |

The orchestrator validates that evidence fields are populated — empty or
generic evidence is treated as a validation failure (not a pass).

### Schema 4: `verifier-result.schema.json`

Must capture the plan verifier's structured output per Section 8.4
Decision 8:

```json
{
  "type": "object",
  "properties": {
    "status": {"enum": ["pass", "fail"]},
    "journey_completeness": {
      "status": "pass|fail",
      "gaps": [{"journey_id", "step", "missing"}]
    },
    "transition_coverage": {
      "status": "pass|fail",
      "uncovered": [{"journey_id", "from", "to", "mechanism"}]
    },
    "intent_alignment": {
      "status": "pass|fail",
      "unaddressed_requirements": ["..."],
      "scope_creep": ["..."]
    },
    "gap_detection": {
      "status": "pass|fail",
      "gaps": [{"between": ["story_id_1", "story_id_2"], "missing"}]
    },
    "validation_sufficiency": {
      "status": "pass|fail",
      "weak_checks": [{"checkpoint", "criterion", "risk"}]
    }
  },
  "required": ["status", "journey_completeness", "transition_coverage",
               "intent_alignment", "gap_detection", "validation_sufficiency"]
}
```

### Definition of Done

- [ ] All 4 schema files exist at `scripts/schemas/`
- [ ] `plan.schema.json` encodes every field from Section 8.4 Decision 3
      including `user_journeys` with `critical_transitions`,
      `state_assumption` per story, and evidence fields per check type
- [ ] `jsonl-events.schema.json` encodes every event type from Section 2
      with universal fields, story-scoped fields, and event-specific
      fields including `failure_category` enum
- [ ] `validation-result.schema.json` matches the `--json-schema` format
      for validation agents with per-check-type evidence requirements
      documented
- [ ] `verifier-result.schema.json` matches the 5-dimension verification
      structure from Section 8.4 Decision 8
- [ ] All schemas use `"$schema": "https://json-schema.org/draft/2020-12/schema"`
- [ ] All schemas include `schema_v: 1` for future evolution
- [ ] Commit: `feat(workflow): add V2 foundational JSON schemas`

---

## Step 2: Delete V1 Artefacts — [x]

**Goal:** Remove all files that V2 replaces outright. This creates a
clean starting point and prevents accidental use of V1 machinery.

**Parallel work (Task):** Group deletions by category and execute in
parallel. Each group is independent.

### Group A: Scripts to Delete

| File | Reason |
|------|--------|
| `scripts/snapshot_tests.py` | No test-author/implementer split in V2 (Section 8.1) |
| `scripts/tasks_from_plan.py` | V2 has no `.tasks/` per-task markdown files (Section 8.1) |
| `scripts/validate_tasks.py` | V2 validates `plan.json` not `.tasks/` structure (Section 8.1) |
| `scripts/epic_reviewer.py` | V2 uses JSONL-based metrics, not TDD phase metrics (Section 8.1) |

**Note:** `scripts/gh_tasks_sync.py` is referenced in the research doc
(Section 3) but does not exist on disk — it was planned but never built.
No deletion needed.

**Keep:** `scripts/run_epic.py` is kept temporarily as a reference for
extracting dispatch logic in Step 4. It is deleted in Step 14 after
extraction is complete.

**Keep permanently:** `scripts/test_quality_check.py` (mock ban
enforcement — project policy, not workflow-specific),
`scripts/health_check.py`, `scripts/seed_di_tracks.py`,
`scripts/gts_admin.py`, `scripts/__init__.py`.

### Group B: Agents to Delete

| File | Reason |
|------|--------|
| `.claude/agents/test-author.md` | No test-author role in V2 — tests written after product works (Section 8.1). GTS test patterns (~120 lines) must be preserved by moving to `gts-testing` skill BEFORE deletion. |
| `.claude/agents/implementer.md` | Replaced by orchestrator-built prompts (Section 8.5). Architectural patterns and banned patterns must be preserved by moving to skills BEFORE deletion. |
| `.claude/agents/gts-lint-checker.md` | Conflicts with "never spend tokens on lint" principle (Section 8.1) |
| `.claude/agents/plan-reviewer.md` | Replaced by two-phase plan verification (Section 8.4 Decision 8) |
| `.claude/agents/epic-context-loader.md` | Replaced by deterministic Python function (Section 8.4 Decision 2) |
| `.claude/agents/epic-gray-area-analyst.md` | Replaced by deterministic Python keyword lookup (Section 8.4 Decision 2) |
| `.claude/agents/epic-goal-backward.md` | Merged into single Opus planner (Section 8.4 Decision 1) |
| `.claude/agents/epic-task-breakdown.md` | Replaced by plan.json story format (Section 8.4 Decision 1) |

**Critical pre-deletion step:** Before deleting `test-author.md` and
`implementer.md`, extract their reusable content:
- From `test-author.md`: ~120 lines of GTS test patterns (correct
  SQLite fixtures, service test patterns, E2E patterns, banned
  patterns) → move to `.claude/skills/gts-testing/references/`
- From `implementer.md`: systematic strategy
  (analyse→plan→execute→verify), architecture context → move to
  relevant skills or preserve as reference

**Keep:** `.claude/agents/debugger.md`, `gts-quality-reviewer.md`,
`gts-error-resolver.md`, `gts-workflow-verifier.md`, `gts-log-monitor.md`
— these are not workflow-specific.

### Group C: Commands to Delete

| File | Reason |
|------|--------|
| `.claude/commands/epic.md` | Trivial 5-line router for TDD workflow (Section 8.1) |
| `.claude/commands/epic-review.md` | TDD-specific review structure (Section 8.1) |

**Keep:** `delegate.md`, `ralph-hybrid.md`, `run-prompt.md`,
`checkpoint.md`, `claim.md`, `merge.md`, `status.md`, `next-issue.md`,
`deps.md`, `check.md`, `arch-review.md`, `worktree.md`,
`workflow-check.md`, `resume.md` — these are not workflow-specific
(Section 8.1 confirms each).

### Group D: Infrastructure to Delete

| Path | Reason |
|------|--------|
| `.tasks/_templates/task.md` | TDD-specific template (Section 8.1) |
| `.tasks/projects/` (entire tree) | V2 uses JSONL + git, not per-task markdown (Section 8.3 Decision 6) |
| `.planning/epics/*/GOALS.md` | Replaced by `plan.json` (Section 8.4) |
| `.planning/epics/*/TASKS.md` | Replaced by `plan.json` stories (Section 8.4) |
| `.planning/epics/*/created.json` | V1 planning artifact |

**Keep:** `.planning/codebase/` (STRUCTURE.md, ARCHITECTURE.md, etc.)
— the context assembly function reads these (Section 8.4 Decision 2).

### Group E: Justfile Recipes to Remove

Remove all TDD-specific recipes from the justfile (lines 382-673
approximately). These are replaced by new recipes in Step 13:

- `epic` (unified router), `epic-start`, `epic-dry-run`, `epic-status`,
  `epic-validate`, `epic-materialise`
- `tdd-test-phase`, `tdd-red`, `tdd-lock`, `tdd-impl-phase`,
  `tdd-green`, `tdd-complete`
- `snapshot-verify`, `snapshot-diff`
- `epic-health`, `debug`, `errors`, `log`, `retry`

**Keep:** `tdd PATH` (line 147-148) — this is the general-purpose test
runner, not TDD-specific despite the name. Consider renaming it in a
future step.

### Definition of Done

- [ ] GTS test patterns extracted from `test-author.md` into
      `gts-testing` skill before deletion
- [ ] Architectural patterns extracted from `implementer.md` into
      relevant skills before deletion
- [ ] All 8 agent files deleted
- [ ] All 2 command files deleted
- [ ] 4 scripts deleted (`snapshot_tests.py`, `tasks_from_plan.py`,
      `validate_tasks.py`, `epic_reviewer.py`)
- [ ] `.tasks/_templates/` deleted
- [ ] `.tasks/projects/` deleted (entire tree)
- [ ] V1 planning artefacts (GOALS.md, TASKS.md, created.json) deleted
      from `.planning/epics/`
- [ ] TDD justfile recipes removed
- [ ] `run_epic.py` kept temporarily (reference for Step 4)
- [ ] No broken references in remaining files (grep for deleted
      filenames across `.claude/`, `AGENTS.md`, `justfile`)
- [ ] Commit: `chore(workflow): remove V1 TDD artefacts`

---

## Step 3: Build Foundation — Git Helpers + JSONL Logger — [x]

**Goal:** Create the two foundational utility modules that the
orchestrator depends on: git operations and structured event logging.

**Parallel work (Task):** Build `git_helpers.py` and `jsonl_logger.py`
in parallel — they have no interdependency.

### File 1: `scripts/git_helpers.py`

Extract from `run_epic.py` (lines 333-431 per Section 8.1):

**`robust_commit(message: str, paths: list[str]) -> str`:**
- Stage specified paths
- Attempt `git commit`
- If pre-commit hooks modify files (exit code 1 with modified files),
  re-stage and retry commit
- Return the commit hash
- This handles ruff/format auto-fixes from pre-commit hooks for free
  (Section 8.2 Strategy 5)

**`git_sync() -> None`:**
- `git fetch origin`
- `git merge origin/<branch>` with conflict detection
- If conflict: raise exception with details (do not auto-resolve)
- `git push`

**`get_current_branch() -> str`:**
- Return current branch name

**`get_commit_hash() -> str`:**
- Return current HEAD short hash

### File 2: `scripts/jsonl_logger.py`

Implement the JSONL logging system from Section 2.

**`EventLogger` class:**
- Constructor takes `log_path: Path` and `run_id: str`
- `log_event(event: str, **kwargs) -> None`: Append a JSONL line with
  universal fields (`schema_v`, `run_id`, `ts`, `event`) plus any
  additional kwargs
- `ts` is ISO 8601 with timezone, monotonically increasing within a run
- Each line is flushed immediately (crash-safe, append-only)

**`read_log(log_path: Path) -> list[dict]`:**
- Read all events from a JSONL file
- Handle partial last line gracefully (truncated write from crash)
- Return list of parsed event dicts

**`find_last_event(events: list[dict], event_type: str, **filters) -> dict | None`:**
- Find the most recent event matching type and optional filters
  (e.g., `story_id="01-architecture"`)

**`is_story_complete(events: list[dict], story_id: str, run_id: str) -> bool`:**
- Return True if a `story_complete` event exists for this story_id
  and run_id (idempotency check — Section 2)

**`generate_run_id() -> str`:**
- Generate a new UUID4 string for a fresh run
- A new `run_id` is generated ONLY on explicit start, not on resume
  (Section 2 crash recovery)

**`get_resumable_state(events: list[dict], run_id: str) -> dict`:**
- Determine the last completed story and the next step
- Used for crash recovery: orchestrator reads log, finds latest
  `run_id`, identifies last completed event, resumes from next step

### Definition of Done

- [ ] `scripts/git_helpers.py` implements `robust_commit()` with
      pre-commit hook retry logic
- [ ] `scripts/git_helpers.py` implements `git_sync()` with conflict
      detection
- [ ] `scripts/jsonl_logger.py` implements `EventLogger` with universal
      fields and flush-per-line
- [ ] `scripts/jsonl_logger.py` handles crash recovery (partial last
      line, resume from last event)
- [ ] `scripts/jsonl_logger.py` implements idempotency check
      (`is_story_complete`)
- [ ] `scripts/jsonl_logger.py` generates `run_id` only on fresh start,
      reuses on resume
- [ ] Both modules have no dependency on `run_epic.py` or V1 code
- [ ] Commit: `feat(workflow): add git helpers and JSONL event logger`

---

## Step 4: Build Agent Dispatch Module — [x]

**Goal:** Create the dispatch module that sends prompts to Claude Code
agents with the correct model, tools, skills, MCP, and budget controls.

**Reference:** Extract the dispatch layer from `run_epic.py` (~100 lines
across `dispatch_agent()`, `build_claude_args()`, `build_mcp_config()`,
`parse_agent_definition()` per Section 8.1) and rebuild for V2.

### File: `scripts/dispatch.py`

**`ProviderAdapter` protocol** (Section 8.6 Decision 1):
- V2 implements only `ClaudeAdapter`. The protocol exists for V2.1
  multi-provider support.
- Methods: `build_args(...)` → `list[str]`, `parse_result(...)` →
  `AgentResult`, `name` property

**`ClaudeAdapter` implementation:**
Uses `--agents` JSON as the canonical dispatch mechanism (Section 8.5
Decision 7). This consolidates model, tools, skills, MCP, and prompt
into a single declaration.

```python
def build_args(self, prompt, model, tools, skills, mcp_config,
               max_turns, max_budget_usd, json_schema):
    agent_def = {
        "story-agent": {
            "description": f"Implementation agent",
            "prompt": prompt,
            "skills": skills,
            "tools": tools,
            "model": model,
            "maxTurns": max_turns,
        }
    }
    if mcp_config:
        agent_def["story-agent"]["mcpServers"] = mcp_config

    args = [
        "claude",
        "--agents", json.dumps(agent_def),
        "--max-budget-usd", str(max_budget_usd),
        "--no-session-persistence",
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]
    if json_schema:
        args.extend(["--json-schema", json.dumps(json_schema)])
    return args
```

**Fallback mechanism:** If `--agents` JSON is unavailable, fall back to
individual CLI flags per Section 8.2 (CLI Flags Reference):
- `-p -` (prompt via stdin)
- `--model`, `--max-turns`, `--max-budget-usd`
- `--tools` (restrict available tools — stronger than `--allowedTools`)
- `--append-system-prompt-file` (skill injection via temp file)
- `--strict-mcp-config --mcp-config` (MCP configuration)
- `--fallback-model` (only for HTTP 529, limited utility per Section 8.6
  Decision 6)
- `--no-session-persistence` (ephemeral sessions)
- `--output-format json` (parseable output)

**`dispatch_agent()` function:**
```python
def dispatch_agent(
    prompt: str,
    model: str,
    tools: list[str],
    skills: list[str],
    mcp_config: dict | None = None,
    max_turns: int = 30,
    max_budget_usd: float = 3.0,
    json_schema: dict | None = None,
    cwd: Path = PROJECT_ROOT,
) -> AgentResult:
```
- Constructs args via adapter
- Runs subprocess with `capture_output=True, text=True`
- Parses result into `AgentResult` dataclass
- Logs dispatch metadata (model, prompt_hash, prompt_tokens, skill_tokens)

**`AgentResult` dataclass:**
- `success: bool`
- `output: str` (raw stdout)
- `structured_output: dict | None` (parsed JSON if `--output-format json`)
- `exit_code: int`
- `cost_usd: float | None`
- `turns: int | None`

**MCP configuration builder:**
Build MCP config JSON from the story's `mcp` field. Chrome DevTools MCP
for `http+dom`, `browser+db`, `screenshot` checks. Playwright MCP for
regression test authoring (Section 8.7).

**Model fallback for overload resilience:**
Although `--fallback-model` only triggers on HTTP 529 (Section 8.6
Decision 6), the execution loop should still use it as a first line of
defence. Every `dispatch_agent()` call for Sonnet implementation agents
should include `--fallback-model haiku` (or a configurable fallback).
For Opus planning calls, `--fallback-model sonnet` (as noted in Step 7).
Additionally, the orchestrator should catch non-529 subprocess failures
(network errors, 5xx, timeouts) and retry once with the fallback
model/provider at the orchestrator level before classifying as a failure:
```python
def dispatch_with_fallback(primary_model, fallback_model, prompt, **kw):
    result = dispatch_agent(prompt, model=primary_model, **kw)
    if result.success:
        return result
    if is_overload_or_transient(result):
        return dispatch_agent(prompt, model=fallback_model, **kw)
    return result  # Real failure, not transient
```
This is distinct from the story-level retry budget (which handles
implementation failures). Transient provider failures should not
consume retry attempts.

**Pre-flight MCP check:**
Before dispatching an MCP-dependent agent, verify the MCP server is
available. Don't discover it's missing 5 minutes into the agent's work
(Section 4.5). If MCP is unavailable, log an `env` failure category and
exit immediately (0 retries — Section 2 failure model).

**Budget defaults** (Section 8.2 Strategy 7 — starting points, adjust
based on JSONL data):

| Agent Type | Max Turns | Max Budget |
|------------|-----------|------------|
| Planning (Opus) | 50 | $5.00 |
| Architecture (Sonnet) | 30 | $3.00 |
| Implementation (Sonnet) | 40 | $4.00 |
| Validation (Haiku) | 15 | $0.50 |
| Regression tests (Sonnet) | 30 | $3.00 |

**Tool restriction per agent role** (Section 8.2 Strategy 4):

| Agent Role | Tools | Denied |
|------------|-------|--------|
| Implementation | Read, Edit, Write, Bash, Glob, Grep | Task |
| Validation (browser) | Read, Bash, Glob, Grep + MCP | Edit, Write |
| Validation (API/DB) | Bash, Read, Glob, Grep | Edit, Write |
| Regression test | Read, Edit, Write, Bash, Glob, Grep | Task |

### Definition of Done

- [ ] `scripts/dispatch.py` implements `ProviderAdapter` protocol
- [ ] `ClaudeAdapter` builds `--agents` JSON with model, tools, skills,
      MCP, maxTurns in a single declaration
- [ ] `ClaudeAdapter` falls back to individual CLI flags if `--agents`
      is unavailable
- [ ] `dispatch_agent()` runs subprocess, parses result, returns
      `AgentResult`
- [ ] MCP config builder generates correct JSON for chrome-devtools and
      playwright
- [ ] Pre-flight MCP availability check implemented
- [ ] Model fallback: `--fallback-model` set on all dispatch calls +
      orchestrator-level retry for transient provider failures (separate
      from story retry budget)
- [ ] Budget defaults match Section 8.2 table
- [ ] Tool restrictions enforced per agent role
- [ ] `run_epic.py` can now be deleted (dispatch logic fully extracted)
- [ ] Commit: `feat(workflow): add V2 agent dispatch module`

---

## Step 5: Build Prompt Assembly System — [x]

**Goal:** Create the 7-section prompt builder that constructs agent
prompts from plan context, skills, and failure feedback.

**Reference:** Section 8.5 Decisions 1-6.

### File: `scripts/prompt_builder.py`

**Core function:**
```python
def build_agent_prompt(story: StorySpec, context: PromptContext) -> str:
    sections = [
        build_role_section(story),
        build_plan_context_section(story, context.plan),
        build_scope_section(story),
        build_implementation_notes_section(story),
        build_verification_section(story, context.checkpoint),
        build_failure_feedback_section(context.retry),
        build_constraints_section(story),
    ]
    return "\n\n---\n\n".join(s for s in sections if s)
```

**Section 1 — Role (static template, ~50-100 words):**
- Short, focused instruction block
- NOT the 230-line agent definitions from V1
- Sets the frame: "You are implementing a story. You receive scope,
  notes, and verification criteria. Implement, verify, commit."
- Separate templates for: implementation agent, validation agent,
  regression test agent
- Validation agent template explicitly states: "You do NOT fix anything.
  Only report." (Section 8.5 Decision 5)

**Section 2 — Plan Context (dynamic, from PLAN.md):**
- Epic goal
- Story name and purpose
- Truths addressed by this story
- Full list of observable truths (for reference — agent needs to
  understand overall "done" even for truths it's not directly
  implementing)

**Section 3 — Scope (dynamic, from plan.json):**
- Files to create, with "follow pattern in X" references
- Files to modify, with specific instructions
- This is the most important section — tells the agent exactly which
  files to touch (Section 8.5 Decision 2)

**Section 4 — Implementation Notes (dynamic, from plan.json):**
- Domain-specific hints from the planner
- Prevents common mistakes without bloating the prompt
- Examples: "Service owns transaction: `async with session.begin():`",
  "Use `joinedload` for all relationships"

**Section 5 — Verification (dynamic, from next checkpoint):**
- Criteria the agent should check before committing
- From Anthropic's guidance: "Give Claude a way to verify its work.
  This is the single highest-leverage thing you can do." (Section 8.2
  Strategy 9)
- Comes from the validation checkpoint that follows this story in the
  plan

**Section 6 — Failure Feedback (dynamic, retry only):**
- Key error message (not raw pytest dump)
- List of files modified by previous attempt
- JSONL failure entry verbatim
- Explicit instruction: "Fix the error. The files listed above already
  exist from the previous attempt. Read them, understand the error,
  and correct it." (Section 8.5 Decision 2)
- Replaces V1's raw 2000-3000 char unprocessed test output

**Section 7 — Constraints (static template):**
- What NOT to do: don't create tests (separate story), don't modify
  files outside scope, don't run `just check` (orchestrator handles
  validation), don't explore beyond exemplar files, commit when done

**Validation agent prompt:**
Minimal — ~100-200 tokens. Criteria + check type + instruction to
report. No skills, no implementation notes (Section 8.5 Decision 5).
Combined with `--json-schema` for structured pass/fail output.

**Prompt size enforcement:**
Total prompt body (sections 1-7) must be under 2,000 tokens. Skill
content is injected via system prompt (`--append-system-prompt-file` or
`--agents` JSON `skills` field) and does not count against this budget
(Section 8.5 Decision 4). Skills are typically 1,000-3,000 tokens each,
with 2-4 skills per agent = 2,000-12,000 tokens in system prompt.

**Prompt logging** (Section 8.5 Decision 6):
Save full prompt text to `prompt-attempt-N.md` alongside the story
JSONL. This is the primary debugging artefact when agents fail.
```
.planning/epics/E95/stories/01-architecture/
├── story.jsonl
├── prompt-attempt-1.md
└── prompt-attempt-2.md
```

**Skill file assembly:**
```python
def write_skill_file(story: StorySpec, tmp_dir: Path) -> Path:
    """Assemble skill content into a temp file for injection."""
```
- Read SKILL.md files for each skill in the story's `skills` list
- Strip YAML frontmatter (not needed at runtime)
- Concatenate with separators
- Write to temp file
- Used as fallback when `--agents` JSON `skills` field is unavailable

**Skill mapping per story type** (Section 8.5 Decision 3):

| Story Type | Typical Skills |
|------------|---------------|
| Architecture | `gts-architecture`, `repository-patterns`, `service-patterns` |
| API + Schemas | `gts-backend-dev`, `web-handlers`, `error-handling` |
| UI Scaffolding | `gts-frontend-dev`, `htmx`, `astro-frontend` |
| CRUD Features | `gts-frontend-dev`, `htmx`, `gts-backend-dev` |
| Regression Tests | `gts-testing`, `playwright` |
| Validation (browser) | `chrome-devtools`, `playwright` |

### Definition of Done

- [ ] `scripts/prompt_builder.py` implements all 7 section builders
- [ ] Role templates exist for: implementation, validation, regression
      test agents
- [ ] Validation agent prompt is minimal (~100-200 tokens) with
      structured output schema
- [ ] Failure feedback section extracts key error (not raw output dump)
- [ ] Prompt size is under 2,000 tokens (verified by counting)
- [ ] Prompt logging saves to `prompt-attempt-N.md` per attempt
- [ ] Skill file assembly function reads and concatenates SKILL.md files
- [ ] Commit: `feat(workflow): add V2 prompt assembly system`

---

## Step 6: Build Epic Ingestion + Context Assembly — [x]

**Goal:** Create the deterministic pipeline that fetches a GitHub epic
and assembles context for the planner. No AI tokens spent.

**Parallel work (Task):** Build ingestion and context assembly in
parallel — ingestion produces EPIC.md, context assembly reads it.

### File 1: `scripts/epic_ingest.py`

**`ingest_epic(epic_number: int) -> Path`:**
Per Section 8.3 Decision 1:
1. Run `gh issue view <number> --repo krazyuniks/guitar-tone-shootout`
   to fetch the raw body
2. Extract title, state, labels from the `gh` output
3. Write to `.planning/epics/E<number>/EPIC.md` with YAML frontmatter:
   ```markdown
   ---
   github_issue: 95
   title: "Phase 4 Completion — ..."
   state: OPEN
   labels: [epic]
   fetched: 2026-02-13T01:00:00Z
   ---

   [Raw GitHub issue body verbatim]
   ```
4. Create `.planning/epics/E<number>/stories/` directory
5. Idempotent — re-running overwrites the local copy

**Note:** The `--repo krazyuniks/guitar-tone-shootout` flag is mandatory
per `.claude/rules/github.md`.

### File 2: `scripts/context_assembler.py`

**`assemble_context(epic_dir: Path) -> Path`:**
Per Section 8.4 Decision 2 — deterministic Python, not an AI agent.
Replaces the `epic-context-loader` agent (haiku) and `epic-gray-area-
analyst` agent (haiku) with zero AI tokens.

1. Read `EPIC.md` (ingested from GitHub)
2. Read relevant wiki sections (architecture, domain model) from
   `../wiki/` — specifically `GTS-Technical-Architecture.md` for domain
   model definitions
3. Read codebase structure files from `.planning/codebase/`
   (STRUCTURE.md, ARCHITECTURE.md, STACK.md, CONVENTIONS.md,
   INTEGRATIONS.md, TESTING.md, CONCERNS.md)
4. Scan epic body for keywords to determine relevant areas using the
   keyword→area mapping from `.claude/skills/epic/references/gray-areas.md`
   and question bank from `.claude/skills/epic/references/question-bank.md`
   — this is structured data, not a reasoning task (Section 8.1)
5. Assemble all inputs into a single `CONTEXT.md` file

**Output:** `.planning/epics/E<number>/CONTEXT.md` — intermediate file
for the planner.

**Keyword scanning logic:**
Extract the keyword→area mapping table and question bank from the
existing skill reference files. These are structured lookup tables:
keyword matches → relevant architecture area → relevant questions.
A Python function with string matching replaces a haiku AI invocation.

### Directory Structure

After this step, an epic directory looks like:
```
.planning/epics/E<N>/
├── EPIC.md          # From ingest
├── CONTEXT.md       # From context assembly
└── stories/         # Empty, ready for execution
```

### Definition of Done

- [ ] `scripts/epic_ingest.py` fetches epic via `gh issue view` with
      `--repo` flag
- [ ] EPIC.md has YAML frontmatter (issue number, title, state, labels,
      fetched timestamp) + verbatim body
- [ ] Ingestion is idempotent (re-run overwrites)
- [ ] `scripts/context_assembler.py` reads EPIC.md + wiki + codebase
      files + keyword scan
- [ ] Context assembly uses zero AI tokens (pure Python I/O)
- [ ] Keyword→area mapping extracted from existing skill references
- [ ] `.planning/epics/E<N>/` directory structure created correctly
- [ ] Commit: `feat(workflow): add epic ingestion and context assembly`

---

## Step 7: Build Plan Generation — [x]

**Goal:** Create the planner that produces PLAN.md + plan.json from
context. This is the single Opus AI invocation that replaces 3 AI
invocations in V1.

**Reference:** Section 8.4 Decisions 1, 3, 4, 5, 6, 7. This is the
most complex step.

### File: `scripts/plan_generator.py`

**`generate_plan(epic_dir: Path, decisions: dict) -> tuple[Path, Path]`:**

1. Read `CONTEXT.md` (from Step 6)
2. Read locked scope decisions (from interactive Phase 2 — passed in as
   `decisions` dict, appended to context)
3. Construct the planner prompt (Opus)
4. Dispatch via `dispatch_agent()` from Step 4
5. Parse output into PLAN.md and plan.json
6. Return paths to both files

**The planner prompt must instruct Opus to:**

- Perform goal-backward analysis (the strongest part of the V1 pipeline,
  preserved intact per Section 8.4):
  1. Define observable truths (user-perspective, verifiable by a human)
  2. Derive required artefacts for each truth
  3. Organise artefacts into stories
  4. Define validation checkpoints between stories
- Produce **user journeys** (Section 8.4 Decision 3): connected,
  end-to-end narratives that link observable truths into coherent flows.
  Not isolated assertions ("GET /gear returns 200") but connected walks
  ("user clicks Gear in nav, sees list, clicks item, sees detail").
  Every truth must appear in at least one journey. Journeys include
  `critical_transitions` with `{from, to, mechanism}`.
- Write PLAN.md in the narrative structure from Section 8.4 Decision 3
  (Goal → Observable Truths → User Journeys → Stories → Validation
  Checkpoints → Artefact Summary)
- Emit `plan.json` conforming to the JSON Schema from Step 1. The
  schema is included in the planner's prompt as a hard constraint.
- For each story, specify: `story_id`, `name`, `purpose`, full `agent`
  config (`model`, `skills`, `tools`, `mcp`, `max_turns`,
  `max_budget_usd`), `scope` (`create`, `modify`),
  `state_assumption` (cumulative or clean), `implementation_notes`,
  `truths_addressed`
- Target 2-5 stories per epic (Section 8.4 Decision 7), each 3-8 files
- Place validation checkpoints strategically (Section 8.4 Decision 5):
  after scaffolding, after CRUD, before regression tests, after
  regression tests. Not after every story — backend-only stories may
  wait for the UI story that exposes them.
- Each checkpoint specifies `check_type` with the correct evidence
  fields per type (Section 8.4 Decision 4)

**Interactive Phase 2 (Scope & Decisions):**
This step assumes the interactive scope discussion has already happened
and the locked decisions are available. The orchestrator (Step 11) will
handle the interactive flow. Plan generation receives the decisions as
input.

The interactive phase covers:
- Gray area resolution (which ambiguities need human answers)
- Scope confirmation ("what does DONE look like?")
- Feature boundaries (what's in, what's out)

Locked decisions are appended to CONTEXT.md before plan generation.

**Model selection:** Opus for plan generation. This is the primary AI
cost ($3-5 per invocation). Use `--fallback-model sonnet` for resilience
against Opus overload.

### Definition of Done

- [ ] `scripts/plan_generator.py` dispatches a single Opus agent with
      full context
- [ ] Planner prompt includes the `plan.json` JSON Schema as a hard
      constraint
- [ ] Planner performs goal-backward analysis (truths → artefacts →
      stories)
- [ ] Output includes user journeys with `critical_transitions`
- [ ] Output includes `state_assumption` per story (cumulative/clean)
- [ ] PLAN.md follows the narrative structure from Section 8.4
- [ ] plan.json conforms to `plan.schema.json`
- [ ] Stories target 2-5 per epic with 3-8 files each
- [ ] Validation checkpoints placed strategically with correct
      `check_type` and `evidence_fields`
- [ ] Commit: `feat(workflow): add V2 plan generator`

---

## Step 8: Build Plan Verification — [x]

**Goal:** Create the two-phase plan verification system that catches
flawed plans before execution. This prevents the E95 failure mode.

**Reference:** Section 8.4 Decision 8.

**Parallel work (Task):** Build Phase A (deterministic) and Phase B
(AI verifier prompt + dispatch) in parallel.

### File 1: `scripts/plan_validator.py` (Phase A — Deterministic, $0)

**`validate_plan(epic_dir: Path) -> ValidationResult`:**

Validates `plan.json` against the JSON Schema from Step 1. Mechanical,
instant, catches structural errors:

1. **Schema conformance** — `plan.json` validates against
   `plan.schema.json` (all required fields present, types correct)
2. **Referential integrity** — every `truths_addressed` ID exists in
   `observable_truths`; every checkpoint `after_story` references a
   valid `story_id`; every journey `truths_covered` ID exists
3. **Truth coverage** — every observable truth is addressed by at least
   one story AND covered by at least one user journey
4. **Journey coverage** — every truth appears in at least one journey's
   `truths_covered` (no orphan truths that are asserted but never
   exercised in a connected flow)
5. **Scope coherence** — files in `modify` scope exist on disk; files
   in `create` scope have existing parent directories
6. **Dependency ordering** — stories that reference files created by
   earlier stories appear after those stories
7. **Budget sanity** — total estimated budget (`sum(max_budget_usd)`)
   within a reasonable limit

Returns structured result: pass/fail with list of specific errors.
If Phase A fails, the planner is re-invoked with the validation errors.
No AI tokens spent on Phase B until the structure is sound.

### File 2: `scripts/plan_verifier.py` (Phase B — AI, ~$1-2)

**`verify_plan(epic_dir: Path) -> VerifierResult`:**

Dispatches a Sonnet agent (not Opus — Section 8.4 Decision 8 explains
why: structured comparison, not creative reasoning, 5x cheaper) with:
- `plan.json` (the full plan)
- `EPIC.md` (the original intent from GitHub)
- `CONTEXT.md` (the assembled codebase context)
- Locked scope decisions

The verifier checks 5 dimensions:

1. **Journey completeness** — do user journeys cover the full epic
   scope? Walk each journey narrative, verify every step has a
   corresponding story and validation checkpoint. Flag steps that no
   story addresses.
2. **Transition coverage** — are all `critical_transitions` covered by
   validation checkpoints? A transition from `/gear` to `/gear/{id}`
   via "list item click" must have a checkpoint verifying both the link
   and the target page. Flag transitions between checkpoints.
3. **Intent alignment** — does the plan deliver what the epic asks for?
   Compare epic scope sections against plan stories. Flag epic
   requirements with no corresponding story. Flag stories addressing
   requirements not in the epic (scope creep).
4. **Gap detection** — are there logical gaps between stories? If Story
   1 creates an entity and Story 3 builds UI, but no story creates the
   API endpoint connecting them, flag it. Walk the dependency chain:
   entity → repo → service → API → template → page. Every link must
   exist in some story.
5. **Validation sufficiency** — are checkpoints strong enough? For each
   checkpoint: "If this check passes, does it prove the feature works,
   or could it false-green?" Flag checks that verify existence but not
   function (e.g., "page returns 200" without checking content).

Returns structured output via `--json-schema` from
`verifier-result.schema.json`.

**Revision cycle:** If Phase B fails, feed the structured output back to
the planner for revision. One revision cycle is budgeted (planner →
verifier → planner). If the second attempt also fails Phase B, exit to
human (Section 8.4 Decision 8).

**What the verifier does NOT check:**
- Whether implementation notes are correct (runtime discovery)
- Whether file paths in scope are the best choice (planner's domain)
- Whether story sizing is optimal (learned from experience)
- Subjective plan quality (human's job at Decision Gate)

### Decision Gate (after verification passes)

The orchestrator presents the human with PLAN.md + verifier report.
Three possible outcomes (Section 8.4):

| Decision | Action |
|----------|--------|
| **Approve** | Proceed to commit + push, then start execution |
| **Revise** | Human edits `plan.json` + `PLAN.md` directly, re-run Phase A + B. No planner re-invocation — the human IS the planner for revisions. |
| **Reject** | Log `exit_to_human` event, exit. Planning artefacts NOT committed. Human restarts from step 1 (re-ingest), step 3 (re-scope), or step 4 (re-plan). |

### Definition of Done

- [ ] `scripts/plan_validator.py` checks all 7 deterministic validations
- [ ] Phase A returns structured errors (not just pass/fail)
- [ ] Phase A errors are formatted for injection into planner retry
      prompt
- [ ] `scripts/plan_verifier.py` dispatches Sonnet agent with
      `--json-schema verifier-result.schema.json`
- [ ] Verifier checks all 5 dimensions (journey completeness, transition
      coverage, intent alignment, gap detection, validation sufficiency)
- [ ] One revision cycle implemented (planner → verifier → planner →
      verifier, then exit to human)
- [ ] Decision Gate logic implemented (approve/revise/reject with
      correct state transitions)
- [ ] Commit: `feat(workflow): add two-phase plan verification`

---

## Step 9: Build Validation Checkpoint System — [x]

**Goal:** Create the type-aware validation system that dispatches
read-only agents to check whether stories produced working results.

**Reference:** Section 8.4 Decisions 4, 5. Section 8.5 Decision 5.

### File: `scripts/validation.py`

**`run_validation_checkpoint(checkpoint: dict, epic_dir: Path, story_id: str) -> ValidationResult`:**

1. Read checkpoint definition from `plan.json`
2. Determine check type and required tools/MCP
3. Construct validation agent prompt (minimal — Section 8.5 Decision 5)
4. Dispatch via `dispatch_agent()` with:
   - Read-only tools: `--tools "Bash,Read,Glob,Grep"` + MCP if needed
   - No Edit/Write tools (validators check, they don't fix)
   - `--json-schema` from `validation-result.schema.json`
   - Budget: Haiku for most types, Sonnet for `browser+db` and
     `screenshot` (Section 8.4 Decision 5)
5. Parse structured output
6. Validate evidence fields are populated — empty or generic evidence
   is treated as a validation failure (Section 8.4 Decision 4)
7. Log result to JSONL (`validation_pass` or `validation_fail`)

**Validation agent configuration per checkpoint type** (Section 8.4
Decision 5):

| Check Type | Model | MCP Required | Pre-conditions |
|------------|-------|-------------|----------------|
| `http` | haiku | none | webapp + nginx running |
| `http+dom` | haiku | chrome-devtools | webapp + nginx + Chrome DevTools MCP |
| `browser+db` | sonnet | chrome-devtools | webapp + nginx + db + Chrome DevTools MCP |
| `api+response` | haiku | none | webapp running |
| `process` | haiku | none | target service running |
| `screenshot` | sonnet | chrome-devtools | webapp + nginx + Chrome DevTools MCP |
| `regression` | haiku | none | all services running, E2E deps on host |
| `quality` | haiku | none | webapp container running |

**Note on HTTP checks vs the curl ban** (Section 8.4 Decision 5):
Validation agents use programmatic HTTP requests (via Bash) as
structured evidence-gathering with required evidence fields (status code,
response excerpt, DOM content). This is distinct from the
`testing-policy.md` curl ban, which prohibits using curl as a
*substitute* for actual testing. Validation agents collect evidence;
they don't claim "the feature works because curl returned 200." The
evidence fields (per-type table) ensure meaningful verification.

**`regression` and `quality` check types:**
These run `just test-golden-path` and `just check` respectively as
subprocess calls from the validation agent. The agent captures exit
code, test count, and failure details as evidence.

### Definition of Done

- [ ] `scripts/validation.py` dispatches type-aware validation agents
- [ ] Validation agents are read-only (no Edit/Write tools)
- [ ] Each check type uses the correct model, MCP, and tools
- [ ] Structured output parsed via `--json-schema`
- [ ] Evidence field validation rejects empty/generic evidence
- [ ] MCP pre-flight check before MCP-dependent validation
- [ ] Results logged to JSONL with `failure_category` on failure
- [ ] Commit: `feat(workflow): add type-aware validation checkpoints`

---

## Step 10: Build Story Execution Loop + Failure Handling — [x]

**Goal:** Create the inner loop that executes a single story: pre-flight
→ dispatch → validate → retry/proceed. Includes the full failure model.

**Reference:** Section 2 (Story Flow, Failure Model, File-to-story
ownership). Section 8.5 Decision 2 (failure feedback).

### File: `scripts/story_executor.py`

**`execute_story(story: dict, plan: dict, epic_dir: Path, logger: EventLogger) -> bool`:**

The inner loop for one story:

```
1. Log story_started event
2. Handle state_assumption (if "clean", run just db-reset)
3. Run pre-flight checks on inputs from previous stories
4. Construct agent prompt (via prompt_builder)
5. Log agent_dispatched event
6. Dispatch implementation agent
7. Log agent_complete or agent_failed
8. If validation checkpoint exists after this story:
   a. Run validation checkpoint
   b. If pass: log validation_pass, log story_complete, return True
   c. If fail: classify failure, retry or exit (see failure model)
9. If no checkpoint: log story_complete, return True
```

**Pre-flight checks** (Section 2):
Before dispatching the story's agent, verify that inputs from previous
stories are present (files that should have been created, routes that
should be registered, etc.). This is a quick filesystem/import check,
not a full validation.

**Minor vs major pre-flight heuristic** (Section 2):
A pre-flight issue is "minor" (agent self-fixes) only if ALL of:
- (a) The fix modifies only files within the agent's assigned `scope`
  from `plan.json`
- (b) The fix touches fewer than 10 lines total
- (c) The fix is mechanical (import path, missing comma, wrong variable
  name) — not architectural

Anything outside these bounds is "major" — the agent logs the failure
and the orchestrator retries the upstream agent.

**File-to-story ownership map** (Section 2):
```python
def build_file_ownership_map(plan: dict) -> dict[str, str]:
    """Map file paths to owning story IDs from plan.json."""
    ownership = {}
    for story in plan["stories"]:
        for path in story["scope"].get("create", []):
            ownership[path] = story["story_id"]
        for path in story["scope"].get("modify", []):
            # Last writer wins — later stories own shared files
            ownership[path] = story["story_id"]
    return ownership
```

When a validation failure references a specific file or error location,
check this map. If the failing file belongs to an earlier story (not the
current one), the failure is `upstream` — exit to human immediately
(Section 2). Don't let a later agent hack around a bug in an earlier
story's scope.

**Failure classification** (Section 2):
Every failure event includes a `failure_category` field:

| Category | Meaning | V2 Retry Policy |
|----------|---------|-----------------|
| `env` | Infrastructure problem (Docker down, port conflict, MCP unavailable) | **0 retries — exit immediately** |
| `scope` | Plan references something wrong (file path doesn't exist, wrong module) | 2 retries |
| `implementation` | Agent wrote incorrect code (TypeError, assertion, wrong logic) | 2 retries |
| `unknown` | Cannot classify (timeout, ambiguous error) | 2 retries |
| `upstream` | Failure traced to file owned by completed earlier story | **0 retries — exit to human** |

The orchestrator classifies failures heuristically: exit code, error
message patterns, file ownership map. V2.1 refines classification using
JSONL log analysis across runs.

**Classification rigour:** The heuristic classifier must be thorough,
not a loose string match. Implement explicit pattern tables:
- `env`: match Docker connection errors, port-in-use errors, MCP
  connection refused, "command not found" for infrastructure tools,
  network timeouts to external services
- `scope`: match "FileNotFoundError" or "ModuleNotFoundError" for paths
  listed in `plan.json` scope, "No such file or directory" for expected
  inputs
- `implementation`: match Python tracebacks (TypeError, ValueError,
  AttributeError, ImportError for internal modules), assertion failures,
  HTTP 500 from the webapp
- `upstream`: triggered by the file ownership map (not string matching)
  — if the error traceback references a file owned by a completed
  earlier story, classify as `upstream`
- `unknown`: fallback when no other pattern matches

The classifier function should return both the category and the
evidence that triggered it (the matched pattern + source text) so the
JSONL `failure_category` entry is auditable. Log the classification
reasoning alongside the category for debugging false classifications.

**Retry semantics** (Section 2):
- 2 attempts per checkpoint (initial + 1 retry)
- All retries use the same agent template — no specialised "fix agent"
- The only difference is an additional Failure Feedback section in the
  prompt (Section 8.5 Decision 2, Section 6)
- "Retry the upstream agent" and "dispatch an agent with failure
  details" both mean: re-invoke the same template with failure context
  appended

**Git state on retry** (Section 2):
When an implementation agent fails after committing code, the
orchestrator does NOT roll back. The retry agent starts from the current
filesystem state (including broken code from the previous attempt) and
receives failure feedback in its prompt. The retry agent's job is to fix
the broken state, not start from scratch. This avoids destructive git
operations. If the retry also fails, exit to human with full JSONL log.

**State assumption handling** (Section 8.4 Decision 7):
If a story's `state_assumption` is `"clean"`, run `just db-reset` (or
equivalent seed script) before dispatching the agent. Most stories are
`"cumulative"` (default) — each builds on what the previous created.

### Definition of Done

- [ ] `scripts/story_executor.py` implements the full inner loop
- [ ] Pre-flight checks verify inputs from previous stories
- [ ] Minor/major pre-flight heuristic implemented (scope + <10 lines +
      mechanical)
- [ ] File-to-story ownership map built from `plan.json`
- [ ] Upstream failures (file belongs to earlier story) exit immediately
- [ ] Failure classification covers all 5 categories with correct retry
      policy
- [ ] Failure classifier uses explicit pattern tables (not loose string
      matching) — env, scope, implementation patterns are enumerated
- [ ] Classifier returns both category and matched evidence for audit
- [ ] `env` failures: 0 retries, exit immediately
- [ ] `upstream` failures: 0 retries, exit to human
- [ ] Other failures: 2 retries with failure feedback in prompt
- [ ] No git rollback on retry — agent fixes broken state
- [ ] State assumption (`clean` vs `cumulative`) handled before dispatch
- [ ] All events logged to story JSONL
- [ ] Commit: `feat(workflow): add story execution loop with failure handling`

---

## Step 11: Build Outer Loop + GitHub Integration — [x]

**Goal:** Create the epic-level orchestrator that runs stories
sequentially, manages the epic JSONL log, and posts GitHub comments.

**Reference:** Section 8.3 Decisions 4, 5. Section 2 (Crash Recovery).

### File: `scripts/orchestrator.py`

**`run_epic(epic_number: int, resume: bool = False) -> None`:**

The main entry point. The outer loop:

```python
while True:
    state = read_log("epic.jsonl")
    next_story = determine_next_story(state, plan)
    if next_story is None:
        comment_on_epic(epic_number, build_completion_comment(plan, state))
        label_epic(epic_number, "workflow-complete")
        break
    if is_exit_to_human(state):
        break
    success = execute_story(next_story, plan, epic_dir, logger)
    if success:
        comment_on_epic(epic_number, build_story_comment(next_story, state))
    else:
        comment_on_epic(epic_number, build_failure_comment(next_story, state))
        break
```

This is the stateless orchestrator from Section 2: read log → determine
next step → build prompt → dispatch agent → wait → loop. No AI tokens
spent on orchestration.

**Epic-level JSONL log** at `.planning/epics/E<N>/epic.jsonl`:
```jsonl
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"epic_started","epic":95,"stories":5}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"story_started","story_id":"01-architecture","attempt":1,"index":1}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"story_complete","story_id":"01-architecture","attempt":1,"commit":"abc123"}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"github_comment","epic":95,"comment_url":"..."}
```

Story-level JSONL at `.planning/epics/E<N>/stories/<story_id>/story.jsonl`
tracks agent invocations within a story. Two levels, same schema.

**Execution crash recovery** (Section 2):
On restart with `resume=True`:
1. Read `epic.jsonl`
2. Find the latest `run_id`
3. Identify the last completed event
4. Resume from the next step
5. Do NOT generate a new `run_id` on resume (reuse the existing one)
6. Idempotency: never replay a step whose completion event is already
   in the log. If `story_complete` exists for a story_id + run_id,
   skip it.

**Planning-phase crash recovery** (research doc Section 8.4):
The `plan` subcommand must also support resume after a crash during
planning. The orchestrator checks which planning steps have completed
by probing for their output artefacts:

| Artefact | Implies |
|----------|---------|
| `EPIC.md` exists | Step 1 (ingest) done |
| `CONTEXT.md` exists | Step 2 (context assembly) done |
| `plan.json` exists | Step 4 (plan generation) done |
| `plan.json` + Phase A pass logged | Step 5a (schema validation) done |
| Verifier result logged | Step 5b (plan verification) done |

On `plan --resume`, the orchestrator reads the epic directory, finds
the last completed planning step, and resumes from the next incomplete
step. Planning steps are idempotent — re-running a completed step
overwrites the output harmlessly. No separate `run_id` is needed for
the planning phase; artefact presence is sufficient.

**GitHub comment push-back** (Section 8.3 Decision 4):
Post comments at 4 points:

| Event | Content |
|-------|---------|
| Planning complete | Story count, agent sequence summary, estimated checkpoints |
| Story validated | Story name, pass/fail, files changed, JSONL excerpt |
| Epic complete | Summary: stories completed, total commits, deferred items |
| Human validation prompt | "All stories passed. Please verify and close." |

**Story completion comment format** (Section 8.3 Decision 4):
```markdown
## Story Complete: UI Scaffolding

**Agent:** arch-scaffold | **Model:** sonnet | **Turns:** 24
**Files:** 12 created, 3 modified | **Commit:** abc1234

### Validation
- GET /gear returns 200 with gear listing
- GET /gear/{id} returns 200 with gear detail
- Navigation links present in header
```

**Implementation:**
```python
def comment_on_epic(epic_number: int, body: str) -> None:
    subprocess.run([
        "gh", "issue", "comment", str(epic_number),
        "--repo", "krazyuniks/guitar-tone-shootout",
        "--body", body,
    ], check=True)

def label_epic(epic_number: int, label: str) -> None:
    subprocess.run([
        "gh", "issue", "edit", str(epic_number),
        "--repo", "krazyuniks/guitar-tone-shootout",
        "--add-label", label,
    ], check=True)
```

**SUMMARY.md generation** (research doc Section 8.3, adopted from taches):
After all stories complete (or after exit-to-human), generate
`.planning/epics/E<N>/SUMMARY.md` from the JSONL logs:
- Stories completed (count and IDs)
- Stories failed (count, IDs, failure categories)
- Total cost (sum of `cost_usd` from `agent_complete` events)
- Total commits (list of commit hashes from `story_complete` events)
- Deferred/unresolved items (from `exit_to_human` events if any)
- Validation checkpoint results (pass/fail per checkpoint)

This is a deterministic Python function ($0 AI cost) that reads the
JSONL and renders markdown. It runs as the final step of both
`run_epic()` and the failure exit path.

**Why NOT auto-close the epic** (Section 8.3 Decision 4):
Closing an epic is a human decision. The agent completed the work, but
"complete" means "the human verified it works." Auto-close would
reproduce the E95 failure mode — the system declares done before anyone
checks.

**The full planning + execution flow wired together:**

```
1. just epic-ingest <N>         → EPIC.md (deterministic)
2. Context Assembly (Python)    → CONTEXT.md (deterministic)
3. Interactive Scope Discussion → locked decisions (human-in-loop)
4. Plan Generation (Opus)       → PLAN.md + plan.json (AI)
5a. Schema Validation (Python)  → pass/fail (deterministic)
5b. Plan Verification (Sonnet)  → structured report (AI)
6. Human Decision Gate          → approve/revise/reject
7. Commit + Push                → planning artefacts on remote
8. Story Execution (loop)       → stories executed sequentially
9. Human Validation             → human closes epic
```

Steps 1, 2, 5a, 7 are deterministic ($0). Step 3 is interactive. Steps
4 and 5b are AI. Step 6 is human. Step 8 is the execution loop.

### Definition of Done

- [ ] `scripts/orchestrator.py` implements the stateless outer loop
- [ ] Epic-level JSONL log at `.planning/epics/E<N>/epic.jsonl`
- [ ] Crash recovery resumes from last completed event using existing
      `run_id`
- [ ] Idempotency: completed stories skipped on resume
- [ ] GitHub comments posted at all 4 milestone points
- [ ] Comment format matches the structured markdown template
- [ ] `comment_on_epic()` uses `--repo krazyuniks/guitar-tone-shootout`
- [ ] Epic NOT auto-closed — human closes after review
- [ ] SUMMARY.md generated from JSONL after epic completes or exits
- [ ] SUMMARY.md includes: stories, costs, commits, failures, validation
      results
- [ ] Planning-phase crash recovery implemented (see below)
- [ ] Full flow wired: ingest → context → scope → plan → verify →
      gate → execute → comments
- [ ] Commit: `feat(workflow): add epic orchestrator with GitHub integration`

---

## Step 12: Update Rules + Skills + AGENTS.md — [x]

**Goal:** Update all configuration files that reference the V1 workflow.
Rules must reflect V2 semantics. Skills must be updated. AGENTS.md must
reference the new workflow.

**Parallel work (Task):** Update rules, skills, and AGENTS.md in
parallel — each is independent.

### Group A: Rules to Replace/Refactor

**`.claude/rules/epic-workflow.md` — REPLACE entirely:**
Current content references "Epics run via the TDD state machine" and
bans manual task file reading. New content must describe the V2
behavioural validation workflow:
- Epics run via the stateless orchestrator (`scripts/orchestrator.py`)
- One command to start: `just epic-start <N>`
- One command to check: `just epic-status <N>`
- The orchestrator reads `plan.json`, dispatches agents, logs JSONL
- Anti-patterns: don't read story files manually, don't dispatch agents
  manually, don't use the old `/epic` skill

**`.claude/rules/testing-policy.md` — REFACTOR:**
Keep: no-mock rule (`test_quality_check.py` gate), no-curl rule (curl is
not testing), E2E runs on host, forbidden patterns.
Remove: TDD framing ("Use `just tdd <path>` for development" stays,
but "TDD-driven" language goes), references to test-author agent,
red/green phases.
Add: "Tests are regression nets — written AFTER the product works, by
an agent that can see the working product. Tests capture current working
behaviour. They are not the definition of done."

**`.claude/rules/mcp-required.md` — REFACTOR:**
Keep: Chrome DevTools MCP required for UI work, Playwright MCP required
for E2E tests, "stop and fail if unavailable."
Remove: References to `run_epic.py`, `build_mcp_config()`, agent types
(`implementer`, `test-author`).
Add: MCP enforcement moves to the orchestrator's pre-flight check in
`dispatch.py`. The rule still applies to manual sessions.

### Group B: Skills to Replace/Refactor

**`.claude/skills/epic/SKILL.md` — REPLACE entirely:**
New content describes the V2 planning pipeline:
1. `just epic-ingest <N>` — fetch from GitHub
2. `just epic-plan <N>` — context assembly → interactive scope →
   plan generation → verification → decision gate
3. `just epic-start <N>` — execute stories
4. `just epic-status <N>` — check progress (reads JSONL)
No references to TASKS.md, `.tasks/`, TDD phases, or materialisation.

**`.claude/skills/epic/references/goal-backward.md` — REFACTOR:**
Keep: goal-backward methodology (truths → artefacts → stories).
Remove: TDD test spec framing, red/green examples.
Add: Behavioural validation framing — truths verified by type-aware
checks, not by test passage. User journeys as the connecting tissue.

**`.claude/skills/gts-testing/SKILL.md` — REFACTOR:**
Change framing from "TDD workflow" to "regression test authoring."
Add content extracted from `test-author.md` (the ~120 lines of GTS
test patterns) in Step 2.
Keep: all existing test patterns, fixtures, banned patterns.

### Group C: AGENTS.md Update

Update the "AI Development Workflow" section in AGENTS.md to describe
V2. Remove references to:
- TDD state machine, red/green/refactor
- test-author and implementer agents
- `.tasks/` file format
- Task materialisation

Add references to:
- Behavioural validation workflow
- `plan.json` + PLAN.md dual format
- JSONL event logging
- Type-aware validation checkpoints
- `just epic-ingest`, `just epic-plan`, `just epic-start`

### Group D: Wiki Pages

**`../wiki/GitHub-Epic-Sync.md` — REPLACE:**
Documents a sync protocol for infrastructure that was never built
(Section 8.3). Replace with V2's approach: lightweight ingestion +
comment push-back.

### Definition of Done

- [ ] `epic-workflow.md` rule describes V2 workflow (not TDD)
- [ ] `testing-policy.md` removes TDD framing, adds regression net
      language
- [ ] `mcp-required.md` updated for orchestrator-based enforcement
- [ ] `epic/SKILL.md` describes V2 commands and pipeline
- [ ] `goal-backward.md` reference reframed for behavioural validation
- [ ] `gts-testing/SKILL.md` reframed as regression test authoring
- [ ] AGENTS.md updated to reference V2 workflow
- [ ] `GitHub-Epic-Sync.md` wiki page replaced
- [ ] No remaining references to TDD state machine, test-author,
      implementer, `.tasks/`, or V1 commands in any updated file
- [ ] Commit: `refactor(workflow): update rules, skills, and docs for V2`

---

## Step 13: Register Just Recipes + Wire Full Flow — [x]

**Goal:** Create all the `just` recipes that expose the V2 workflow and
wire the full flow from ingestion through execution.

### New Justfile Recipes

```
# Epic Workflow V2 — Behavioural Validation

# Fetch a GitHub epic locally
epic-ingest epic_num:
    python scripts/epic_ingest.py {{epic_num}}

# Run the full planning pipeline (context → scope → plan → verify → gate)
epic-plan epic_num:
    python scripts/orchestrator.py plan {{epic_num}}

# Start epic execution (dispatches stories sequentially)
epic-start epic_num:
    python scripts/orchestrator.py run {{epic_num}}

# Resume a crashed/interrupted epic execution
epic-resume epic_num:
    python scripts/orchestrator.py run {{epic_num}} --resume

# Resume a crashed/interrupted planning phase
epic-plan-resume epic_num:
    python scripts/orchestrator.py plan {{epic_num}} --resume

# Show epic status from JSONL logs
epic-status epic_num:
    python scripts/orchestrator.py status {{epic_num}}

# Validate plan.json against schema (Phase A only)
epic-validate-plan epic_num:
    python scripts/plan_validator.py {{epic_num}}
```

**The `orchestrator.py` subcommands:**
- `plan` — runs steps 1-7 of the planning flow (ingest → context →
  scope → plan → verify → gate → commit)
- `plan --resume` — planning crash recovery (resumes from last
  completed planning step based on artefact presence)
- `run` — runs step 8 (story execution loop)
- `run --resume` — execution crash recovery
- `status` — reads JSONL logs and reports progress

**Single entry point design:** The orchestrator script is the unified
entry point. `just` recipes are thin wrappers. This keeps command
discovery simple (`just --list`) while centralising logic.

### Delete `run_epic.py`

After all dispatch logic has been extracted (Step 4) and the new
orchestrator is complete, delete `scripts/run_epic.py`. It has served
its purpose as a reference.

### Definition of Done

- [ ] All 7 `just` recipes registered in justfile
- [ ] `just epic-ingest` fetches from GitHub
- [ ] `just epic-plan` runs the full planning pipeline
- [ ] `just epic-plan-resume` recovers from planning crash
- [ ] `just epic-start` executes stories
- [ ] `just epic-resume` recovers from execution crash
- [ ] `just epic-status` reports progress from JSONL
- [ ] `just epic-validate-plan` runs Phase A schema validation
- [ ] `scripts/run_epic.py` deleted
- [ ] `just --list` shows the new recipes
- [ ] Commit: `feat(workflow): add V2 just recipes and delete run_epic.py`

---

## Step 14: Integration Test — Dry Run on Real Epic — [ ]

**Goal:** Verify the full V2 flow end-to-end by running it against a
real (or synthetic) epic. Fix issues discovered.

### Test Approach

1. **Create a small test epic** on GitHub (or use a closed epic like
   #95 as a read-only test subject)
2. Run `just epic-ingest <N>` — verify EPIC.md is created with correct
   frontmatter
3. Run the context assembly — verify CONTEXT.md is created
4. Skip interactive scope (provide pre-canned decisions) — or run
   interactively
5. Run plan generation — verify PLAN.md + plan.json are produced
6. Run Phase A validation — verify plan.json passes schema checks
7. Run Phase B verification — verify verifier agent returns structured
   output
8. Approve plan at Decision Gate
9. Execute one story — verify:
   - Agent dispatched with correct model/tools/skills
   - Prompt logged to `prompt-attempt-1.md`
   - JSONL events logged correctly
   - Code committed via `robust_commit()`
10. Run a validation checkpoint — verify:
    - Validation agent dispatched read-only
    - Structured output parsed correctly
    - Evidence fields populated
11. Verify crash recovery:
    - Kill the orchestrator mid-story
    - Resume with `just epic-resume <N>`
    - Verify it skips completed stories and resumes from the right point
12. Verify GitHub comments posted at milestone points

### Known Risk Areas

- `--agents` JSON flag compatibility — may need fallback to individual
  CLI flags if the `skills` field isn't supported in the current Claude
  Code version
- MCP pre-flight check — may need adjustment based on how Chrome
  DevTools and Playwright MCP servers are actually started
- Prompt size budget — verify <2,000 tokens with real plan content
- JSONL partial write handling — test by writing a truncated last line

### Definition of Done

- [ ] Full pipeline runs: ingest → plan → verify → execute → validate
- [ ] JSONL logs contain correct events with all required fields
- [ ] Prompts logged to `prompt-attempt-N.md`
- [ ] GitHub comments posted (or dry-run verified)
- [ ] Crash recovery works (skip completed, resume from next)
- [ ] At least one validation checkpoint runs with structured output
- [ ] No unhandled exceptions in the orchestrator
- [ ] All discovered issues fixed
- [ ] Commit: `test(workflow): verify V2 end-to-end flow`

---

## Appendix A: File Manifest

### New Files Created by V2

| File | Step | Purpose |
|------|------|---------|
| `scripts/schemas/plan.schema.json` | 1 | Plan specification contract |
| `scripts/schemas/jsonl-events.schema.json` | 1 | JSONL event types contract |
| `scripts/schemas/validation-result.schema.json` | 1 | Validation output contract |
| `scripts/schemas/verifier-result.schema.json` | 1 | Plan verifier output contract |
| `scripts/git_helpers.py` | 3 | Git operations (commit, sync) |
| `scripts/jsonl_logger.py` | 3 | JSONL event logging + crash recovery |
| `scripts/dispatch.py` | 4 | Agent dispatch (ProviderAdapter + ClaudeAdapter) |
| `scripts/prompt_builder.py` | 5 | 7-section prompt assembly |
| `scripts/epic_ingest.py` | 6 | GitHub epic fetching |
| `scripts/context_assembler.py` | 6 | Deterministic context assembly |
| `scripts/plan_generator.py` | 7 | Opus plan generation dispatch |
| `scripts/plan_validator.py` | 8 | Phase A deterministic validation |
| `scripts/plan_verifier.py` | 8 | Phase B AI verification dispatch |
| `scripts/validation.py` | 9 | Type-aware validation checkpoints |
| `scripts/story_executor.py` | 10 | Story inner loop + failure handling |
| `scripts/orchestrator.py` | 11 | Epic outer loop + GitHub integration |

### Runtime Artefacts Generated Per Epic

| File | Generated by | Purpose |
|------|-------------|---------|
| `.planning/epics/E<N>/EPIC.md` | `epic_ingest.py` | Ingested GitHub issue |
| `.planning/epics/E<N>/CONTEXT.md` | `context_assembler.py` | Assembled context for planner |
| `.planning/epics/E<N>/PLAN.md` | `plan_generator.py` | Human-readable plan |
| `.planning/epics/E<N>/plan.json` | `plan_generator.py` | Machine-readable plan |
| `.planning/epics/E<N>/epic.jsonl` | `orchestrator.py` | Epic-level event log |
| `.planning/epics/E<N>/SUMMARY.md` | `orchestrator.py` | Post-epic summary from JSONL |
| `.planning/epics/E<N>/stories/<id>/story.jsonl` | `story_executor.py` | Story-level event log |
| `.planning/epics/E<N>/stories/<id>/prompt-attempt-N.md` | `prompt_builder.py` | Logged agent prompts |

### Files Deleted by V2

| File | Step | Reason |
|------|------|--------|
| `scripts/snapshot_tests.py` | 2 | No test/impl split |
| `scripts/tasks_from_plan.py` | 2 | No `.tasks/` format |
| `scripts/validate_tasks.py` | 2 | Validates `.tasks/` not `plan.json` |
| `scripts/epic_reviewer.py` | 2 | TDD metrics |
| `scripts/run_epic.py` | 13 | Fully replaced by V2 orchestrator |
| `.claude/agents/test-author.md` | 2 | No test-author role |
| `.claude/agents/implementer.md` | 2 | Replaced by orchestrator prompts |
| `.claude/agents/gts-lint-checker.md` | 2 | "Never spend tokens on lint" |
| `.claude/agents/plan-reviewer.md` | 2 | Replaced by plan verifier |
| `.claude/agents/epic-context-loader.md` | 2 | Demoted to Python function |
| `.claude/agents/epic-gray-area-analyst.md` | 2 | Demoted to Python function |
| `.claude/agents/epic-goal-backward.md` | 2 | Merged into planner |
| `.claude/agents/epic-task-breakdown.md` | 2 | Merged into planner |
| `.claude/commands/epic.md` | 2 | Trivial V1 router |
| `.claude/commands/epic-review.md` | 2 | TDD review structure |
| `.tasks/_templates/task.md` | 2 | TDD template |
| `.tasks/projects/` (tree) | 2 | V1 execution artefacts |

### Files Modified by V2

| File | Step | Change |
|------|------|--------|
| `.claude/rules/epic-workflow.md` | 12 | Replace: V2 workflow description |
| `.claude/rules/testing-policy.md` | 12 | Refactor: remove TDD framing |
| `.claude/rules/mcp-required.md` | 12 | Refactor: orchestrator enforcement |
| `.claude/skills/epic/SKILL.md` | 12 | Replace: V2 commands and pipeline |
| `.claude/skills/epic/references/goal-backward.md` | 12 | Refactor: behavioural framing |
| `.claude/skills/gts-testing/SKILL.md` | 12 | Refactor: regression test framing |
| `AGENTS.md` | 12 | Update workflow section |
| `justfile` | 2, 13 | Remove TDD recipes, add V2 recipes |
| `../wiki/GitHub-Epic-Sync.md` | 12 | Replace: V2 approach |

---

## Appendix B: Design Principles (from research doc Section 6)

These principles govern every implementation decision. Reference them
when making trade-offs.

1. **Forward progress per token.** Every agent invocation produces
   committed code or a clear failure report.
2. **Behaviour over tests.** The gate is "does the thing work?" Tests
   exist for regression safety, not as the definition of done.
3. **Simplicity over machinery.** Python script + JSONL + git. Not a
   framework.
4. **Exit early, exit clearly.** Two retries per checkpoint, then exit
   with a clear log.
5. **Plan thoroughly, build fast.** Invest in planning. Let agents
   build uninterrupted.
6. **Same agent, different prompt.** No agent taxonomy. Just Claude Code
   with a well-constructed prompt.
7. **Provider-agnostic where possible (V2.1).** V2 ships Claude-only.
   The adapter pattern exists for V2.1.
8. **Machine-readable contracts as single sources of truth.** If
   there's no schema, it's not a contract.

---

## Appendix C: V2 Scope Boundary Reminder

**V2 ships (this plan covers):**
Orchestrator, planning pipeline, plan verification, agent dispatch
(Claude-only), JSONL logging with crash recovery, type-aware validation,
failure handling (5-type classification: env/scope/implementation/unknown/upstream,
2-retry budget), GitHub integration (ingest + comments), `.planning/` file
structure, SUMMARY.md generation.

**V2 does NOT ship (explicitly excluded):**
Multi-provider dispatch (Codex/Gemini adapters), `just sync-skills`,
JSONL-analytics-driven retry policy refinement (per-category budgets tuned
from historical data), JSONL analytics dashboards, parallel story
execution, local model routing, Gemini CLI setup, auto-close of GitHub
epics. See research doc Section 9 and Section 10 for V2.1 roadmap.
