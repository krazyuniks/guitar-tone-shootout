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

## CLI UX Rules

**CRITICAL:** One question at a time. Context immediately above the question. Never dump large tables then ask multiple questions. Summarise progress periodically.

## Reference Files

| File | Purpose |
|------|---------|
| `references/plan-phases.md` | Detailed phase descriptions and actions |
| `references/output-format.md` | Output templates for each phase |
| `references/review-criteria.md` | Plan review checklist and GitHub mutation rules |
