---
name: plan
description: Iterative epic planning with 8 phases. Analyse project context, process unprocessed issues, brainstorm, decompose into TDD tasks, recompute issue graph, and execute GitHub mutations.
---

# Iterative Epic Planning

**Activation:** Epic planning, issue decomposition, TDD task breakdown, roadmap management

## Usage

```
/plan <issue-url or number>   # Work on existing epic
/plan <topic>                 # Start new epic from scratch
/plan                         # Resume active planning session
```

## Core Philosophy

**The Epic is the source of truth.** Ideas flow through the epic, not directly to sub-issues.

```
Ideas -> Epic -> Sub-issues
          ^
       Iterate
```

- User interacts with the EPIC through planning cycles
- Sub-issues are DERIVED from the epic state
- Every GitHub mutation requires explicit user approval
- ANALYSE happens FIRST -- full project context before any planning
- RECOMPUTE is mandatory -- new work integrates into the issue graph

## Workflow States

```
ANALYSE          -> Full project context (worktrees, issues, deps) [MANDATORY]
PROCESS UNPROC.  -> Integrate unprocessed issues [MANDATORY]
SUMMARIZE        -> Show current state with impact analysis
BRAINSTORM       -> Explore ideas, one question at a time
  -> RESEARCH    -> (if needed) Web research
REFINE           -> Update epic content (draft)
DECOMPOSE (TDD)  -> Break into TEST + IMPL tasks
RECOMPUTE        -> Update issue graph [MANDATORY]
EXECUTE          -> GitHub mutations (requires approval)
DISPLAY          -> Show final state and next steps
```

User can exit at any state. Nothing is committed until EXECUTE.

See `references/plan-phases.md` for detailed phase descriptions.

## Key Principles

1. **Never Auto-Execute** -- all GitHub mutations require explicit "yes"
2. **Epic-First Thinking** -- update the epic, then derive sub-issues
3. **TDD is Mandatory** -- every feature has explicit TEST tasks blocking IMPL tasks
4. **Iteration Expected** -- running `/plan` multiple times is normal
5. **Explicit State Transitions** -- always tell the user what phase you're in
6. **Use /gh-workflow Skill** -- for GitHub CLI commands and dependency management

## Task Sizing Constraints

Tasks must be small enough for a single agent session (~30 turns). Oversized tasks are the #1 cause of TDD pipeline failures.

### Hard Limits

- **Max ~10-15 tests per task** — more than this overwhelms the implementer agent
- **Max 3 implementation files per task** — keeps scope focused
- **Single layer boundary per task** — don't mix repository + service + API in one task

### Splitting Rules

If acceptance criteria exceed 15 tests, split by:

1. **Layer**: Repository + Service = 1 task, API + Schemas = 1 task
2. **Domain entity**: Job tasks separate from Shootout tasks
3. **Complexity**: Simple CRUD separate from complex business logic

### Good Task Scoping

| Scope | Typical Tests | Example |
|-------|--------------|---------|
| Repository + Service for one entity | ~8-10 | "Gear repository and service" |
| API endpoints + schemas for one resource | ~10 | "Gear API endpoints" |
| Frontend page + template | ~5-8 | "Gear library page" |

### Bad Task Scoping

| Scope | Problem |
|-------|---------|
| Repository + Service + API for multiple entities | ~40+ tests, agent exhausts turns |
| Crossing bounded contexts in one task | Too many files, unclear scope |
| "Implement all CRUD for X" (all layers) | Should be 2-3 tasks |

### Terminology

| Term | Meaning | Command |
|------|---------|---------|
| golden-path test | E2E full user journey | `just test-golden-path` |
| unit test | Pure logic, no I/O | `just test` (Docker) |
| integration test | Real DB/Redis | `just test` (Docker) |
| regression test | Stack connectivity | `just test-regression` |

## CLI UX Rules

**CRITICAL:** One question at a time. Context immediately above the question. Never dump large tables then ask multiple questions. Summarise progress periodically.

## Reference Files

| File | Purpose |
|------|---------|
| `references/plan-phases.md` | Detailed phase descriptions and actions |
| `references/output-format.md` | Output templates for each phase |
| `references/review-criteria.md` | Plan review checklist and GitHub mutation rules |
