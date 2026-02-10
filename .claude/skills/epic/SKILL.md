---
name: epic
description: Unified epic lifecycle — plan, validate, fix, start, status.
context: fork
---

# Epic Skill

**Activation:** `/epic` command — unified lifecycle management for epics.

**Command:** `/epic` — See `.claude/commands/epic.md`

---

## Subcommands

| Command | Purpose |
|---------|---------|
| `/epic plan {n}` | Plan: context -> gray areas -> goals -> tasks -> materialise |
| `/epic validate {n}` | Pre-flight: check all tasks have AC, deps are valid |
| `/epic fix {n}` | Enrich sparse tasks (add AC, scope, fix deps) |
| `/epic start {n}` | Run TDD state machine (delegates to run_epic.py) |
| `/epic status {n}` | Show task states and blockers |

---

## Architecture

### Planning Pipeline (subagents)

| Phase | Agent/Script | Model | Purpose |
|-------|--------------|-------|---------|
| Context | `epic-context-loader` | haiku | Load wiki docs, write CONTEXT.md |
| Gray Areas | `epic-gray-area-analyst` | haiku | Detect areas, return questions |
| Goals | `epic-goal-backward` | sonnet | Derive truths, write GOALS.md |
| Tasks | `epic-task-breakdown` | sonnet | Break down, write TASKS.md |
| Materialise | `tasks_from_plan.py` | (deterministic) | Parse TASKS.md, write .tasks/ + created.json |

Interactive phases (Core Understanding, Gray Area Q&A, Decision Gate) run in the orchestrator.

**Agents:** Located in `.claude/agents/epic-*.md`

### Execution Pipeline (scripts)

| Step | Script | Purpose |
|------|--------|---------|
| Validate | `scripts/validate_tasks.py` | Pre-flight checks on task files |
| Execute | `scripts/run_epic.py run` | TDD state machine (red-green-validate) |
| Status | `scripts/run_epic.py status` | Show task states and blockers |

### State File Contract

| File | Written By | Read By |
|------|------------|---------|
| `CONTEXT.md` | epic-context-loader + orchestrator | epic-goal-backward |
| `GOALS.md` | epic-goal-backward | epic-task-breakdown |
| `TASKS.md` | epic-task-breakdown | `tasks_from_plan.py` |
| `created.json` | `tasks_from_plan.py` | run_epic.py, external tools |
| `.tasks/E{n}/tasks/T{id}.md` | `tasks_from_plan.py` or `/epic fix` | run_epic.py |

---

## `/epic plan {n}` — Planning Workflow

### CRITICAL: Always Plan Fresh

**Planning always starts from scratch.** The pipeline derives its own task breakdown from the epic body and codebase analysis.

- **Ignore existing GitHub issues** referenced in the epic body. They are irrelevant to planning.
- **Delete stale planning state** (`.planning/epics/{slug}/`) before starting.
- **Never ask** whether to reuse, reopen, or materialise from existing issues.
- If the epic body references closed child issues, **treat them as historical context only** — do not interact with them.

### CRITICAL: Everything Ships — No Deferral

**Every capability in the epic gets built. 100%. No tech debt. Nothing deferred.**

- **Never ask** "what's the ONE thing that must work" or "what's the core priority"
- **Never ask** what's "out of scope" or what to "defer to future phases"
- **Never suggest** reducing scope, cutting features, or building an MVP subset
- The epic defines the work. ALL of it gets planned. ALL of it gets built.
- During Core Understanding, ask what DONE looks like — enumerate every capability

### Phase Flow

1. **Setup** — Fetch epic from GitHub, derive slug, clean planning dir, start fresh
2. **Context Loading** — Dispatch `epic-context-loader` subagent
3. **Core Understanding** — Interactive: user provides full vision and completeness criteria
4. **Gray Areas** — Dispatch `epic-gray-area-analyst` + interactive Q&A
5. **Testing Strategy** — Interactive: confirm test patterns (REQUIRED)
6. **Goal-Backward** — Dispatch `epic-goal-backward` subagent
7. **Task Breakdown** — Dispatch `epic-task-breakdown` subagent
8. **Decision Gate** — Interactive: user approves or revises
9. **Materialise** — Run `tasks_from_plan.py` to write .tasks/ files

### Phase Prerequisites (MANDATORY)

**Before Goal-Backward phase, you MUST read:**
1. `references/goal-backward.md` — GTS test patterns and artifact mappings
2. `../wiki/GTS-Technical-Architecture.md#testing-strategy` — Official testing strategy
3. `../wiki/GTS-Technical-Architecture.md#domain-model` — Authoritative domain model
4. `libs/core/src/core/domain/` — Actual GTS entities

### READ Before DERIVE (MANDATORY)

**NEVER assume data models exist. ALWAYS read the source.**

Before deriving ANY artifact (model, repository, service, API):
1. Use the **Read tool directly** on the authoritative file — NO summarisation agents
2. Cite the exact file and line where the entity/field is defined
3. If you cannot cite a source, **STOP and ASK**

**GTS is source-agnostic.** Core domain models NEVER contain source-specific fields.

