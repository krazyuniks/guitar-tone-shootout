# Design Session — Final Plan Output (line 193)

That's a thorough picture. Here's the synthesis — what the epic workflow has that the mini-epic can borrow, and where they differ.

---

## Epic Workflow → Mini-Epic: Reusable Components

### 1. Deterministic Validation Layer ($0)

The epic's Phase A (`plan_validator.py`) runs 7 structural checks instantly, no tokens spent. The mini-epic has **nothing equivalent**. Before spending $1-2 on Codex validation (Phase 5), the mini-epic should run free structural checks:

| Epic Check | Mini-Epic Equivalent |
|---|---|
| Referential integrity (truths ↔ stories ↔ checkpoints) | Every success criterion in PLAN.md maps to at least one `02-implement-*.md` prompt |
| Truth coverage (every truth in a story + journey) | Every requirement traced to a prompt AND a verification command |
| Scope coherence (modify files exist, create parents exist) | Every "key file affected" in PLAN.md exists on disk |
| Dependency ordering (create before modify) | `02-implement-*` prompts reference files in correct order |
| Budget sanity | Prompt count reasonable, no empty prompts |

This could be a simple Python script or shell validation in Phase 4.5 (between prompt generation and Codex validation).

### 2. Revision Cycle Pattern

The epic's `verify_with_revision_cycle()` is sophisticated:
```
Phase A → fail → re-plan → Phase A retry
Phase A pass → Phase B → fail → re-plan → Phase A re-check → Phase B retry
Phase B revision causes Phase A regression → restore pre-revision plan
```

The mini-epic's Phase 6 (Validation Review) says "discuss findings, revise prompts if needed, may suggest re-running Phase 5." This is ad-hoc. Adopt the epic's structured cycle: **revise → re-validate → confirm no regressions**.

### 3. Command-Based Validation (Not Agent-Assessed)

The epic's `validation.py` resolves every check criterion to a shell command and determines pass/fail by **exit code**, not by asking an agent "did this work?" The mini-epic's `03-validate.md` asks Codex to "run tests and checks" — the agent decides what to run and self-assesses.

Instead: the mini-epic's validation prompt should specify exact commands from `PLAN.md` success criteria, run them, and report exit codes. Pass/fail is deterministic.

### 4. Failure Classification

The epic classifies every failure into 5 categories with different retry policies. The mini-epic's `run.sh` uses `set -euo pipefail` — every failure is identical. Adopt the taxonomy:

```bash
# In run.sh, wrap each step:
if ! run_step "$f"; then
    classify_and_handle "$f" "$?"
fi
```

### 5. Evidence Standards

The epic's `validation-result.schema.json` **bans generic phrases** ("looks good", "seems fine", "appears correct", "n/a") and requires check-type-specific evidence fields. The mini-epic should adopt this for `03-validate.md` — require specific observed values for each criterion.

### 6. Dispatch Adapter Pattern

The epic's `dispatch.py` wraps CLI invocations with:
- Budget controls (`--max-turns`, `--max-budget-usd`)
- Timeout (10 minutes)
- Transient failure retry (529 overloaded → retry with fallback model)
- Stdin piping (avoids arg length limits)

The mini-epic's `run.sh` uses raw `cat "$f" | codex --quiet`. Wrap each invocation in a dispatch function with timeout and retry.

### 7. JSONL Event Logging

The epic logs every event to append-only JSONL, enabling crash recovery (`get_resumable_state()`). The mini-epic has no execution audit beyond output files. Adding a lightweight event log to `run.sh` enables `--resume` after partial failure:

```bash
log_event() { echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"event\":\"$1\",\"step\":\"$2\"}" >> "$PLAN_DIR/events.jsonl"; }
```

### 8. Git Sync Pattern

The epic's `git_helpers.py` does `robust_commit()` (handles pre-commit hook retry) and `git_sync()` (fetch → merge → push with `--force-with-lease`). The mini-epic has no git operations during execution. Add per-step commits for rollback.

### 9. Domain-Filtered Prompt Construction

The epic's `prompt_builder.py` scans `<!-- domains: ... -->` tags in `.claude/rules/` and only includes relevant rules per story. The mini-epic's prompts embed "full project context" — which could be huge. Adopt selective context injection based on which files the implementation step touches.

### 10. Goal-Backward Methodology

The epic's `references/goal-backward.md` defines the 7-step methodology: goal → observable truths → user journeys → artefacts → wiring → checkpoints → stories. The mini-epic's Phase 1 brainstorm produces similar output but doesn't use the structured methodology. The mini-epic should require:
- Observable truths (verifiable statements about what must be TRUE)
- Key wiring (what must be CONNECTED)
- Verification commands (how to PROVE each truth)

---

## Where They're Fundamentally Different

| Aspect | Epic | Mini-Epic |
|---|---|---|
| **Scale** | Multi-story, multi-day | Single-session, few hours |
| **State** | Stateless orchestrator + JSONL | Shell script + output files |
| **Planning agent** | Opus with structured JSON output | Interactive brainstorm with human |
| **Execution** | Python orchestrator dispatches agents | Shell script pipes prompts to CLIs |
| **Cross-model review** | Single-model (Claude variants only) | Claude creates, Codex critiques |
| **Human involvement** | Decision gate only | Multiple interactive phases |
| **Infrastructure** | Docker, containers, services | Just the CLI tools |

The mini-epic is intentionally lighter. Don't over-engineer it into the epic. But the verification patterns transfer directly.

---

## Concrete Adoption Plan

**Borrow as-is (reference/adapt):**
1. `references/goal-backward.md` methodology → feed into Phase 1 brainstorm structure
2. Evidence reject list from `validation-result.schema.json` → embed in `references/validation-criteria.md`
3. Failure classification taxonomy → add to `run.sh`

**Build mini versions of:**
4. Deterministic validation script → `scripts/validate-prompts.sh` (Phase 4.5, $0)
5. Event logging → 5-line function in `run.sh`
6. Per-step git commits → 3 lines in `run.sh` loop
7. Dispatch wrapper → timeout + retry function in `run.sh`

**Adopt the pattern, not the code:**
8. Revision cycle → structured revise-revalidate-confirm in Phase 6
9. Command-based validation → `03-validate.md` runs explicit commands, reports exit codes
10. Domain-filtered context → selective rule injection in prompt templates

Want me to update `mini-epic-plan.md` with these changes incorporated?
