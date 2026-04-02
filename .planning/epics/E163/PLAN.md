# Plan: Epic #163

## Goal

Pipeline critique gates are advisory across all three stages (critique once, revise once, done), revision prompts are scoped to story block + diff + findings + AGENTS.md, every validation checkpoint triggers a git commit with dirty-file fail-fast, entry points are consolidated (just for non-interactive, CC for interactive), and ~1,970 lines of dead code are removed with all stale references cleaned.

## Observable Truths

1. All three critique gates (Phase B, story, epic) are advisory — critique once, revise once, done; no retry loops exist in any critique path
2. Unresolved critique findings are posted as GitHub comments on the epic issue and never block the pipeline
3. Story revision prompts include only: the story block from plan.json, the implementation diff, critique findings, and AGENTS.md
4. Phase B executes exactly one cycle: Codex critiques once, Opus revises once, Phase A re-validates the revision
5. If post-revision Phase A validation fails, findings are posted as a GitHub comment and the pipeline continues without retry
6. A git commit occurs at every validation checkpoint in story execution and epic-level validation
7. A dirty working tree causes immediate fail-fast with a clear error before any pipeline step begins
8. The Phase B critique-vs-revision diff is printed in the CC conversation for human review
9. Each pipeline step is invokable in exactly one environment: just for non-interactive, CC skills for interactive
10. Dead code files are deleted: workflow/context_assembler.py, workflow/gap_detection.py, workflow/test_generator.py, all V1 scripts/ modules, and their test files (~1,970+ lines removed)
11. All stale references to deleted modules are cleaned from schemas, artifacts, docs, skills, and event handlers

## User Journeys

### Journey J1: Pipeline operator running a full epic

Operator runs just epic 163. Phase A validates the plan (14 deterministic checks, hard gate). Phase B begins: Codex critiques the plan once. Opus revises based on findings once. Phase A re-validates the revision. If re-validation fails, findings are posted as a GitHub comment and the pipeline continues — no retry. The critique-vs-revision diff is printed in the CC conversation for human review. The committed plan triggers a git commit. Stories execute sequentially: each is implemented, validated at checkpoint (triggering a git commit), then critiqued once (advisory). If critique finds issues, one revision is attempted; any unresolved findings post as a GitHub comment. After all stories complete, epic critique runs once — unresolved findings post as a GitHub comment. Pipeline completes without any blocking retry loops.

**Truths covered:** 1, 2, 4, 5, 6, 7, 8
**Entry point:** /cli
**Critical transitions:**
- Terminal -> Phase A validation (just epic N)
- Phase A pass -> Phase B Codex critique (Automatic pipeline progression)
- Phase B critique -> Opus revision + Phase A re-check (Single-pass advisory cycle: critique once, revise once, re-validate)
- Phase A re-check failure -> GitHub comment posted (comment_on_epic() posts findings, pipeline continues)
- Validation checkpoint -> Git commit (robust_commit() called after each checkpoint)
- Story implementation -> Advisory story critique (Critique once, revise once, post unresolved as GH comment)
- All stories complete -> Advisory epic critique (Epic critique once, post unresolved as GH comment, done)
### Journey J2: Developer invoking individual pipeline steps and reviewing critique output

Developer opens terminal and runs just epic-validate-plan 163 to run Phase A only. Runs just epic-status 163 to check progress. Runs just epic 163 for the full pipeline. Each command maps to exactly one action via just — developer never needs to call ./wf directly. Interactive operations use CC skills. After the pipeline runs, developer opens the GitHub issue and reviews critique findings posted as comments. Developer also reviews the Phase B diff printed in the CC conversation.

**Truths covered:** 2, 3, 8, 9
**Entry point:** /cli
**Critical transitions:**
- Terminal -> Phase A validation only (just epic-validate-plan N)
- Terminal -> Pipeline status report (just epic-status N)
- Terminal -> Full pipeline execution (just epic N)
- GitHub issue -> Critique findings review (Comments posted by comment_on_epic())
### Journey J3: Developer verifying codebase health after dead code cleanup

Developer searches the codebase for imports of deleted workflow modules (context_assembler, gap_detection, test_generator). Zero results found. V1 scripts/ files are gone. Verifier schema no longer references gap_detection. Skill docs no longer mention context_assembler. just check passes clean with no broken imports or type errors. The codebase is ~1,970 lines lighter.

