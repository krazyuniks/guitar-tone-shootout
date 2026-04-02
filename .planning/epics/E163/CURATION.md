# Curation: Epic #163

## Candidate Journeys

### Epic happy path (`CJ1`)

**Entry point:** just epic N triggers orchestrator.py which reads JSONL state and advances through plan → stories → critique → done
**Desired outcome:** Epic completes end-to-end with advisory critique gates, checkpoint commits at every validation boundary, and revision prompts scoped to story block + git diff + findings
**Key steps:**
- Plan ingested and Phase A validated (14 deterministic checks unchanged)
- Phase B critique runs advisory-only, findings posted to GitHub comment
- Stories execute sequentially with STORY_CONTEXT.md inter-story memory
- Story critique runs once, revision runs once if needed, then done
- Checkpoint git commit after every validation pass with dirty-file fail-fast
- Epic critique runs advisory-only, findings posted to GitHub comment

### Phase B critique-revise cycle (`CJ2`)

**Entry point:** Phase B advisory critique dispatched after plan_committed JSONL event
**Desired outcome:** Phase B findings are presented as a diff-annotated summary in CLI, posted to GitHub issue comment, and do not block execution
**Key steps:**
- Phase B critique dispatched via dispatch adapter (Claude/Codex preserved)
- Findings collected and formatted for GitHub comment
- CLI presents findings summary with diff context
- Human reviews advisory output (no blocking gate)
- Execution continues to story dispatch regardless of critique severity

## Story Slices

### Advisory critique gates (`SL1`)

Convert Plan Phase B, story critique, and epic critique from blocking cross-model gates to advisory-only: critique once, revise once, done. Unresolved findings posted to GitHub issue comments.

**Likely surfaces:**
- workflow/orchestrator.py
- workflow/dispatch.py
- workflow/cli.py

### Story revision prompt scoping (`SL2`)

Scope revision prompts to: story block + git diff + critique findings + AGENTS.md pointer. Remove bloated context from revision dispatch.

**Likely surfaces:**
- workflow/prompt_builder.py
- workflow/orchestrator.py

**Dependencies:**
- SL1

### Phase B simplification (`SL3`)

Simplify Phase B to present findings as diff-annotated summary in CLI and post to GitHub comment. Remove blocking retry loop.

**Likely surfaces:**
- workflow/orchestrator.py
- workflow/cli.py

**Dependencies:**
- SL1

### Checkpoint commits (`SL4`)

Git commit at every validation checkpoint with dirty-file fail-fast. Ensures crash-resume has clean state boundaries.

**Likely surfaces:**
- workflow/orchestrator.py

### Entry point consolidation (`SL5`)

Consolidate entry points: just commands for non-interactive, Claude Code for interactive. Update AGENTS.md documentation to match.

**Likely surfaces:**
- workflow/cli.py
- AGENTS.md
- scripts/epic_ingest.py

**Dependencies:**
- SL1
- SL3

### Dead code removal (`SL6`)

Remove ~1,970 lines of dead code: context_assembler.py, gap_detection.py, test_generator.py, unused config UI, and their tests. Verify script references before deletion.

**Likely surfaces:**
- workflow/context_assembler.py
- workflow/gap_detection.py
- workflow/test_generator.py
- workflow/artifacts.py
- scripts/context_assembler.py
- scripts/plan_verifier.py
- scripts/plan_generator.py
- tests/unit/workflow/test_test_generator.py

**Dependencies:**
- SL1
- SL2
- SL3
- SL4
- SL5

## Missing Assumptions

- **Assumption:** What happens when Phase A validation fails AFTER a story revision — does the story fail permanently or get a second revision pass?
  **Why it matters:** The 'critique once, revise once, done' model needs an explicit failure path when revision introduces new Phase A violations. Without this, the orchestrator may silently accept broken revisions or enter an undefined state.
  **Planner action:** Define explicit failure path: if Phase A fails post-revision, the story fails with findings posted to GitHub comment. No second revision pass.
- **Assumption:** The ~1,970 lines of dead code have been precisely identified and confirmed dead by the epic author
  **Why it matters:** If any of these modules are still called at runtime (especially gap_detection via plan_verifier.py and plan_generator.py), deleting them breaks the pipeline. The line count estimate may also be inaccurate.
  **Planner action:** SL6 must begin with grep verification of all import paths and call sites for each target module. Confirm scripts/plan_verifier.py and scripts/plan_generator.py liveness before removing gap_detection.
