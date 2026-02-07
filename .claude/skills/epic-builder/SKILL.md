---
name: epic-builder
description: Interactive epic creation with GTS-specific patterns. Transforms feature ideas into fully-specified GitHub issues through structured questioning, gray area analysis, and goal-backward planning.
context: fork
---

# Epic Builder Skill

**Activation:** Epic creation, feature planning, local task materialisation, TDD task breakdown

**Command:** `/epic-build` - See `.claude/commands/epic-build.md`

---

## Architecture

The epic-build command uses a subagent architecture to reduce context usage by ~78%:

| Phase | Agent/Script | Model | Purpose |
|-------|--------------|-------|---------|
| Context | `epic-context-loader` | haiku | Load wiki docs, write CONTEXT.md |
| Gray Areas | `epic-gray-area-analyst` | haiku | Detect areas, return questions |
| Goals | `epic-goal-backward` | sonnet | Derive truths, write GOALS.md |
| Tasks | `epic-task-breakdown` | sonnet | Break down, write TASKS.md |
| Materialise | `tasks_from_plan.py` | (deterministic) | Parse TASKS.md, write .tasks/ + created.json |

Interactive phases (Core Understanding, Gray Area Q&A, Decision Gate) run in the orchestrator.
Task materialisation is a deterministic Python script — no AI agent needed.

**Agents:** Located in `.claude/agents/epic-*.md`

---

## When to Use

- Planning a new feature from scratch
- Breaking down a sparse epic into tasks
- Creating GitHub issues with full specifications
- TDD task generation with proper dependencies

---

## Workflow Phases

| Phase | Mode | Purpose |
|-------|------|---------|
| Context Loading | Autonomous (subagent) | Load architecture, rules, codebase map |
| Core Understanding | Interactive | User provides vision, stories, boundaries |
| Gray Areas | Autonomous (subagent) + Interactive | Detect areas, user answers questions |
| Testing Strategy | Interactive | **REQUIRED** - Confirm test patterns |
| Goal-Backward | Autonomous (subagent) | Derive truths, artifacts, wiring |
| Task Breakdown | Autonomous (subagent) | Generate task structure |
| Decision Gate | Interactive | User approves or revises |
| Task Materialisation | Deterministic (script) | Parse TASKS.md → .tasks/ files + created.json |

### State File Contract

| File | Written By | Read By |
|------|------------|---------|
| `CONTEXT.md` | epic-context-loader + orchestrator | epic-goal-backward |
| `GOALS.md` | epic-goal-backward | epic-task-breakdown |
| `TASKS.md` | epic-task-breakdown | `tasks_from_plan.py` |
| `created.json` | `tasks_from_plan.py` | run_epic.py, external tools |

### Phase Prerequisites (MANDATORY)

**Before Goal-Backward phase, the subagent MUST:**
1. READ `references/goal-backward.md` - Contains GTS test patterns and artifact mappings
2. READ `../wiki/GTS-Technical-Architecture.md#testing-strategy` - Official testing strategy
3. READ `../wiki/GTS-Technical-Architecture.md#domain-model` - Authoritative domain model
4. READ `libs/core/src/core/domain/` directory structure - Actual GTS entities
5. Complete Testing Strategy phase with user (do NOT skip)

### READ Before DERIVE (MANDATORY)

**NEVER assume data models exist. ALWAYS read the source.**

Before deriving ANY artifact (model, repository, service, API):
1. Use the **Read tool directly** on the authoritative file - NO summarization agents
2. Cite the exact file and line where the entity/field is defined
3. If you cannot cite a source, **STOP and ASK**

**Forbidden:**
- Assuming fields exist because "they make sense"
- Deriving models from external system names (T3K, Tone3000, etc.)
- Using Task agents to summarize domain model (use Read tool directly)

**GTS is source-agnostic.** Sources (T3K, future providers) are adapters. Core domain models NEVER contain source-specific fields.

**Testing Strategy phase MUST:**
1. Confirm test levels: Regression → Unit → Integration → E2E
2. Confirm test commands (ONLY `just` commands allowed):
   - `just test-regression` - E2E quality gate (stack connectivity + endpoint validation)
   - `just test-unit` - Domain logic
   - `just test-integration` - Real DB
   - `just test-golden-path` - Full user journeys
   - `just tdd <path>` - Single test during TDD
3. **NEVER** use raw `docker compose exec`, `pytest`, or `python` commands for running tests
4. **NEVER** generate curl-based acceptance tests - use pytest patterns only