**Truths covered:** 10, 11
**Entry point:** /cli
**Critical transitions:**
- Search for deleted module imports -> Zero results (grep -r finds no import references to deleted modules)
- Run quality gate -> Clean pass (just check confirms no broken imports or type errors)

## Contract Decisions

| ID | Epic Contract | Repo Convention | Resolution | Affected Stories |
|---|---|---|---|---|
| CD1 | just is the sole non-interactive entry point for all pipeline steps | ./wf thin Python wrapper script exists at repo root, called by justfile targets; users could invoke ./wf directly bypassing just | bridge: just remains the sole user-facing entry point. ./wf remains as internal implementation detail called by justfile. AGENTS.md documents that users must use just commands, never ./wf directly. No code changes to wf needed — this is already the de facto pattern, only documentation formalises it. | `05-entry-points` |

## Stories

### Story: Advisory critique gates for story and epic (`01-advisory-gates`)

**Purpose:** Make story critique and epic critique advisory — critique once, revise once, done. Post unresolved findings as GitHub comments via a unified template. Remove retry loops from critique paths.

**Agent:**
- model: sonnet
- skills: []
- tools: [Read, Edit, Write, Bash, Grep, Glob]

**Scope:**
- Modify: `workflow/story_executor.py`
- Modify: `workflow/orchestrator.py`

### Acceptance Criteria

- Story critique in story_executor.py runs at most once per story — no retry loop exists in the critique path
- If story critique finds issues, exactly one revision attempt is made, then the pipeline continues regardless of outcome
- Epic critique in orchestrator.py runs at most once — no retry loop exists in the epic critique path
- Unresolved findings from both story and epic critique are posted as GitHub comments via comment_on_epic()
- A unified markdown comment template is used for all critique finding posts (story and epic use the same format)
- STORY_CONTEXT.md generation and dispatch adapter pattern are unchanged (regression boundaries)
- just check passes with no type or lint errors

### Architectural Context

- Story critique lives in story_executor.py:_run_story_critique() — dispatched via AgentAdapter with role='story_critique'
- Epic critique lives in orchestrator.py:_run_epic_critique() — dispatched via AgentAdapter with role='epic_critique'
- comment_on_epic() in orchestrator.py posts GitHub comments via gh api — reuse this for posting findings
- The current story execution loop in execute_story() has MAX_RETRIES=2 which drives the retry behaviour
- STORY_CRITIQUE_SCHEMA at dispatch.py:508 and EPIC_CRITIQUE_SCHEMA at dispatch.py:531 define critique output format

### Navigation Guide

- workflow/story_executor.py:781 — _run_story_critique()
- workflow/story_executor.py:1153 — execute_story() with MAX_RETRIES loop
- workflow/orchestrator.py:882 — _run_epic_critique()
- workflow/orchestrator.py:85 — comment_on_epic() helper
- workflow/dispatch.py:508 — STORY_CRITIQUE_SCHEMA
- workflow/dispatch.py:531 — EPIC_CRITIQUE_SCHEMA

**Implementation Notes:**
- The MAX_RETRIES=2 in execute_story() drives the current retry loop. Advisory means: implement → validate → critique once → if findings, revise once → post unresolved as GH comment → continue. MAX_RETRIES should become 1 or the retry mechanism should be replaced with a single-pass structure.
- comment_on_epic() already exists and works. Define a markdown template like: '## Critique Findings ({gate_type})\n\n{formatted_findings}\n\n*Advisory — pipeline continued.*'
- Do NOT modify STORY_CONTEXT.md generation or the AgentAdapter/dispatch pattern — these are regression boundaries.
- The critique schemas in dispatch.py should NOT be modified — they define the AI output format, not the pipeline behaviour.

**Truths Addressed:** 1, 2

---

### Validation Checkpoint: After Advisory critique gates for story and epic

**Type:** process
**Checks:**
- Type and lint checks pass after advisory gate changes (evidence: command, exit_code, output_tail) [cmd: `just check`]
- Story critique no longer retries — MAX_RETRIES is 1 or retry loop is removed from execute_story critique path (evidence: command, exit_code, output_tail) [cmd: `! grep -n 'MAX_RETRIES.*=.*2' workflow/story_executor.py`]
- comment_on_epic is called from story_executor.py for posting unresolved critique findings (evidence: command, exit_code, output_tail) [cmd: `grep -q 'comment_on_epic' workflow/story_executor.py`]
- comment_on_epic is called from orchestrator.py in the epic critique path for posting unresolved findings (evidence: command, exit_code, output_tail) [cmd: `grep -q 'comment_on_epic' workflow/orchestrator.py`]

