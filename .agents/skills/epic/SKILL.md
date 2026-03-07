---
name: epic
description: Epic lifecycle commands for the current orchestrated workflow.
argument-hint: "<epic-number> [run|status|validate-plan|report]"
context: fork
---

# Epic Skill

Run the matching command immediately. Do not invent alternate commands.

## Dispatch

| Args pattern | Run |
|---|---|
| `<N>`, `run <N>`, `/epic <N>`, `/epic run <N>` | `just epic <N>` |
| `status <N>`, `/epic status <N>` | `just epic-status <N>` |
| `validate-plan <N>`, `/epic validate-plan <N>` | `just epic-validate-plan <N>` |
| `report <N>`, `/epic report <N>` | `just epic-report <N>` |
| `brainstorm <N>`, `/epic brainstorm <N>` | Load `brainstorm.md` and follow it |
| `deps <N>`, `/epic deps <N>` | Load `deps.md` and follow it |
| `next`, `/epic next` | Load `next.md` and follow it |

If args are empty, ask for the epic number.

## Live Workflow Contract

- `just epic <N>` is idempotent.
- First run: ingest -> plan -> verify -> human gate -> commit.
- Second run: execute committed stories.
- Planning is issue-first and tool-equipped.
- The planner explores the repo directly.
- The verifier critiques against the original epic contract.
- The human gate is explicit and cannot be bypassed.

## Commands

| Command | Purpose |
|---|---|
| `just epic <N>` | Full epic pipeline |
| `just epic-status <N>` | Read current epic state |
| `just epic-validate-plan <N>` | Run deterministic Phase A only |
| `just epic-report <N>` | Generate HTML report |

## Rules

- Never run `yes | just epic <N>`.
- Never describe `CONTEXT.md`, gap detection, or `review-tests` as part of the live pipeline.
- Never auto-approve a plan.
- Treat the GitHub issue as the source of truth.
- If you need the detailed workflow reference, read `../wiki/Epic-Workflow.md`.

## Artefacts

The active epic directory is `.planning/epics/E<N>/`.

Key files:
- `EPIC.md`
- `plan.json`
- `PLAN.md`
- `epic.jsonl`
- `dispatch.jsonl`
- `dispatches/`
- `REPORT.html`
