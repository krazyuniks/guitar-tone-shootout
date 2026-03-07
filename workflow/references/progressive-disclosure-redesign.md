# Workflow Redesign Checklist

This document is the implementation target for the epic workflow redesign now
tracked in GitHub issue #155. Reporting remains coordinated separately in #133.

The intended workflow is pull-based, progressive-disclosure, and tool-enabled:

- Agents get the current artefact they must operate on.
- Agents get the tools needed to discover anything else.
- Prompts define the task and constraints, not a large pre-chewed context dump.
- Artefacts, logs, and prior outputs carry context forward between dispatches.
- Human approval is explicit and cannot be bypassed by wrappers or defaults.

## Non-Negotiables

- Planning is agentic. The planner explores the repo with tools instead of
  being force-fed broad context.
- Revision prompts are targeted. They contain the current `plan.json` plus the
  exact Phase A or Phase B findings, nothing more.
- Execution prompts are progressive. Story agents receive only the story spec,
  prior story outputs they actually consume, and the tools required to inspect
  the repo and runtime.
- Test generation is post-implementation and cross-model. The implementer does
  not write or approve its own tests.
- All dispatches stream. If an agent is running, its transcript and metadata are
  visible while it runs.
- Unified dispatch logging is the source of truth. Prompt/response pairing,
  token counts, duration, turns, and transcript links must be recorded under one
  schema.
- Dead metadata must be removed. If a field is not consumed at runtime, it must
  not be required during planning.

## Current Drift To Remove

- `depends_on_summary` is still required by the planner, validator, and prompt
  builder even though execution already has real prior-story outputs.
- Planner, verifier, and planner revisions do not stream.
- Prompt and dispatch artefacts are written only after completion, which hides
  in-flight work.
- Legacy prompt logging still exists beside the unified dispatch log.
- The human decision gate is bypassed by `yes | just epic <N>` and non-TTY
  auto-approval logic.
- The desired post-implementation test-writing stage is still not wired into
  story execution.
- Docs and skills still describe removed stages and obsolete state gates.

## Ordered Patch Sequence

### 1. Remove schema friction before touching prompts

Goal: stop spending planner retries on obsolete metadata.

Files:
- `workflow/models.py`
- `workflow/plan_validator.py`
- `workflow/plan_generator.py`
- `workflow/prompt_builder.py`
- `workflow/report.py`
- `workflow/schemas/plan.schema.json`

Changes:
- Remove `depends_on_summary` from the plan schema and validator rules.
- Remove any planner guidance that asks the model to populate
  `depends_on_summary`.
- Remove any prompt-builder rendering that consumes `depends_on_summary`.
- Remove or update report/status code that expects the old field.
- Confirm there is no remaining runtime consumer before deleting the field.

Acceptance:
- `just epic-validate-plan 146` no longer fails on empty `depends_on_summary`.
- Planner revision is not triggered by dead metadata alone.

### 2. Finish unified dispatch logging

Goal: make unified dispatch logging real, not partial.

Files:
- `workflow/dispatch.py`
- `workflow/dispatch_log.py`
- `workflow/conversation_logger.py`
- `workflow/report.py`

Changes:
- Make every `dispatch_agent()` call stream through `conversation_log`.
- Persist prompt metadata and prompt file at dispatch start, not only on
  completion.
- Record transcript file paths in the unified dispatch log.
- Remove `_log_dispatch_prompt`, `codex-response-*`, `last-planner-output.txt`,
  and any other ad-hoc logging side paths.
- Keep one JSONL schema for dispatch summaries and one transcript schema for
  streamed events, both documented and stable.

Acceptance:
- Planner, verifier, planner_revision, implementation, critique, and
  test_writer all emit live transcript events.
- An in-flight dispatch is visible in `dispatch.jsonl` before it exits.
- There is no legacy prompt/response logging path left in use.

### 3. Enforce the human decision gate

Goal: remove silent plan approval paths.

Files:
- `.claude/skills/epic/SKILL.md`
- `workflow/cli.py`

