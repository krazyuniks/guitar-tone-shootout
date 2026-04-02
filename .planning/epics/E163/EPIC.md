---
github_issue: 163
title: "Workflow pipeline: critique simplification, entry point consolidation, cleanup"
state: OPEN
labels: ["epic"]
fetched: 2026-03-29T19:33:53Z
---

## Summary

Simplify the workflow pipeline to match the manual workflow that actually works: critique once, revise once, move on. Remove cross-model gates that block on disagreement rather than defects. Consolidate entry points so each pipeline step has exactly one invocation environment. Remove dead code.

## Observable Outcomes

- [ ] Cross-model critique is advisory across all three gates (plan Phase B, story critique, epic critique) — critique once, revise once, done
- [ ] Unresolved critique findings are posted as GitHub comments for future iteration, never block the pipeline
- [ ] Story execution: implement → validate → critique → targeted revision (story block + diff + findings + AGENTS.md) → complete
- [ ] Plan Phase B: Codex critiques once → Opus revises once → Phase A re-check → done (no second Phase B dispatch)
- [ ] Epic critique: findings posted as GitHub comment → epic completes
- [ ] Git commit at every validation checkpoint; steps fail-fast on dirty files
- [ ] Phase B critique-vs-revision diff shown in CC conversation for human review
- [ ] Each pipeline step invokable in exactly one environment — `just` for non-interactive, Claude Code for interactive
- [ ] Dead code removed: context_assembler.py, gap_detection.py, test_generator.py, unused config UI (~1,970 lines)
- [ ] Stale schemas, docs, and skill references cleaned up

## Decisions

- Critique model: "critique once → revise once → done" uniformly across all gates
- Revision prompt scoping: story block + git diff + critique findings + AGENTS.md pointer (not full original prompt)
- Entry point split: `just` for what can't run in CC, CC for interactive phases — no overlap
- Phase B presentation: show critique→revision diff in CC conversation, refine UI iteratively

## Regression Boundaries

- JSONL state machine and crash-resume must continue to work
- Phase A deterministic validation (14 checks) unchanged
- Validation checkpoints (command-based correctness gate) unchanged
- STORY_CONTEXT.md inter-story memory unchanged
- Dispatch adapter pattern (Claude/Codex) unchanged
- `just epic-status`, `just epic-validate-plan`, `just epic-report` remain functional
