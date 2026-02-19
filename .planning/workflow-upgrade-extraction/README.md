# Cross-Model Verification — Extraction Archive

Extracted 2026-02-19 from Claude Code session JSONL files.

## What Happened

The epic workflow was upgraded from single-model (Claude-only) to cross-model
(Opus + Codex) verification. No design document was written — the plan lived
only in session transcripts. This extraction preserves the full history.

## Timeline

| When (UTC)          | Session                  | What                                     |
|---------------------|--------------------------|------------------------------------------|
| Feb 18 21:21-01:53  | `8a4ba572` (design)      | Brainstormed mini-epic, pivoted to upgrading the existing epic workflow with Codex |
| Feb 19 01:53-02:07  | `e42f8bf1` (impl batch1) | Steps 1, 2, 7, 9: CodexAdapter, models, templates, MCP config |
| Feb 19 02:07-11:34  | `b6303e0a` (impl batch2) | Steps 3, 4, 5, 6, 8: plan_verifier, story_executor, orchestrator, JSONL schema |
| Feb 19 11:29        | Commit `871dab90`        | All changes committed to main |

## Files in This Archive

### Plans & Design

| File | Description |
|------|-------------|
| `00-cross-model-verification-plan.md` | **The 15K-char implementation plan** — 9 steps, file-by-file changes, dependency order, verification criteria |
| `00b-design-session-final-plan-output.md` | Final plan output from the design session (how Codex fits the existing pipeline) |
| `00c-design-session-all-analysis.md` | All substantial analysis from the design session (mini-epic critique, workflow comparison, architecture decisions) |

### Session Transcripts

| File | Description |
|------|-------------|
| `01-design-session.md` | Full conversation from design session — user requirements, Claude analysis, iteration |
| `02-implementation-batch1.md` | Implementation session 1 — CodexAdapter, templates |
| `03-implementation-batch2.md` | Implementation session 2 — verifier, executor, orchestrator, commit |

### Code Changes

| File | Description |
|------|-------------|
| `04-commit-diff.patch` | Full `git diff` for commit `871dab90` (986 insertions, 68 deletions, 11 files) |

### Wiki (Current State — Needs Updating)

| File | Description |
|------|-------------|
| `05-wiki-current-epic-workflow-reference.md` | Current operational reference — still says Sonnet for Phase B |
| `06-wiki-current-v2-behavioural-validation.md` | Current design rationale — still explains "why Sonnet not Opus" |
| `07-wiki-current-v2-implementation.md` | Current implementation plan — still specifies Sonnet for Phase B |

## What Changed (Before → After)

| Aspect | Before | After |
|--------|--------|-------|
| Plan verification (Phase B→C) | Sonnet agent, 5-dimension structured comparison | Codex read-only, adversarial cross-model review |
| Post-story critique | Did not exist | Opus read-only, reviews Codex implementation, shared retry budget |
| Post-epic critique | Did not exist | Opus read-only, final quality gate, hard fail to human |
| JSONL schema | v1 | v2 — new critique event types, adapter/role fields |
| Story implementation | Sonnet/Opus | Codex 5.3-gpt (high effort) |
| Principle | Single-model | No model marks its own homework |

## Documentation Gaps

These artefacts need updating to reflect the new cross-model workflow:

1. **Wiki: Epic-Workflow-Reference.md** — operational reference (Phase B→C, critique gates)
2. **Wiki: Epic-Workflow-V2-Behavioural-Validation.md** — design rationale (why Codex, not Sonnet)
3. **Wiki: Epic-Workflow-V2-Implementation.md** — implementation plan (updated steps)
4. **Skills: .claude/skills/epic/SKILL.md** — already partially updated
5. **AGENTS.md** — may need cross-model workflow summary