---

### Story: Checkpoint git commits and dirty-file fail-fast (`02-checkpoint-commits`)

**Purpose:** Add robust_commit() calls at every validation checkpoint so progress is persisted to git. Add dirty-file detection that fails fast at pipeline entry with a clear error.

**Agent:**
- model: sonnet
- skills: []
- tools: [Read, Edit, Write, Bash, Grep, Glob]

**Scope:**
- Modify: `workflow/story_executor.py`
- Modify: `workflow/orchestrator.py`
- Modify: `workflow/git_helpers.py`
- Modify: `workflow/cli.py`

### Acceptance Criteria

- robust_commit() is called after each successful validation checkpoint in story execution (story_executor.py)
- robust_commit() is called after Phase A and Phase B validation in the epic flow (orchestrator.py or cli.py)
- A check_working_tree_clean() function exists in git_helpers.py that detects dirty working tree state
- Pipeline entry in cli.py calls check_working_tree_clean() and exits with a clear error message if the tree is dirty
- The dirty-file check runs before any pipeline step begins, not after
- just check passes with no type or lint errors

### Architectural Context

- robust_commit() exists at git_helpers.py:36 — handles git add, commit with proper error handling
- cli.py is the entry point for all just epic commands — dirty-file check goes at the top of the command handler
- Validation checkpoints in story_executor.py occur after implementation validation and after critique/revision
- Epic-level checkpoints in orchestrator.py/cli.py occur after Phase A, after Phase B, and after plan commit

### Navigation Guide

- workflow/git_helpers.py:36 — robust_commit() definition
- workflow/cli.py:444 — call to verify_with_revision_cycle (epic-level checkpoint location)
- workflow/cli.py:537 — existing robust_commit call in cli
- workflow/story_executor.py — validation checkpoint locations within execute_story()

**Implementation Notes:**
- Use git status --porcelain to detect dirty state. If output is non-empty, exit with message like 'Working tree is dirty. Commit or stash changes before running the pipeline.'
- Add check_working_tree_clean() to git_helpers.py alongside robust_commit(). Call it from cli.py before dispatching any pipeline command.
- robust_commit() should be called after successful validation, not after failures. Failed validations should not create commits.
- Identify checkpoint locations by searching for validation result handling (success paths) in story_executor.py and the epic-level flow.

**Truths Addressed:** 6, 7

---

### Validation Checkpoint: After Checkpoint git commits and dirty-file fail-fast

**Type:** process
**Checks:**
- Type and lint checks pass after checkpoint commit changes (evidence: command, exit_code, output_tail) [cmd: `just check`]
- robust_commit is called in story_executor.py at validation checkpoints (evidence: command, exit_code, output_tail) [cmd: `grep -q 'robust_commit' workflow/story_executor.py`]
- A dirty-file check function exists in git_helpers.py (evidence: command, exit_code, output_tail) [cmd: `grep -q 'def check_working_tree_clean\|def ensure_clean_tree\|def assert_clean_working_tree' workflow/git_helpers.py`]
- cli.py calls the dirty-file check before pipeline execution (evidence: command, exit_code, output_tail) [cmd: `grep -q 'check_working_tree_clean\|ensure_clean_tree\|assert_clean_working_tree' workflow/cli.py`]

---

### Story: Scope story revision prompts (`03-prompt-scoping`)

**Purpose:** Restrict story revision prompts to include only the story block from plan.json, the implementation diff, critique findings, and AGENTS.md. Remove excess context that wastes agent tokens.

**Agent:**
- model: sonnet
- skills: []
- tools: [Read, Edit, Write, Bash, Grep, Glob]

**Scope:**
- Modify: `workflow/prompt_builder.py`

### Acceptance Criteria

- Story revision prompts include the story block from plan.json (the specific story being revised)
- Story revision prompts include the git diff of the story's implementation
- Story revision prompts include the critique findings for the story
- Story revision prompts include AGENTS.md as project context
- Story revision prompts do NOT include the full plan, other stories, codebase maps, or other excess context
- just check passes with no type or lint errors

### Architectural Context

