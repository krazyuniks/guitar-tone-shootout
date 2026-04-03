# Workflow Architecture

This document captures the workflow contracts agreed in GitHub issue `#166`.
It is the in-repo reference for how skills, `just` commands, hooks, rules,
and workflow artefacts are expected to relate.

## Invocation Modes

| Mode | Runs in | Character |
|---|---|---|
| Autonomous | `just` | Runs deterministically to completion or to the next gate. |
| Gate | `just` | Detects a human decision point, prints next-step instructions, exits cleanly, and is safe to re-run. |
| Interactive | Skill or command conversation | Open-ended discussion, research, and drafting with the user in the loop. |

### Gate Behaviour

- A gated `just` command must stop cleanly rather than guessing past a human
  decision.
- Re-running the same `just` command at the same unresolved gate must be safe
  and idempotent.
- After the human resolves the gate, re-running the same `just` command
  continues the pipeline.

## Workflow Types

| Type | When to use | Examples |
|---|---|---|
| Skill | Needs user conversation and does not have a fixed completion point. | `/epic brainstorm`, `/research`, code review |
| `just` command | Runs autonomously to completion or to the next gate. Deterministic and repeatable. | `just epic 166`, `just check`, `just map-codebase` |
| Hook | Enforces an invariant automatically on an event. | `mock-gate`, `adherence-check`, `block-adhoc-infra` |
| Rule | Always-on context that shapes behaviour without being explicitly invoked. | container execution, authentication, worktree branching |

The discriminator between a skill and a `just` command is simple: if the user
must stay in the loop, it is a skill; if the system can run to completion or to
the next gate, it is a `just` command.

## Artefact Storage

Skills do not own storage locations. Output goes where it naturally belongs.

- Planning artefacts live under `.planning/`.
- Issue state lives in GitHub.
- Prompt and debug artefacts live with the workflow stage that generated them.
- Some interactive work produces no file at all; the conversation is the output.
- Every autonomous workflow artefact must have a defined schema or typed model.
  A file location alone is not a contract.

Do not create new top-level artefact directories for workflow features when an
existing home already fits the output.

## Inter-Skill Contracts

Interactive skills do not have a formal contract system. They should:

- state their prerequisites plainly
- fail clearly if those prerequisites are missing
- leave sequencing to the user

Formal contracts matter in the autonomous workflow pipeline, where one stage
must hand structured artefacts to the next without a human in between.

## Autonomous Stage Contracts

The autonomous pipeline depends on explicit read and write contracts between
stages. Each stage should consume the previous stage's typed artefacts rather
than inventing ad-hoc inputs.

| Stage | Reads | Writes | Contract |
|---|---|---|---|
| Ingest | GitHub issue `#N` | `EPIC.md` | The issue contract is materialised as `EpicArtifact`. |
| Repo facts | `EPIC.md`, live repo, optional `.planning/codebase/` hints | `repo_facts.json` | `RepoFactsArtifact` is the deterministic repo-grounding contract for planning. |
| Curation | `EPIC.md`, `repo_facts.json`, optional mapper hints, repo docs | `curation.json`, `CURATION.md` | `CurationArtifact` is a bounded planner handoff, not a final plan. |
| Plan generation | `EPIC.md`, `repo_facts.json`, optional `curation.json`, plan schema | `plan.json`, `PLAN.md` | `PlanArtifact` is the execution contract the rest of the pipeline consumes. |
| Verification | `EPIC.md`, `repo_facts.json`, `plan.json`, optional `curation.json` | Phase A results, Phase B feedback, or a revised accepted plan | Verification checks the plan contract without silently replacing it. |
| Decision gate | `PLAN.md`, unresolved verification results | `plan_approved`, `plan_revised`, or `plan_rejected` event | Human resolution is recorded as the gate outcome only when verification cannot auto-resolve. |
| Execution | committed `plan.json`, `epic.jsonl`, repo state | story JSONL logs, critique events, `STORY_CONTEXT.md`, summary artefacts | Execution consumes the committed plan contract and appends runtime state. |

These contracts are both file-level and schema-level:

- file-level: each stage knows the stable path it reads from and writes to
- schema-level: each autonomous artefact has a typed structure, such as
  `EpicArtifact`, `RepoFactsArtifact`, `CurationArtifact`, `PlanArtifact`, or
  `RunArtifact`
- behavioural: downstream stages may reject missing or malformed inputs, but
  must not silently reinterpret them

## `/research` And `/epic brainstorm`

`/research` and `/epic brainstorm` are intentionally independent.

- `/research` is a general interactive exploration skill.
- `/epic brainstorm` is a GTS issue-enrichment skill that prepares a GitHub
  issue for `just epic <N>`.
- They may share thinking patterns, but they do not inherit from each other and
  do not require a shared contract layer.

## Architecture-Mapper-Workflow Contract

These layers form one dependency chain:

```text
Architecture document
    -> Codebase mapper
    -> Workflow
    -> Skills
```

Rules:

1. The architecture document is the source of truth for structure,
   conventions, and dependency boundaries.
2. The codebase mapper reflects implementation reality and should be organised
   to match the architecture shape.
3. The workflow reads both: architecture for intended design, mapper output for
   repo reality. When they disagree, architecture wins and the mismatch should
   be surfaced explicitly.
4. Skills may read both. Architecture is always available. Mapper output is a
   prerequisite when a skill depends on it; if it is missing, instruct the user
   to run `just map-codebase`.

## Current Epic Pipeline Contract

The live `just epic <N>` planning flow is:

1. Ingest the GitHub issue into `EPIC.md`
2. Build `repo_facts.json`
3. Generate `curation.json` and `CURATION.md`
4. Generate `plan.json` and `PLAN.md`
5. Run Phase A validation and Phase B verification
6. If verification still fails, stop at the human decision gate
7. Commit and push planning artefacts
8. Resume into execution from JSONL state when re-run

Retired planning stages such as `CONTEXT.md`, gap-detection handoff, and
`tests_approved` are not part of the active contract unless the code path is
explicitly reintroduced and the docs are updated to match.