Changes:
- Remove `yes | just epic <N>` from the skill.
- Remove any non-TTY or auto-approve code path that marks the plan approved.
- Require an explicit human approve/revise/reject action after Phase B.

Acceptance:
- Planning cannot pass the gate without an explicit human decision.
- Running the skill non-interactively does not auto-commit plan artefacts.

### 4. Make planning truly progressive-disclosure

Goal: planner gets the task and the tools, not a bloated synthetic brief.

Files:
- `workflow/plan_generator.py`
- `workflow/plan_verifier.py`
- `workflow/cli.py`
- `workflow/context_assembler.py`
- `workflow/gap_detection.py`

Changes:
- Keep plan generation input to `EPIC.md` plus schema and planning rules.
- Keep Phase A and Phase B revision prompts targeted to `plan.json` plus the
  exact findings.
- Remove any remaining dependency on `CONTEXT.md` or gap-detection artefacts
  from the planning path.
- Treat the planner as a repo-exploring agent, not a passive recipient of
  assembled context.

Acceptance:
- Initial planner prompt stays small and task-focused.
- Planner revisions do not cold-restart with broad context.
- The planning pipeline no longer depends on `CONTEXT.md` or
  `user-decisions.json`.

### 5. Make execution prompts use real prior outputs

Goal: pass forward actual context rather than planner-authored summaries.

Files:
- `workflow/prompt_builder.py`
- `workflow/orchestrator.py`
- `workflow/story_executor.py`

Changes:
- Build story prompts from the story spec, current repo state, and actual
  outputs logged by prior stories.
- Only include prior-story context that the current story actually consumes.
- Keep tool access broad enough for the agent to inspect repo/runtime details
  itself.

Acceptance:
- Story prompts do not rely on synthetic `depends_on_summary`.
- Execution context is derived from real artefacts and logs.

### 6. Restore post-implementation test writing

Goal: preserve cross-model integrity if a dedicated test-writing lane is
reintroduced.

Files:
- `workflow/orchestrator.py`
- `workflow/test_generator.py`
- `workflow/story_executor.py`
- `workflow/default_config.toml`

Changes:
- Reintroduce a per-story `test_writer` dispatch after implementation succeeds.
- Feed the test writer the story's `test_spec` plus the actual implementation.
- Let the implementer fix code in response to failing generated tests, but do
  not let the implementer author the tests.
- Remove stale `tests_approved` and frozen upfront test-generation paths.

Acceptance:
- Story execution order is implementation -> validation -> test writing ->
  critique, or implementation -> test writing -> validation if validation is
  defined against generated tests.
- `workflow/test_generator.py` is on a live orchestrator path again.

### 7. Align status, report, and docs with the real pipeline

Goal: remove stale documentation and reporting drift.

Files:
- `workflow/report.py`
- `workflow/orchestrator.py`
- `AGENTS.md`
- `.claude/skills/epic/SKILL.md`
- `../wiki/Epic-Workflow.md`

Changes:
- Remove references to retired stages, gates, and artefacts.
- Update status/report views to reflect streaming dispatches and unified logs.
- Document the actual 2-command epic flow and the real decision gate.

Acceptance:
- A new engineer can read the docs and predict the runtime behavior correctly.
- Status/report output matches the current pipeline and log structure.

## Suggested Implementation Order

Apply the changes in this order:

1. Schema cleanup (`depends_on_summary` and other dead metadata)
2. Unified dispatch logging completion
3. Human gate enforcement
4. Planning path cleanup
5. Execution-context cleanup
6. Post-implementation test generation
7. Docs and report alignment

This order removes the current waste first, then fixes visibility, then fixes
workflow correctness.

## Done Means

The redesign is complete when all of the following are true:

- A planner run does not re-dispatch just to fill obsolete metadata.
- Every agent dispatch streams live output and writes unified log records.
- The human decision gate cannot be skipped.
- Planner and verifier prompts are lean and task-scoped.
- Story execution receives real prior outputs instead of planner-authored
  summaries.
- Test generation happens after implementation by a different agent.
- Docs, skills, status, and report output all describe the same workflow the
  code actually runs.