- prompt_builder.py constructs prompts for agent dispatch including story implementation and revision prompts
- AGENTS.md contains project conventions and architecture rules that agents need for context
- The story block is the specific story object from plan.json that the agent is implementing/revising

### Navigation Guide

- workflow/prompt_builder.py — main target file, find the story revision prompt construction
- AGENTS.md — project context included in revision prompts

**Implementation Notes:**
- Read prompt_builder.py fully to understand current prompt construction before making changes.
- The four components of a story revision prompt are: (1) story block JSON, (2) git diff of implementation, (3) critique findings, (4) AGENTS.md content.
- If the current prompt includes full plan.json, codebase maps, wiki content, or other stories — remove those inclusions from the revision prompt path specifically.
- Do NOT change the initial story implementation prompt — only the revision prompt used after critique.

**Truths Addressed:** 3

---

### Validation Checkpoint: After Scope story revision prompts

**Type:** process
**Checks:**
- Type and lint checks pass after prompt scoping changes (evidence: command, exit_code, output_tail) [cmd: `just check`]
- AGENTS.md is referenced in prompt_builder.py for inclusion in revision prompts (evidence: command, exit_code, output_tail) [cmd: `grep -q 'AGENTS.md\|agents_md\|agents_content' workflow/prompt_builder.py`]

---

### Story: Phase B single-pass critique-revise cycle (`04-phase-b-single-pass`)

**Purpose:** Rewrite the Phase B verification cycle to: Codex critiques once, Opus revises once, Phase A re-validates. If re-validation fails, post findings as GitHub comment and continue. Print the critique-vs-revision diff in the CC conversation for human review.

**Agent:**
- model: sonnet
- skills: []
- tools: [Read, Edit, Write, Bash, Grep, Glob]

**Scope:**
- Modify: `workflow/plan_verifier.py`
- Modify: `workflow/cli.py`
- Modify: `workflow/plan_generator.py`

### Acceptance Criteria

- verify_with_revision_cycle() in plan_verifier.py executes exactly one critique-revise cycle — no retry loop
- Codex critiques the plan once, then Opus revises the plan once based on critique findings
- After Opus revision, Phase A re-validates the revised plan automatically
- If post-revision Phase A fails, findings are posted as a GitHub comment via comment_on_epic() and the pipeline continues
- The diff between the pre-revision and post-revision plan is printed in the CC conversation for human review
- just check passes with no type or lint errors

### Architectural Context

- verify_with_revision_cycle() at plan_verifier.py:570 is the current retry loop that must become single-pass
- cli.py:444 calls verify_with_revision_cycle — this is the CC conversation context where the diff should be printed
- make_phase_b_revision_prompt() at plan_generator.py:492-691 constructs the prompt for Opus revision
- Phase A validation is a 14-check deterministic gate that can be called as a subroutine after revision
- comment_on_epic() from orchestrator.py:85 posts GitHub comments — import and use for Phase A failure

### Navigation Guide

- workflow/plan_verifier.py:570 — verify_with_revision_cycle() definition
- workflow/cli.py:444 — call site for verify_with_revision_cycle
- workflow/cli.py:307 — robust_commit import
- workflow/plan_generator.py:492 — make_phase_b_revision_prompt()
- workflow/orchestrator.py:85 — comment_on_epic() to import for GH comment posting

**Implementation Notes:**
- The core change is in verify_with_revision_cycle(): remove the while/for retry loop. New flow: (1) Codex critiques plan, (2) Opus revises plan, (3) run Phase A on revised plan, (4) if Phase A fails → post GH comment + continue, (5) return revised plan.
- For diff presentation: capture plan JSON before and after revision, compute a unified diff (Python difflib.unified_diff), print to stdout in the cli.py call site so it appears in the CC conversation.
- make_phase_b_revision_prompt() may need minor adjustments if it references iterative revision semantics (e.g. 'improve your previous revision'). Read the function to check.
- Import comment_on_epic from orchestrator into the module that handles Phase A failure posting, or pass it as a callback.

**Truths Addressed:** 1, 4, 5, 8

---

### Validation Checkpoint: After Phase B single-pass critique-revise cycle

