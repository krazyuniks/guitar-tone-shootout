# Epic Workflow V2 — Strategy Document

A meta-paper for designing the next-generation epic workflow for GTS. This is a
brainstorm and research plan, not an implementation guide. Each section captures
what we've agreed, what we need to explore, and what questions remain open.

This document is self-contained. A fresh agent should be able to read it and
continue the work without further exploration.

---

## 1. What We're Replacing and Why

### The Current Workflow

GTS uses a TDD-driven epic workflow built around a **deterministic state machine**
(`scripts/run_epic.py`) that orchestrates AI agents through red → green → refactor
cycles for each task in an epic.

The full pipeline:

1. **Planning** (`/epic plan`) — interactive phase producing CONTEXT.md → GOALS.md →
   TASKS.md → materialised `.tasks/` files
2. **Validation** (`/epic validate`) — pre-flight checks on task file structure
3. **Execution** (`/epic start`) — TDD state machine dispatches `test-author` and
   `implementer` agents per task, enforces red/green gates, manages retries
4. **Review** (`/epic-review`) — post-mortem analysis of epic metrics

### An Example Failure

In Epic E95 (Phase 4 Completion), the signal chain builder — a core deliverable
— was never built. The test-author wrote `xfail` stubs ("component not yet
implemented"), which pass as expected failures. The implementer had nothing to
make green. The state machine saw green and marked 30/30 tasks complete. Nobody
ever asked "can you actually build a signal chain in the browser?"

This is one example, not the root cause. The root cause is the workflow itself.

### The Systemic Problems

The TDD workflow is fundamentally broken at every stage — planning, testing, and
execution. These are not isolated bugs. They are design flaws in the workflow itself.

**1. Tests as the only gate produces false completions.**

The state machine's only completion signal is "tests pass." But tests can pass
without the product working — via xfail, mock stubs, trivially satisfied
assertions, tests that check structure instead of function. The workflow trusts
test passage as proof of completion, and that trust is misplaced.

**2. The test-author/implementer split creates perverse incentives.**

The test-author writes tests. The implementer makes them pass. This creates an
optimisation target: the implementer optimises for "pass the test" not "build
the product." If the test is shallow, the implementation will be shallow. If the
test uses xfail, there's nothing to implement. The agents are doing exactly what
their prompts tell them to do — the prompts are wrong.

**3. Planning produces task lists, not product specifications.**

The planning phase (context → gray areas → goals → task breakdown) produces
granular task files with acceptance criteria. But the acceptance criteria are
technical ("User entity has email field") not behavioural ("when I create a
user, their profile shows up on the users page"). The planner never specifies
what the product should DO — only what code artifacts should exist.

**4. No behavioural validation at any stage.**

Between planning and human review, nobody checks whether the product actually
works. The state machine runs tests. Tests check code. But no agent opens a
browser, submits a form, queries a database to verify the product functions as
described. The verification gap is structural.

**5. Token waste on workflow overhead.**

The current workflow burns tokens on: lint checking (should be free via git
hooks), re-exploration of the codebase by every agent, context rot from long
orchestrator sessions, test-author/implementer round-trips, retry loops for
test-driven issues that don't resolve on retry.

**6. Rigid per-task cadence doesn't match reality.**

Every task gets the same treatment: test-author → implementer → validate → next.
But a domain model task has nothing to validate in a browser. A UI colour tweak
doesn't need a test-author. An infrastructure task needs process verification,
not HTTP assertions. One-size-fits-all TDD can't express this.

### The Shift

From **test-driven development** to **behaviour-validated development**.

The gate is not "do tests pass?" but "does the thing work?" — verified by
type-appropriate checks. Tests remain as regression safety nets, written after
the product works, not before implementation.

---

## 2. Proposed Architecture

### Stateless Orchestrator

The orchestrator is a **Python script** — no AI tokens spent on orchestration.
It reads a JSONL log, determines the next step, builds a prompt, dispatches one
agent, waits for completion, and loops.

```python
while True:
    state = read_log("story.jsonl")
    next_step = determine_next_step(state)
    if next_step == "done":
        break
    if next_step == "exit_human":
        notify_and_break()
    prompt = build_prompt(state, plan, feedback_from_log)
    dispatch_agent(prompt)
    # agent appends to story.jsonl, commits code, exits
```

This replaces the current `run_epic.py` TDD state machine. The new orchestrator
does not make AI calls. It is pure logic: read log → determine next step →
build prompt → dispatch → wait → loop.

### JSONL Log as Source of Truth

Every event is logged in structured JSONL — not just failures, but everything.
The JSONL log is a **versioned, schema-governed contract**, not illustrative
output. Every event conforms to a stable schema with mandatory fields that
enable mechanical parsing, crash recovery, and cross-run analytics.

**Universal fields (present on every event):**

| Field | Type | Purpose |
|-------|------|---------|
| `schema_v` | int | Schema version (currently `1`). Allows future evolution. |
| `run_id` | UUID | Generated once when the orchestrator starts. Groups all events from one execution. |
| `ts` | ISO 8601 | Timestamp with timezone. Monotonically increasing within a run. |
| `event` | string | Event type identifier. Enum of known types (see below). |

**Story-scoped fields (present on all story-level events, absent on epic-level events):**

| Field | Type | Purpose |
|-------|------|---------|
| `story_id` | string | Story identifier from `plan.json` (e.g., `"01-architecture"`). |
| `attempt` | int | Attempt number for this story (1-based). Increments on retry. |

**Epic-level events** (no `story_id` or `attempt`): `epic_started`, `github_comment`, `epic_complete`.

**Story-level events** (include `story_id` + `attempt`): `story_started`, `agent_dispatched`, `preflight_pass`, `preflight_fail`, `agent_complete`, `agent_failed`, `validation_pass`, `validation_fail`, `story_complete`, `story_failed`, `exit_to_human`.

**Event-specific fields** extend the above per event type:

```jsonl
{"schema_v":1,"run_id":"a1b2c3","ts":"2026-02-13T10:00:00Z","event":"story_started","story_id":"01-architecture","attempt":1}
{"schema_v":1,"run_id":"a1b2c3","ts":"2026-02-13T10:00:01Z","event":"agent_dispatched","story_id":"01-architecture","attempt":1,"model":"sonnet","prompt_hash":"abc123","prompt_tokens":1420,"skill_tokens":4200}
{"schema_v":1,"run_id":"a1b2c3","ts":"2026-02-13T10:05:00Z","event":"agent_complete","story_id":"01-architecture","attempt":1,"commit":"def456","turns":18,"cost_usd":1.80}
{"schema_v":1,"run_id":"a1b2c3","ts":"2026-02-13T10:05:30Z","event":"validation_pass","story_id":"01-architecture","attempt":1,"check_type":"quality","results":[{"criterion":"just check-types passes","status":"pass","evidence":{"exit_code":0,"test_count":42}}]}
{"schema_v":1,"run_id":"a1b2c3","ts":"2026-02-13T10:10:00Z","event":"validation_fail","story_id":"02-ui-scaffold","attempt":1,"check_type":"http+dom","failure_category":"implementation","results":[{"criterion":"GET /gear returns 200","status":"fail","evidence":{"status_code":404,"url":"http://localhost:9010/gear"}}]}
{"schema_v":1,"run_id":"a1b2c3","ts":"2026-02-13T10:15:00Z","event":"exit_to_human","story_id":"02-ui-scaffold","attempt":2,"reason":"validation failed after retry","failure_category":"implementation"}
```

**Known event types:** `epic_started`, `story_started`, `agent_dispatched`,
`preflight_pass`, `preflight_fail`, `agent_complete`, `agent_failed`,
`validation_pass`, `validation_fail`, `github_comment`, `story_complete`,
`story_failed`, `exit_to_human`, `epic_complete`.

**Crash recovery:** On restart, the orchestrator reads the JSONL log, finds
the latest `run_id`, identifies the last completed event, and resumes from
the next step. Events are append-only — a crashed run leaves a partial log
that the next run can continue. The orchestrator generates a new `run_id`
only if explicitly re-starting (not resuming).

**Idempotency:** The orchestrator never replays a step whose completion
event is already in the log. If `story_complete` exists for a story_id +
run_id, that story is skipped on resume. This prevents duplicate work
after crashes.

The log serves multiple purposes:
- **State**: script reads it to determine next step (mechanical, not heuristic)
- **Context**: agents read relevant entries to understand what's been done
- **Debugging**: humans read it to understand what went wrong
- **Recovery**: orchestrator resumes from last completed event after crash
- **Analytics**: patterns across logs inform prompt improvements over time (V2.1)

### Agent Model

All agents are the same — Claude Code invocations with different prompts.
No "test agent", "fix agent", or "validation agent" types. Just agents with
prompts constructed from: plan context + log state + any failure feedback.

This replaces the current split between `test-author` and `implementer` agents
with their separate prompt files and path restrictions.

Each **implementation agent**:
1. Reads relevant log entries + plan context (provided in prompt)
2. Runs pre-flight checks (validates inputs from previous agents)
3. Does its work (multiple tasks internally)
4. Appends events to the JSONL log
5. Commits code to git
6. Exits

Each **validation agent** is read-only (no Edit/Write tools). It:
1. Reads the validation criteria from its prompt
2. Performs type-aware checks (HTTP, DOM, DB, process)
3. Returns structured pass/fail results via `--json-schema`
4. Does NOT commit code or modify files

### Git as Handoff

Agents don't share context windows. The handoff between agents is:
- **Git**: modified/new files are committed, next agent reads from filesystem
- **JSONL log**: structured record of what happened
- **Plan**: stable document that all agents reference

### Failure Model

| Failure type | Action | Budget |
|-------------|--------|--------|
| Pre-flight minor | Agent self-fixes (<5 lines), logs it, continues | No budget cost |
| Pre-flight major | Script retries upstream agent with failure feedback appended to prompt | 2 attempts per checkpoint |
| Validation failure | Script dispatches agent with failure details to fix | 2 attempts per checkpoint |
| Planning failure | Exit to human immediately — plan doesn't match reality | No retry |

**Minor vs major heuristic:** A pre-flight issue is "minor" (agent self-fixes)
only if it meets ALL of these criteria: (a) the fix modifies only files within
the agent's assigned `scope` from `plan.json`, (b) the fix touches fewer than
10 lines total, and (c) the fix is mechanical (import path, missing comma,
wrong variable name) not architectural. Anything outside these bounds is
"major" — the agent logs the failure and the orchestrator retries the
upstream agent.

**Retry identity:** There is no specialised "Fix Agent" or "Repair Agent."
All retries use the same agent template as the original attempt. The only
difference is an additional Failure Feedback section in the prompt (see
Section 8.5 Decision 2, Section 6). "Retry the upstream agent" and "dispatch
an agent with failure details" both mean: re-invoke the same template with
the failure context appended.

"Planning failure" = the plan doesn't match reality (e.g., acceptance criteria
reference infrastructure that doesn't exist). No amount of retrying fixes this.
The agent logs it and exits. Human fixes the plan, re-runs from the failed step.

**Failure categorisation:** Every failure event in the JSONL log includes a
`failure_category` field. V2 applies the uniform 2-retry budget for most
categories, with one exception: `env` failures that are deterministically
unrecoverable (MCP unavailable, Docker not running, port conflict) exit
immediately — retrying wastes tokens on a problem only a human can fix.
V2.1 extends this to a full category-aware retry policy.

| Category | Meaning | Example | V2 retry policy |
|----------|---------|---------|-----------------|
| `env` | Infrastructure/environment problem | Docker down, port conflict, MCP unavailable | **0 retries — exit immediately** |
| `scope` | Plan references something wrong | File path doesn't exist, wrong module name | 2 retries (V2.1: 0) |
| `implementation` | Agent wrote incorrect code | TypeError, assertion failure, wrong logic | 2 retries |
| `unknown` | Cannot classify automatically | Agent timed out, ambiguous error | 2 retries (V2.1: 1) |
| `upstream` | Failure traced to a file owned by a completed earlier story | File ownership map shows failing file belongs to story N-2 | **0 retries — exit to human** |

The orchestrator classifies failures heuristically (exit code, error message
patterns, file ownership map). V2.1 refines classification using JSONL log
analysis across runs.

**File-to-story ownership map:** The orchestrator builds a reverse lookup
from `plan.json` at startup: for every file in every story's `scope.create`
and `scope.modify`, map `file_path → story_id`. When a validation failure
references a specific file or error location, the orchestrator checks this
map. If the failing file belongs to an earlier story (not the one being
validated), the retry targets that earlier story instead of the current one.
This prevents a later agent from hacking around a bug that belongs to an
earlier story's scope.

```python
def build_file_ownership_map(plan: dict) -> dict[str, str]:
    """Map file paths to owning story IDs from plan.json."""
    ownership = {}
    for story in plan["stories"]:
        for path in story["scope"].get("create", []):
            ownership[path] = story["story_id"]
        for path in story["scope"].get("modify", []):
            # Last writer wins — later stories that modify the same file own it
            ownership[path] = story["story_id"]
    return ownership
```

If the ownership map traces a failure to a completed story, the orchestrator
logs a `failure_category: "upstream"` event and exits to human — re-running
a previously validated story is a planning problem, not an implementation one.

**Git state on retry:** When an implementation agent fails after committing
code, the orchestrator does NOT roll back the failed commits. The retry
agent starts from the current filesystem state (including any broken code
from the previous attempt) and receives the failure feedback in its prompt.
The retry agent's job is to fix the broken state, not start from scratch.
This avoids destructive git operations and matches the "failure feedback in
prompt" pattern. If the retry also fails, the orchestrator exits to human
with the full JSONL log — the human decides whether to `git revert`, fix
manually, or adjust the plan.

### Story Flow

```
Plan → Agent (architecture) → Agent (UI scaffolding) → Validation (scaffold)
     → Agent (feature UI) → Validation (CRUD/behaviour) → Agent (regression tests)
     → Human validation → Done
```

Each box is a **separate agent invocation** with fresh context. The script
dispatches them sequentially. Tasks happen INSIDE agents — an architecture
agent might create the entity, repo, service, and migration all in one session.

Validation checkpoints are **strategic** — after scaffolding and after features.
Not after every internal task. Implementation agents run uninterrupted.

### Validation is Type-Aware

| Task type | How to validate |
|-----------|----------------|
| UI page | HTTP GET + DOM assertions — pages render, expected elements present |
| CRUD feature | Browser interaction + DB query — create/read/update/delete, DB reflects |
| API endpoint | HTTP request + response — correct status, correct data shape |
| Infrastructure | Process/connectivity — service starts, connects, functions |
| Style/design | Screenshot — visual appearance matches intent |
| Worker/pipeline | DB state after run — data landed where expected |

### Tests Are Regression Nets

Written AFTER the product works, by an agent that can see and interact with the
working product. Tests capture the current working behaviour so future changes
don't break it. They are not the definition of done.

---

## 3. Files to Be Replaced or Updated

### Scripts (in `scripts/`)

| File | Current purpose | V2 disposition |
|------|----------------|----------------|
| `run_epic.py` | TDD state machine — dispatches test-author/implementer agents, enforces red/green gates, manages task state | **Replace** with new stateless orchestrator. Core dispatch + JSONL log logic may be reusable. |
| `validate_tasks.py` | Pre-flight check on `.tasks/` file structure (AC exists, deps valid) | **Replace or refactor** — validation moves to planning output format, not task file structure |
| `tasks_from_plan.py` | Parse TASKS.md → `.tasks/` individual task files | **Replace** — planning output format changes (agent sequences + validation checkpoints, not TDD task files) |
| `snapshot_tests.py` | Hash test files to detect tampering between test-author and implementer phases | **Delete** — no test-author/implementer split, no snapshot enforcement |
| `test_quality_check.py` | Static analysis for mock violations, trivial assertions | **Keep (possibly refactor)** — mock banning and test quality checks still valuable for regression tests |
| `epic_reviewer.py` | Post-mortem mock density analysis, per-task metrics | **Replace** — review metrics change (no TDD phases, no bounce-back rate, new JSONL-based metrics) |
| `health_check.py` | Infrastructure health check | **Keep** — not workflow-related |
| `seed_di_tracks.py` | Seed data script | **Keep** — not workflow-related |
| `gts_admin.py` | Admin utilities | **Keep** — not workflow-related |

### Commands (in `.claude/commands/`)

| File | Current purpose | V2 disposition |
|------|----------------|----------------|
| `epic.md` | Unified `/epic` command routing (plan/validate/fix/start/status) | **Replace** — new workflow has different subcommands and different planning pipeline |
| `epic-review.md` | `/epic-review` post-mortem command | **Replace** — metrics and review structure change |
| `delegate.md` | `/delegate` orchestrator workflow for single issues | **Evaluate** — may overlap with new orchestrator, or may serve a different purpose (single-issue vs epic) |
| `ralph-hybrid.md` | Ralph Hybrid autonomous loop | **Evaluate** — different workflow approach, may coexist or be absorbed |
| `run-prompt.md` | `/run-prompt` sub-task delegation | **Evaluate** — prompt execution concept may be useful for new agent dispatch |
| `checkpoint.md` | Mid-session WIP commit | **Keep** — not workflow-specific |
| `claim.md` | Claim issue + create worktree | **Keep** — not workflow-specific |
| `merge.md` | PR + CI + auto-merge | **Keep** — not workflow-specific |
| `status.md` | Session state display | **Keep** — not workflow-specific |
| `next-issue.md` | Find next unblocked issue | **Keep** — not workflow-specific |
| `deps.md` | Issue dependency graph | **Keep** — not workflow-specific |
| `check.md` | Quality gates | **Keep** — not workflow-specific |
| `arch-review.md` | Architecture review | **Keep** — not workflow-specific |
| `worktree.md` | Git worktree management | **Keep** — not workflow-specific |
| `workflow-check.md` | Dev infrastructure verification | **Keep** — not workflow-specific |
| `resume.md` | Load previous session context | **Keep** — not workflow-specific |

### Agents (in `.claude/agents/`)

| File | Current purpose | V2 disposition |
|------|----------------|----------------|
| `test-author.md` | Write failing tests before implementation (TDD red phase) | **Delete** — no test-author role in V2. Tests written after product works. |
| `implementer.md` | Build code to make tests pass (TDD green phase) | **Replace** — new agent prompts built by orchestrator script, not static files. Architectural patterns and banned patterns from this file move to skills. |
| `plan-reviewer.md` | Review TASKS.md quality | **Replace** — planning output format changes |
| `epic-context-loader.md` | Load wiki docs, write CONTEXT.md | **Evaluate** — context loading concept may survive into new planning phase |
| `epic-gray-area-analyst.md` | Detect ambiguities, return questions | **Evaluate** — gray area detection concept may survive |
| `epic-goal-backward.md` | Derive observable truths from decisions | **Evaluate** — goal-backward concept may be refactored into behavioural acceptance criteria |
| `epic-task-breakdown.md` | Break goals into executable tasks | **Replace** — V2 produces agent invocation sequences, not granular task files |
| `gts-quality-reviewer.md` | Pre-merge quality validation | **Keep** — not workflow-specific |
| `gts-error-resolver.md` | Debug build/lint/type/test errors | **Keep** — not workflow-specific |
| `gts-lint-checker.md` | Check lint without fixing | **Evaluate** — may conflict with "never spend tokens on lint" principle |
| `debugger.md` | General debugging | **Keep** — not workflow-specific |
| `gts-workflow-verifier.md` | Verify hot reload infrastructure | **Keep** — not workflow-specific |
| `gts-log-monitor.md` | Tail Docker container logs | **Keep** — not workflow-specific |

### Skills (in `.claude/skills/`)

| File | Current purpose | V2 disposition |
|------|----------------|----------------|
| `epic/SKILL.md` | Full `/epic` lifecycle (plan/validate/fix/start/status) | **Replace** — entire planning pipeline changes |
| `epic/references/goal-backward.md` | GTS test patterns for goal-backward planning | **Replace** — test patterns change from TDD to behavioural validation |
| `epic/references/question-bank.md` | GTS-specific planning questions | **Evaluate** — questions may still be useful |
| `epic/references/gray-areas.md` | Ambiguity detection patterns | **Evaluate** — patterns may still be useful |
| `epic/references/github-templates.md` | GitHub issue templates | **Keep** |
| `ralph-hybrid-plan/` | Ralph Hybrid planning workflow | **Evaluate** — may overlap with new planner |
| `ralph-hybrid-overview/` | Ralph Hybrid workflow overview | **Evaluate** — may overlap |
| `micro-task-workflow/SKILL.md` | Micro-task decomposition patterns | **Evaluate** — 50% context budget concept may inform agent prompt sizing |
| `gts-testing/SKILL.md` | Test patterns, fixtures, banned patterns | **Refactor** — still needed but framing changes from "TDD workflow" to "regression test authoring" |
| `prompt-builder/SKILL.md` | Prompt creation guidance | **Evaluate** — may inform meta-prompting research |
| All other skills | Domain knowledge (architecture, auth, frontend, backend, etc.) | **Keep** — not workflow-specific, injected into agent prompts by orchestrator |

### Rules (in `.claude/rules/`)

| File | Current purpose | V2 disposition |
|------|----------------|----------------|
| `epic-workflow.md` | "Epics run via the TDD state machine" | **Replace** — entirely new workflow |
| `testing-policy.md` | TDD-centric testing rules | **Refactor** — keep no-mock, no-curl rules; remove TDD framing |
| `mcp-required.md` | MCP pre-flight requirements | **Refactor** — still needed but enforcement moves to orchestrator script |
| All other rules | Infrastructure, security, frontend, queries, etc. | **Keep** — not workflow-specific |

### Task Infrastructure (`.tasks/`)

| Directory | Current purpose | V2 disposition |
|-----------|----------------|----------------|
| `.tasks/projects/.../epics/E*/` | Per-epic task files, snapshots, logs, error reports | **Replace** — V2 uses JSONL log + git, not per-task markdown files |
| `.tasks/_templates/task.md` | Task file template | **Delete** — no individual task files |
| `.planning/epics/*/` | Planning artifacts (CONTEXT.md, GOALS.md, TASKS.md) | **Replace** — V2 planning produces different output format |

### GitHub Sync Infrastructure

| File/Command | Current purpose | V2 disposition |
|-------------|----------------|----------------|
| `scripts/gh_tasks_sync.py` (referenced, may not exist) | Pull GitHub epic + child issues into `.tasks/` | **Replace** — V2 needs to get epic content local but into a different format |
| `just epic-sync` | Trigger sync | **Replace** — new command for V2 epic ingestion |
| `../wiki/GitHub-Epic-Sync.md` | Documents sync protocol | **Replace** — V2 has different local format and different sync needs |

### The Outer Loop (Not Yet Designed)

The V2 workflow needs an outer loop around the story-level execution described
in Section 2. This outer loop handles the relationship between GitHub and local
work:

```
GitHub Epic (source of truth)
  → Ingest epic locally (fetch body, understand scope)
  → Planning phase (break into stories, define agent sequences + validation)
  → [Should planning ENRICH the GitHub epic? Add AC, update description?]
  → Execute stories (Section 2 flow, one story at a time)
  → Push results back to GitHub (close epic, comment with outcomes)
```

**Open questions:**

1. **Epic ingestion** — the current sync pulls child issues into `.tasks/`
   markdown files. V2 doesn't use `.tasks/`. What does the planner read?
   Just the raw GitHub issue body? A local copy in a different format?

2. **Planning output → GitHub** — should the planner write behavioural
   acceptance criteria back to the GitHub epic so the epic itself becomes
   the specification? Or does the spec stay local only (plan file)?

3. **Story ≠ GitHub issue** — in V2, a "story" is a chunk of work with an
   agent sequence. Does each story map 1:1 to a GitHub child issue? Or does
   the planner break an epic into stories that don't correspond to existing
   issues?

4. **Completion sync** — when a story finishes, should the orchestrator
   close the corresponding GitHub issue? Add a comment with the JSONL
   summary? Or is that manual?

5. **Multi-story orchestration** — an epic may have multiple stories.
   Does the outer loop run them sequentially? Can some run in parallel
   (on separate worktrees)? Who decides the order?

These questions belong in Research Area 4.8 below.

---

## 4. Research Areas

Each area below needs individual exploration. Order roughly reflects dependencies.

### 4.1 Current Workflow Audit

**Goal:** Deep-read every file listed in Section 3 to confirm dispositions and
identify reusable logic.

- `run_epic.py` — what's reusable? Agent dispatch logic, CLI arg parsing,
  subprocess management? Or start fresh?
- Planning pipeline agents — is the context → gray areas → goals flow worth
  preserving? Or does V2 planning need a completely different structure?
- How much code is shared between `validate_tasks.py`, `tasks_from_plan.py`,
  and `run_epic.py`? Can we extract common utilities?

### 4.2 Prompt Engineering & Meta-Prompting

**Goal:** Determine how to build rich, effective prompts for each agent invocation.

- **[taches-cc-resources/create-meta-prompts](https://github.com/glittercowboy/taches-cc-resources/tree/main/skills/create-meta-prompts)** —
  Can the orchestrator script use a prompter-agent to build the actual prompt?
  Flow would be: script determines what to do → dispatches prompter-agent →
  prompter builds rich prompt → script dispatches coder-agent with that prompt.
  Trade-off: extra agent invocation (tokens) vs better prompt quality.
  Or: can the meta-prompt patterns be baked into templates that the script fills
  in without an AI call?
- **Prompt templates** — should prompts be Jinja2/Mustache templates filled by
  the script? Variables: plan context, failure feedback, relevant skill content,
  log excerpts, file paths.
- **Skill inclusion** — which skills should be injected into which agent prompts?
  Architecture agent gets `gts-architecture`, `repository-patterns`,
  `service-patterns`. UI agent gets `gts-frontend-dev`, `htmx`, `astro-frontend`.
  Validation agent gets `playwright`, `chrome-devtools`.

### 4.3 Planning Phase Design

**Goal:** Design the planning phase that produces agent sequences and validation
criteria instead of TDD task files.

- **[taches-cc-resources/create-plans](https://github.com/glittercowboy/taches-cc-resources/tree/main/skills/create-plans)** —
  Study the workflow definitions approach. Is this how we should organise our
  planning output? What structure works for agent dispatch sequences?
- **Acceptance criteria format** — how to express behavioural criteria that are
  specific enough to validate but not so rigid they become tests-by-another-name?
  Example: "when I start the T3K worker process, it syncs API data to the local
  source database and fetches NAM files to local storage."
- **Validation checkpoint placement** — the planner decides where validation
  checkpoints go. A UI-heavy story needs browser validation. A backend-only story
  might only need API/DB validation. The planner must be task-type-aware.
- **Agent sequence** — the planner produces the ordered list of agent invocations
  with their purpose, required tools (MCP), and relevant skills to inject.

### 4.4 Token Efficiency

**Goal:** Minimise wasted tokens. Every agent invocation should make forward progress.

- **[claude-flow CLAUDE.md](https://github.com/ruvnet/claude-flow/blob/main/CLAUDE.md)** —
  Study their efficiency patterns: batched tool calls, TodoWrite usage, parallel
  operations, context management.
- **[Anthropic Claude Code docs](https://docs.anthropic.com/en/docs/claude-code)** —
  Latest official guidance on what we can influence: tool call batching, context
  window management, system prompt optimisation.
- **Lint/format** — NEVER spend agent tokens. Git pre-commit hooks run
  ruff/format for free. Agents should not invoke linting, type checking, or
  formatting. If pre-commit hooks fix something, the agent just re-commits.
- **Exploration overhead** — agents should receive full context from the plan,
  not re-explore the codebase. If an agent needs to read 5 files to understand
  the architecture, those file paths should be in its prompt.
- **TodoWrite** — is this useful for tracking progress within an agent, or is
  the JSONL log sufficient?
- **Tool call batching** — agents should make parallel tool calls whenever
  possible (parallel file reads, parallel searches).

### 4.5 Infrastructure Pre-Flight & MCP Configuration

**Goal:** Nail down how agents get their tools (MCP servers) reliably.

- **Chrome DevTools MCP** — required for UI validation. Currently invoked via
  shell aliases (`opus cp`). Needs to work via strict JSON config on the
  command line (`--strict-mcp-config --mcp-config`).
- **Playwright MCP** — required for E2E test authoring. Same config challenge.
- **Strict JSON config** — the orchestrator script needs to build the
  `--mcp-config <path>` arguments based on what the agent needs. Validation
  agents need browser tools. Architecture agents don't.
- **Shell aliases vs script dispatch** — current aliases (`opus`, `opus cp`,
  `opus p`, `sonnet c`) encode model + MCP combinations. The orchestrator
  script needs to replicate this without aliases. Need to document the exact
  `claude` CLI invocation for each combination.
- **Pre-flight MCP check** — before dispatching an agent that needs MCP,
  verify the MCP server is available. Don't discover it's missing 5 minutes
  into the agent's work.

### 4.6 Multi-Model & Multi-Provider Agent Dispatch

**Goal:** Dispatch agents to different models/providers based on task requirements.

- **Claude models** — Opus for complex architecture/planning, Sonnet for
  straightforward implementation, Haiku for validation/checks. The orchestrator
  picks the model based on task type.
- **GLM (local model)** — uses `--settings` file parameter instead of Anthropic
  API. Need to design the dispatch interface so it works with both.
- **Codex** — has its own skills feature. Can sync with Claude skills but not
  exactly 1:1. Need to understand the mapping and decide what to sync.
- **Gemini** — no skills/agents concept. Would need the full prompt built
  including all relevant skill content inlined. Deferred until later, but the
  architecture should not prevent it.
- **Dispatch interface** — the orchestrator script needs an abstraction:
  `dispatch_agent(prompt, model, mcp_config)` that handles the differences
  between providers. This was nearly working before — need to find and
  evaluate that prior work.
- **Cost/capability matrix** — which tasks go to which models? Architecture
  planning → Opus. Template creation → Sonnet. Pre-flight checks → Haiku.
  Validation with browser → needs MCP regardless of model.

### 4.7 Cross-Tool Skill Synchronisation

**Goal:** Keep skill knowledge consistent across Claude, Codex, and (later) Gemini.

- **Claude skills** — `.claude/skills/` with XML/markdown format, auto-loaded
  by skill name.
- **Codex skills** — similar concept, different format. Need to understand
  the mapping.
- **Gemini** — no native concept. Skills would need to be inlined into prompts
  or referenced as `@file` includes. Need to generate Gemini-compatible
  prompt fragments from the canonical skill definitions.
- **Single source of truth** — skills should be defined once and transformed
  per-provider. Not maintained separately.

### 4.8 GitHub Epic Lifecycle & Outer Loop

**Goal:** Design how GitHub epics flow into the V2 workflow and how results
flow back out.

- **Epic ingestion** — what replaces `gh_tasks_sync.py`? The planner needs
  the epic content locally. Options: (a) just `gh issue view` and work from
  the raw body, (b) a lightweight local copy in the planning directory,
  (c) a structured format the orchestrator can read.
- **Planning output → GitHub** — should the planner enrich the GitHub epic
  with behavioural acceptance criteria, story breakdowns, validation
  checkpoints? This would make the epic the single source of truth for
  both humans and agents. Or does the spec stay local only?
- **Story mapping** — does a "story" in V2 correspond 1:1 to a GitHub child
  issue? Or does the planner decompose differently? If stories don't map to
  issues, how do we track progress on GitHub?
- **Completion sync** — when a story completes (human-validated), should the
  orchestrator automatically close the GitHub issue, add a comment with JSONL
  summary, update labels? Or is push-back manual?
- **Multi-story sequencing** — an epic with multiple stories needs an outer
  loop. Sequential? Parallel on separate worktrees? Does the outer loop also
  use the JSONL log, or a separate epic-level state file?
- **`../wiki/GitHub-Epic-Sync.md`** — read and evaluate what's reusable from
  the current sync protocol.

---

## 5. Research Sequence

Suggested order for exploring the research areas. Each becomes its own session.

| # | Area | Depends on | Output |
|---|------|-----------|--------|
| 1 | Current workflow audit (4.1) | Nothing | **DONE** — See Section 8.1 |
| 2 | Token efficiency (4.4) | Nothing | **DONE** — See Section 8.2 |
| 3 | GitHub epic lifecycle (4.8) | 4.1 | **DONE** — See Section 8.3 |
| 4 | Planning phase design (4.3) | 4.1, 4.8 | **DONE** — See Section 8.4 |
| 5 | Prompt engineering (4.2) | 4.3 | **DONE** — See Section 8.5 |
| 6 | MCP configuration (4.5) | 4.1 | **DONE** — See Section 8.7 |
| 7 | Multi-model dispatch (4.6) | 4.5 | **DONE** — See Section 8.6 |
| 8 | Skill sync (4.7) | 4.6 | **DONE** — See Section 8.8 |

Items 1 and 2 can run in parallel. MCP configuration (6) must precede
multi-model dispatch (7) since dispatch needs MCP config patterns. GitHub
lifecycle (3) should come before planning design (4) since the planner
needs to know what it reads and writes.

---

## 6. Design Principles

Guiding principles for all decisions in this workflow redesign.

1. **Forward progress per token.** Every agent invocation should produce
   committed code or a clear failure report. No exploration loops, no lint
   fixing, no re-reading the same files.

2. **Behaviour over tests.** The gate is "does the thing work?" verified by
   type-appropriate checks. Tests exist for regression safety, not as the
   definition of done.

3. **Simplicity over machinery.** A Python script + JSONL log + git is the
   orchestrator. Not a framework, not a state machine with 20 states, not
   an AI agent deciding what to do next.

4. **Exit early, exit clearly.** When something's wrong, stop and tell the
   human. Don't burn tokens trying to fix planning failures. Two retries
   per checkpoint, then exit with a clear log of what happened.

5. **Plan thoroughly, build fast.** Invest time in planning (acceptance
   criteria, agent sequence, validation checkpoints). Then let agents build
   uninterrupted. Validation is strategic, not per-task.

6. **Same agent, different prompt.** No agent taxonomy. Just Claude Code with
   a well-constructed prompt. The prompt includes: what to do, what context
   to reference, what tools are available, and what went wrong last time
   (if anything).

7. **Provider-agnostic where possible (V2.1).** V2 ships Claude-only.
   The dispatch interface is designed so adding providers (Codex, Gemini,
   local models) is a localised change — one adapter file per provider.
   The adapter pattern (Section 8.6) is the architecture; V2 implements
   only `ClaudeAdapter`. Skills defined once, synced per-provider via
   `just sync-skills` (V2.1).

8. **Machine-readable contracts as single sources of truth.** Every
   interface between components — planner → orchestrator, orchestrator →
   agent, agent → validator — is defined by a versioned schema. Human-
   readable artefacts (PLAN.md, story.jsonl pretty-printed) are derived
   views, not the contract. `plan.json` (not PLAN.md) is what the
   orchestrator parses. JSONL events conform to a versioned schema with
   stable identifiers (`run_id`, `story_id`, `attempt`). Validation
   results use typed `--json-schema` with evidence fields per check type.
   If there's no schema, it's not a contract — it's a suggestion.

---

## 7. External References

Resources to study during research phases.

| Resource | Relevant for | Key concept |
|----------|-------------|-------------|
| [GSD (Get Shit Done)](https://github.com/gsd-build/get-shit-done) | Planning, validation | Goal-backward verification: "what must be TRUE?" not "what tasks did we do?" |
| [taches-cc-resources/create-meta-prompts](https://github.com/glittercowboy/taches-cc-resources/tree/main/skills/create-meta-prompts) | Prompt engineering | Meta-prompting: can a script or agent build richer prompts than static templates? |
| [taches-cc-resources/create-plans](https://github.com/glittercowboy/taches-cc-resources/tree/main/skills/create-plans) | Planning design | Workflow definition structure for organising planning output |
| [claude-flow CLAUDE.md](https://github.com/ruvnet/claude-flow/blob/main/CLAUDE.md) | Token efficiency | Tool call batching, TodoWrite, parallel operations, context management |
| [Anthropic Claude Code docs](https://docs.anthropic.com/en/docs/claude-code) | Efficiency, dispatch | Official guidance on CLI flags, MCP config, model selection |

---

## 8. Research Findings

> **Note:** "✅" and "DONE" markers in this section indicate **research complete**,
> not implementation complete. None of this has been built yet. Implementation
> begins after this strategy document is finalised and approved.

### 8.1 Current Workflow Audit (Area 4.1) ✅

**Completed.** Deep-read of every file listed in Section 3. Confirmed
dispositions, identified reusable logic, catalogued shared code.

#### Scripts Inventory

| Script | Lines | Disposition | Reusable Logic |
|--------|-------|-------------|----------------|
| `run_epic.py` | 2045 | **Replace** | Agent dispatch (~100 lines), MCP config, git helpers |
| `validate_tasks.py` | 313 | **Replace** | Circular dependency detection (~20 lines) |
| `tasks_from_plan.py` | 493 | **Replace** | ID mapping concept only |
| `snapshot_tests.py` | 333 | **Delete** | None |
| `test_quality_check.py` | 351 | **Keep** | Entire file (mock ban + quality antipatterns) |
| `epic_reviewer.py` | 587 | **Replace** | Mock pattern analysis per file |

#### Agent Dispatch Layer — Primary Reusable Asset

The most valuable code for V2 is the agent dispatch layer in `run_epic.py`
(~100 lines across 4 functions):

```
dispatch_agent()          — subprocess.run with stdin prompt, capture_output
build_claude_args()       — --allowedTools, --model, --max-turns, --mcp-config
build_mcp_config()        — agent + project → MCP JSON (chrome-devtools, playwright)
parse_agent_definition()  — YAML frontmatter parser for .claude/agents/*.md
```

This is the exact dispatch interface V2 needs. It handles:
- Tool enforcement via `--allowedTools` from agent YAML frontmatter
- Model selection per agent
- MCP server configuration (Chrome DevTools, Playwright) based on task type
- Prompt delivery via stdin (avoids command-line length limits)
- `--dangerously-skip-permissions` for autonomous execution

V2 should extract these into a `dispatch.py` module and build the new
orchestrator on top.

#### Git Helpers — Secondary Reusable Asset

`robust_commit()` (lines 333-358) handles pre-commit hook auto-fix retry:
commit → if hook modifies files → re-stage → retry commit. This is needed
regardless of workflow. `git_sync()` (lines 366-431) handles fetch → merge →
push with conflict detection. Both should move to a shared `git_helpers.py`.

#### Planning Pipeline Assessment

| Agent | Lines | Model | Disposition | Notes |
|-------|-------|-------|-------------|-------|
| `epic-context-loader` | 113 | haiku | **Demote to function** | File reading + template filling, no AI needed |
| `epic-gray-area-analyst` | 111 | haiku | **Demote to function** | Keyword lookup table, no AI needed |
| `epic-goal-backward` | 205 | sonnet | **Refactor** | Methodology excellent, output format changes |
| `epic-task-breakdown` | 256 | sonnet | **Replace** | V2 produces agent sequences, not task files |
| `plan-reviewer` | 175 | opus | **Replace** | Review criteria valuable, format changes |

**Key insight:** Two of the five planning agents (context-loader, gray-area-
analyst) can be replaced by deterministic Python functions, saving ~2 AI
invocations per planning session. The keyword→area mapping and question bank
are structured data, not reasoning tasks.

The goal-backward methodology (truths → artifacts → wiring → tests) is the
strongest part of the pipeline and should survive into V2, with the output
format changing from TDD test specs to behavioural validation criteria.

#### Execution Agent Assessment

| Agent | Lines | Model | Disposition | Salvageable Content |
|-------|-------|-------|-------------|---------------------|
| `test-author` | 276 | opus | **Delete** | GTS test patterns (→ skill), banned patterns (→ skill) |
| `implementer` | 230 | sonnet | **Replace** | Architecture context, systematic strategy |
| `gts-lint-checker` | 166 | haiku | **Delete** | Conflicts with "never spend tokens on lint" principle |

The test-author contains ~120 lines of GTS-specific test patterns (correct
SQLite fixtures, correct service tests, E2E patterns, banned patterns) that
should be preserved as reference material in a skill. The implementer's
systematic strategy (analyse→plan→execute→verify) could inform V2 agent prompts.

#### Command/Skill Assessment

| File | Disposition | Notes |
|------|-------------|-------|
| `commands/epic.md` | **Replace** | 5-line router, trivial |
| `commands/epic-review.md` | **Replace** | TDD-specific review structure |
| `commands/delegate.md` | **Keep** | Different scope (single issue), no overlap |
| `commands/ralph-hybrid.md` | **Keep** | Different paradigm (prd.json loop), may coexist |
| `commands/run-prompt.md` | **Keep** | Generic prompt delegation, not workflow-specific |
| `skills/epic/SKILL.md` | **Replace** | Planning pipeline changes entirely |
| `skills/epic/references/goal-backward.md` | **Refactor** | Good patterns, remove TDD framing |
| `skills/epic/references/question-bank.md` | **Keep** | GTS-specific, not workflow-coupled |
| `skills/epic/references/gray-areas.md` | **Keep** | Keyword patterns, not workflow-coupled |

#### Rules Assessment

| Rule | Disposition | Notes |
|------|-------------|-------|
| `epic-workflow.md` | **Replace** | Entirely TDD state machine references |
| `testing-policy.md` | **Refactor** | Keep no-mock, no-curl; remove TDD framing |
| `mcp-required.md` | **Refactor** | Enforcement moves to orchestrator script |
| All other rules | **Keep** | Not workflow-specific |

#### Infrastructure Assessment

| Item | Disposition | Notes |
|------|-------------|-------|
| `.tasks/_templates/task.md` | **Delete** | TDD-specific template |
| `.tasks/projects/.../E*/` | **Replace** | V2 uses JSONL + git, not per-task markdown |
| `.planning/epics/*/` | **Replace** | V2 planning output format changes |
| `gh_tasks_sync.py` | **Never existed** | Referenced in wiki, never built |
| `just` epic/tdd recipes | **Replace** | 15+ recipes tied to TDD phases |

#### Shared Code Analysis

Four scripts share duplicated code with no common utility module:

- **`TASKS_BASE` / `PROJECT_ROOT`** — identical constant in `run_epic.py`,
  `validate_tasks.py`, `tasks_from_plan.py`, `epic_reviewer.py`
- **Task file parsing** (title, state, project, blocked_by from markdown
  tables) — partially duplicated across 3 scripts
- **`VALID_PROJECTS` set** — duplicated in `run_epic.py` and `validate_tasks.py`

Not worth extracting shared utilities since V2 abandons the `.tasks/` markdown
format. Better to start clean with the V2 orchestrator.

#### Key Findings for V2 Design

1. **The dispatch layer is the primary reusable asset.** ~100 lines of clean
   subprocess management with MCP config, tool enforcement, model selection,
   stdin prompt. Extract to `dispatch.py` as the V2 orchestrator foundation.

2. **The planning pipeline has good methodology but bad output format.**
   Goal-backward thinking is sound. Output needs to become agent sequences +
   validation checkpoints, not TDD task files.

3. **Two planning agents can be replaced by deterministic code:**
   context-loader (file reading + template) and gray-area-analyst (keyword
   lookup). Saves ~2 AI invocations per planning run.

4. **The `.tasks/` format is a dead end.** Per-task markdown files with inline
   state tables create fragile parsing, massive git noise, and duplicated code.
   V2's JSONL log + git is the right direction.

5. **The TDD split is the root cause of E95's failure.** Everything
   downstream — snapshots, bounce-backs, known_failures.txt, scope-derived
   test files, test-lock commits — exists to paper over this fundamental
   design flaw. Removing the split eliminates ~1500 lines of machinery.

6. **`gts-lint-checker` should be deleted.** Conflicts directly with the V2
   principle of "never spend agent tokens on lint" — pre-commit hooks handle
   this for free.

7. **`delegate.md` and `ralph-hybrid.md` are separate concerns.** They solve
   different problems (single-issue orchestration and autonomous feature
   loops) and should coexist with V2, not be absorbed. `run-prompt.md` is
   a generic utility and should stay.

8. **`test_quality_check.py` is the one script that survives intact.** Mock
   ban enforcement and test antipattern detection are project policy, not
   workflow-specific. Keep as-is.

### 8.2 Token Efficiency (Area 4.4) ✅

**Completed.** Studied claude-flow CLAUDE.md, Anthropic official docs (overview,
best practices, sub-agents, CLI reference, headless mode, Agent SDK), GTS
pre-commit configuration, and current dispatch layer in `run_epic.py`.

#### The Fundamental Constraint

From Anthropic's official best practices:

> "Most best practices are based on one constraint: Claude's context window
> fills up fast, and performance degrades as it fills."

Every efficiency pattern traces back to this. The context window holds the
entire conversation — every message, every file read, every command output.
Performance degrades as it fills. The V2 orchestrator must treat context as
the primary resource to manage.

#### Strategy 1: Context Isolation (Highest Impact)

**Each agent invocation gets a fresh context window.** This is the single
most impactful efficiency pattern — it eliminates context rot entirely.

The V2 architecture already mandates this: agents are separate `claude -p`
invocations with no shared conversation history. Handoff is via git (files)
and JSONL (structured state). No agent inherits another's context pollution.

From Anthropic docs on subagents:

> "Subagents run in separate context windows and report back summaries ...
> The verbose output stays in the subagent's context while only the relevant
> summary returns to your main conversation."

**V2 implication:** Each agent invocation is inherently a fresh context. The
orchestrator constructs the prompt with exactly the context needed — no more.
Agents don't re-explore; they receive file paths, plan excerpts, and failure
feedback pre-assembled.

#### Strategy 2: Prompt Construction (High Impact)

**Give agents everything they need upfront.** From Anthropic best practices:

> "Reference specific files, mention constraints, and point to example
> patterns. ... The more precise your instructions, the fewer corrections
> you'll need."

The orchestrator should construct rich prompts containing:

1. **Plan context** — relevant excerpt from the story plan
2. **Skill content** — domain knowledge injected via the `skills` field in
   `--agents` JSON (see Section 8.5 Decision 7 for canonical dispatch mechanism)
3. **File paths** — exact files to read/modify (no "go find" exploration)
4. **Failure feedback** — if retrying, the JSONL failure entry verbatim
5. **Verification criteria** — how the agent checks its own work

The `--agents` JSON flag consolidates model, tools, skills, MCP, and prompt
into a single declaration. The `skills` field injects full skill content at
startup. This is the canonical V2 dispatch mechanism (see Section 8.5
Decision 7 for rationale). The `--append-system-prompt-file` flag is the
fallback for environments where `--agents` isn't available.

Example `--agents` JSON with skill injection:

```json
{
  "arch-agent": {
    "description": "Architecture agent for backend work",
    "prompt": "Implement the following...",
    "skills": ["gts-architecture", "repository-patterns", "service-patterns"],
    "tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
    "model": "sonnet"
  }
}
```

**V2 implication:** The orchestrator builds the prompt from templates. Skill
injection is automated — the script determines which skills an agent needs
based on task type and includes them. No agent wastes tokens exploring the
codebase to understand patterns that are already documented in skills.

#### Strategy 3: Model Routing (Medium Impact)

**Match model capability to task complexity.** The CLI supports `--model`
and `--fallback-model` for automatic downgrade on overload.

| Task Type | Model | Rationale |
|-----------|-------|-----------|
| Planning, complex architecture | Opus | Requires deep reasoning across many concerns |
| Implementation, feature building | Sonnet | Good balance of capability and speed |
| Validation, pre-flight checks | Haiku | Fast, cheap, sufficient for HTTP/DOM checks |
| Style/screenshot comparison | Sonnet | Needs visual reasoning but not Opus-level |

The `--fallback-model` flag provides resilience:

```bash
claude -p "..." --model opus --fallback-model sonnet
```

If Opus is overloaded, it falls back to Sonnet automatically. The orchestrator
should set this for all non-critical invocations.

**V2 implication:** The orchestrator selects model per agent type. Planning
agents get Opus. Implementation agents get Sonnet. Validation agents get
Haiku. The plan format should annotate each agent invocation with its
intended model.

#### Strategy 4: Tool Restriction (Medium Impact)

**Scope each agent to the tools it actually needs.** From the CLI docs:

- `--allowedTools "Tool1,Tool2"` — auto-approve specific tools
- `--tools "Bash,Edit,Read"` — restrict which tools are available at all
- `--disallowedTools "Tool1"` — explicitly deny specific tools

Restricting tools reduces the system prompt size (fewer tool descriptions
in context) and prevents agents from wasting turns on irrelevant tool use.

| Agent Role | Required Tools | Explicitly Denied |
|------------|---------------|-------------------|
| Architecture/implementation | Read, Edit, Write, Bash, Glob, Grep | Task (no sub-agent spawning) |
| Validation (browser) | Read, Bash, Glob, Grep + MCP tools | Edit, Write (read-only) |
| Validation (API/DB) | Bash, Read, Glob, Grep | Edit, Write (read-only) |
| Regression test authoring | Read, Edit, Write, Bash, Glob, Grep | Task |

**V2 implication:** The `--tools` flag (which _restricts_ available tools)
is more appropriate than `--allowedTools` (which _auto-approves_ specific
tools). Combined with `--dangerously-skip-permissions`, the agent has exactly
the tools it needs and no others.

#### Strategy 5: Lint/Format Elimination (Low-Medium Impact)

**NEVER spend agent tokens on lint, formatting, or type checking.**

GTS pre-commit hooks already handle this for free:

```yaml
# .pre-commit-config.yaml (prek)
- id: trailing-whitespace
- id: end-of-file-fixer
- id: check-yaml / check-toml
- id: check-added-large-files
- id: check-merge-conflict
- id: detect-private-key
- id: ruff (--fix)
- id: ruff-format
- id: astro-lint
```

When an agent commits code:
1. Pre-commit hooks auto-fix lint/format issues
2. `robust_commit()` detects the hook modifications
3. Re-stages fixed files and retries the commit
4. Zero agent tokens spent

**V2 implication:** No lint-checking agents. No type-checking agents. The
`gts-lint-checker` agent should be deleted (confirmed in Area 4.1). Quality
gates (`just check`) run as a validation checkpoint — the orchestrator
invokes it as a subprocess, not as an AI agent call.

#### Strategy 6: Structured Output (Medium Impact)

**Parse agent results programmatically, not from prose.**

The CLI supports `--output-format json` and `--json-schema` for structured
output:

```bash
claude -p "Validate the scaffold" \
  --output-format json \
  --json-schema '{"type":"object","properties":{
    "status":{"enum":["pass","fail"]},
    "failures":{"type":"array","items":{"type":"string"}}
  },"required":["status","failures"]}'
```

The orchestrator can parse the `structured_output` field directly —
no regex parsing of agent prose. This is particularly valuable for
validation checkpoints where the orchestrator needs a clear pass/fail
signal.

**V2 implication:** Validation agents should return structured results.
The orchestrator defines a JSON schema per validation type and passes it
via `--json-schema`. The agent does its checks and returns structured
pass/fail with failure details. The orchestrator logs this to JSONL
and determines next steps mechanically.

#### Strategy 7: Budget Controls (Safety)

**Cap spending and prevent runaway agents.**

| Flag | Purpose |
|------|---------|
| `--max-turns N` | Hard limit on agentic turns (exits with error when reached) |
| `--max-budget-usd N` | Dollar cap per invocation |
| `--no-session-persistence` | Don't save ephemeral sessions to disk |

Recommended defaults for V2:

| Agent Type | Max Turns | Max Budget |
|------------|-----------|------------|
| Planning (Opus) | 50 | $5.00 |
| Architecture (Sonnet) | 30 | $3.00 |
| Implementation (Sonnet) | 40 | $4.00 |
| Validation (Haiku) | 15 | $0.50 |
| Regression tests (Sonnet) | 30 | $3.00 |

These are starting points — adjust based on actual usage data from the
JSONL logs.

**V2 implication:** Every agent invocation includes `--max-turns` and
`--max-budget-usd`. The orchestrator logs actual cost from the JSON
output for each invocation. Over time, the logs reveal optimal budgets
per agent type.

#### Strategy 8: CLI Dispatch vs Agent SDK

**Two dispatch mechanisms are available:**

1. **CLI dispatch** (`claude -p "..." via subprocess`) — current GTS approach
2. **Agent SDK** (`claude-agent-sdk` Python package) — new programmatic API

| Aspect | CLI Dispatch | Agent SDK (Python) |
|--------|-------------|-------------------|
| Invocation | `subprocess.run(["claude", "-p", ...])` | `async for msg in query(prompt, options)` |
| Output parsing | JSON string → `json.loads()` | Native Python message objects |
| Session management | `--resume <session-id>` | `resume=session_id` in options |
| Hook integration | Shell commands only | Python callback functions |
| MCP config | `--mcp-config <json>` | `mcp_servers={...}` in options |
| Structured output | `--json-schema <json>` | Same, via options |
| Complexity | Simple, proven | Adds `claude-agent-sdk` dependency |
| Streaming | `--output-format stream-json` | Native async generator |

**Recommendation:** Start V2 with CLI dispatch — it's already working in
GTS (`dispatch_agent()` in `run_epic.py`), well-understood, and requires
no new dependencies. The Agent SDK is the better long-term choice for V3
once V2 is proven. The dispatch interface should be designed so swapping
CLI for SDK is a localised change.

#### Strategy 9: Verification as the Primary Gate

From Anthropic best practices:

> "Give Claude a way to verify its work ... This is the single
> highest-leverage thing you can do."

This aligns perfectly with V2's "behaviour over tests" principle. Each
agent should receive explicit verification criteria in its prompt:

- Architecture agent: "After creating the entity and repository, run
  `just check-types` and verify no type errors in the new files."
- UI agent: "After creating the page, use Chrome DevTools to verify
  the page loads at `/gear` with the expected heading."
- CRUD agent: "After implementing create, use Playwright to submit
  the form and query the database to verify the row exists."

Verification criteria come from the plan. The planner writes them.
The orchestrator injects them into agent prompts. The agent executes
them and reports results.

#### Patterns Evaluated but NOT Adopted

**From claude-flow (not applicable to V2):**
- HNSW indexing, neural learning, SONA adaptation, LoRA distillation —
  custom to their framework, not available in Claude Code
- Agent Booster (WASM) — their custom optimiser, not generalised
- Hive-Mind consensus, CRDT strategy — multi-agent coordination framework
  features, V2 is sequential-agent with a Python orchestrator
- Memory architecture (SQLite + AgentDB) — their persistence layer,
  V2 uses JSONL + git

**From claude-flow (principle adopted, implementation differs):**
- "1 MESSAGE = ALL RELATED OPERATIONS" → V2 agents make parallel tool
  calls internally (Claude Code already does this natively)
- 3-tier model routing → Adopted as Strategy 3 above
- Task complexity detection → The planner decides agent type, not runtime
- "Do what has been asked; nothing more, nothing less" → Enforced via
  focused prompts with explicit scope

**TodoWrite:**
- Available as `TaskCreate`/`TaskUpdate` tools in Claude Code
- Useful for tracking progress _within_ a single agent invocation
- The JSONL log tracks progress _across_ agent invocations
- **Recommendation:** Don't inject TodoWrite into agent prompts. It adds
  overhead without clear benefit when agents are scoped to focused tasks.
  The JSONL log is the cross-agent progress tracker.

#### CLI Flags Reference for V2 Orchestrator

Complete set of flags the orchestrator should use when dispatching agents:

```python
# V2 dispatch command construction
args = [
    "claude",
    "-p", "-",                              # Prompt via stdin
    "--model", model,                        # opus/sonnet/haiku
    "--max-turns", str(max_turns),           # Safety limit
    "--max-budget-usd", str(budget),         # Cost cap
    "--tools", ",".join(tools),              # Restrict available tools
    "--dangerously-skip-permissions",        # Autonomous execution
    "--no-session-persistence",              # Don't save ephemeral sessions
    "--output-format", "json",               # Parseable output
    "--append-system-prompt-file", skills_file,  # Inject skills
]

# Optional: structured validation output
if json_schema:
    args.extend(["--json-schema", json.dumps(json_schema)])

# Optional: MCP servers for browser-based agents
if mcp_config:
    args.extend(["--strict-mcp-config", "--mcp-config", json.dumps(mcp_config)])

# Optional: fallback model for resilience
if fallback_model:
    args.extend(["--fallback-model", fallback_model])
```

**New flags not used in current `run_epic.py`:**
- `--tools` (restricts available tools, stronger than `--allowedTools`)
- `--max-budget-usd` (cost cap per invocation)
- `--no-session-persistence` (ephemeral sessions)
- `--output-format json` (parseable output)
- `--json-schema` (structured validation output)
- `--append-system-prompt-file` (skill injection without replacing defaults)
- `--fallback-model` (automatic model downgrade)

#### Key Findings for V2 Design

1. **Context isolation is already built into the V2 architecture.** Each
   agent invocation is a separate `claude -p` call with fresh context.
   This eliminates the #1 cause of token waste (context rot) by design.

2. **Prompt construction is the highest-leverage optimisation.** Rich
   prompts with plan context + skills + file paths + verification criteria
   eliminate exploration overhead. Use `--append-system-prompt-file` for
   skill injection.

3. **Model routing saves 50-80% on non-critical tasks.** Haiku for
   validation (~$0.0002/call) vs Opus for planning (~$0.015/call).
   The plan format should annotate each step with its intended model.

4. **Structured output via `--json-schema` enables mechanical validation.**
   Validation agents return pass/fail + failure details as JSON. The
   orchestrator parses this without regex or prose interpretation.

5. **Pre-commit hooks handle lint/format for free.** Zero agent tokens.
   `robust_commit()` handles the retry. Delete `gts-lint-checker`.

6. **CLI dispatch is the right choice for V2.** Agent SDK is better
   long-term but adds dependency and complexity. The current dispatch
   layer needs minimal changes — add new flags, extract to `dispatch.py`.

7. **Budget controls are essential for autonomous execution.** `--max-turns`
   and `--max-budget-usd` prevent runaway agents. JSONL logs track actual
   cost per invocation for tuning.

8. **Verification criteria in prompts is the "single highest-leverage
   thing."** The planner writes verification criteria. The orchestrator
   injects them into agent prompts. The agent verifies its own work.
   This is the behavioural validation core of V2.

### 8.3 GitHub Epic Lifecycle & Outer Loop (Area 4.8) ✅

**Completed.** Studied the current GitHub epic format (issues #95, #112),
the wiki sync protocol (`GitHub-Epic-Sync.md`), the current `.tasks/`
infrastructure (E1, E86, E95), the planning pipeline output (`.planning/`),
and two external references (GSD and taches-cc-resources) for patterns.

#### Current State Assessment

**What exists today:**

1. **GitHub epics** are monolithic issue bodies with structured sections:
   Overview, Context, Pre-requisites, Scope (per sub-phase), Dependency
   Graph, Verification criteria, Key Files. Example: #95 has ~200 lines
   of rich context across 5 sub-phases with file-level scope.

2. **No sub-issues.** GitHub sub-issues API returns `[]` for #95. Epics
   are self-contained — child tasks live in the issue body or in `.tasks/`
   markdown files, not as separate GitHub issues.

3. **`gh_tasks_sync.py` was never built.** The wiki documents it
   extensively (sync protocol, CLI commands, GitHub Action config,
   bidirectional sync) but the script doesn't exist. The wiki is
   aspirational, not documentation of reality.

4. **Push-back is manual.** The wiki explicitly notes: "Automated
   push-back of task state (issue close, label updates, validation
   comments) is not yet implemented." In practice, epic issues stay
   OPEN even after all work is done (#95 is still OPEN despite 30/30
   tasks complete).

5. **The planning pipeline produces local-only artifacts.** `.planning/`
   contains CONTEXT.md, GOALS.md, TASKS.md — none of which sync back
   to GitHub. The planner reads the GitHub epic body (manually or via
   `gh issue view`) and produces local files.

6. **`.tasks/` is the execution format.** `tasks_from_plan.py` converts
   TASKS.md into per-task markdown files in `.tasks/`. These are the
   files `run_epic.py` reads. GitHub is not consulted during execution.

**Summary: GitHub is write-once input, `.tasks/` is the working copy,
push-back never happens.** The "sync" is one-directional and manual.

#### Design Decision 1: Epic Ingestion

**Recommendation: Lightweight local copy via `gh issue view`, stored
as a single plan input file.**

The planner needs the epic content locally. Three options were evaluated:

| Option | Mechanism | Pros | Cons |
|--------|-----------|------|------|
| **(a) Live `gh issue view`** | Planner calls `gh` at runtime | Always current | Network dependency during planning; slow; no offline work |
| **(b) Lightweight local copy** | Script fetches once to `epic.md` | Fast reads; works offline; versionable | Can go stale |
| **(c) Structured format** | Parse into JSON/YAML schema | Machine-readable for orchestrator | Over-engineering; epic format varies |

**Chosen: Option (b)** — a `just epic-ingest <number>` command that:

1. Runs `gh issue view <number> --repo krazyuniks/guitar-tone-shootout`
   to fetch the raw body
2. Writes it to `.planning/epics/E<number>/EPIC.md` with metadata header
   (issue number, title, state, labels, fetched timestamp)
3. Is idempotent — re-running overwrites the local copy

This replaces the never-built `gh_tasks_sync.py` with something much
simpler. The planner reads `EPIC.md` as its primary input. No parsing
into a schema — the epic body is already well-structured markdown that
Claude reads natively.

**Format of `.planning/epics/E<number>/EPIC.md`:**

```markdown
---
github_issue: 95
title: "Phase 4 Completion — DI Tracks, Groups, Shootout Workflow..."
state: OPEN
labels: [epic]
fetched: 2026-02-13T01:00:00Z
---

[Raw GitHub issue body verbatim]
```

The YAML frontmatter is for the orchestrator script. The body is for
the planner agent.

**Why not option (c)?** GitHub epic bodies vary in structure. #95 has
sub-phases (4A–4E) with inline scope. #112 has phases (5C/5E/5F/5V)
with different structure. Trying to parse these into a schema would
be brittle and add complexity for no clear benefit — the AI planner
reads markdown directly.

#### Design Decision 2: Planning Output → GitHub

**Recommendation: Do NOT enrich the GitHub epic. The plan stays local.**

Two approaches were evaluated:

| Approach | Pros | Cons |
|----------|------|------|
| **Enrich GitHub epic** | Single source of truth; visible to non-agents; PR-linkable | Noisy diffs on the epic issue; coupling between local format and GitHub format; requires write-back automation; epic becomes a living document edited by both humans and agents |
| **Local-only plan** | Simple; no sync complexity; plan format can evolve freely; GitHub epic stays stable as the *intent* document | Two places to look; human must check local plan for details |

**Chosen: Local-only plan.** The GitHub epic expresses *intent* ("what
we want to build"). The local plan expresses *strategy* ("how we'll
build it" — agent sequences, validation checkpoints, file paths). These
are different concerns with different audiences and different change
frequencies.

The planner produces its output in `.planning/epics/E<number>/PLAN.md`
(or similar — exact format is Research Area 4.3's responsibility). The
GitHub epic is not modified during planning or execution.

**However: the orchestrator SHOULD comment on the epic at key points**
(see Design Decision 4 below).

#### Design Decision 3: Story Mapping

**Recommendation: Stories do NOT map 1:1 to GitHub issues. Stories are
an internal planning concept.**

The V2 "story" is a chunk of work with an agent sequence and validation
checkpoints. In the current GTS workflow:

- Epics have no sub-issues (confirmed: #95 sub-issues = `[]`)
- Tasks are internal to `.tasks/`, not GitHub issues
- The only GitHub artifact is the epic issue itself

Creating GitHub issues for each story would add overhead without clear
benefit — the stories are implementation detail that the orchestrator
manages internally. The relevant tracking granularity for GitHub is
the epic level, not the story level.

**Progress visibility is achieved through epic comments** (Design
Decision 4), not through child issue status.

**Exception: if a story reveals a bug or a new feature that's out of
scope for the current epic, that SHOULD become a new GitHub issue.**
The agent or orchestrator can create issues for discovered work. But
planned stories within an epic stay local.

#### Design Decision 4: Completion Sync (Push-Back Protocol)

**Recommendation: Automated comments at milestones, manual close.**

The orchestrator should push status back to GitHub at four points:

| Event | Action | Content |
|-------|--------|---------|
| **Planning complete** | Comment on epic | Story count, agent sequence summary, estimated validation checkpoints |
| **Story validated** | Comment on epic | Story name, pass/fail, files changed, JSONL excerpt (key events) |
| **Epic complete (all stories pass)** | Comment on epic + add label | Summary: stories completed, total commits, any deferred items |
| **Human validation complete** | Close epic issue | Human closes after review (NOT automated) |

**Why not auto-close?** Closing an epic is a human decision. The agent
completed the work, but "complete" means "the human verified it works."
Auto-close would reproduce the E95 failure mode — the system declares
done before anyone checks.

**Implementation:**

```python
def comment_on_epic(epic_number: int, body: str) -> None:
    """Post a comment to the GitHub epic issue."""
    subprocess.run([
        "gh", "issue", "comment", str(epic_number),
        "--repo", "krazyuniks/guitar-tone-shootout",
        "--body", body,
    ], check=True)

def label_epic(epic_number: int, label: str) -> None:
    """Add a label to the GitHub epic issue."""
    subprocess.run([
        "gh", "issue", "edit", str(epic_number),
        "--repo", "krazyuniks/guitar-tone-shootout",
        "--add-label", label,
    ], check=True)
```

**Comment format (story completion):**

```markdown
## Story Complete: UI Scaffolding ✅

**Agent:** arch-scaffold | **Model:** sonnet | **Turns:** 24
**Files:** 12 created, 3 modified | **Commit:** abc1234

### Validation
- ✅ GET /gear returns 200 with gear listing
- ✅ GET /gear/{id} returns 200 with gear detail
- ✅ Navigation links present in header

### JSONL Summary
```jsonl
{"event":"agent_complete","story_id":"ui_scaffold","commit":"abc1234"}
{"event":"validation_pass","checks":3,"failures":0}
```
```

This provides GitHub visibility without coupling the local workflow to
GitHub's data model.

#### Design Decision 5: Multi-Story Sequencing (The Outer Loop)

**Recommendation: Sequential execution with an epic-level JSONL log.**

The outer loop is simpler than the inner loop (Section 2). It:

1. Reads the plan to get the ordered list of stories
2. For each story, runs the inner loop (Section 2 flow)
3. After each story, posts a GitHub comment
4. If a story fails after retries, exits to human
5. After all stories pass, posts a summary comment

**State tracking: epic-level JSONL log** at
`.planning/epics/E<number>/epic.jsonl`:

```jsonl
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"epic_started","epic":95,"stories":5}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"story_started","story_id":"01-architecture","attempt":1,"index":1}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"story_complete","story_id":"01-architecture","attempt":1,"commit":"abc123"}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"github_comment","epic":95,"comment_url":"..."}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"story_started","story_id":"02-ui-scaffold","attempt":1,"index":2}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"story_failed","story_id":"02-ui-scaffold","attempt":2,"reason":"validation failed after retry"}
{"schema_v":1,"run_id":"x1y2z3","ts":"...","event":"exit_to_human","story_id":"02-ui-scaffold","attempt":2,"context":"..."}
```

The story-level JSONL (`story.jsonl`) tracks agent invocations within
a story. The epic-level JSONL tracks story progression. Two levels,
same format.

**Why sequential, not parallel?** Stories within an epic typically have
dependencies (architecture before UI, UI before CRUD, CRUD before
regression tests). Parallel execution on separate worktrees is
theoretically possible but adds significant complexity:

- Merge conflicts between stories
- Validation that assumes cumulative state
- Worktree management automation
- Story dependency resolution

**Deferral: parallel story execution is a V3 concern.** V2 should nail
sequential execution first. The JSONL log format doesn't prevent future
parallel execution — it's append-only and story-scoped.

#### Design Decision 6: `.planning/` as the Single Local Root

**Recommendation: `.planning/epics/E<number>/` replaces both `.planning/epics/*/`
(current planning) and `.tasks/.../E*/` (current execution).**

The current workflow has two local roots:
- `.planning/epics/` — planning artifacts (CONTEXT.md, GOALS.md, TASKS.md)
- `.tasks/projects/.../epics/` — execution artifacts (index.md, tasks/, snapshots/, logs/)

V2 collapses these into one:

```
.planning/
└── epics/
    └── E95/
        ├── EPIC.md          # Ingested from GitHub (Design Decision 1)
        ├── PLAN.md          # Human-readable plan (for review)
        ├── plan.json        # Machine-readable plan (for orchestrator)
        ├── epic.jsonl       # Epic-level outer loop log
        ├── stories/
        │   ├── 01-architecture/
        │   │   └── story.jsonl   # Story-level inner loop log
        │   ├── 02-ui-scaffold/
        │   │   └── story.jsonl
        │   └── 03-crud-features/
        │       └── story.jsonl
        └── SUMMARY.md       # Post-epic summary (generated)
```

**What's deleted:**
- `.tasks/` directory entirely (per-task markdown, snapshots, error logs)
- `.tasks/_templates/`
- All TDD phase tracking

**What's preserved (in new format):**
- Epic metadata (EPIC.md replaces `EPIC.md` + `index.md`)
- Execution logs (versioned JSONL replaces error log markdown files)
- Planning artifacts (PLAN.md + plan.json replace CONTEXT.md + GOALS.md + TASKS.md)

#### Evaluation of `../wiki/GitHub-Epic-Sync.md`

**Verdict: Replace entirely.** The wiki documents a sync protocol for
infrastructure that was never built (`gh_tasks_sync.py`, GitHub Actions,
webhooks, bidirectional sync). None of it exists. The V2 approach
(lightweight ingestion + comment push-back) is much simpler and actually
implementable.

**Reusable concepts (carried into V2 design above):**
- The idea that GitHub is source of truth for epic structure
- The conflict resolution table (GitHub closed wins over local pending)
- The principle that execution state stays local

**Not reusable:**
- Per-task sync (V2 has no per-task GitHub issues)
- Bidirectional sync protocol (V2 is ingest + comment, not sync)
- Index file format (replaced by JSONL)
- Snapshot tracking (eliminated with TDD split)
- The entire `.tasks/` directory structure

#### External Reference Findings

**From GSD (Get Shit Done):**

GSD is entirely file-based with no GitHub integration at all. Their
`.planning/` structure inspired the V2 approach but with different
trade-offs:

| GSD Pattern | V2 Adoption | Notes |
|-------------|-------------|-------|
| File-based persistence in `.planning/` | **Adopted** | V2 uses `.planning/epics/E<N>/` |
| Plans ARE prompts (not docs transformed into prompts) | **Adopted** | PLAN.md is the planner's output, agents read it directly |
| STATE.md for cross-session persistence | **Not adopted** | V2 uses JSONL which is more structured and append-only |
| No GitHub integration | **Partially adopted** | V2 has minimal GitHub interaction (ingest + comment) but does not try full sync |
| Phase → Plan → Task hierarchy | **Adapted** | V2 uses Epic → Story → Agent Invocation |
| 7-dimension plan validation | **Deferred** | Interesting for Research Area 4.3 (planning design) |
| Wave-based parallel execution | **Deferred to V3** | V2 is sequential first |

**Key GSD insight adopted:** "Fresh context windows" — each agent
operates independently, preventing accumulative degradation. This is
already core to V2's architecture (Section 2).

**From taches-cc-resources (create-plans):**

Their planning system uses a four-level hierarchy with aggressive
atomicity (2-3 tasks per plan, context budget awareness).

| taches Pattern | V2 Adoption | Notes |
|----------------|-------------|-------|
| Plans ARE executable prompts | **Adopted** | Aligns with GSD — the plan is what agents read |
| 2-3 tasks per plan maximum | **Adopted as principle** | V2 stories should be small; the planner decides agent count |
| XML task schema with 4 required fields | **Partially adopted** | V2 agent invocations need structured definition but not necessarily XML |
| Checkpoint types (human-verify, decision, human-action) | **Adopted** | V2 validation checkpoints map to these types |
| Deviation handling rules (auto-fix vs escalate) | **Adopted** | Aligns with V2's failure model (minor self-fix, major retry, planning failure → exit) |
| Context budget monitoring (50% threshold) | **Adopted** | V2 uses `--max-turns` and `--max-budget-usd` for budget control |
| SUMMARY.md per plan execution | **Adopted** | V2 should produce a summary after each story |
| `.continue-here.md` handoff | **Not adopted** | V2 uses JSONL for handoff state |

**Key taches insight adopted:** Aggressive task atomicity prevents
context degradation. The planner should produce small, focused stories
rather than large multi-concern ones.

#### Key Findings for V2 Design

1. **GitHub integration should be minimal and unidirectional.** Ingest
   the epic body once, push comments at milestones, let humans close.
   Full bidirectional sync is over-engineering for a single-developer
   workflow with AI agents.

2. **The local plan is the source of truth for execution.** GitHub
   expresses intent, the plan expresses strategy. Don't conflate them.

3. **Stories are internal to the orchestrator.** They don't map to
   GitHub issues. Progress visibility comes from epic comments, not
   from issue status tracking.

4. **Sequential story execution is correct for V2.** Parallel execution
   adds merge conflict complexity that isn't worth solving until
   sequential execution is proven.

5. **One local root (`.planning/epics/E<N>/`) replaces two.** Eliminates
   the split between `.planning/` (planning) and `.tasks/` (execution).
   JSONL logs replace per-task markdown files, snapshots, and error logs.

6. **`GitHub-Epic-Sync.md` should be replaced.** The sync protocol
   it documents was never built and is far more complex than V2 needs.

7. **Both GSD and taches confirm the "plans are prompts" pattern.**
   The planner's output should be directly consumable by agents —
   not an intermediate format that gets transformed.

8. **Comment push-back provides GitHub visibility without coupling.**
   Structured comments at story completion give humans a paper trail
   on the epic issue without requiring the orchestrator to manage
   GitHub state.

### 8.4 Planning Phase Design (Area 4.3) ✅

**Completed.** Studied the current GTS planning pipeline (5 agents,
1 script, SKILL.md, goal-backward reference), the taches-cc-resources
create-plans skill (SKILL.md, plan-phase.md, execute-phase.md,
handoff.md workflows), GSD's planning architecture, and the existing
GTS planning output (GOALS.md, TASKS.md from E86/E95).

#### What the V2 Planner Must Produce

The planner's output must answer four questions for the orchestrator:

1. **What stories make up this epic?** (ordered list with names)
2. **What does each story's agent do?** (scope, files, skills, model)
3. **How do we validate each story?** (type-aware behavioural checks)
4. **Where are the validation checkpoints?** (strategic, not per-task)

This replaces the current pipeline's output chain:
`CONTEXT.md → GOALS.md → TASKS.md → .tasks/T*.md`

#### Design Decision 1: Planning Pipeline Structure

**Recommendation: 3 phases — 1 deterministic, 1 interactive, 1 AI.**

| Phase | Mechanism | Purpose |
|-------|-----------|---------|
| **1. Context Assembly** | Deterministic Python | Read EPIC.md + wiki + codebase structure → assemble context file |
| **2. Scope & Decisions** | Interactive (human-in-loop) | Gray area resolution, scope confirmation, "what does DONE look like?" |
| **3. Plan Generation** | Single AI agent (Opus) | Goal-backward analysis → stories + agent sequences + validation criteria |

This replaces the current 5-agent pipeline with a leaner structure:

| Current | V2 Replacement | Savings |
|---------|----------------|---------|
| `epic-context-loader` (haiku AI) | Python function | 1 AI invocation saved |
| `epic-gray-area-analyst` (haiku AI) | Python keyword lookup | 1 AI invocation saved |
| Interactive Q&A (orchestrator) | Interactive Q&A (unchanged) | — |
| `epic-goal-backward` (sonnet AI) | Combined into Plan Generator (opus) | — |
| `epic-task-breakdown` (sonnet AI) | Combined into Plan Generator (opus) | 1 AI invocation saved |
| `plan-reviewer` (opus AI) | Deterministic validation | 1 AI invocation saved |

**Net result:** 5 AI invocations → 1 AI invocation + 2 deterministic
functions. The single Opus invocation does the heavy reasoning
(goal-backward → stories → agent sequences) in one pass, with richer
context than the fragmented pipeline could provide.

**Why combine goal-backward and task-breakdown?** The current split
forces goal-backward to produce GOALS.md as an intermediate artifact,
which task-breakdown then re-reads and transforms. This loses context
across the handoff. A single agent that reasons from truths through to
stories maintains the full reasoning chain in one context window.

#### Design Decision 2: Context Assembly (Deterministic)

**Recommendation: Python function, not an AI agent.**

The current `epic-context-loader` agent reads files and fills a
template. This is pure I/O — no reasoning required. The V2 context
assembler:

1. Reads `EPIC.md` (ingested from GitHub, per 8.3 Decision 1)
2. Reads relevant wiki sections (architecture, domain model)
3. Reads codebase structure (existing `.planning/codebase/` files)
4. Scans for keywords to determine relevant areas (auth, frontend,
   audio, etc.) — currently done by `epic-gray-area-analyst` via
   keyword lookup table
5. Assembles a single context document with all inputs for the planner

The keyword → area mapping and question bank from
`skills/epic/references/gray-areas.md` and `question-bank.md` are
structured data. They don't need AI to process.

**Output:** A `CONTEXT.md` file containing assembled inputs. This is
an intermediate file for the planner, not a final artifact.

#### Design Decision 3: Plan Output Format (PLAN.md + plan.json)

**Recommendation: Dual-format output. PLAN.md for humans, `plan.json`
for the orchestrator. The planner produces both. The orchestrator
parses only `plan.json` — never PLAN.md.**

Both GSD and taches-cc-resources confirm the "plans are prompts"
pattern: the plan is directly consumable by agents. V2 extends this
with a machine-readable companion file that eliminates the gap between
what the planner writes and what the orchestrator expects.

**Why dual format?** PLAN.md is markdown written by an Opus agent.
Markdown is ambiguous to parse — heading levels, list indentation,
code fence boundaries all create fragile parsing logic. The
orchestrator needs deterministic access to story specs, validation
criteria, and agent configurations. A JSON file with a defined schema
provides this without regex or heuristic parsing.

**The contract:** The planner's prompt includes the `plan.json` JSON
Schema as a hard constraint. The planner writes PLAN.md first (for
human review), then emits `plan.json` conforming to the schema. The
plan validation script (Design Decision 8) validates `plan.json`
against the schema — structural errors are caught before the human
even reviews.

**Files:**
- `.planning/epics/E<number>/PLAN.md` — human-readable, for review
- `.planning/epics/E<number>/plan.json` — machine-readable, for orchestrator

**`plan.json` schema (simplified):**

```json
{
  "schema_v": 1,
  "epic_number": 95,
  "goal": "...",
  "observable_truths": [
    {"id": 1, "statement": "..."}
  ],
  "user_journeys": [
    {
      "journey_id": "J1",
      "persona": "authenticated user",
      "narrative": "User visits the homepage, clicks 'Gear' in the navigation, sees a list of their gear items sorted by name. They click a gear item and see the detail page with model information, NAM file status, and IR assignments. They click 'Edit', change the name, submit, and see the updated name on the detail page. They return to the list and the new name appears in the correct sort position.",
      "truths_covered": [1, 2, 3, 4],
      "entry_point": "/",
      "critical_transitions": [
        {"from": "homepage", "to": "/gear", "mechanism": "nav link click"},
        {"from": "/gear", "to": "/gear/{id}", "mechanism": "list item click"},
        {"from": "/gear/{id}", "to": "/gear/{id}/edit", "mechanism": "edit button"},
        {"from": "/gear/{id}/edit", "to": "/gear/{id}", "mechanism": "form submit"}
      ]
    }
  ],
  "stories": [
    {
      "story_id": "01-architecture",
      "name": "Architecture — Entity, Repo, Service",
      "purpose": "...",
      "agent": {
        "model": "sonnet",
        "skills": ["gts-architecture", "repository-patterns"],
        "tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
        "mcp": [],
        "max_turns": 30,
        "max_budget_usd": 3.00
      },
      "scope": {
        "create": ["libs/core/src/core/domain/entities/shootout.py"],
        "modify": ["apps/webapp/src/webapp/api/router.py"]
      },
      "state_assumption": "cumulative",
      "implementation_notes": ["Follow pattern in gear.py", "..."],
      "truths_addressed": [1, 2]
    }
  ],
  "validation_checkpoints": [
    {
      "after_story": "02-ui-scaffold",
      "check_type": "http+dom",
      "checks": [
        {"criterion": "GET /gear returns 200", "evidence_fields": ["status_code", "url"]},
        {"criterion": "Page contains heading 'Gear Library'", "evidence_fields": ["dom_selector", "element_text"]}
      ]
    }
  ]
}
```

The orchestrator reads `plan.json` via `json.load()` — no markdown
parsing, no regex, no ambiguity. Story IDs in `plan.json` match
directory names in `.planning/epics/E<N>/stories/`. Validation
checkpoint `after_story` references story IDs. Everything is
cross-referenced by stable identifiers.

**PLAN.md remains valuable** — it's what the human reads during the
Decision Gate (step 6 of the planning flow). It contains the same
information as `plan.json` in a readable narrative format. But the
orchestrator never touches it.

**PLAN.md structure** (for human review):

**Structure:**

```markdown
# Plan: {Epic Title}

## Goal

{Outcome-shaped goal statement — from goal-backward analysis}

## Observable Truths

1. {Truth 1 — user perspective, verifiable by a human}
2. {Truth 2}
...

## User Journeys

### Journey 1: {Persona} — {Summary}

{Narrative: a connected, end-to-end walkthrough of what the user does
and what they see. Written in plain English, present tense. Covers the
happy path from entry point through all critical transitions to
completion. Every observable truth referenced in this journey must be
exercised — not just asserted in isolation, but connected into a
coherent flow.}

**Truths covered:** 1, 2, 3, 4
**Entry point:** /
**Critical transitions:**
- Homepage → /gear (nav link click)
- /gear → /gear/{id} (list item click)
- /gear/{id} → /gear/{id}/edit (edit button)
- /gear/{id}/edit → /gear/{id} (form submit)

### Journey 2: {Persona} — {Summary}
...

## Stories

### Story 1: {Name}

**Purpose:** {What this story delivers — 1-2 sentences}

**Agent:**
- model: sonnet
- skills: [gts-architecture, repository-patterns, service-patterns]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- mcp: none
- max_turns: 30
- max_budget_usd: 3.00

**Scope:**
- Create: `path/to/new/file.py`
- Modify: `path/to/existing/file.py`

**Implementation Notes:**
- Follow pattern in `gear_repository.py` for repository
- Register route in `api/router.py`
- Service owns transaction: `async with session.begin():`

**Truths Addressed:** 1, 2

---

### Story 2: {Name}

**Purpose:** {What this story delivers}

**Agent:**
- model: sonnet
- skills: [gts-frontend-dev, htmx, astro-frontend]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- mcp: [chrome-devtools]
- max_turns: 40
- max_budget_usd: 4.00

**Scope:**
- Create: `frontend/astro/src/pages/feature.html.ts`
- Modify: `apps/webapp/src/webapp/api/pages.py`

**Implementation Notes:**
- Extend `layouts/base.html` for new page
- Add `data-testid` attributes for all interactive elements
- Use HTMX for form submission, not full page reload

**Truths Addressed:** 3, 4

---

### Validation Checkpoint: After Scaffolding

**Type:** http+dom
**Checks:**
- GET /feature returns 200
- Page contains heading "Feature Title"
- Navigation includes link to /feature

---

### Story 3: {Name} ...

---

### Validation Checkpoint: After CRUD

**Type:** browser+db
**Checks:**
- Submit form at /feature/create → row in database
- List page shows created item
- Edit form populates with existing data
- Delete removes item from list and database

---

### Story N: Regression Tests

**Purpose:** Capture working behaviour as regression tests

**Agent:**
- model: sonnet
- skills: [gts-testing, playwright]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- mcp: [playwright]
- max_turns: 30
- max_budget_usd: 3.00

**Scope:**
- Create: `tests/e2e/python/tests/test_feature.py`
- Modify: `tests/e2e/python/tests/test_regression.py`

**Implementation Notes:**
- Three-layer E2E: UI action → DOM update → database state
- No mocking — real database, real services
- Use fixtures from conftest.py (db_session, page, guest_page)

**Truths Addressed:** 1-7 (all)

---

### Final Validation: All Truths

**Type:** regression
**Checks:**
- `just test-golden-path` passes
- `just check` passes (lint + types)
- All observable truths verified via E2E tests

## Artifact Summary

| Truth | Key Artifacts | Story |
|-------|---------------|-------|
| Truth 1 | entity, repo, service, API | Story 1 |
| Truth 2 | page template, HTMX fragments | Story 2 |
...
```

#### Design Decision 4: Acceptance Criteria Format

**Recommendation: Behavioural checks with type-aware verification
methods. NOT test assertions.**

The key tension: criteria must be specific enough that a validation
agent can mechanically check them, but not so rigid they become
tests-by-another-name (which was the V1 failure mode).

**The format:** natural-language behaviour statements with an implicit
verification method determined by the check type.

| Check Type | Verification Method | Example Criterion |
|------------|--------------------|--------------------|
| `http` | HTTP GET + status code | "GET /gear returns 200" |
| `http+dom` | HTTP GET + DOM element assertion | "GET /gear contains heading 'Gear Library'" |
| `browser+db` | Playwright interaction + SQL query | "Submit create form → row exists in `gear` table" |
| `api+response` | HTTP request + response shape | "POST /api/v1/gear returns 201 with `id` field" |
| `process` | Process check + log assertion | "Worker process starts and logs 'Ready'" |
| `screenshot` | Visual comparison | "Page matches design intent (no broken layout)" |
| `regression` | `just test-golden-path` | "All golden path tests pass" |
| `quality` | `just check` | "Lint, types, and import rules pass" |

**What this avoids:**
- "Tests pass" (vacuous — tests can pass without the product working)
- "SyncService.sync() is called" (implies mocking)
- Exact assertion syntax (too rigid, becomes a test specification)
- xfail markers (the V1 escape hatch)

**What this enables:**
- The orchestrator can dispatch a validation agent with the criteria
  and a check type. The agent knows HOW to check based on the type.
- Structured output (`--json-schema`) returns pass/fail per criterion.
- The criteria are human-readable — a person can manually verify them.

**Evidence format requirements per check type:**

Validation results are only trustworthy if they include concrete
evidence — not just "pass" or "fail" but provable artifacts. The
`--json-schema` for validation agents requires type-specific evidence
fields. A validation that returns `"evidence": "looks good"` is a
false green.

| Check Type | Required Evidence Fields | Example |
|------------|------------------------|---------|
| `http` | `status_code`, `url`, `response_excerpt` | `{"status_code": 200, "url": "/gear", "response_excerpt": "<!DOCTYPE html>..."}` |
| `http+dom` | `status_code`, `url`, `dom_selector`, `element_text` | `{"dom_selector": "h1", "element_text": "Gear Library"}` |
| `browser+db` | `action_performed`, `sql_query`, `row_count`, `sample_row` | `{"sql_query": "SELECT id FROM gear WHERE...", "row_count": 1}` |
| `api+response` | `status_code`, `url`, `method`, `response_body_excerpt` | `{"status_code": 201, "method": "POST", "response_body_excerpt": "{\"id\": \"...\"}"}` |
| `process` | `process_name`, `pid_or_status`, `log_excerpt` | `{"process_name": "worker", "pid_or_status": "running", "log_excerpt": "Ready"}` |
| `screenshot` | `screenshot_path`, `observations` | `{"screenshot_path": ".planning/.../screenshot-01.png", "observations": "..."}` |
| `regression` | `test_command`, `exit_code`, `test_count`, `failure_count` | `{"test_command": "just test-golden-path", "exit_code": 0, "test_count": 24}` |
| `quality` | `commands_run`, `exit_code`, `error_count` | `{"commands_run": ["just check"], "exit_code": 0, "error_count": 0}` |

The validation JSON schema (`--json-schema`) includes these fields as
`required` properties per check type. The orchestrator validates that
evidence fields are populated — empty or generic evidence is treated
as a validation failure, not a pass.

#### Design Decision 5: Validation Checkpoint Placement

**Recommendation: The planner places checkpoints strategically based
on story types, not mechanically after every story.**

| Pattern | When to Checkpoint | Why |
|---------|-------------------|-----|
| After scaffolding | Pages exist, routes respond, navigation works | Catch wiring failures before building on top of broken scaffolding |
| After CRUD | Create/read/update/delete work end-to-end | Catch data flow failures before building complex features |
| After complex features | Feature-specific behaviour verified | Catch integration failures |
| Before regression tests | Full product works | Don't waste tokens writing tests for broken product |
| After regression tests | Tests pass, quality gates pass | Final gate before human review |

**Not every story needs a checkpoint.** Backend-only stories
(entity + repository + service) might not need validation until the
UI story that exposes them. The planner decides based on task type
and risk.

**Validation agent configuration:**

| Checkpoint Type | Model | MCP Required | Tools | Pre-conditions |
|-----------------|-------|-------------|-------|----------------|
| `http` | haiku | none | Bash (curl), Read | webapp + nginx running |
| `http+dom` | haiku | chrome-devtools | Bash, Read + MCP | webapp + nginx running, Chrome DevTools MCP available |
| `browser+db` | sonnet | chrome-devtools | Bash, Read + MCP | webapp + nginx + db running, Chrome DevTools MCP available |
| `api+response` | haiku | none | Bash, Read | webapp running |
| `process` | haiku | none | Bash, Read | target service running (e.g., worker, scheduler) |
| `screenshot` | sonnet | chrome-devtools | Read + MCP | webapp + nginx running, Chrome DevTools MCP available |
| `regression` | haiku | none | Bash | all services running, E2E deps installed on host |
| `quality` | haiku | none | Bash | webapp container running (for Docker exec) |

Validation agents are read-only — they receive `--tools "Bash,Read,Glob,Grep"`
with no Edit/Write. They check, they don't fix.

**Note on HTTP checks:** Validation agents use programmatic HTTP requests
(via Bash) as structured evidence-gathering with required evidence fields
(status code, response excerpt, DOM content). This is distinct from the
testing-policy curl ban, which prohibits using curl as a substitute for
actual testing. Validation agents collect evidence; they don't claim
"the feature works because curl returned 200."

#### Design Decision 6: Agent Sequence Structure

**Recommendation: Each story definition contains the full agent
dispatch specification. The orchestrator reads it mechanically.**

The agent specification in each story block contains everything the
orchestrator needs to dispatch:

```python
# Orchestrator reads from plan.json:
story = {
    "name": "Architecture — Entity, Repo, Service",
    "model": "sonnet",
    "skills": ["gts-architecture", "repository-patterns"],
    "tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
    "mcp": [],
    "max_turns": 30,
    "max_budget_usd": 3.00,
    "scope": {"create": [...], "modify": [...]},
    "state_assumption": "cumulative",
    "implementation_notes": "...",
    "truths_addressed": [1, 2],
}
```

The orchestrator constructs the agent prompt from:
1. **Plan context** — the story block from PLAN.md
2. **Skills** — loaded from `.claude/skills/` based on the `skills` list
3. **Failure feedback** — if retrying, the JSONL failure entry
4. **Verification criteria** — from the next validation checkpoint

This replaces the current per-task markdown files in `.tasks/` with
inline story definitions in a single plan file.

#### Design Decision 7: Story Sizing and Atomicity

**Recommendation: 2-5 stories per epic. Each story is a coherent
chunk that an agent can complete in one invocation.**

Both taches-cc-resources (2-3 tasks per plan, ~50% context budget)
and GSD (2-3 atomic tasks with embedded verification) enforce aggressive
atomicity. The current GTS pipeline produces 15-30 tasks per epic,
which is far too granular.

**V2 story sizing:**

| Factor | Guidance |
|--------|----------|
| **Context budget** | Story should use <50% of agent context window |
| **File count** | 3-8 files created/modified per story |
| **Scope boundary** | Full vertical slice OR one layer across multiple entities |
| **Validation boundary** | Story should produce something checkable |
| **Independence** | Each story builds on the previous but is self-contained |
| **State assumption** | Planner declares whether the story expects cumulative or clean state |

**State assumption:** Each story in `plan.json` includes a `state_assumption`
field with one of two values:

| Value | Meaning | Orchestrator action |
|-------|---------|---------------------|
| `cumulative` | Story expects data and state from all previous stories to be present. This is the default and the norm for GTS epics. | No action — agent runs against current database and filesystem state. |
| `clean` | Story expects a reset database (empty tables, seed data only). Rare — used when validation criteria assert counts or absence of data. | Orchestrator runs `just db-reset` (or equivalent seed script) before dispatching the agent. |

If omitted, `state_assumption` defaults to `cumulative`. The planner should
explicitly set `clean` only when validation criteria depend on known data
state (e.g., "list page shows exactly 0 items before create"). Most GTS
stories are cumulative — each builds on what the previous story created.

**Example story breakdown for a typical GTS epic:**

| Story | Scope | Model | Estimated Budget |
|-------|-------|-------|-----------------|
| 1. Architecture | Entity, ORM, repo, service, migration | Sonnet | $3 |
| 2. API + Schemas | Routes, Pydantic schemas, route registration | Sonnet | $2 |
| 3. UI Scaffolding | Page templates, fragments, navigation | Sonnet | $3 |
| 4. CRUD Features | Form handling, HTMX interactions, DB writes | Sonnet | $4 |
| 5. Regression Tests | E2E tests, regression test updates | Sonnet | $3 |

This is 5 stories vs the current pipeline's ~30 tasks. Each story
does meaningful work. Validation checkpoints go after stories 2, 4,
and 5.

#### Design Decision 8: Two-Phase Plan Verification

**Recommendation: Deterministic schema validation (Phase A), then
AI plan verifier agent (Phase B). Both must pass before the human
Decision Gate.**

Planning is the highest-leverage phase of the entire workflow. A few
minutes of rigorous plan verification prevents hours of wasted agent
tokens on stories built from a flawed plan. The E95 failure was
fundamentally a planning failure — the plan never specified that the
signal chain builder should actually work in a browser. No amount of
execution rigour fixes a plan that doesn't express the right intent.

**Phase A: Deterministic Schema Validation (Python script, $0)**

Validates `plan.json` against the JSON Schema. Mechanical, instant,
catches structural errors:

1. **Schema conformance** — `plan.json` validates against the
   published JSON Schema (all required fields present, types correct)
2. **Referential integrity** — every `truths_addressed` ID exists in
   `observable_truths`; every checkpoint `after_story` references a
   valid `story_id`; every journey `truths_covered` ID exists
3. **Truth coverage** — every observable truth is addressed by at
   least one story AND covered by at least one user journey
4. **Journey coverage** — every truth appears in at least one user
   journey's `truths_covered` (no orphan truths that are asserted
   but never exercised in a connected flow)
5. **Scope coherence** — files in `modify` scope exist on disk;
   files in `create` scope have existing parent directories
6. **Dependency ordering** — stories that reference files created by
   earlier stories appear after those stories
7. **Budget sanity** — total estimated budget within epic budget

If Phase A fails, the planner is re-invoked with the validation
errors. No AI tokens are spent on Phase B until the structure is sound.

**Phase B: AI Plan Verifier Agent (Sonnet, ~$1-2)**

A dedicated verification agent that reads the plan holistically and
checks what deterministic validation cannot: narrative completeness,
intent alignment, and gap detection. This is NOT a subjective quality
review ("is this plan good?"). It is a structured verification with
specific pass/fail criteria.

The verifier agent receives:
- `plan.json` (the full plan)
- `EPIC.md` (the original intent from GitHub)
- `CONTEXT.md` (the assembled codebase context)
- The locked scope decisions from Phase 2

The verifier checks:

1. **Journey completeness** — do the user journeys cover the full
   scope of the epic? Walk through each journey narrative and verify
   every step has a corresponding story that builds it and a
   validation checkpoint that verifies it. Flag any step in a journey
   that no story addresses.

2. **Transition coverage** — are all `critical_transitions` in the
   journeys covered by validation checkpoints? A transition from
   `/gear` to `/gear/{id}` via "list item click" must have a
   checkpoint that verifies the link exists AND the target page
   renders. Flag transitions that fall between checkpoints.

3. **Intent alignment** — does the plan deliver what the epic asks
   for? Compare the epic's scope sections against the plan's stories.
   Flag epic requirements that have no corresponding story. Flag
   stories that address requirements not in the epic (scope creep).

4. **Gap detection** — are there logical gaps between stories? If
   Story 1 creates an entity and Story 3 builds a UI that displays
   it, but no story creates the API endpoint that connects them,
   flag the gap. Walk the dependency chain: entity → repo → service
   → API → template → page. Every link must exist in some story.

5. **Validation sufficiency** — are the validation checkpoints
   strong enough to catch real failures? For each checkpoint, ask:
   "If this check passes, does it prove the feature works, or could
   it false-green?" Flag checks that verify existence but not
   function (e.g., "page returns 200" without checking content).

The verifier returns structured output (`--json-schema`):

```json
{
  "status": "pass|fail",
  "journey_completeness": {
    "status": "pass|fail",
    "gaps": [{"journey_id": "J1", "step": "...", "missing": "..."}]
  },
  "transition_coverage": {
    "status": "pass|fail",
    "uncovered": [{"journey_id": "J1", "from": "...", "to": "...", "mechanism": "..."}]
  },
  "intent_alignment": {
    "status": "pass|fail",
    "unaddressed_requirements": ["..."],
    "scope_creep": ["..."]
  },
  "gap_detection": {
    "status": "pass|fail",
    "gaps": [{"between": ["story_id_1", "story_id_2"], "missing": "..."}]
  },
  "validation_sufficiency": {
    "status": "pass|fail",
    "weak_checks": [{"checkpoint": "...", "criterion": "...", "risk": "..."}]
  }
}
```

If Phase B fails, the verifier's structured output is fed back to
the planner for revision. The planner receives the specific gaps,
uncovered transitions, and weak checks — not a vague "try harder."
One revision cycle (planner → verifier → planner) is budgeted.
If the second attempt also fails Phase B, exit to human.

**Why an AI agent, not just the human?**

The human reviews the plan at the Decision Gate (step 6). But humans
skim. A plan with 5 stories, 15 truths, 3 journeys, and 8 validation
checkpoints has dozens of cross-references to verify. The verifier
agent systematically walks every cross-reference and flags gaps that
a human would miss on a quick read. The human then reviews the
verifier's structured report alongside the plan — a much more
efficient use of human attention.

**Why Sonnet, not Opus?**

The verifier doesn't need Opus-level reasoning. It's performing
structured comparison (plan vs epic, journeys vs stories, transitions
vs checkpoints). Sonnet is sufficient and ~5x cheaper. The planner
(which does the creative reasoning) remains Opus.

**Cost impact:** ~$1-2 per planning run for the verifier agent. Total
planning cost rises from ~$3-5 (1 Opus invocation) to ~$4-7 (1 Opus +
1 Sonnet). This is negligible against the cost of executing a flawed
plan (5 stories × $2-4 each = $10-20 wasted on a bad plan).

**What the verifier does NOT check:**
- Whether implementation notes are correct (runtime discovery)
- Whether file paths in scope are the best choice (planner's domain)
- Whether the story sizing is optimal (learned from experience)
- Subjective plan quality (human's job at Decision Gate)

#### Evaluation of External References

**From taches-cc-resources (create-plans):**

| Pattern | Adopted | Notes |
|---------|---------|-------|
| Plans ARE executable prompts | **Yes** | Core V2 principle — PLAN.md is directly consumed |
| 2-3 tasks per plan, ~50% context | **Yes** | V2 targets 2-5 stories per epic |
| XML task schema (name/files/action/verify/done) | **Adapted** | V2 uses markdown story blocks with similar fields |
| Task types: auto, checkpoint:human-verify, checkpoint:decision | **Adopted** | V2 validation checkpoints map directly |
| Deviation handling (auto-fix / ask-first / log-defer) | **Adopted** | Aligns with V2 failure model |
| Split if >3 tasks or >5 files per task | **Adopted** | Sizing guidance for story boundaries |
| Anti-patterns (story points, Jira language, nested sub-tasks) | **Adopted** | Stories are agent instructions, not PM artifacts |

**From GSD:**

| Pattern | Adopted | Notes |
|---------|---------|-------|
| XML task structure (name/files/action/verify/done) | **Adapted** | Same fields, markdown format instead of XML |
| Thin orchestrator + specialized agents | **Adopted** | Core V2 architecture |
| Fresh context windows per executor | **Adopted** | Already in V2 design |
| 4 parallel researchers | **Deferred** | V2 planning is sequential (single Opus agent) |
| STATE.md for cross-session persistence | **Not adopted** | V2 uses JSONL (more structured, append-only) |
| 7-dimension plan validation | **Partially adopted** | V2 validates structure and coverage, not subjective quality |

**From current GTS pipeline:**

| Component | V2 Adoption | Notes |
|-----------|-------------|-------|
| Goal-backward methodology | **Core** | Observable truths → artifacts → stories is the planning spine |
| Artifact mapping (entity/repo/service/API/template) | **Kept** | GTS-specific, injected via skills |
| Three-layer E2E validation (UI → DOM → DB) | **Kept** | Validation criteria format |
| Breaking change companion tasks | **Kept as principle** | Planner splits stories at breaking change boundaries |
| Mock policy reminder | **Kept** | Injected into agent prompts via skills |
| Task sizing heuristics (max 3 create, max 5 total) | **Adapted** | Story sizing is coarser — 3-8 files per story |
| Execution waves / parallelism | **Deferred** | V2 stories are sequential |
| CONTEXT.md + GOALS.md + TASKS.md pipeline | **Replaced** | Dual-format PLAN.md + plan.json with context assembled by script |

#### The Complete V2 Planning Flow

```
1. `just epic-ingest <N>`        → .planning/epics/E<N>/EPIC.md
                                    (deterministic: gh issue view)

2. Context Assembly (Python)     → .planning/epics/E<N>/CONTEXT.md
                                    (deterministic: read files, keyword scan)

3. Interactive Scope Discussion  → locked decisions appended to CONTEXT.md
                                    (human-in-loop: gray areas, "what is DONE?")

4. Plan Generation (Opus agent)  → .planning/epics/E<N>/PLAN.md
                                    .planning/epics/E<N>/plan.json
                                    (AI: goal-backward → truths → journeys
                                     → stories → validation checkpoints)
                                    (planner prompt includes plan.json schema)

5a. Schema Validation (Python)   → validate plan.json against JSON Schema
                                    (deterministic: structure, refs, coverage)
                                    If fail → re-invoke planner with errors

5b. Plan Verification (Sonnet)   → verify narrative completeness, intent
                                    alignment, transition coverage, gap
                                    detection, validation sufficiency
                                    (AI: structured comparison, pass/fail)
                                    If fail → re-invoke planner with gaps
                                    Max 1 revision cycle, then exit to human

6. Human Decision Gate           → approve / revise / reject
                                    (interactive: human reviews PLAN.md
                                     + verifier report)

7. Commit + Push                 → planning artifacts on remote
                                    (deterministic: git commit + push)
```

Steps 1, 2, 5a, and 7 are deterministic (no AI tokens). Step 3 is
interactive (human provides answers, orchestrator records them).
Step 4 is the primary AI invocation (Opus). Step 5b is the verifier
(Sonnet). Step 6 is human review with the verifier's structured report.

**Decision Gate state transitions (step 6):**

| Decision | Orchestrator action | Resume semantics |
|----------|-------------------|------------------|
| **Approve** | Proceed to step 7 (commit + push), then start execution | Normal flow — execution begins |
| **Revise** | Human edits `plan.json` + `PLAN.md` directly, then re-runs step 5a (schema validation) and 5b (verifier). No planner re-invocation — the human IS the planner for revisions. | Orchestrator re-enters at step 5a with modified plan files |
| **Reject** | Orchestrator logs `exit_to_human` event and exits. Planning artifacts are NOT committed. Human may restart from step 1 (re-ingest), step 3 (re-scope), or step 4 (re-plan) depending on the reason for rejection. | Fresh planning run — no partial state carried forward |

**After a crash during planning:** The orchestrator checks which steps
have completed (EPIC.md exists → step 1 done, CONTEXT.md exists → step 2
done, plan.json exists → step 4 done). It resumes from the next
incomplete step. Planning steps are idempotent — re-running a completed
step overwrites the output harmlessly.

**Total AI cost per planning run:** ~1 Opus + ~1 Sonnet = $4-7,
down from ~5 invocations ($15-25) in the current pipeline. The
verifier adds ~$1-2 but prevents $10-20+ of wasted execution on
flawed plans.

#### Key Findings for V2 Design

1. **The planner produces PLAN.md (human-readable) + plan.json
   (machine-readable).** No intermediate GOALS.md → TASKS.md → .tasks/
   pipeline. The orchestrator parses `plan.json` (validated against a
   JSON Schema) to get story definitions, agent specs, and validation
   criteria. PLAN.md is for human review during the Decision Gate.

2. **Goal-backward methodology is the strongest part of the current
   pipeline and survives intact.** Observable truths → required
   artifacts → stories is the planning spine. The output format
   changes, not the reasoning approach.

3. **3 of 5 current planning AI invocations are eliminated, 1 is
   replaced by the plan verifier.** Context loading and gray-area
   detection are deterministic. The plan-reviewer is replaced by a
   two-phase verification: deterministic schema validation + AI
   verifier agent. Net: 5 AI calls → 2 AI calls (Opus planner +
   Sonnet verifier).

4. **User journeys are an explicit plan output, not guidance.**
   The planner produces connected, end-to-end user narratives that
   link observable truths into coherent flows. Isolated assertions
   ("GET /gear returns 200") are necessary but not sufficient —
   the journey ("user clicks Gear in nav, sees list, clicks item,
   sees detail") catches the gaps between assertions. Every truth
   must appear in at least one journey.

5. **Behavioural acceptance criteria use type-aware verification.**
   The check type (http, browser+db, regression, etc.) determines
   HOW to validate. The criterion describes WHAT to check. The
   orchestrator dispatches a validation agent with the right tools
   for the check type.

6. **Stories replace tasks as the unit of work.** 2-5 stories per
   epic vs 15-30 tasks. Each story is a coherent chunk with its own
   agent spec, scope, and implementation notes. Validation checkpoints
   go between stories, not after every task.

7. **Validation checkpoint placement is strategic, not mechanical.**
   The planner decides where to validate based on story type and risk.
   Not every story gets a checkpoint — backend-only stories may
   be validated only when the UI story exposes them.

8. **Plan verification is two-phase: deterministic + AI.** Phase A
   (Python script) validates schema, referential integrity, and
   coverage. Phase B (Sonnet verifier agent) checks narrative
   completeness, intent alignment, transition coverage, and gap
   detection. Both must pass before the human Decision Gate. The
   ~$1-2 verifier cost prevents $10-20+ of wasted execution.

### 8.5 Prompt Engineering & Meta-Prompting (Area 4.2) ✅

**Completed.** Studied taches-cc-resources/create-meta-prompts (SKILL.md,
do-patterns.md, plan-patterns.md, research-patterns.md), Anthropic's
official Claude Code documentation (best practices, CLI reference,
sub-agents), and the existing GTS prompt construction system in
`run_epic.py` and `.claude/agents/`.

#### The Core Question: Meta-Prompting vs Templates

Research Area 4.2 poses one fundamental question: should the orchestrator
use **an AI agent to build prompts** for other AI agents (meta-prompting),
or should it use **deterministic templates** filled by the script?

**Answer: Deterministic templates.** The meta-prompting approach is
rejected for V2.

**Evidence from taches-cc-resources:**

The taches `create-meta-prompts` skill dispatches an AI agent to classify
task purpose (Do/Plan/Research/Refine), scan for dependencies, generate
structured prompts with XML metadata, and save to `.prompts/`. It adds
a full AI invocation per prompt constructed — the prompter-agent — before
the actual work begins.

This is appropriate for their use case (ad-hoc human-initiated workflows
where the task type is unknown until runtime). It is inappropriate for
V2 because:

1. **V2 already knows the task type.** The planner produces PLAN.md with
   explicit story blocks containing model, skills, tools, MCP, scope,
   and implementation notes. There's nothing for a prompter-agent to
   discover — the orchestrator has all the information.

2. **Extra AI invocation per story.** With 2-5 stories per epic, a
   prompter-agent adds 2-5 Opus/Sonnet invocations ($6-25) before
   any work begins. The same prompt can be assembled deterministically
   for $0.

3. **Non-deterministic prompt quality.** A meta-prompter can produce
   inconsistent prompts across runs. Templates produce identical prompts
   given identical inputs, which is essential for debugging agent
   failures — if the agent fails, it's the code, not the prompt.

4. **The planner IS the meta-prompter.** In V2, the single Opus
   planning agent already performs the reasoning that a meta-prompter
   would do: understanding scope, determining required context, writing
   implementation notes. The plan output IS the meta-prompt output.
   Adding another layer of AI on top would be redundant.

**What V2 adopts from taches (principle, not mechanism):**

| taches Pattern | V2 Adoption | Mechanism |
|----------------|-------------|-----------|
| Purpose-specific prompt structure (Do/Plan/Research) | **Adopted** | Template variants per agent role |
| Dependency chain detection (research → plan → do) | **Not needed** | V2 stories are explicitly ordered in PLAN.md |
| XML metadata tags (confidence, dependencies) | **Partially adopted** | Structured output via `--json-schema` for validation agents |
| SUMMARY.md per execution | **Adopted** | JSONL log per story (structured, not prose) |
| Verification criteria in prompt | **Adopted** | Verification section in every agent prompt |
| Chain artifacts via @ references | **Adapted** | File paths in prompt, not @ references |

#### Design Decision 1: Template Architecture

**Recommendation: Python string templates with section assembly. Not
Jinja2, not Mustache — just f-strings with a section builder.**

The V2 prompt is assembled from discrete sections. Each section is a
Python function that returns a string (or empty string if not applicable).
The orchestrator calls each section function and concatenates results.

**Why not Jinja2/Mustache?**

- Adds a dependency for trivial string assembly
- Conditional sections are clearer as Python `if/else` than template
  syntax (`{% if retry_context %}`)
- Template files would need to be loaded, parsed, and rendered — the
  functions are already in memory
- The "template" IS Python code, and the orchestrator IS a Python script

**Why not static markdown files?**

- Agent prompts need dynamic content (file paths, failure feedback,
  plan excerpts, skill content)
- A static file with `{placeholder}` markers is just a worse f-string
- The boundary between "template" and "code" is arbitrary when the
  assembler IS the orchestrator

**The architecture:**

```python
def build_agent_prompt(story: StorySpec, context: PromptContext) -> str:
    """Assemble the complete prompt for an agent invocation."""
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

Each section function is 5-20 lines. The total assembler is ~150 lines.
This is intentionally simple — the complexity lives in the PLAN.md
(written by Opus) not in the template system.

#### Design Decision 2: Prompt Sections

**Recommendation: 7 standard sections, all optional except Role and
Plan Context.**

Every agent prompt is assembled from these sections:

| # | Section | Required | Content | Source |
|---|---------|----------|---------|--------|
| 1 | **Role** | Yes | What the agent is and what it does | Template per agent role |
| 2 | **Plan Context** | Yes | Story purpose, truths addressed, overall goal | Extracted from PLAN.md |
| 3 | **Scope** | Yes (impl) | Files to create/modify, with patterns to follow | Extracted from PLAN.md |
| 4 | **Implementation Notes** | No | Domain-specific guidance, patterns, gotchas | Extracted from PLAN.md |
| 5 | **Verification** | No | How the agent checks its own work | From next validation checkpoint |
| 6 | **Failure Feedback** | No | What went wrong last time (retry only) | From JSONL failure entry |
| 7 | **Constraints** | Yes | What NOT to do, hard boundaries | Template per agent role |

**Section details:**

**1. Role (template, static per role):**

The role section is a short, focused instruction block. NOT the 230-line
agent definition files in the current system. Those files contain too
much — architecture patterns, banned patterns, systematic strategies —
that belong in skills, not in every prompt.

```markdown
# Role: Implementation Agent

You are implementing a story in the GTS codebase. You receive a clear
scope (files to create/modify), implementation notes, and verification
criteria. Your job is to write working code that satisfies the criteria.

You do NOT explore the codebase. You do NOT plan. You do NOT write
tests. You implement the scope, verify your work, and commit.
```

The role section is ~50-100 words. It sets the frame. Domain knowledge
comes from skills (injected via `--append-system-prompt-file`).

**2. Plan Context (dynamic, from PLAN.md):**

```markdown
# Context

## Goal
{epic goal from PLAN.md}

## Story: {story name}
**Purpose:** {purpose from PLAN.md}
**Truths Addressed:** {list of observable truths this story delivers}

## Observable Truths (for reference)
{numbered list of all truths — agent needs to understand what "done"
looks like even for truths it's not directly implementing}
```

**3. Scope (dynamic, from PLAN.md):**

```markdown
# Scope

## Create
- `libs/core/src/core/domain/entities/shootout.py` — follow pattern in `gear.py`
- `apps/webapp/src/webapp/adapters/persistence/models/shootout.py`
- `apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py`

## Modify
- `apps/webapp/src/webapp/api/router.py` — register new routes
- `apps/webapp/src/webapp/services/__init__.py` — export new service
```

The scope is the most important section. It tells the agent exactly
which files to touch. "Follow pattern in X" is the primary mechanism
for consistency — the agent reads the exemplar file and follows its
structure.

**4. Implementation Notes (dynamic, from PLAN.md):**

```markdown
# Implementation Notes

- Service owns the transaction: `async with session.begin():`
- Repository uses `joinedload` for all relationships, `lazy="raise"` on models
- Register routes in `api/router.py` under `/api/v1/shootouts`
- Pydantic schemas in `schemas/shootout.py` with reasonable field limits
```

These are the planner's domain-specific hints. They prevent common
mistakes without bloating the prompt with entire skill files.

**5. Verification (dynamic, from next checkpoint):**

```markdown
# Verification

After completing your work, verify:
- `just check-types` passes with no errors in new files
- New ORM model can be imported: `from webapp.adapters.persistence.models.shootout import Shootout`
- Repository query returns results with relationships loaded
```

From Anthropic's official guidance: "Give Claude a way to verify its
work. This is the single highest-leverage thing you can do." The
verification criteria come from the validation checkpoint that follows
this story in the plan.

**6. Failure Feedback (dynamic, retry only):**

```markdown
# Previous Attempt Failed

## Error
TypeError: ShootoutRepository.get_by_id() got an unexpected keyword argument 'user_id'

## Files Modified
- libs/core/src/core/domain/entities/shootout.py (created)
- apps/webapp/src/webapp/adapters/persistence/models/shootout.py (created)
- apps/webapp/src/webapp/adapters/persistence/repositories/shootout_repository.py (created)

## JSONL Entry
{"event":"agent_failed","story_id":"01-architecture","attempt":1,"error":"TypeError","turns":24}

## What to Do
Fix the error. The files listed above already exist from the previous
attempt. Read them, understand the error, and correct it.
```

The failure section replaces the current system's raw pytest output
dump (2000-3000 chars of unprocessed text). V2 extracts the key error,
lists modified files, and provides the structured JSONL entry.

**7. Constraints (template, static per role):**

```markdown
# Constraints

- Do NOT create test files. Tests are a separate story.
- Do NOT modify files outside your scope unless fixing an import.
- Do NOT run `just check` or `just test` — the orchestrator handles validation.
- Do NOT explore the codebase beyond reading exemplar files listed in scope.
- Commit your work when done. The pre-commit hooks handle formatting.
```

#### Design Decision 3: Skill Injection Strategy

**Recommendation: Use `--append-system-prompt-file` with assembled
skill content. The orchestrator writes a temp file and passes it.**

**The mechanism (from Anthropic docs):**

```bash
claude -p - \
  --append-system-prompt-file /tmp/gts-agent-skills-xyz.md \
  --model sonnet \
  ...
```

`--append-system-prompt-file` appends content to Claude Code's default
system prompt. This is better than `--system-prompt` (which replaces
the entire default prompt, losing Claude Code's built-in capabilities)
and better than `skills` in the `--agents` JSON (which preloads full
skill content but requires the more complex agents dispatch path).

**How the orchestrator assembles skill content:**

```python
def write_skill_file(story: StorySpec, tmp_dir: Path) -> Path:
    """Assemble skill content into a temp file for injection."""
    skills_content = []
    for skill_name in story.skills:
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_path.exists():
            content = skill_path.read_text()
            # Strip YAML frontmatter (not needed at runtime)
            if content.startswith("---"):
                _, _, content = content.partition("---")[2].partition("---")
            skills_content.append(content.strip())

    path = tmp_dir / f"skills-{story.name}.md"
    path.write_text("\n\n---\n\n".join(skills_content))
    return path
```

**Skill mapping per agent role:**

The plan specifies skills per story (e.g., `skills: [gts-architecture,
repository-patterns, service-patterns]`). The orchestrator doesn't guess
— the planner decided which skills are relevant during planning.

| Story Type | Typical Skills |
|------------|---------------|
| Architecture (entity, repo, service) | `gts-architecture`, `repository-patterns`, `service-patterns` |
| API + Schemas (routes, Pydantic) | `gts-backend-dev`, `web-handlers`, `error-handling` |
| UI Scaffolding (pages, templates) | `gts-frontend-dev`, `htmx`, `astro-frontend` |
| CRUD Features (forms, interactions) | `gts-frontend-dev`, `htmx`, `gts-backend-dev` |
| Regression Tests (E2E, Playwright) | `gts-testing`, `playwright` |
| Validation (browser checks) | `chrome-devtools`, `playwright` |

**What does NOT go into skill injection:**

- The role section (already in the prompt)
- The plan context (already in the prompt)
- CLAUDE.md rules (loaded automatically by Claude Code)
- Banned patterns (moved into the constraints section or skills)

**Alternative considered: `skills` frontmatter in `--agents` JSON.**

The `--agents` flag supports a `skills` array that preloads full skill
content into the subagent's context at startup:

```json
{
  "impl-agent": {
    "description": "Implementation agent",
    "prompt": "...",
    "skills": ["gts-architecture", "repository-patterns"],
    "tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
    "model": "sonnet"
  }
}
```

This is functionally equivalent to `--append-system-prompt-file` but
uses the agents dispatch path. **V2 should support both** — the
orchestrator can use `--agents` JSON for dispatch (which handles model,
tools, skills, MCP in one declaration) rather than assembling CLI flags
manually. This is cleaner than the current `build_claude_args()` which
constructs a long argument list.

**Recommendation update:** Use `--agents` JSON for dispatch. The
`skills` field handles skill injection natively. The prompt goes in the
`prompt` field. The temp file approach (`--append-system-prompt-file`)
is the fallback for environments where `--agents` isn't available.

#### Design Decision 4: Prompt Size Budget

**Recommendation: Keep agent prompts under 2,000 tokens. Skill content
is separate (system prompt injection, not prompt body).**

**The budget breakdown:**

| Component | Estimated Tokens | Notes |
|-----------|-----------------|-------|
| Role section | 100-200 | Short, static |
| Plan context | 200-400 | Goal + story purpose + truths |
| Scope | 100-300 | File paths with patterns |
| Implementation notes | 100-300 | Domain-specific hints |
| Verification | 50-150 | Criteria from checkpoint |
| Failure feedback | 0-400 | Only on retry |
| Constraints | 50-100 | Short, static |
| **Total prompt** | **600-1,850** | Under 2K target |

Skill content (injected via system prompt) is separate and doesn't
count against the prompt budget. Skills are typically 1,000-3,000
tokens each, with 2-4 skills per agent invocation = 2,000-12,000
tokens in the system prompt.

**Why 2,000 tokens?** This leaves maximum context for the agent's
actual work (reading files, making edits, running commands). The prompt
should be dense with information, not padded with explanation. Every
token in the prompt is a token not available for the agent's work.

**Comparison with current system:**

The current GTS agent definitions are 230-276 lines each (~3,000-4,000
tokens) of static instruction body, PLUS dynamic task context. Total
prompt tokens are 4,000-6,000. V2 cuts this by 60-70% by:

1. Moving domain patterns to skills (loaded separately)
2. Moving banned patterns to skills or constraints (shorter list)
3. Removing systematic strategy instructions (agent decides its own
   approach within scope constraints)
4. Removing TDD-specific sections (no red/green/refactor phases)

#### Design Decision 5: Validation Agent Prompts

**Recommendation: Validation agents get a minimal prompt + structured
output schema. No skills, no implementation notes.**

Validation agents are fundamentally different from implementation
agents. They check, they don't build. Their prompts should be:

```markdown
# Role: Validation Agent

You are checking whether a set of criteria pass or fail. For each
criterion, perform the check and report the result. Do not fix
anything — only report.

# Criteria

1. GET /gear returns HTTP 200
2. Response contains heading "Gear Library"
3. Navigation bar includes link to /gear

# Check Type: http+dom

Use Chrome DevTools MCP to load the page and inspect the DOM.
Report each criterion as pass or fail with evidence.
```

The validation prompt is 100-200 tokens. Combined with `--json-schema`:

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
          "evidence": {"type": "string"}
        },
        "required": ["criterion", "status", "evidence"]
      }
    }
  },
  "required": ["status", "results"]
}
```

The orchestrator parses the structured output mechanically. No regex,
no prose interpretation. This is the most important application of
structured output in V2 — validation results determine whether the
orchestrator proceeds, retries, or exits to human.

#### Design Decision 6: Prompt Logging

**Recommendation: Log every prompt to the story JSONL. The prompt is
the primary debugging artifact.**

When an agent fails, the first question is: "What prompt did it
receive?" The current system doesn't log prompts — they're constructed
in memory and passed via stdin. V2 logs them:

```jsonl
{"event":"agent_dispatched","story_id":"01-architecture","attempt":1,"ts":"...","prompt_tokens":1420,"skill_tokens":4200,"model":"sonnet","prompt_hash":"abc123"}
{"event":"agent_complete","story_id":"01-architecture","attempt":1,"ts":"...","result":"success","turns":18,"cost_usd":1.80}
```

The full prompt text is stored alongside the JSONL log (too large for
inline JSON):

```
.planning/epics/E95/stories/01-architecture/
├── story.jsonl           # Structured event log
├── prompt-attempt-1.md   # Full prompt text (first attempt)
└── prompt-attempt-2.md   # Full prompt text (retry, if any)
```

**Why log the prompt?**

1. **Debugging:** When an agent fails, compare the prompt to the error.
   Was the scope wrong? Were implementation notes missing?
2. **Improvement:** After an epic, review prompt patterns that led to
   failures. Improve the plan or the template.
3. **Reproducibility:** Re-run the exact same prompt to reproduce a
   failure. Essential for debugging non-deterministic agent behaviour.
4. **Auditing:** Track which skills, file paths, and criteria were
   injected into each agent invocation.

#### Design Decision 7: Dispatch Mechanism

**Recommendation: Use `--agents` JSON for V2 dispatch. It consolidates
model, tools, skills, MCP, and prompt into a single declaration.**

The current `dispatch_agent()` constructs a long CLI argument list:

```python
# Current: 10+ CLI flags assembled manually
args = ["claude", "-p", "-", "--model", model, "--allowedTools", tools,
        "--max-turns", turns, "--mcp-config", mcp, ...]
```

V2 should use `--agents` JSON, which handles all configuration in one
declaration:

```python
def dispatch_story(story: StorySpec, prompt: str, context: PromptContext) -> AgentResult:
    """Dispatch an agent for a story using --agents JSON.

    The prompt goes in the --agents JSON 'prompt' field. Stdin ('-p -')
    is not used — the prompt is fully contained in the agent definition.
    """
    agent_def = {
        "story-agent": {
            "description": f"Implement story: {story.name}",
            "prompt": prompt,
            "skills": story.skills,
            "tools": story.tools,
            "model": story.model,
            "maxTurns": story.max_turns,
        }
    }

    # Add MCP servers if needed
    if story.mcp:
        agent_def["story-agent"]["mcpServers"] = story.mcp

    args = [
        "claude",
        "--agents", json.dumps(agent_def),
        "--max-budget-usd", str(story.max_budget_usd),
        "--no-session-persistence",
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]

    # Optional: structured output for validation agents
    if story.json_schema:
        args.extend(["--json-schema", json.dumps(story.json_schema)])

    result = subprocess.run(
        args, capture_output=True, text=True
    )
    return parse_agent_result(result)
```

**Advantages over the current approach:**

- `skills` field handles skill injection natively (no temp files)
- `tools` field restricts available tools (not just auto-approves)
- `mcpServers` field provides MCP without separate `--mcp-config`
- `maxTurns` is per-agent (safety limit)
- All configuration in one JSON object — easier to log and debug

**Note:** `--max-budget-usd` remains a top-level CLI flag because it's
a safety control for the orchestrator, not an agent configuration.

#### Evaluation of Patterns NOT Adopted

**From taches — XML metadata tags:**

taches requires research and plan outputs to include XML tags:
`<confidence>`, `<dependencies>`, `<open_questions>`, `<assumptions>`.
V2 doesn't use XML metadata because:

- V2 agents produce code, not research documents
- Confidence levels are meaningless for code (it either works or not)
- Dependencies are explicit in the plan (file paths, story order)
- Open questions should be resolved during planning, not during execution

The one exception is validation agents, where structured output
(`--json-schema`) replaces XML metadata with machine-parseable JSON.

**From taches — `.prompts/` directory structure:**

taches creates `001-topic-research/`, `002-topic-plan/`,
`003-topic-implement/` directories. V2 doesn't adopt this because:

- V2's `.planning/epics/E<N>/stories/` already provides the structure
- Numbered directories add friction (what's the next number?)
- The taches structure assumes ad-hoc workflows; V2 is plan-driven

**From taches — Quality assurance framework for research:**

taches includes verification checklists, blind spots reviews, critical
claims audits, and source verification. V2 doesn't adopt this because:

- V2 agents build code, they don't research
- Code quality is checked by validation agents and `just check`
- The "quality" of agent work is measured by behavioural criteria, not
  by self-reported confidence levels

**From taches — Incremental output strategy:**

taches requires writing findings incrementally to prevent token limit
failures. V2 agents inherently do this — they write code to files as
they go. The `--max-turns` and `--max-budget-usd` flags prevent
runaway execution. No special incremental strategy needed.

**From Anthropic docs — "Let Claude interview you":**

The docs suggest having Claude interview you before implementation.
V2 handles this in the planning phase (Phase 2: Scope & Decisions,
interactive human-in-loop). By execution time, all decisions are
locked. Agents don't interview — they implement.

**From current GTS — 230-276 line agent definitions:**

The current implementer and test-author agent definitions are massive
because they embed domain knowledge (query patterns, banned patterns,
architecture rules) directly in the agent body. V2 moves this to
skills and injects it via `--append-system-prompt-file` or the
`skills` frontmatter field. The agent prompt itself stays under
2,000 tokens.

#### The Complete V2 Prompt Construction Flow

```
1. Orchestrator reads plan.json (machine-parseable, schema-validated)
   └── Extracts: story spec (model, skills, tools, MCP, scope, notes)

2. build_agent_prompt(story, context)
   ├── Role section (static template, ~100 tokens)
   ├── Plan context (from PLAN.md, ~300 tokens)
   ├── Scope (from PLAN.md, ~200 tokens)
   ├── Implementation notes (from PLAN.md, ~200 tokens)
   ├── Verification (from next checkpoint, ~100 tokens)
   ├── Failure feedback (from JSONL, ~300 tokens, retry only)
   └── Constraints (static template, ~75 tokens)
   Total: ~1,000-1,500 tokens

3. Dispatch via --agents JSON
   ├── prompt: assembled prompt text
   ├── skills: ["gts-architecture", "repository-patterns", ...]
   ├── tools: ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
   ├── model: "sonnet"
   ├── maxTurns: 30
   └── mcpServers: [...] (if needed)

4. Log prompt + dispatch metadata to story.jsonl
   └── Save full prompt to prompt-attempt-N.md

5. Agent receives:
   ├── System prompt: Claude Code defaults + injected skills
   └── User prompt: assembled prompt text (~1,000-1,500 tokens)
```

#### Key Findings for V2 Design

1. **Meta-prompting is rejected. Deterministic templates win.** The
   planner already does the meta-prompt reasoning. Adding a prompter-
   agent on top is redundant, non-deterministic, and expensive. Python
   string assembly is the right tool for this job.

2. **Prompts are assembled from 7 discrete sections.** Each section is
   a Python function. The orchestrator calls them and concatenates. No
   template engine needed — f-strings and conditionals are sufficient.

3. **Agent prompts should be under 2,000 tokens.** Domain knowledge
   lives in skills (injected via system prompt), not in the prompt
   body. The prompt provides role, scope, context, and verification.
   The skills provide patterns, conventions, and banned practices.

4. **`--agents` JSON is the preferred dispatch mechanism.** It
   consolidates model, tools, skills, MCP, and prompt into one
   declaration. Cleaner than assembling 10+ CLI flags. The `skills`
   field handles injection natively.

5. **Validation agents use structured output (`--json-schema`).**
   Pass/fail results are machine-parseable. The orchestrator never
   interprets prose — it reads JSON.

6. **Every prompt is logged.** Full prompt text saved to
   `prompt-attempt-N.md` alongside the story JSONL. This is the
   primary debugging artifact when agents fail.

7. **The "single highest-leverage thing" is verification criteria.**
   From Anthropic's official guidance. Every implementation agent
   prompt includes verification criteria from the next validation
   checkpoint. The agent checks its own work before committing.

8. **Skill injection separates domain knowledge from task scope.**
   The prompt says WHAT to do. The skills say HOW to do it in this
   codebase. This separation means the same prompt template works
   regardless of which skills are loaded — the orchestrator composes
   them at dispatch time.

### 8.6 Multi-Model & Multi-Provider Agent Dispatch (Area 4.6) ✅

**Completed.** Studied Claude Code CLI reference (flags, --settings,
--agents JSON, model identifiers, local model routing via Ollama/LM
Studio), OpenAI Codex CLI (exec mode, skills, AGENTS.md, model
providers, MCP), Google Gemini CLI (headless mode, Agent Skills, MCP,
model identifiers), the existing GTS dispatch layer in `run_epic.py`,
and prior Codex migration work in `CODEX_MIGRATION.md` and
`CODEX_GAP_ANALYSIS.md`.

#### The Core Architecture Question

Research Area 4.6 asks: how does the V2 orchestrator dispatch agents to
different models and providers from a single interface?

**Answer: Provider adapters behind a unified `dispatch_agent()` interface.**
Each provider has different CLI syntax, flag names, and capabilities, but
the orchestrator's view is the same: prompt + model + tools + skills +
MCP → result. An adapter per provider translates the common interface
into provider-specific CLI arguments.

#### Provider Landscape Assessment

Four providers were evaluated for V2 compatibility:

| Provider | CLI Tool | Headless Flag | Skills | MCP | Sub-agents | Local Models |
|----------|----------|---------------|--------|-----|------------|-------------|
| **Claude Code** | `claude` | `-p` | `.claude/skills/` | Yes | Native (`Task`) | Via `ANTHROPIC_BASE_URL` |
| **Codex CLI** | `codex` | `exec` | `.agents/skills/` | Yes | Via MCP server mode | Via `--oss` / `OPENAI_BASE_URL` |
| **Gemini CLI** | `gemini` | `-p` | `.gemini/skills/` | Yes | No native | Via Vertex AI / API key |
| **Local (Ollama/LM Studio)** | `claude` | `-p` | Inherited from Claude | Yes | Inherited | Native |

**Key finding:** All three major providers now have structurally similar
CLIs with headless modes, skills systems, and MCP support. The dispatch
abstraction is viable because the providers have converged on similar
patterns.

#### Design Decision 1: Dispatch Interface

**Recommendation: A Python `ProviderAdapter` protocol with one
implementation per provider. The orchestrator calls the adapter, not
the CLI directly.**

```python
from typing import Protocol

class ProviderAdapter(Protocol):
    """Interface for dispatching agents to any provider."""

    def build_args(
        self,
        prompt: str,
        model: str,
        tools: list[str],
        skills: list[str],
        mcp_config: dict | None,
        max_turns: int,
        max_budget_usd: float | None,
        json_schema: dict | None,
    ) -> list[str]:
        """Build CLI arguments for this provider."""
        ...

    def parse_result(
        self, completed: subprocess.CompletedProcess
    ) -> AgentResult:
        """Parse provider-specific output into common result."""
        ...

    @property
    def name(self) -> str: ...
```

Three concrete adapters:

```python
class ClaudeAdapter:       # claude -p ...
class CodexAdapter:        # codex exec ...
class GeminiAdapter:       # gemini -p ...
```

The orchestrator's `dispatch_agent()` accepts a provider name and
delegates:

```python
ADAPTERS = {
    "claude": ClaudeAdapter(),
    "codex": CodexAdapter(),
    "gemini": GeminiAdapter(),
}

def dispatch_agent(
    provider: str, prompt: str, model: str, **kwargs
) -> AgentResult:
    adapter = ADAPTERS[provider]
    args = adapter.build_args(prompt, model, **kwargs)
    result = subprocess.run(
        args, input=prompt, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return adapter.parse_result(result)
```

**Why not a single abstract `dispatch_agent()` with if/else?** Because
the providers have meaningfully different CLI structures (different
flag names, different output formats, different MCP config formats).
Each adapter encapsulates one provider's specifics. Adding a new
provider means adding one file, not modifying shared dispatch logic.

#### Design Decision 2: CLI Flag Mapping

The adapters translate a common interface to provider-specific flags.
The mapping for the core dispatch parameters:

**Headless execution:**

| Parameter | Claude Code | Codex CLI | Gemini CLI |
|-----------|-------------|-----------|------------|
| Non-interactive | `-p -` (stdin) | `exec` (positional or stdin with `-`) | `-p` (positional) |
| Auto-approve | `--dangerously-skip-permissions` | `--full-auto --yolo` | `--yolo` |
| Model | `--model opus` | `-m gpt-5.3-codex` | `-m gemini-2.5-pro` |
| Max turns | `--max-turns 30` | (not available) | (not available) |
| Budget cap | `--max-budget-usd 5.00` | (not available) | (not available) |
| Structured output | `--output-format json` | `--json` | `--output-format json` |
| JSON schema | `--json-schema '{...}'` | `--output-schema ./file.json` | (not available) |
| No session save | `--no-session-persistence` | `--ephemeral` | (not available) |

**Tool restriction:**

| Parameter | Claude Code | Codex CLI | Gemini CLI |
|-----------|-------------|-----------|------------|
| Restrict tools | `--tools "Bash,Read,Edit"` | `--sandbox workspace-write` | `--approval-mode auto_edit` |
| Auto-approve tools | `--allowedTools "Bash(git *)"` | `--full-auto` | `--yolo` |
| Deny tools | `--disallowedTools "WebFetch"` | `--sandbox read-only` | (not available) |

**System prompt / skills:**

| Parameter | Claude Code | Codex CLI | Gemini CLI |
|-----------|-------------|-----------|------------|
| Append system prompt | `--append-system-prompt-file` | `developer_instructions` in config | (GEMINI.md only) |
| Replace system prompt | `--system-prompt` | `model_instructions_file` in config | (not available) |
| Skill injection | `skills` field in `--agents` JSON | Skills auto-discovered | Skills auto-discovered |
| Subagent definition | `--agents '{...}'` JSON | (not available) | `-e <extension>` |

**MCP configuration:**

| Parameter | Claude Code | Codex CLI | Gemini CLI |
|-----------|-------------|-----------|------------|
| MCP config | `--mcp-config <json>` | `[mcp_servers.*]` in config.toml | `mcpServers` in settings.json |
| Strict MCP | `--strict-mcp-config` | (not available) | (not available) |
| MCP format | JSON with `mcpServers` key | TOML with `[mcp_servers.*]` tables | JSON with `mcpServers` key |

**Key observation:** Claude Code and Gemini CLI share similar MCP JSON
format. Codex uses TOML. The adapter needs to generate the right config
file format per provider.

#### Design Decision 3: Local Model Routing

**Recommendation: Route local models through Claude Code's
`ANTHROPIC_BASE_URL` mechanism. Do not build a separate local adapter.**

Claude Code supports local models (GLM, Qwen, GPT-OSS) via environment
variable overrides:

```python
# In ClaudeAdapter, for local model dispatch:
env = {
    **os.environ,
    "ANTHROPIC_BASE_URL": "http://localhost:11434",  # Ollama
    "ANTHROPIC_AUTH_TOKEN": "ollama",
    "ANTHROPIC_API_KEY": "",
}
args = ["claude", "-p", "-", "--model", "glm-4.7", ...]
result = subprocess.run(args, input=prompt, env=env, ...)
```

Alternatively, use the `--settings` flag with inline JSON:

```python
settings = json.dumps({
    "env": {
        "ANTHROPIC_BASE_URL": "http://localhost:11434",
        "ANTHROPIC_AUTH_TOKEN": "ollama",
        "ANTHROPIC_API_KEY": "",
    }
})
args = ["claude", "-p", "-", "--settings", settings, "--model", "glm-4.7"]
```

**Why not a separate local adapter?** Because local models run through
existing provider CLIs (Claude Code via Ollama/LM Studio, Codex via
`--oss` flag). The adapter just needs to set environment variables.
Adding a `LocalModelMixin` or a `local_model_env()` helper to the
Claude adapter is sufficient.

**Ollama shortcut:** `ollama launch claude` auto-configures the
environment. For orchestrator use, the explicit env vars are better
(deterministic, no dependency on Ollama's launcher).

**Requirements for local model dispatch:**
- Ollama or LM Studio running on localhost
- Model with ≥64K token context window (Ollama recommendation)
- The gateway must expose Anthropic Messages API format (`/v1/messages`)

**Recommended local models (from Ollama docs):**
- `glm-4.7` — strong general coding
- `qwen3-coder` — code-focused
- `gpt-oss:20b` / `gpt-oss:120b` — OpenAI's open-source models

**V2 implication:** Local model dispatch is a configuration concern, not
an architecture concern. The orchestrator's plan format can specify
`provider: claude` with `model: glm-4.7` and `local: true` to trigger
the environment override. No separate adapter needed.

#### Design Decision 4: Codex Skill Synchronisation

**Recommendation: Maintain skills in Claude Code's `.claude/skills/`
format as canonical. Transform to Codex format via a sync script.**

GTS already has Codex configuration set up (confirmed in
`CODEX_MIGRATION.md`):

- `~/.codex/AGENTS.md` — global overlay
- `~/.codex/config.toml` — MCP, model config (`gpt-5.3-codex`)
- `~/.codex/rules/default.rules` — permission rules
- `~/.codex/skills/` — synced from Claude Code skills (51 skill dirs)

**Skill format comparison:**

| Aspect | Claude Code | Codex CLI | Gemini CLI |
|--------|-------------|-----------|------------|
| Skill file | `SKILL.md` | `SKILL.md` | `SKILL.md` |
| Location (project) | `.claude/skills/` | `.agents/skills/` | `.gemini/skills/` |
| Location (user) | `~/.claude/skills/` | `~/.agents/skills/` | `~/.gemini/skills/` |
| Frontmatter | YAML (name, description) | YAML (name, description) | YAML (name, description) |
| Body | Markdown instructions | Markdown instructions | Markdown instructions |
| References | `references/` subdir | `references/` subdir | Bundled resources |
| Invocation | `$skill-name` or auto | `$skill-name` or auto | `activate_skill` tool |
| Loading | Eager (all loaded) | Lazy (metadata only, then on-demand) | Lazy (metadata only) |

**The SKILL.md format is nearly identical across all three providers.**
The differences are:
1. Directory location (`.claude/` vs `.agents/` vs `.gemini/`)
2. Loading strategy (eager vs lazy)
3. Optional metadata (Codex has `agents/openai.yaml`, Gemini has none)

**Sync approach:**

```bash
# One-liner to sync skills from Claude Code to Codex
rsync -av --delete ~/.claude/skills/ ~/.codex/skills/
rsync -av --delete .claude/skills/ .codex/skills/ 2>/dev/null

# For Gemini CLI
rsync -av --delete ~/.claude/skills/ ~/.gemini/skills/
rsync -av --delete .claude/skills/ .gemini/skills/ 2>/dev/null
```

This works because `SKILL.md` format is compatible. Provider-specific
metadata files (`agents/openai.yaml`) are optional and can be added
per-skill if needed.

**V2 implication:** Add a `just sync-skills` recipe that copies skills
to all provider directories. Run it as a pre-flight step before
dispatching to non-Claude providers.

#### Design Decision 5: Model Routing Matrix

**Recommendation: The plan specifies provider + model per story. The
orchestrator's default matrix is a starting point; the planner can
override.**

**Default routing matrix:**

| Task Type | Provider | Model | Rationale |
|-----------|----------|-------|-----------|
| Planning (complex) | Claude | `opus` | Best reasoning, highest cost |
| Architecture (domain) | Claude | `sonnet` | Good balance, domain skills loaded |
| Implementation (CRUD) | Claude or Codex | `sonnet` / `gpt-5.3-codex` | Interchangeable for structured code |
| UI scaffolding | Claude | `sonnet` + Chrome MCP | Chrome DevTools MCP integration |
| Validation (browser) | Claude | `haiku` + Playwright MCP | Cheap, MCP-dependent |
| Validation (API/DB) | Any | `haiku` / `gpt-5.2` / `gemini-2.5-flash` | Cheapest available |
| Regression tests | Claude or Codex | `sonnet` / `gpt-5.3-codex` | Needs test writing capability |
| Local quick check | Claude | `glm-4.7` (via Ollama) | Free, fast, low quality |

**Cost comparison (approximate per invocation):**

| Model | Cost/1K input | Cost/1K output | Typical invocation |
|-------|---------------|----------------|-------------------|
| Claude Opus 4.6 | $0.015 | $0.075 | $2–8 |
| Claude Sonnet 4.5 | $0.003 | $0.015 | $0.50–2 |
| Claude Haiku 4.5 | $0.0008 | $0.004 | $0.05–0.30 |
| GPT-5.3-codex | ~$0.003 | ~$0.015 | $0.50–2 |
| Gemini 2.5 Pro | $0.001–0.003 | $0.004–0.015 | $0.20–1 |
| Gemini 2.5 Flash | $0.0003 | $0.001 | $0.02–0.10 |
| Local (Ollama) | Free | Free | $0 (hardware cost) |

**When to use non-Claude providers:**

1. **Codex for CRUD implementation** — competitive with Sonnet on
   structured code tasks, potentially cheaper with OpenAI's pricing
2. **Gemini Flash for validation** — cheapest option for pass/fail
   checks that don't need MCP
3. **Local models for iteration** — free, fast feedback during
   development (not for epic execution)

**When Claude is the only option:**

1. **Tasks needing MCP** — Chrome DevTools and Playwright MCP are
   configured for Claude Code. Codex and Gemini have MCP support but
   the GTS MCP config is Claude-specific.
2. **Tasks needing skills** — Claude Code's skill injection via
   `--agents` JSON or `--append-system-prompt-file` is the most
   mature. Codex and Gemini auto-discover skills but can't inject
   them programmatically into headless invocations.
3. **Planning** — Opus is the strongest reasoning model for complex
   planning tasks. No equivalent from other providers.

#### Design Decision 6: `--fallback-model` Limitations

**Finding: `--fallback-model` only triggers on HTTP 529 (overload).**

Claude Code's `--fallback-model` flag is intentionally limited to
overload scenarios. It does NOT trigger on:
- Invalid model names
- Server downtime
- Network errors
- 4xx/5xx errors other than 529

GitHub issue #8413 requested broader fallback triggers but was closed
as NOT_PLANNED.

**V2 implication:** Do not rely on `--fallback-model` for provider
resilience. Instead, the orchestrator should catch subprocess failures
and retry with a different provider/model:

```python
def dispatch_with_fallback(
    primary: tuple[str, str],     # (provider, model)
    fallback: tuple[str, str],    # (provider, model)
    prompt: str,
    **kwargs,
) -> AgentResult:
    """Try primary, fall back on failure."""
    result = dispatch_agent(primary[0], prompt, primary[1], **kwargs)
    if result.success:
        return result

    log(f"Primary failed ({primary}), trying fallback ({fallback})")
    return dispatch_agent(fallback[0], prompt, fallback[1], **kwargs)
```

This is more robust than `--fallback-model` because:
1. It works across providers (not just models)
2. It triggers on any failure (not just overload)
3. It's logged to JSONL for debugging

#### Design Decision 7: Gemini CLI Integration

**Recommendation: Support Gemini CLI as a tier-2 provider. Not for
V2 launch, but the architecture should not prevent it.**

Gemini CLI is the most compatible non-Claude provider:
- Same `-p` flag for headless mode
- Same MCP configuration format (JSON with `mcpServers`)
- Same skills format (`SKILL.md` in `.gemini/skills/`)
- `--yolo` for auto-approval (like `--dangerously-skip-permissions`)
- `--output-format json` for structured output
- Free tier with 1,000 requests/day

**What's missing for V2:**
- No `--max-turns` or `--max-budget-usd` (safety controls)
- No `--json-schema` (structured validation output)
- No native sub-agent spawning
- No `--append-system-prompt-file` (skills injected via GEMINI.md only)
- Skills are lazy-loaded by model decision, not injected by orchestrator

**The GeminiAdapter would be:**

```python
class GeminiAdapter:
    name = "gemini"

    def build_args(self, prompt, model, tools, skills, mcp_config,
                   max_turns, max_budget_usd, json_schema):
        args = [
            "gemini",
            "-p", prompt,
            "-m", model,
            "--output-format", "json",
            "--yolo",
        ]
        # No --max-turns, --max-budget-usd, --json-schema equivalents
        # Skills auto-discovered from .gemini/skills/ (must be synced)
        # MCP config from .gemini/settings.json (must be pre-configured)
        return args
```

**V2 launch: Claude-only with Codex as opt-in.** The Gemini adapter
exists in the design but is not required for V2 to be functional.

#### Prior GTS Multi-Provider Work

**Finding: Codex coexistence is already set up but not integrated
into the dispatch layer.**

The `CODEX_MIGRATION.md` wiki page documents a complete Codex setup:

| Component | Status | Location |
|-----------|--------|----------|
| Global AGENTS.md | ✅ Done | `~/.codex/AGENTS.md` |
| Global config | ✅ Done | `~/.codex/config.toml` (model: gpt-5.3-codex) |
| Global rules | ✅ Done | `~/.codex/rules/default.rules` |
| MCP servers | ✅ Done | chrome-devtools + playwright in config.toml |
| Skill sync | ✅ Done | 51 skill dirs synced to `~/.codex/skills/` |
| Repo-local config | ✅ Done | `.codex/AGENTS.md`, `.codex/config.toml`, `.codex/rules/` |
| Dispatch integration | ❌ Not done | `run_epic.py` only dispatches to Claude |
| Dual-mode orchestrator | ❌ Not done | Listed as "Optional Future Enhancement" |

**The gap is narrow.** Codex is configured, skills are synced, MCP
is set up. The missing piece is the dispatch adapter — the
`CodexAdapter` that translates the common interface to `codex exec`
arguments.

The `CODEX_MIGRATION.md` doc provides execution templates that
confirm the dispatch pattern:

```bash
# Test author (read-only to tests/)
codex exec --full-auto --sandbox=workspace-write --add-dir tests/ \
  "Write failing tests for TNN based on the task acceptance criteria"

# Implementer
codex exec --full-auto --sandbox=workspace-write \
  --add-dir libs/ --add-dir apps/ --add-dir sources/ \
  "Implement code to satisfy tests for TNN. Do not modify tests."
```

These map directly to the V2 story dispatch pattern — just with
different CLI flags.

The existing `dispatch_agent()` in `run_epic.py` (lines 571–607) is
Claude-only. V2 replaces it with the adapter pattern above.

#### Evaluation of Cross-Tool Skill Sync (Area 4.7 Overlap)

Research Area 4.7 asks about keeping skills consistent across providers.
This research addresses the technical mechanism:

**Finding: The `SKILL.md` format is a de facto standard across all
three providers.** Name + description in YAML frontmatter, markdown
body, optional `references/` subdirectory. The only difference is
the directory path.

**Sync mechanism:** A `just sync-skills` recipe that:
1. Copies `~/.claude/skills/` → `~/.codex/skills/` and `~/.gemini/skills/`
2. Copies `.claude/skills/` → `.codex/skills/` and `.gemini/skills/`
3. Runs after any skill creation or modification

**What can't be synced:**
- Claude Code slash commands (`/commit`, `/merge`) — no equivalent
- Claude Code hooks (SessionStart, PreToolUse) — no equivalent
- Claude Code `--agents` JSON subagent definitions — no equivalent
- Codex `agents/openai.yaml` metadata — Claude-specific
- Codex execution policies (`requirements.toml`) — Codex-specific

**V2 implication:** Skills are the easy part. The hard part is
feature parity for hooks, commands, and subagent definitions. V2
should not try to achieve full parity — it should use Claude Code
as the primary provider and treat others as opt-in alternatives
for specific task types.

#### Key Findings for V2 Design

1. **All three major providers have converged on similar CLI patterns.**
   Headless mode, skills, MCP, and AGENTS.md/CLAUDE.md/GEMINI.md are
   structurally equivalent. A unified dispatch adapter is viable and
   not over-engineering.

2. **The adapter pattern is the right abstraction.** One `ProviderAdapter`
   per CLI tool. The orchestrator doesn't know provider specifics — it
   passes prompt + model + config and gets back a result.

3. **Local model routing goes through Claude Code's env vars.** Set
   `ANTHROPIC_BASE_URL` to Ollama/LM Studio endpoint. No separate
   adapter needed. The `--settings` flag can also inject env vars
   via inline JSON.

4. **Claude Code is the primary provider for V2.** It has the richest
   dispatch interface (`--agents` JSON, `--tools`, `--max-turns`,
   `--max-budget-usd`, `--json-schema`, `--append-system-prompt-file`).
   Codex and Gemini lack safety controls (max turns, budget caps) and
   programmatic skill injection.

5. **Codex is the best second provider.** Already configured in GTS
   (`~/.codex/`, `.codex/`, 51 skills synced). `codex exec` is the
   direct equivalent of `claude -p`. The adapter is straightforward.
   Best for CRUD implementation tasks where MCP isn't needed.

6. **Gemini CLI is tier-2 (architecture supports it, not needed for
   V2 launch).** Free tier is attractive. Agent Skills and MCP support
   are there. But missing safety controls and programmatic skill
   injection make it unsuitable as a primary provider.

7. **`--fallback-model` is too limited for provider resilience.** Only
   triggers on HTTP 529. The orchestrator should implement its own
   retry-with-fallback at the adapter level, catching any subprocess
   failure.

8. **Skill format is a de facto standard.** `SKILL.md` with YAML
   frontmatter works across all three providers. Sync is a
   file-copy operation. The sync gap is in commands, hooks, and
   subagent definitions — not skills.

9. **The plan format should annotate provider + model per story.**
   Default to Claude + Sonnet. Override to Codex or Gemini for
   specific task types. The orchestrator reads the annotation and
   selects the adapter.

10. **Prior Codex work closes the gap significantly.** Config, rules,
    MCP, and skills are already set up. Only the dispatch adapter
    (`CodexAdapter`) needs to be built for V2.

### 8.7 MCP Configuration (Area 4.5) ✅

**Completed.** Findings are distributed across Sections 8.2 (CLI flags
reference, lines 1025-1064), 8.4 (validation agent MCP requirements,
Decision 5), 8.5 (dispatch mechanism with `--mcp-config`, Decision 7),
and 8.6 (MCP config format per provider, Decision 2). No standalone
section needed — MCP configuration is a cross-cutting concern addressed
within each research area where it applies.

**Summary of MCP decisions:**
- Chrome DevTools MCP required for `http+dom`, `browser+db`, `screenshot` checks
- Playwright MCP required for regression test authoring
- MCP config built by orchestrator per story from `plan.json` agent spec
- `--strict-mcp-config --mcp-config <json>` on Claude Code dispatch
- Pre-flight MCP availability check before dispatching MCP-dependent agents
- Non-Claude providers have their own MCP config formats (TOML for Codex,
  JSON for Gemini) — handled by provider adapters

### 8.8 Cross-Tool Skill Synchronisation (Area 4.7) ✅

**Completed.** Studied the Agent Skills open standard
(agentskills.io/specification), Claude Code's skill system (official
docs, DeepWiki source analysis, `skill-creator` reference
implementation), Codex CLI's skill system (`render.rs` source,
`openai/skills` catalogue, `config.toml` reference), Gemini CLI's
skill system (official docs, `activate_skill` tool, extension
architecture), the existing GTS skill inventory (22 project-level,
28 global Claude, 50 global Codex), and prior Codex migration work
in `CODEX_MIGRATION.md`.

#### The Core Question

Research Area 4.7 asks: how does the V2 orchestrator keep skill
knowledge consistent across Claude Code, Codex CLI, and Gemini CLI?

**Answer: SKILL.md is already a de facto interoperable standard. The
sync problem is solved for skill content. The real challenge is the
non-skill artefacts (commands, hooks, agents, rules) that each
provider handles differently.**

#### Finding 1: The Agent Skills Open Standard

All three major providers have converged on the same skill format.
The "Agent Skills" specification (originated by Anthropic, now an
open standard at agentskills.io) defines:

```yaml
---
name: skill-name          # Required. Max 64 chars, lowercase + hyphens.
description: ...          # Required. Max 1024 chars. Primary trigger signal.
---

# Skill Title

Markdown instructions body...
```

**Required frontmatter:** `name` and `description` only. Both fields
are read by all three providers.

**Optional frontmatter** (informational, not consumed by providers):
`license`, `metadata`, `compatibility`, `allowed-tools`.

**Directory structure** (identical across all three):

```
skill-name/
├── SKILL.md              # Required — metadata + instructions
├── scripts/              # Optional — executable code
├── references/           # Optional — additional docs loaded on demand
└── assets/               # Optional — templates, images, data files
```

**This is the same format.** A skill directory from one provider can
be copied verbatim to another. GTS already demonstrates this — the
50 Codex skills in `~/.codex/skills/` are byte-identical copies of
the Claude skills.

#### Finding 2: Skill Discovery Paths

Each provider reads skills from different directory paths:

| Tier | Claude Code | Codex CLI | Gemini CLI |
|------|-------------|-----------|------------|
| **Project** | `.claude/skills/` | `.agents/skills/` | `.gemini/skills/` |
| **User** | `~/.claude/skills/` | `~/.codex/skills/` (compat for `~/.agents/skills/`) | `~/.gemini/skills/` |
| **Extension** | Plugins (`--plugin-dir`) | System skills (`.system/`) | Extensions (`gemini-extension.json`) |

**The only difference is the directory path.** The sync operation
is a directory copy with no content transformation required.

#### Finding 3: Skill Loading Strategies

Each provider uses a different loading strategy, but the skill
content itself is unaffected:

| Provider | Phase 1 (Always) | Phase 2 (On demand) | Phase 3 (Resources) |
|----------|-------------------|--------------------|--------------------|
| **Claude Code** | Skill descriptions injected into context (15K char budget, 2% of context window via `SLASH_COMMAND_TOOL_CHAR_BUDGET`) | Full SKILL.md body loaded when skill is invoked (via `/skill-name` or auto-match) | `references/` loaded by Claude as needed |
| **Codex CLI** | Name + description + file path listed in system prompt (rendered by `render.rs`) | Full SKILL.md loaded when model decides to use skill (progressive disclosure) | `references/` loaded on demand, `scripts/` preferred over retyping |
| **Gemini CLI** | Name + description injected into system prompt metadata | Full SKILL.md body loaded via `activate_skill` tool (user consent required) | Skill directory added to agent's allowed file paths |

**Key difference: Claude loads eagerly within a character budget.
Codex and Gemini load lazily with progressive disclosure.** This
does not affect skill portability — the same SKILL.md works in all
three systems. However, it means:

- Claude Code skills should keep descriptions under ~200 words to
  fit within the 15K character budget across all project + global
  skills
- Codex and Gemini are more tolerant of verbose descriptions since
  they only load metadata initially

#### Finding 4: Programmatic Skill Injection

For the V2 orchestrator to inject specific skills into headless agent
invocations, each provider offers different mechanisms:

| Mechanism | Claude Code | Codex CLI | Gemini CLI |
|-----------|-------------|-----------|------------|
| **Inject skills into subagent** | `--agents '{"name": {"skills": ["skill1", "skill2"]}}'` | Not available — skills auto-discovered from `~/.codex/skills/` | Not available — skills auto-discovered from `~/.gemini/skills/` |
| **Append custom instructions** | `--append-system-prompt-file ./skill.md` | `developer_instructions` in `config.toml` | No equivalent — GEMINI.md only |
| **Replace system prompt** | `--system-prompt-file ./prompt.txt` | `model_instructions_file` in `config.toml` | Not available |
| **Control loaded skills** | `--agents` JSON with `skills` array | `[[skills.config]]` in `config.toml` with `enabled = false` | `/skills disable name` persisted to `settings.json` |

**Claude Code is the only provider with fine-grained programmatic
skill injection via the `--agents` JSON flag.** The `skills` array
in subagent definitions lets the orchestrator precisely control
which skills each agent receives. This is the critical capability
for V2's dispatch pattern.

**Codex CLI loads all discovered skills automatically.** The
orchestrator cannot selectively inject specific skills per
invocation. To restrict skills, you'd need to manipulate the skill
discovery directories before invocation (e.g., a temporary
`~/.codex/skills/` with only the desired skills). This is
fragile and not recommended.

**Gemini CLI's `activate_skill` tool requires the model to
autonomously decide to use a skill** — the orchestrator cannot
force activation from outside. Skills can be enabled/disabled via
`settings.json`, but this is a static configuration, not a
per-invocation control.

#### Finding 5: Non-Skill Artefacts That Cannot Be Synced

Skills are the easy part. The following artefacts are
provider-specific and have no equivalent in other providers:

| Artefact | Claude Code | Codex CLI | Gemini CLI |
|----------|-------------|-----------|------------|
| **Slash commands** | `.claude/commands/*.md` (16 in GTS) | No equivalent | Extension `commands/` (different format) |
| **Hooks** | `.claude/hooks/*.sh` (11 in GTS) | No equivalent | Extension `hooks/` (JS-based, different events) |
| **Agents/subagents** | `.claude/agents/*.md` (13 in GTS) | No equivalent (no native sub-agents) | Extension `agents/` (different format) |
| **Rules** | `.claude/rules/*.md` (10 in GTS) | `~/.codex/rules/default.rules` (prefix-rule format) | No equivalent |
| **Settings** | `.claude/settings.json` (allowlists) | `~/.codex/config.toml` (approval policies) | `~/.gemini/settings.json` (different schema) |
| **Context file** | `CLAUDE.md` (auto-loaded) | `AGENTS.md` (auto-loaded) | `GEMINI.md` (auto-loaded, configurable name) |

**GTS currently has:** 16 slash commands, 11 hooks, 13 agent
definitions, 10 rule files, and project settings. None of these
can be synced to other providers mechanically.

**Codex workaround:** The `CODEX_MIGRATION.md` documents manual
equivalents — e.g., `just` commands replace slash commands,
`AGENTS.md` replaces `CLAUDE.md` (Codex reads `AGENTS.md`
natively), rules are mapped to `default.rules` format. This is a
one-time manual translation, not an automated sync.

**Gemini workaround:** Gemini CLI's configurable `context.fileName`
setting can be set to read `AGENTS.md`:
```json
{ "context": { "fileName": ["AGENTS.md", "GEMINI.md"] } }
```
This eliminates the need for a separate GEMINI.md — Gemini reads
the same `AGENTS.md` that Codex reads. However, provider-specific
instructions (Claude Code flags, Codex sandbox modes) embedded in
`AGENTS.md` will be irrelevant noise for non-Claude providers.

#### Finding 6: GTS Skill Inventory

**Project-level skills (22):**
`epic`, `gts-architecture`, `gts-auth`, `gts-backend-dev`,
`gts-frontend-dev`, `gts-testing`, `gts-video`, `gts-security`,
`chrome-devtools`, `site-verify`, `screenshot-eval`, `ui-debug`,
`ui-contract`, `docker-infra`, `documentation-style`,
`codebase-review`, `incident-response`, `micro-task-workflow`,
`prompt-builder`, `python-cheatsheet`, `ralph-hybrid-plan`,
`ralph-hybrid-overview`.

**Global Claude skills (28):**
`astro-frontend`, `check`, `claude-config-consolidation`,
`code-archaeology`, `commit`, `conventions`, `error-handling`,
`expertise`, `explore`, `fix-issue`, `gh-workflow`, `health-check`,
`htmx`, `infrastructure-protection`, `issue-triage`, `plan`,
`playwright`, `pr-create`, `prompt-optimizer`, `pr-review`,
`repository-patterns`, `security-review`, `service-patterns`,
`skill-creator`, `software-architecture`, `test-failure-analysis`,
`web-handlers`, `worktree`.

**Global Codex skills (50):** All 28 global Claude skills + all 22
project-level GTS skills synced to `~/.codex/skills/`. This is a
superset because Codex has no project vs global distinction — all
skills go into one directory.

**Global Gemini skills (0):** No `~/.gemini/skills/` directory
exists. Gemini CLI has not been configured for GTS yet.

**Skills with references/ subdirectories (11 project-level):**
`epic`, `gts-frontend-dev`, `gts-architecture`, `gts-testing`,
`ralph-hybrid-plan`, `prompt-builder`, `gts-security`,
`ralph-hybrid-overview`, `codebase-review`, `docker-infra`,
`gts-auth`. These skills have additional reference files that
must be synced alongside SKILL.md.

**Frontmatter format:** All GTS skills use only `name` and
`description` — no `globs`, `alwaysApply`, or other optional
fields. This simplifies cross-provider compatibility.

#### Design Decision 1: Canonical Source

**Recommendation: Claude Code's `.claude/skills/` remains the
single source of truth. All other providers sync from it.**

Rationale:
1. Claude Code has the richest skill system (programmatic injection,
   subagent skill arrays, hot-reload)
2. All GTS skills are already authored in Claude Code format
3. The SKILL.md format is identical across providers
4. Claude Code is the primary V2 provider (per Research Area 4.6)

#### Design Decision 2: Sync Mechanism

**Recommendation: A `just sync-skills` recipe that copies skill
directories to all configured providers.**

```bash
# Sync global skills: Claude → Codex + Gemini
rsync -av --delete ~/.claude/skills/ ~/.codex/skills/
rsync -av --delete ~/.claude/skills/ ~/.gemini/skills/

# Sync project skills: .claude/skills/ → .codex/skills/ + .gemini/skills/
rsync -av --delete .claude/skills/ .codex/skills/ 2>/dev/null
rsync -av --delete .claude/skills/ .gemini/skills/ 2>/dev/null
```

**When to run:**
- After creating or modifying any skill
- As a pre-flight step before dispatching to non-Claude providers
- Optionally as a git pre-commit hook

**What this syncs:** SKILL.md + scripts/ + references/ + assets/
(the complete skill directory tree).

**What this does NOT sync:** Commands, hooks, agents, rules,
settings. These remain provider-specific and are maintained
manually per the `CODEX_MIGRATION.md` approach.

#### Design Decision 3: Gemini CLI Configuration

**Recommendation: Set up Gemini CLI for GTS with minimal
configuration. Not required for V2 launch but easy to do.**

```bash
# Create global skills directory
mkdir -p ~/.gemini/skills

# Sync skills from Claude
rsync -av --delete ~/.claude/skills/ ~/.gemini/skills/

# Configure GEMINI.md to read AGENTS.md
cat > ~/.gemini/settings.json << 'EOF'
{
  "context": {
    "fileName": ["AGENTS.md", "GEMINI.md"]
  }
}
EOF
```

This gives Gemini CLI access to all GTS skills and project
instructions without maintaining separate GEMINI.md files.

#### Design Decision 4: Provider-Specific Instruction Layering

**Recommendation: Keep `AGENTS.md` tool-agnostic. Put
provider-specific instructions in provider-specific files only.**

```
AGENTS.md              # Shared: architecture, patterns, rules
                       # Read by Claude (via CLAUDE.md @include),
                       # Codex (native), and Gemini (via settings)
CLAUDE.md              # Claude-specific: @AGENTS.md include
~/.codex/AGENTS.md     # Codex-specific: overlays, coexistence
~/.gemini/GEMINI.md    # Gemini-specific: overlays (if needed)
```

Provider-specific instructions (e.g., "use `--dangerously-skip-
permissions` for auto-approval") belong in the provider's own
config, not in `AGENTS.md`. The shared `AGENTS.md` should contain
only tool-agnostic project rules.

#### Design Decision 5: V2 Dispatch Skill Injection

**Recommendation: For V2, use Claude Code's `--agents` JSON to
inject skills into subagents. For non-Claude providers, rely on
auto-discovery from synced skill directories.**

Claude Code dispatch (precise control):
```python
class ClaudeAdapter:
    def build_args(self, prompt, model, tools, skills, ...):
        agents_json = {
            "worker": {
                "description": "Implementation agent",
                "prompt": prompt,
                "skills": skills,  # ["gts-backend-dev", "gts-testing"]
                "tools": tools,
                "model": model,
            }
        }
        return [
            "claude", "-p", "-",
            "--agents", json.dumps(agents_json),
            "--dangerously-skip-permissions",
        ]
```

Codex dispatch (auto-discovery):
```python
class CodexAdapter:
    def build_args(self, prompt, model, tools, skills, ...):
        # Skills are auto-discovered from ~/.codex/skills/
        # No way to inject specific skills per invocation
        return [
            "codex", "exec",
            "--full-auto",
            "--sandbox=workspace-write",
            prompt,
        ]
```

Gemini dispatch (auto-discovery):
```python
class GeminiAdapter:
    def build_args(self, prompt, model, tools, skills, ...):
        # Skills auto-discovered from .gemini/skills/
        # Model decides which to activate via activate_skill tool
        return [
            "gemini", "-p", prompt,
            "-m", model,
            "--yolo",
        ]
```

**The skill injection gap is real but acceptable.** Claude Code is
the primary provider and has full control. Codex and Gemini
providers have all skills available but cannot be directed to use
specific ones — the model decides based on skill descriptions.
For well-described skills, this is sufficient.

#### Key Findings for V2 Design

1. **The SKILL.md format is an interoperable standard.** All three
   providers read identical files. Sync is a directory copy.
   No content transformation needed.

2. **Skill sync is solved. The real gap is non-skill artefacts.**
   Commands, hooks, agents, and rules are provider-specific.
   V2 should not attempt to unify these — manual translation
   per `CODEX_MIGRATION.md` is the pragmatic approach.

3. **Claude Code has the best programmatic skill injection.**
   The `--agents` JSON with `skills` array is unique to Claude
   Code. Codex and Gemini rely on auto-discovery. This reinforces
   Claude Code as the primary V2 provider.

4. **Loading strategies differ but don't affect portability.**
   Claude loads eagerly (15K char budget), Codex and Gemini
   load lazily (progressive disclosure). The same SKILL.md
   works in all three — the loading difference is transparent
   to the skill author.

5. **Gemini CLI is the easiest to add.** Set `context.fileName`
   to read `AGENTS.md`, sync skills, done. The `activate_skill`
   tool handles the rest autonomously.

6. **A `just sync-skills` recipe is the complete sync solution.**
   Run it after skill changes. Handles global + project skills.
   Pre-flight step for multi-provider dispatch.

7. **GTS skills are already sync-compatible.** All 22 project
   skills and 28 global skills use only `name` + `description`
   frontmatter. No provider-specific fields. The 50 Codex skills
   are already byte-identical copies.

8. **Provider-specific instructions should stay provider-specific.**
   Keep `AGENTS.md` tool-agnostic. Provider overlays go in
   `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`, etc.

9. **V2.1 deliverables: `just sync-skills` recipe + Gemini `settings.json`
   setup.** These are the only two deliverables needed for multi-provider
   skill sync. Everything else (Codex config, skill content, directory
   structure) is already in place. Deferred from V2 per Section 9 scope
   boundary — V2 is Claude-only.

---

## 9. V2 Scope Boundary

V2 is a **reliability-first** release. It replaces the broken TDD
state machine with behaviour-validated development, using Claude Code
as the sole provider. Everything not essential to the core loop is
explicitly deferred to V2.1 or later.

### What V2 Ships

| Component | Deliverable |
|-----------|-------------|
| **Orchestrator** | Stateless Python script: read `plan.json` → dispatch agent → log JSONL → loop |
| **Planning pipeline** | Context assembly (Python) → interactive scope → plan generation (Opus) → `plan.json` + PLAN.md with user journeys |
| **Plan verification** | Two-phase: deterministic schema validation (Phase A) + AI plan verifier agent (Phase B, Sonnet) |
| **Agent dispatch** | Claude Code only, via `--agents` JSON with skill injection |
| **JSONL log** | Versioned event schema (`schema_v`, `run_id`, `story_id`, `attempt`) with crash recovery |
| **Validation** | Type-aware checkpoints with evidence-based structured output (`--json-schema`) |
| **Failure handling** | 4-type classification (env/scope/implementation/unknown), 2-retry budget, exit-to-human |
| **GitHub integration** | Ingest (`just epic-ingest`), milestone comments, manual close |
| **File structure** | `.planning/epics/E<N>/` with EPIC.md, PLAN.md, plan.json, epic.jsonl, stories/ |

### What V2 Does NOT Ship

These are **explicitly excluded** from V2 scope. They are not forgotten
— they are deferred with intent. Each has a named V2.1 item below.

| Excluded | Reason |
|----------|--------|
| Multi-provider dispatch (Codex, Gemini adapters) | Core loop must be stable before adding provider complexity |
| Provider adapter pattern implementation | Architecture is designed (Section 8.6), but only `ClaudeAdapter` is built |
| Cross-tool skill sync automation (`just sync-skills`) | Skills work fine in Claude-only mode; sync is a multi-provider concern |
| Failure-category-aware retry policy | Need real failure data from JSONL logs before building smart retries |
| JSONL analytics / feedback loop | Need accumulated logs from multiple epics first |
| Parallel story execution (multi-worktree) | Sequential must be proven before parallelism adds merge complexity |
| Local model routing (Ollama/LM Studio) | Environment variable config documented, but not integrated into dispatch |
| Gemini CLI configuration | Architecture supports it (Section 8.6 Decision 7), setup deferred |
| Auto-close of GitHub epics | Human closes after review — V2 prioritises trust over automation |

---

## 10. V2.1 Roadmap

Planned enhancements after V2 is proven on 2-3 real epics. Each item
has a clear trigger (what V2 data or experience unlocks it) and a
defined scope.

### 10.1 Provider Adapter Pattern (Multi-Provider Dispatch)

**Trigger:** V2 Claude-only loop is stable; desire to use cheaper models
for validation or alternative providers for implementation.

**Scope:** Implement the `ProviderAdapter` protocol (Section 8.6,
Decision 1) with concrete adapters:

| Adapter | CLI | Priority |
|---------|-----|----------|
| `ClaudeAdapter` | `claude -p` | **V2** (built during V2 implementation) |
| `CodexAdapter` | `codex exec` | **V2.1** — config already exists (Section 8.6, Decision 7) |
| `GeminiAdapter` | `gemini -p` | **V2.1** — architecture designed, free tier attractive |
| Local model env | `claude -p` + `ANTHROPIC_BASE_URL` | **V2.1** — env var mechanism documented |

The adapter pattern is the keystone for multi-provider support. The
orchestrator's `dispatch_agent()` delegates to adapters via provider
name. Adding a provider means adding one Python file. The common
interface (`build_args()`, `parse_result()`) is defined in Section 8.6.

**Depends on:** Stable V2 dispatch interface, proven `--agents` JSON
dispatch, JSONL logging that captures provider metadata.

**Deliverables:**
- `scripts/adapters/codex.py` — `CodexAdapter` implementation
- `scripts/adapters/gemini.py` — `GeminiAdapter` implementation
- `scripts/adapters/local.py` — local model env var helper
- `plan.json` schema update: `provider` field per story (default: `claude`)
- `just sync-skills` recipe for cross-provider skill sync

### 10.2 Cross-Tool Skill Synchronisation

**Trigger:** V2.1 multi-provider adapters are implemented; need skills
available in Codex and Gemini directories.

**Scope:** Automated sync of `.claude/skills/` → `.codex/skills/` +
`.gemini/skills/` (Section 8.8, Decision 2). Content is identical
(SKILL.md is a de facto standard). Sync is a directory copy.

**Deliverables:**
- `just sync-skills` recipe (rsync-based, global + project)
- Gemini CLI setup (`~/.gemini/settings.json` with `context.fileName`)
- Pre-flight sync check in orchestrator before non-Claude dispatch
- Documentation of non-syncable artefacts (commands, hooks, agents, rules)

### 10.3 Failure Taxonomy & Smart Retry

**Trigger:** V2 has accumulated JSONL logs from 3+ epics; failure
category distribution is visible.

**Scope:** Analyse accumulated `failure_category` fields across runs.
Build retry policies that vary by category:

| Category | V2 Policy | V2.1 Policy |
|----------|-----------|-------------|
| `env` | 2 retries | 0 retries — exit immediately, env needs human fix |
| `scope` | 2 retries | 0 retries — exit immediately, plan needs human fix |
| `implementation` | 2 retries | 3 retries with escalating feedback detail |
| `unknown` | 2 retries | 1 retry then exit with diagnostic dump |

**Deliverables:**
- Failure category analyser script (reads JSONL, reports distribution)
- Category-aware retry logic in orchestrator
- JSONL schema update: `failure_detail` structured field (stack trace,
  exit code, file paths) for richer diagnostics

### 10.4 JSONL Analytics & Feedback Loop

**Trigger:** V2 has accumulated JSONL logs from 5+ epics; patterns
are visible across runs.

**Scope:** Build tooling that extracts actionable insights from JSONL:

- **Cost tracking:** actual $ per story, per model, per epic
- **Prompt effectiveness:** correlation between prompt size/content and
  success rate
- **Failure patterns:** which story types fail most, which check types
  catch real bugs vs false-green
- **Budget tuning:** optimal `max_turns` and `max_budget_usd` per story type

**Deliverables:**
- `scripts/analyse_logs.py` — JSONL analytics (reads all `epic.jsonl`
  and `story.jsonl` files)
- Dashboard output (markdown report or terminal summary)
- Prompt template adjustments based on findings
- Budget recommendation report (suggested values per story type)

### 10.5 Parallel Story Execution

**Trigger:** V2 sequential execution is stable; independent stories
identified in plans that could run concurrently.

**Scope:** Stories with no shared file scope can run in parallel on
separate git worktrees. The orchestrator spawns multiple agents and
merges results.

**Complexity:**
- Worktree creation and cleanup automation
- Merge conflict detection and resolution strategy
- Validation checkpoints across parallel branches
- Story dependency graph (which stories can run concurrently)
- JSONL logs per worktree, merged into epic-level log

**Deferred because:** Merge conflict resolution is hard. V2 sequential
execution eliminates this class of problems entirely. Only pursue
parallel execution when sequential is stable AND epic throughput becomes
a bottleneck.

### 10.6 Crash Recovery Hardening

**Trigger:** V2 crash recovery (resume from last event in JSONL) has
been exercised in practice; edge cases discovered.

**Scope:** Harden the resume logic:
- Handle partial JSONL writes (truncated last line)
- Handle agent that committed code but didn't log completion
- Handle orphaned MCP server processes after crash
- `just epic-resume <N>` command that picks up from last good state

### 10.7 Plan Quality Feedback

**Trigger:** Multiple plans have been generated and executed; patterns
in plan quality → execution success are visible.

**Scope:** Feed execution outcomes back into planning:
- Which story sizing patterns led to successful single-attempt completions?
- Which acceptance criteria formats caught real issues vs false-greened?
- Which implementation notes were actually useful to agents?

**Deliverables:**
- Post-epic plan review script (compares `plan.json` predictions to
  JSONL actual outcomes)
- Planning prompt refinements based on findings
- Updated story sizing guidance with data-backed thresholds

---

## 11. Foundational Contracts Summary

The V2 architecture is built on machine-readable contracts at every
interface. This is Design Principle 8 made concrete.

| Interface | Contract | Format | Schema |
|-----------|----------|--------|--------|
| **GitHub → Planner** | Epic ingestion | `EPIC.md` with YAML frontmatter | Loose (markdown body, YAML header) |
| **Planner → Orchestrator** | Plan specification | `plan.json` | **JSON Schema** (story specs, user journeys, validation checkpoints, agent configs) |
| **Planner → Verifier** | Plan for verification | `plan.json` + `EPIC.md` + `CONTEXT.md` | Same JSON Schema — verifier reads plan + original intent |
| **Verifier → Orchestrator** | Verification result | `--json-schema` structured output | **Typed JSON Schema** (journey_completeness, transition_coverage, intent_alignment, gap_detection, validation_sufficiency) |
| **Planner → Human** | Plan review | `PLAN.md` + verifier report | Narrative markdown + structured verification results |
| **Orchestrator → Agent** | Agent prompt | Assembled prompt string | **7-section template** (role, plan context, scope, notes, verification, failure, constraints) |
| **Orchestrator → Agent** | Agent config | `--agents` JSON | **CLI JSON spec** (model, tools, skills, MCP, maxTurns) |
| **Agent → Orchestrator** | Implementation result | Git commit + JSONL event | **JSONL event schema** (schema_v, run_id, story_id, attempt + event-specific fields) |
| **Validator → Orchestrator** | Validation result | `--json-schema` structured output | **Typed JSON Schema per check type** (status, results[], evidence fields) |
| **Orchestrator → GitHub** | Progress update | `gh issue comment` | Structured markdown comment template |
| **Orchestrator → Human** | Failure escalation | JSONL `exit_to_human` event | **JSONL event schema** with failure_category and context |

**The rule:** If two components communicate, a schema governs the
interface. If there's no schema, it's not a contract — it's a
suggestion. Schemas are versioned (`schema_v`)
so they can evolve without breaking running orchestrators.

**Canonical schema file paths:**

| Schema | File | Governs |
|--------|------|---------|
| Plan specification | `scripts/schemas/plan.schema.json` | `plan.json` structure, story specs, validation checkpoints |
| JSONL events | `scripts/schemas/jsonl-events.schema.json` | All JSONL event types, universal + story-scoped fields |
| Validation output | `scripts/schemas/validation-result.schema.json` | `--json-schema` for validation agents, evidence fields per check type |
| Verifier output | `scripts/schemas/verifier-result.schema.json` | `--json-schema` for plan verifier agent |

These files are the canonical contracts. The descriptions in this document
are explanatory — the schema files are authoritative. Schema files are
created during V2 implementation and committed to git.

**Single sources of truth:**
- `plan.json` is the single source of truth for what the orchestrator executes
- JSONL logs are the single source of truth for what happened
- `--json-schema` validation output is the single source of truth for pass/fail
- Git is the single source of truth for code state
- GitHub epic is the single source of truth for intent
