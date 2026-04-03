---
name: epic
description: Epic lifecycle -- ingest, plan, execute, status. Behavioural validation workflow.
argument-hint: "<epic-number> [run|status|validate-plan]"
context: fork
---

# Epic Skill

**Activation:** `/epic` command -- lifecycle management for epics using the
current issue-first workflow.

**NEVER run `just --list` or search for commands.** All commands are listed
below. Use them exactly as written.

---

## Dispatch (EXECUTE IMMEDIATELY)

**User arguments: `$ARGUMENTS`**

Parse the arguments above and run the matching command. Do NOT ask clarifying
questions. Do NOT search for commands.

**Argument matching rules** (args may arrive as just the number, or with the
full `/epic` prefix):

| Args pattern | Run this immediately |
|---|---|
| `run <N>`, `/epic run <N>` | `just epic <N>` |
| `brainstorm <N>`, `/epic brainstorm <N>` | Load `brainstorm.md` skill and follow it |
| `status <N>`, `/epic status <N>` | `just epic-status <N>` |
| `validate-plan <N>`, `/epic validate-plan <N>` | `just epic-validate-plan <N>` |
| `review-tests <N>`, `/epic review-tests <N>` | Load `review-tests.md` skill and follow it |
| `deps <N>`, `/epic deps <N>` | Load `deps.md` skill and follow it |
| `next`, `/epic next` | Load `next.md` skill and follow it |

Where `<N>` is a number (the epic or issue number).

**A bare number (for example `/epic 95`) is ambiguous.** Ask the user which
action they want:

> Epic #N — what would you like to do?
> 1. **brainstorm** — enrich the issue interactively before planning
> 2. **run** — execute the full pipeline
> 3. **status** — check progress from JSONL logs

If args are empty, ask which epic number, then ask which action.

---

## Commands

| Command | Purpose |
|---|---|
| `just map-codebase` | Refresh `.planning/codebase/` when repo maps are missing or stale |
| `just epic <N>` | Full pipeline: ingest -> repo-facts -> curation -> plan -> verify -> execute (gate only on unresolved planning failures) |
| `just epic-status <N>` | Show progress from JSONL logs |
| `just epic-validate-plan <N>` | Validate plan.json against schema (Phase A only) |

---

## Workflow Contracts

Read `workflow/references/workflow-architecture.md` for the canonical
invocation model and workflow type framework.

### Invocation Modes

| Mode | Runs in | Character |
|---|---|---|
| Autonomous | `just` | Runs to completion or the next gate without requiring conversation. |
| Gate | `just` | Stops cleanly at a human decision point and is safe to re-run. |
| Interactive | `/epic brainstorm` | User-in-the-loop exploration and issue refinement. |

### Workflow Types

| Type | Use it when | Examples |
|---|---|---|
| Skill | The user must stay in the loop. | `/epic brainstorm`, `/epic next` |
| `just` command | The workflow can run deterministically by itself. | `just epic <N>`, `just check` |
| Hook | The system should enforce an invariant automatically. | mock gate, adherence check |
| Rule | Context should always shape behaviour without explicit invocation. | container execution, worktree branching |

### Current Epic Pipeline

**Principle: "No model marks its own homework."** Planning and execution use
cross-model verification rather than self-approval.

Planning pipeline:

1. Ingest the GitHub issue into `EPIC.md`
2. Build `repo_facts.json`
3. Generate `curation.json` and `CURATION.md`
4. Generate `plan.json` and `PLAN.md`
5. Run Phase A validation and Phase B verification
6. If verification still fails, stop at the decision gate
7. Commit and push planning artefacts

Execution continues from JSONL state when `just epic <N>` is re-run after
planning is committed.

### Gate Behaviour

- Run `just epic <N>` directly. Do not pipe `yes` into it.
- When the workflow stops at a gate, resolve the requested review or revision,
  then re-run the same `just` command.
- Re-running `just epic <N>` at an unresolved gate is expected and safe.
- If `.planning/codebase/` is missing and a workflow or skill needs mapper
  output, run `just map-codebase`.

### File Structure Per Epic

```
.planning/epics/E<N>/
  EPIC.md           # Ingested GitHub issue (YAML frontmatter + body)
  repo_facts.json   # Deterministic repo-grounding facts for the epic contract
  CURATION.md       # Human-readable curation handoff
  curation.json     # Machine-readable curation handoff
  PLAN.md           # Human-readable plan (narrative)
  plan.json         # Machine-readable plan (stories, checkpoints, truths)
  epic.jsonl        # Epic-level event log
  SUMMARY.md        # Post-epic summary generated from JSONL
  stories/
    <story_id>/
      story.jsonl         # Story-level event log
      prompt-attempt-N.md # Logged agent prompts per attempt
```

---

## Execution Workflow

### Story Execution Loop

For each story in `plan.json`:

1. Check state assumptions and pre-flight dependencies
2. Build the story prompt with `workflow/prompt_builder.py`
3. Dispatch the implementation agent via `workflow/dispatch.py`
4. Run the checkpoint after the story when required
5. On validation pass, run post-story critique
6. Retry or exit to human based on the failure category
7. After all stories pass, run the post-epic critique

### Failure Categories

| Category | Retry Policy |
|---|---|
| `env` | 0 retries -- exit immediately |
| `upstream` | 0 retries -- exit to human |
| `scope` | 2 retries |
| `implementation` | 2 retries |
| `unknown` | 2 retries |

### Validation Checkpoint Types

| Check Type | Model | MCP Required |
|---|---|---|
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
|---|---|---|
| Run tests | `just test-unit`, `just test-integration` | `pytest`, `python -m pytest` |
| Run E2E | `just test-golden-path` | `cd tests/e2e && pytest` |
| Single test | `just tdd <path>` | `docker compose exec webapp pytest` |
| Lint and types | `just check` | `ruff check`, `mypy` |
| Build frontend | `just build-astro` | `pnpm build` |

---

## Reference Files

| File | When to Read | Purpose |
|---|---|---|
| `workflow/references/workflow-architecture.md` | Before changing workflow contracts | Invocation model, artefact storage, mapper contract |
| `references/goal-backward.md` | Before plan generation | Planning guide with GTS artefact mappings |

---

## Context Sources

| Source | Path | Purpose |
|---|---|---|
| Architecture | `../wiki/GTS-Technical-Architecture.md` | Stack, domain model |
| Epic workflow wiki | `../wiki/Epic-Workflow.md` | Full orchestrator pipeline walkthrough |
| Agent Guide | `AGENTS.md` | Development workflow, rules |

---

## GitHub CLI Requirements

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with all `gh`
commands.

---

## State Persistence And Audit Trail

`.planning/` is tracked in git, forming a complete audit trail:

```
GitHub Issue (epic)
  -> .planning/epics/E<N>/    (planning: EPIC.md, repo_facts.json, curation.json, PLAN.md, plan.json)
  -> .planning/epics/E<N>/    (execution: epic.jsonl, stories/, SUMMARY.md, STORY_CONTEXT.md)
```

All events logged to JSONL. JSONL is the source of truth for crash recovery,
status reporting, and post-epic analysis.