**Type:** process
**Checks:**
- Type and lint checks pass after Phase B rewrite (evidence: command, exit_code, output_tail) [cmd: `just check`]
- verify_with_revision_cycle exists in plan_verifier.py (evidence: command, exit_code, output_tail) [cmd: `grep -q 'def verify_with_revision_cycle' workflow/plan_verifier.py`]
- No while-loop retry pattern exists in verify_with_revision_cycle — single-pass only (evidence: command, exit_code, output_tail) [cmd: `! python3 -c "import ast, sys; tree = ast.parse(open('workflow/plan_verifier.py').read()); funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'verify_with_revision_cycle']; whiles = [n for f in funcs for n in ast.walk(f) if isinstance(n, ast.While)]; sys.exit(1 if whiles else 0)"`]
- Phase B diff is computed and displayed — difflib or similar is used in cli.py or plan_verifier.py (evidence: command, exit_code, output_tail) [cmd: `grep -rq 'difflib\|unified_diff\|plan_diff\|revision_diff' workflow/plan_verifier.py workflow/cli.py`]
- Post-revision Phase A failure posts a GitHub comment instead of blocking (evidence: command, exit_code, output_tail) [cmd: `grep -q 'comment_on_epic' workflow/plan_verifier.py || grep -q 'comment_on_epic' workflow/cli.py`]

---

### Story: Entry point consolidation and documentation (`05-entry-points`)

**Purpose:** Audit and document that each pipeline step is invokable in exactly one environment. Ensure just is the sole non-interactive entry point and CC skills handle interactive operations. Formalise the ./wf bridge in AGENTS.md.

**Agent:**
- model: sonnet
- skills: []
- tools: [Read, Edit, Write, Bash, Grep, Glob]

**Scope:**
- Modify: `AGENTS.md`
- Modify: `justfile`

### Acceptance Criteria

- AGENTS.md documents the canonical entry point for each pipeline step (just commands for non-interactive, CC skills for interactive)
- AGENTS.md explicitly states that ./wf is an internal implementation detail and must not be invoked directly
- No duplicate or ambiguous entry points exist in justfile for the same pipeline step
- Every just epic-* command in the justfile maps to exactly one pipeline operation
- just check passes with no type or lint errors

### Architectural Context

- justfile lines 422-454 define epic workflow commands: epic, epic-status, epic-validate-plan, epic-report, epic-compile-prompts
- All justfile epic commands call ./wf with different subcommands
- ./wf is a 473-byte thin Python script that calls workflow.cli.main — it is NOT dead code
- CC skills in .claude/skills/epic/ handle interactive operations like /epic plan

### Navigation Guide

- justfile:422-454 — epic workflow command definitions
- wf — thin CLI wrapper script at repo root
- workflow/cli.py — CLI implementation with subcommands
- .claude/skills/epic/SKILL.md — interactive skill definitions

**Implementation Notes:**
- This story is primarily documentation and verification. Read the justfile epic commands, verify each maps to exactly one pipeline step, and update AGENTS.md accordingly.
- The ./wf script is a bridge (see CD1). Document it as internal only in AGENTS.md Epic Workflow section.
- If any justfile commands are redundant or ambiguous, consolidate them. If all commands are already clean, document the mapping.
- Do NOT modify ./wf or workflow/cli.py — the bridge decision means ./wf stays as-is.

**Truths Addressed:** 9

---

### Validation Checkpoint: After Entry point consolidation and documentation

**Type:** process
**Checks:**
- Type and lint checks pass (if any code was changed) (evidence: command, exit_code, output_tail) [cmd: `just check`]
- AGENTS.md documents that ./wf is internal and just is the canonical entry point (evidence: command, exit_code, output_tail) [cmd: `grep -q 'wf.*internal\|wf.*implementation detail\|never.*wf.*directly' AGENTS.md`]

---

### Story: Dead code removal and stale reference cleanup (`06-dead-code-removal`)

**Purpose:** Delete ~1,970 lines of dead workflow modules, V1 scripts, and their tests. Clean all stale references to deleted modules from schemas, artifacts, event handlers, docs, and skills.

**Agent:**
- model: sonnet
- skills: []
- tools: [Read, Edit, Write, Bash, Grep, Glob]

**Scope:**
- Modify: `workflow/artifacts.py`
- Modify: `workflow/schemas/verifier-result.schema.json`
- Modify: `workflow/dispatch.py`
- Modify: `workflow/jsonl_logger.py`
- Modify: `workflow/report.py`
- Modify: `workflow/plan_generator.py`
- Modify: `.claude/skills/epic/SKILL.md`
- Modify: `.claude/skills/epic/references/gray-areas.md`