**Note:** `just` commands wrap the underlying execution (Docker for unit/integration, host for E2E). Implementation details are hidden - always specify `just` commands in acceptance criteria.

**Verification:** If your acceptance tests contain `curl` commands instead of pytest test names, STOP and re-read the testing documentation.

---

## Container-First Commands (MANDATORY)

**All commands MUST use `just`.** This is a container-first architecture.

| Action | Use This | NEVER This |
|--------|----------|------------|
| Run tests | `just test-unit`, `just test-integration` | `pytest`, `python -m pytest` |
| Run E2E tests | `just test-golden-path` | `cd tests/e2e && pytest` |
| Run single test | `just tdd <path>` | `docker compose exec webapp pytest` |
| Lint/type check | `just check` | `ruff check`, `mypy` |
| Build frontend | `just build-astro` | `pnpm build`, `npm run build` |
| Materialise tasks | `just plan {epic}` (step 7 auto-writes .tasks/) | `python scripts/tasks_from_plan.py` |

**Why:** All project code runs in Docker. The `justfile` wraps commands with correct container context, volumes, and environment.

**Verification:** If your task acceptance criteria contain raw `docker compose`, `python`, `pytest`, `ruff`, `mypy`, or `pnpm` commands, STOP and replace them with `just` equivalents.

---

## Reference Files (READ BEFORE EACH PHASE)

| File | When to Read | Purpose |
|------|--------------|---------|
| `references/question-bank.md` | Before Core Understanding | GTS-specific questions for each phase |
| `references/gray-areas.md` | Before Gray Areas | Detection patterns and area definitions |
| `references/goal-backward.md` | **Before Goal-Backward** | Planning guide with GTS test patterns |
| `references/github-templates.md` | Before Task Materialisation | Issue body templates (legacy, for reference) |

**CRITICAL:** These are not optional references. READ the relevant file BEFORE executing each phase.

---

## Context Sources (MUST READ)

**Primary Sources (READ during Context Loading phase):**

| Source | Path | Purpose |
|--------|------|---------|
| Implementation Plan | `../wiki/IMPLEMENTATION.md` | **Phase scope, archive mappings, deliverables** |
| Architecture | `../wiki/GTS-Technical-Architecture.md` | Stack, domain model, testing strategy |
| Agent Guide | `AGENTS.md` | Development workflow, rules |

**Secondary Sources (READ when relevant):**

| Source | Path | When |
|--------|------|------|
| Auth Rules | `.claude/rules/authentication.md` | Auth-related features |
| Test Policy | `.claude/rules/testing-policy.md` | Always for test specs |
| Frontend Rules | `.claude/rules/frontend-standards.md` | UI features |
| GitHub Rules | `.claude/rules/github.md` | All GitHub operations |

**CRITICAL: The wiki docs are authoritative.** If building from a GitHub issue that references `../wiki/IMPLEMENTATION.md`, you MUST read that file first. Do NOT rely on the issue body alone — the wiki contains archive mappings, dependency orders, and scope constraints.

---

## State Persistence

Epic building may span sessions. State persists in `.planning/epics/{slug}/`:

| File | Purpose |
|------|---------|
| `CONTEXT.md` | Locked decisions from gray area discussion |
| `GOALS.md` | Goal-backward analysis output |
| `TASKS.md` | Task breakdown before GitHub creation |
| `created.json` | Issue numbers after creation |

---

## GitHub CLI Requirements

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.

---

## Task Quality Criteria

Each task must have:
- [ ] Clear objective (2-3 sentences)
- [ ] Specific acceptance criteria (checkboxes)
- [ ] Each task has ≤15 acceptance criteria (split if more)
- [ ] Each task stays within a single layer boundary
- [ ] Exact GTS file paths in scope
- [ ] Dependencies noted (`Blocked by: #n`)
- [ ] `project:{workspace}` label

**Test:** Could a different Claude instance execute this task without asking clarifying questions?

---

## Integration with TDD Workflow

After epic planning completes (step 7 materialises tasks automatically):

```bash
# Check task status
just epic-status {epic}

# Start TDD orchestration
just epic-start {epic}
```

Tasks are materialised locally by `tasks_from_plan.py` during planning step 7.
No separate sync step is needed. The epic GH issue body is updated with a task summary.

**Note:** Always use `just` commands, never direct `python scripts/...` calls. See `.claude/rules/container-execution.md`.