### Testing Strategy Phase (MUST NOT SKIP)

1. Confirm test levels: Regression -> Unit -> Integration -> E2E
2. Confirm test commands (ONLY `just` commands allowed)
3. **NEVER** use raw `docker compose exec`, `pytest`, or `python` for running tests
4. **NEVER** generate curl-based acceptance tests — use pytest patterns only

---

## `/epic validate {n}` — Pre-Flight Validation

Runs `scripts/validate_tasks.py {n}`. Checks:

- Every task has non-TODO acceptance criteria
- Every task has non-empty scope (file paths)
- Dependencies reference valid task IDs
- No circular dependencies
- Task files match expected format

Pass `--strict` to treat warnings as errors.

---

## `/epic fix {n}` — Enrich Sparse Tasks

Interactive workflow for fixing sparse or incomplete task files:

1. Run `validate_tasks.py {n}` to identify failing tasks
2. For each failing task:
   a. Read the GitHub issue body (if referenced) for Goal/Why content
   b. Read the epic body for phase descriptions
   c. **Ask the user** to confirm/provide acceptance criteria
   d. **Ask the user** to confirm/provide scope file paths
   e. Write the updated task file
3. Re-run validation to confirm all tasks pass

### Rules for Fixing

- Preserve existing State field (don't reset complete tasks)
- Keep task IDs unchanged (never renumber)
- Source AC from: GH issue body, epic body phases, wiki IMPLEMENTATION.md
- Source scope from: existing codebase structure, architectural patterns
- Every task must be complete — no deferral, no tech debt

---

## `/epic start {n}` — TDD Execution

Delegates to `scripts/run_epic.py run {n}`.

Pre-flight validation runs automatically before the state machine starts.
If validation fails, it halts with instructions to run `/epic fix {n}`.

---

## `/epic status {n}` — Status Display

Delegates to `scripts/run_epic.py status {n}`.

Shows: total/complete/actionable/blocked counts, task details, and index path.

---

## Container-First Commands (MANDATORY)

| Action | Use This | NEVER This |
|--------|----------|------------|
| Run tests | `just test-unit`, `just test-integration` | `pytest`, `python -m pytest` |
| Run E2E | `just test-golden-path` | `cd tests/e2e && pytest` |
| Single test | `just tdd <path>` | `docker compose exec webapp pytest` |
| Lint/types | `just check` | `ruff check`, `mypy` |
| Build frontend | `just build-astro` | `pnpm build` |

---

## Reference Files (READ BEFORE EACH PHASE)

| File | When to Read | Purpose |
|------|--------------|---------|
| `references/question-bank.md` | Before Core Understanding | GTS-specific questions |
| `references/gray-areas.md` | Before Gray Areas | Detection patterns |
| `references/goal-backward.md` | **Before Goal-Backward** | Planning guide with GTS test patterns |

---

## Context Sources (MUST READ)

| Source | Path | Purpose |
|--------|------|---------|
| Implementation Plan | `../wiki/IMPLEMENTATION.md` | Phase scope, deliverables |
| Architecture | `../wiki/GTS-Technical-Architecture.md` | Stack, domain model |
| Agent Guide | `AGENTS.md` | Development workflow, rules |

---

## Task Quality Criteria

Each task must have:
- [ ] Clear objective (2-3 sentences)
- [ ] Specific acceptance criteria (checkboxes, 3-15 items)
- [ ] Each task stays within a single layer boundary
- [ ] Exact GTS file paths in scope
- [ ] Dependencies noted (Blocked by: T{n})
- [ ] Project label assigned
- [ ] Breaking changes split into companion tasks

**Test:** Could a different Claude instance execute this task without asking clarifying questions?

### Sizing

- Completable in 1-2 work sessions (~15-60 minutes)
- No more than ~200-400 lines of changes
- Max 3 implementation files, max 15 tests
- If scope lists >3 Create files OR >5 total files, split the task

### Split Patterns

| Pattern | When |
|---------|------|
| **Vertical slice** | Full feature for narrow scope |
| **Layer slice** | Repository, then service, then API |
| **Phase slice** | Schema/migration, then implementation, then tests |

### Split Triggers

- Task touches multiple components (backend + frontend + API)
- Task has multiple distinct acceptance criteria groups
- Task title contains "and"
- Any model-level breaking change requires a companion consumer-fix task

### Dependency Checklist

- [ ] No circular dependencies
- [ ] Foundation tasks (schema, models) come first
- [ ] Independent tasks identified for parallel execution waves
- [ ] Dependencies use explicit task references (Blocked by: T{n})

---

## GitHub CLI Requirements

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.

---

## State Persistence

Planning state persists in `.planning/epics/{slug}/`:

| File | Purpose |
|------|---------|
| `CONTEXT.md` | Locked decisions from gray area discussion |
| `GOALS.md` | Goal-backward analysis output |
| `TASKS.md` | Task breakdown before materialisation |
| `created.json` | Task ID mapping after materialisation |

Task execution state persists in `.tasks/projects/guitar-tone-shootout/epics/E{n}/`.