### Acceptance Criteria

- All dead files deleted: workflow/context_assembler.py, workflow/gap_detection.py, workflow/test_generator.py
- All V1 script files deleted: scripts/orchestrator.py, scripts/plan_verifier.py, scripts/plan_generator.py, scripts/context_assembler.py
- All dead test files deleted: tests/unit/workflow/test_gap_detection.py, tests/unit/workflow/test_context_assembler.py, tests/unit/workflow/test_test_generator.py
- No import statements referencing deleted modules remain anywhere in the codebase
- gap_detection dimension removed from VERIFIER_DIMENSIONS tuple in artifacts.py
- TestReviewArtifact class removed from artifacts.py
- gap_detection property removed from verifier-result.schema.json
- Stale gap_detection references cleaned from dispatch.py docstrings, jsonl_logger.py comments, report.py event handlers, and plan_generator.py
- context_assembler references cleaned from .claude/skills/epic/SKILL.md and references/gray-areas.md
- If scripts/ directory is empty after deletion, the directory is removed
- just check passes with no type or lint errors — confirming no broken imports

### Architectural Context

- Dead workflow/ files have zero V2 imports — confirmed by grep. context_assembler.py (23,133 bytes), gap_detection.py (20,095 bytes), test_generator.py (20,631 bytes)
- Dead scripts/ V1 files are only imported by each other and scripts/orchestrator.py — all form a dead cluster
- VERIFIER_DIMENSIONS tuple in artifacts.py:17 includes gap_detection — this dimension name is used in verifier schema and prompts
- TestReviewArtifact in artifacts.py:1383-1428 was used by test_generator.py — becomes dead after its deletion
- report.py references gap_detection_started and gap_detection_complete event types at lines 53, 56, 332, 335, 456 — dead event handlers
- Skill path is .claude/skills/epic/ (not .agents/skills/epic/)

### Navigation Guide

- workflow/artifacts.py:17 — VERIFIER_DIMENSIONS tuple with gap_detection
- workflow/artifacts.py:1383-1428 — TestReviewArtifact class
- workflow/schemas/verifier-result.schema.json:30 — gap_detection property
- workflow/dispatch.py:901 — gap_detection docstring reference
- workflow/jsonl_logger.py:244 — test_generator comment reference
- workflow/report.py:53,56,332,335,456 — gap_detection event type references
- workflow/plan_generator.py:458,583 — gap_detection dimension references
- .claude/skills/epic/SKILL.md — context_assembler reference to clean
- .claude/skills/epic/references/gray-areas.md — context_assembler reference to clean

**Implementation Notes:**
- CRITICAL: Run liveness verification BEFORE deleting any file. For each dead file, run: grep -r 'from workflow.{module}\|import workflow.{module}' workflow/ tests/ scripts/ apps/ — confirm zero matches excluding the file itself and its own tests.
- Delete files using git rm so they are properly tracked in the commit.
- For VERIFIER_DIMENSIONS gap_detection entry: verify whether Phase B critique prompts reference this dimension by name. If the dimension is no longer evaluated by the AI critique, remove it entirely. If it is still referenced in critique prompts, rename it to something descriptive.
- The 'unused config UI' mentioned in the epic has no evidence in the codebase — no action needed for it.
- After all deletions and cleanups, run just check to confirm no broken imports. This is the most critical verification — a clean just check proves all references are resolved.
- If the scripts/ directory has no remaining .py files after deletion, remove the directory entirely (git rm -r scripts/).

**Truths Addressed:** 10, 11

---

### Validation Checkpoint: After Dead code removal and stale reference cleanup