- **Assumption:** GitHub comment format for posting unresolved critique findings is not specified
  **Why it matters:** Multiple slices (SL1, SL3) need to post findings to GitHub comments. Without a defined format, each slice may implement differently, creating inconsistency.
  **Planner action:** Define a single GitHub comment template in SL1 that SL3 reuses. Format should include: critique source, severity, finding text, and relevant file/line references.
- **Assumption:** scripts/plan_verifier.py and scripts/plan_generator.py may themselves be dead code
  **Why it matters:** These scripts reference gap_detection (the deletion target). If the scripts themselves are dead, SL6 can delete them too. If alive, they need gap_detection references removed before gap_detection.py is deleted.
  **Planner action:** SL6 must verify whether plan_verifier.py and plan_generator.py are called by orchestrator.py, cli.py, or any just command before deciding to delete vs. edit them.

## Scope Tensions

- **Tension:** Advisory-only critique vs quality assurance
  **Tradeoff:** Making all critique gates advisory removes the safety net that catches plan/story defects before they land on main. The pipeline becomes faster but less guarded.
  **Planner guidance:** Phase A deterministic validation (14 checks) remains the hard gate and regression boundary. Advisory critique is for subjective quality — the planner should NOT soften Phase A. Checkpoint commits provide rollback points if advisory findings reveal serious issues post-merge.
- **Tension:** Dead code removal sequencing vs early wins
  **Tradeoff:** SL6 (dead code) is the easiest slice but depends on all others being stable first. Doing it early risks removing code that other slices reference during development. Doing it last delays the satisfying cleanup.
  **Planner guidance:** Keep SL6 last. The dependency is real: SL1-SL5 may temporarily reference modules that SL6 deletes. The planner should sequence SL6 after all functional changes are committed and passing.
- **Tension:** Entry point consolidation scope vs documentation drift
  **Tradeoff:** SL5 consolidates entry points and updates AGENTS.md. But AGENTS.md is read by every dispatched agent — errors propagate widely. Over-consolidation may remove entry points that edge-case workflows still need.
  **Planner guidance:** SL5 should audit actual usage (grep for just commands in orchestrator, cli, justfile) before removing any entry point. AGENTS.md updates must match the actual just commands that exist after consolidation.
- **Tension:** False positive in repo_facts: shiki pnpm-store JSON file flagged as JSONL edit target
  **Tradeoff:** The file frontend/astro/.pnpm-store/.../shiki@3.22.0.json contains 'JSONL'-like strings in package metadata. Editing it would corrupt the pnpm store.
  **Planner guidance:** Exclude ALL files under .pnpm-store/ from every story slice. The planner must not include this file in any edit target list. It is a false positive from repo_facts keyword matching.

## Planner Handoff

**Recommended story shape:** Each slice is a vertical cut through the orchestrator pipeline: change the gate/flow in orchestrator.py, update the prompt or CLI surface, verify with just epic-validate-plan, commit at checkpoint. SL6 is a horizontal sweep (delete dead modules + references) gated on all vertical slices being stable.

**Priority order:**
- SL1 — Advisory critique gates (unblocks SL2, SL3, SL5)
- SL4 — Checkpoint commits (independent, high safety value)
- SL2 — Story revision prompt scoping (depends on SL1)
- SL3 — Phase B simplification (depends on SL1)
- SL5 — Entry point consolidation (depends on SL1, SL3)
- SL6 — Dead code removal (depends on all others)

**Watchouts:**
- Do NOT edit any file under .pnpm-store/ — false positive from repo_facts
- Do NOT soften Phase A deterministic validation — it is the hard regression boundary
- Do NOT delete gap_detection.py before verifying plan_verifier.py and plan_generator.py liveness
- Do NOT change JSONL event type names without checking apps/webapp/src/webapp/api/pages/workflow.py which reads epic.jsonl
- Do NOT remove the dispatch adapter pattern (Claude/Codex) — it is explicitly preserved in the epic contract
- Do NOT change STORY_CONTEXT.md inter-story memory — it is explicitly preserved in the epic contract
