---
name: epic
description: Epic lifecycle -- ingest, plan, execute, status. Behavioural validation workflow.
argument-hint: "<epic-number> [run|status|validate-plan]"
context: fork
---

# Epic Skill

**Activation:** `/epic` command -- lifecycle management for epics using the behavioural validation workflow.

**NEVER run `just --list` or search for commands.** All commands are listed below. Use them exactly as written.

---

## Dispatch (EXECUTE IMMEDIATELY)

The user's arguments are provided as the input to this skill. Parse them and run the matching command. Do NOT ask clarifying questions. Do NOT search for commands.

**Argument matching rules** (args may arrive as just the number, or with the full `/epic` prefix):

| Args pattern | Run this immediately |
|-----------|---------------------|
| `<N>`, `run <N>`, `/epic <N>`, `/epic run <N>` | `yes \| just epic <N>` |
| `status <N>`, `/epic status <N>` | `just epic-status <N>` |
| `validate-plan <N>`, `/epic validate-plan <N>` | `just epic-validate-plan <N>` |

Where `<N>` is a number (the epic/issue number). A bare number like `112` means **run** that epic.

If no args provided (empty input), ask which epic number. That is the ONLY question you may ask.

---

## Commands

| Command | Purpose |
|---------|---------|
| `just epic <N>` | Full pipeline: ingest -> plan -> verify -> gate -> execute |
| `just epic-status <N>` | Show progress from JSONL logs |
| `just epic-validate-plan <N>` | Validate plan.json against schema (Phase A only) |

---

## Architecture

### Planning Pipeline

| Phase | Script | Model | Purpose |
|-------|--------|-------|---------|
| Ingest | `scripts/epic_ingest.py` | (deterministic) | Fetch epic from GitHub, write EPIC.md |
| Context | `scripts/context_assembler.py` | (deterministic) | Assemble wiki + codebase context into CONTEXT.md |
| Scope | (orchestrator, interactive) | - | Human confirms scope, resolves gray areas |
| Plan | `scripts/plan_generator.py` | Opus | Goal-backward analysis -> PLAN.md + plan.json |
| Validate | `scripts/plan_validator.py` | (deterministic) | Phase A: schema + referential integrity checks |
| Verify | `scripts/plan_verifier.py` | Sonnet | Phase B: journey completeness, gap detection |
| Gate | (orchestrator, interactive) | - | Human approves, revises, or rejects |

### Execution Pipeline

| Phase | Script | Purpose |
|-------|--------|---------|
| Execute | `scripts/orchestrator.py run` | Dispatch stories, run validation checkpoints |
| Resume | `scripts/orchestrator.py run --resume` | Crash recovery from JSONL log |
| Status | `scripts/orchestrator.py status` | Read JSONL, report progress |

### File Structure Per Epic

```
.planning/epics/E<N>/
  EPIC.md           # Ingested GitHub issue (YAML frontmatter + body)
  CONTEXT.md        # Assembled context for planner
  PLAN.md           # Human-readable plan (narrative)
  plan.json         # Machine-readable plan (stories, checkpoints, truths)
  epic.jsonl        # Epic-level event log
  SUMMARY.md        # Post-epic summary generated from JSONL
  stories/
    <story_id>/
      story.jsonl           # Story-level event log
      prompt-attempt-N.md   # Logged agent prompts per attempt
```

---

## Planning Workflow

### CRITICAL: Always Plan Fresh

**Planning always starts from scratch.** The pipeline derives its own story breakdown from the epic body and codebase analysis.

- **Delete stale planning state** (`.planning/epics/E<N>/`) before starting
- **Never reuse** old plans or partial artefacts

### CRITICAL: Everything Ships -- No Deferral

**Every capability in the epic gets built. 100%. No tech debt. Nothing deferred.**

- **Never ask** "what's the ONE thing that must work" or "what's the core priority"
- **Never suggest** reducing scope, cutting features, or building an MVP subset
- The epic defines the work. ALL of it gets planned. ALL of it gets built.