**Type:** process
**Checks:**
- Type and lint checks pass — confirms no broken imports after deletion (evidence: command, exit_code, output_tail) [cmd: `just check`]
- All dead workflow files are deleted (evidence: command, exit_code, output_tail) [cmd: `test ! -f workflow/context_assembler.py && test ! -f workflow/gap_detection.py && test ! -f workflow/test_generator.py`]
- All V1 script files are deleted (evidence: command, exit_code, output_tail) [cmd: `test ! -f scripts/orchestrator.py && test ! -f scripts/plan_verifier.py && test ! -f scripts/plan_generator.py && test ! -f scripts/context_assembler.py`]
- All dead test files are deleted (evidence: command, exit_code, output_tail) [cmd: `test ! -f tests/unit/workflow/test_gap_detection.py && test ! -f tests/unit/workflow/test_context_assembler.py && test ! -f tests/unit/workflow/test_test_generator.py`]
- No import references to deleted modules remain in the codebase (evidence: command, exit_code, output_tail) [cmd: `! grep -rq 'from workflow\.context_assembler\|from workflow\.gap_detection\|from workflow\.test_generator\|from scripts\.orchestrator\|from scripts\.plan_verifier\|from scripts\.plan_generator\|from scripts\.context_assembler' workflow/ scripts/ tests/ apps/`]
- gap_detection removed from VERIFIER_DIMENSIONS in artifacts.py (evidence: command, exit_code, output_tail) [cmd: `! grep -q 'gap_detection' workflow/artifacts.py`]
- TestReviewArtifact removed from artifacts.py (evidence: command, exit_code, output_tail) [cmd: `! grep -q 'TestReviewArtifact' workflow/artifacts.py`]
- gap_detection removed from verifier result schema (evidence: command, exit_code, output_tail) [cmd: `! grep -q 'gap_detection' workflow/schemas/verifier-result.schema.json`]

---

### Validation Checkpoint: After Dead code removal and stale reference cleanup

**Type:** regression
**Checks:**
- Full quality gate passes after all changes — no regressions introduced (evidence: command, exit_code, output_tail) [cmd: `just check`]
- Workflow unit tests pass (excluding deleted test files) (evidence: command, exit_code, output_tail) [cmd: `just tdd tests/unit/workflow/`]

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| 1. All three critique gates (Phase B, story, epic) are advisory — critique once, revise once, done; no retry loops exist in any critique path | `workflow/story_executor.py`, `workflow/orchestrator.py`, `workflow/plan_verifier.py` (+2 more) | Advisory critique gates for story and epic, Phase B single-pass critique-revise cycle |
| 2. Unresolved critique findings are posted as GitHub comments on the epic issue and never block the pipeline | `workflow/story_executor.py`, `workflow/orchestrator.py` | Advisory critique gates for story and epic |
| 3. Story revision prompts include only: the story block from plan.json, the implementation diff, critique findings, and AGENTS.md | `workflow/prompt_builder.py` | Scope story revision prompts |
| 4. Phase B executes exactly one cycle: Codex critiques once, Opus revises once, Phase A re-validates the revision | `workflow/plan_verifier.py`, `workflow/cli.py`, `workflow/plan_generator.py` | Phase B single-pass critique-revise cycle |
| 5. If post-revision Phase A validation fails, findings are posted as a GitHub comment and the pipeline continues without retry | `workflow/plan_verifier.py`, `workflow/cli.py`, `workflow/plan_generator.py` | Phase B single-pass critique-revise cycle |
| 6. A git commit occurs at every validation checkpoint in story execution and epic-level validation | `workflow/story_executor.py`, `workflow/orchestrator.py`, `workflow/git_helpers.py` (+1 more) | Checkpoint git commits and dirty-file fail-fast |
| 7. A dirty working tree causes immediate fail-fast with a clear error before any pipeline step begins | `workflow/story_executor.py`, `workflow/orchestrator.py`, `workflow/git_helpers.py` (+1 more) | Checkpoint git commits and dirty-file fail-fast |
| 8. The Phase B critique-vs-revision diff is printed in the CC conversation for human review | `workflow/plan_verifier.py`, `workflow/cli.py`, `workflow/plan_generator.py` | Phase B single-pass critique-revise cycle |
| 9. Each pipeline step is invokable in exactly one environment: just for non-interactive, CC skills for interactive | `AGENTS.md`, `justfile` | Entry point consolidation and documentation |
| 10. Dead code files are deleted: workflow/context_assembler.py, workflow/gap_detection.py, workflow/test_generator.py, all V1 scripts/ modules, and their test files (~1,970+ lines removed) | `workflow/artifacts.py`, `workflow/schemas/verifier-result.schema.json`, `workflow/dispatch.py` (+5 more) | Dead code removal and stale reference cleanup |
| 11. All stale references to deleted modules are cleaned from schemas, artifacts, docs, skills, and event handlers | `workflow/artifacts.py`, `workflow/schemas/verifier-result.schema.json`, `workflow/dispatch.py` (+5 more) | Dead code removal and stale reference cleanup |