### Phase Flow

1. **Ingest** -- Fetch epic from GitHub via `gh issue view`, write EPIC.md with YAML frontmatter
2. **Context Assembly** -- Read EPIC.md + wiki + codebase files, keyword scan for relevant areas, write CONTEXT.md (deterministic, $0)
3. **Interactive Scope** -- User confirms scope, resolves ambiguities, locks decisions
4. **Plan Generation** -- Opus performs goal-backward analysis: observable truths -> user journeys -> stories -> validation checkpoints. Produces PLAN.md + plan.json
5. **Schema Validation** -- Phase A: deterministic checks on plan.json (referential integrity, truth coverage, scope coherence, dependency ordering)
6. **Plan Verification** -- Phase B: Sonnet checks journey completeness, transition coverage, intent alignment, gap detection, validation sufficiency
7. **Decision Gate** -- Human approves, revises, or rejects
8. **Commit + Push** -- Planning artefacts committed to remote

### READ Before DERIVE (MANDATORY)

**NEVER assume data models exist. ALWAYS read the source.**

Before deriving ANY artefact:
1. Use the **Read tool directly** on the authoritative file -- NO summarisation agents
2. Cite the exact file and line where the entity/field is defined
3. If you cannot cite a source, **STOP and ASK**

**GTS is source-agnostic.** Core domain models NEVER contain source-specific fields.

---

## Execution Workflow

### Story Execution Loop

For each story in plan.json:

1. Check state assumption (if `"clean"`, reset DB before dispatch)
2. Run pre-flight checks (verify inputs from previous stories exist)
3. Construct prompt via `scripts/prompt_builder.py` (7-section: role, plan context, scope, implementation notes, verification, failure feedback, constraints)
4. Dispatch agent via `scripts/dispatch.py` (model, tools, skills, MCP from plan.json)
5. If validation checkpoint follows this story, dispatch read-only validation agent
6. On pass: log `story_complete`, proceed to next story
7. On fail: classify failure, retry (up to 2 attempts) or exit to human

### Failure Categories

| Category | Retry Policy |
|----------|-------------|
| `env` | 0 retries -- exit immediately (Docker down, MCP unavailable) |
| `upstream` | 0 retries -- exit to human (bug in earlier story's scope) |
| `scope` | 2 retries (plan references wrong path) |
| `implementation` | 2 retries (agent wrote incorrect code) |
| `unknown` | 2 retries (timeout, ambiguous error) |

### Validation Checkpoint Types

| Check Type | Model | MCP Required |
|------------|-------|-------------|
| `http` | haiku | none |
| `http+dom` | haiku | chrome-devtools |
| `browser+db` | sonnet | chrome-devtools |
| `api+response` | haiku | none |
| `process` | haiku | none |
| `screenshot` | sonnet | chrome-devtools |
| `regression` | haiku | none |
| `quality` | haiku | none |

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
| `references/question-bank.md` | Before interactive scope | GTS-specific questions |
| `references/gray-areas.md` | Before context assembly | Detection patterns |
| `references/goal-backward.md` | **Before plan generation** | Planning guide with GTS artefact mappings |

---

## Context Sources (MUST READ)

| Source | Path | Purpose |
|--------|------|---------|
| Architecture | `../wiki/GTS-Technical-Architecture.md` | Stack, domain model |
| Agent Guide | `AGENTS.md` | Development workflow, rules |

---

## GitHub CLI Requirements

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.

---

## State Persistence and Audit Trail

`.planning/` is tracked in git, forming a complete audit trail:

```
GitHub Issue (epic)
  -> .planning/epics/E<N>/    (planning: EPIC.md, CONTEXT.md, PLAN.md, plan.json)
  -> .planning/epics/E<N>/    (execution: epic.jsonl, stories/, SUMMARY.md)
```

All events logged to JSONL. JSONL is the source of truth for crash recovery, status reporting, and post-epic analysis.
