# Design Session — All Analysis & Discussion

This file contains all substantial assistant analysis from the design session.

---

## Assistant (line 90, 9110 chars, ts: 2026-02-18T22:46:42.274Z)

Now I have everything. Let me provide the full analysis.

---

## Mini-Epic Plan — Analysis & Critique

### What's Strong

The plan has excellent bones:

- **Audit trail** — immutable snapshots at every phase (ORIGINAL-PROMPT, PLAN-ORIGINAL, ANALYSIS, VALIDATION) create genuine traceability
- **Cross-agent review** — Claude creates, Codex critiques. No agent marks its own homework. This is the single most important pattern.
- **Self-contained prompts** — correctly assumes zero shared memory between agents
- **Phase 0 prompt optimisation** — catches ambiguity before it propagates through the entire pipeline
- **Disposable workspace** — `.planning/mini/` gitignored, working state separated from source code

### Structural Critiques

**1. Verification validates the *plan to build*, not *what was built***

This is the critical gap. Phase 5 (Implementation Validation) runs *before* execution. It checks whether the prompts are coherent and map to requirements. But after `run.sh` completes, the only verification is:

- `03-validate.md` — "Codex runs tests and checks" (one line of description, extremely thin)
- `04-review.md` — Claude Opus "architectural review" (not goal-backward)

Neither checks whether the original intent was actually delivered. Tests passing ≠ goal achieved.

**2. Step 00-decompose undermines Phase 5 validation**

Phase 5 validates the prompt files. But `00-decompose.md` *generates new implementation prompts at runtime*. So Phase 5 validated prompts that may be overwritten by Step 0 of execution. The prompts that actually run haven't been validated by anyone.

**3. Manual Codex handoff is friction**

Phases 2 and 5 say "paste this into Codex, type `done` when finished" — yet `run.sh` uses `codex --quiet` as a CLI. If Codex is CLI-capable, why is the interactive phase manual copy-paste? This inconsistency will be the first thing you abandon.

**4. No git checkpoints during execution**

If `02-implement-05` fails after `02-implement-01` through `04` have written to the codebase, there's no rollback point. `set -euo pipefail` stops execution but doesn't restore state.

**5. Self-assessed success criteria**

Each implementation prompt contains its own success criteria and verification commands. The implementing agent checks its own work. This violates the plan's own principle that "no single agent marks its own homework."

**6. No failure taxonomy**

When `run.sh` fails, all failures look the same. Is it an environment problem (Docker down)? A scope error (wrong file path in prompt)? An implementation bug? The GTS workflow's failure classification (`env` → 0 retries, `upstream` → exit to human, `implementation` → 2 retries) is far more actionable.

---

## Verification Comparison: Three Systems

| Dimension | Mini-Epic | GTS Epic Workflow | GSD Verifier |
|---|---|---|---|
| **When it runs** | Pre-execution only (Phase 5) | Pre-execution + per-story + post-epic | Post-implementation |
| **What it checks** | Prompt coherence, intent mapping | Structural integrity, narrative coherence, runtime evidence | Goal achievement via artifact inspection |
| **Verification model** | "Will this plan work?" | "Did each step produce evidence?" | "Does the codebase deliver the outcome?" |
| **Stub detection** | None | Rejects generic evidence phrases | 3-level: exists → substantive → wired |
| **Failure handling** | Stop on first error | Classify → retry or exit-to-human | Structure gaps → re-plan |
| **Cost** | ~$1-2 (one Codex pass) | $0 (Phase A) + ~$1-2 (Phase B) + per-story | ~$0.50 (grep/file checks, minimal AI) |
| **Re-verification** | Start over | Re-run story | Focus on failed items only |
| **Evidence standard** | Trust agent claims | Reject generic phrases, require specifics | Verify against actual codebase, don't trust summaries |
| **Gap output** | Prose in VALIDATION.md | JSONL events + human checklist | YAML frontmatter → actionable re-planning |
| **Human handoff** | "Discuss findings" | Checklist posted to GitHub issue | Explicit "needs human" items with test scripts |

### Key Insight from Each System

**GTS Epic:** Deterministic-first layering. Phase A costs $0 and catches structural errors before spending tokens. Evidence-based validation rejects "looks good" — requires `status_code`, `url`, `response_excerpt`. This prevents false-green.

**GSD Verifier:** Goal-backward thinking. "Task completion ≠ Goal achievement." Start from what must be TRUE, work backwards to what must EXIST, then to what must be WIRED. The three-level artifact check (exists → substantive → wired) catches 80% of stubs that pass existence checks.

**Mini-Epic:** Intent preservation tracing (ORIGINAL-PROMPT → PLAN → prompts) is genuinely novel and neither of the other systems do it pre-execution. But it needs a post-execution counterpart.

---

## Recommendations: Building a Robust Verifier

### Architecture: Three Verification Layers

```
Layer 1: Deterministic ($0)          ← From GTS
    just check (lint, types, tests, imports)
    File existence for all plan.md "key files affected"

Layer 2: Goal-Backward Artifact ($0) ← From GSD
    3-level check: exists → substantive → wired
    Anti-pattern scan (TODO, placeholder, stub)
    Key link verification (service→repo→API→template)

Layer 3: Intent Verification (~$1)   ← From Mini-Epic + GSD
    Trace: ORIGINAL-PROMPT → PLAN → codebase
    Success criteria matrix: every requirement → evidence
    Goal achievement assessment (not task completion)
```

### Specific Changes to the Mini-Epic Plan

**A. Add Phase 8: Post-Execution Verification**

After `run.sh` completes, a new verification phase runs all three layers. This is the missing piece. It should:

1. Run `just check` (deterministic, $0, catches regressions)
2. For every "key file affected" in PLAN.md, run GSD's 3-level check
3. For every success criterion in PLAN.md, verify evidence exists in the codebase
4. Scan all modified files for anti-patterns (TODO, placeholder, stub, empty handler)
5. Produce a VERIFICATION.md with structured gap output

**B. Replace self-assessed verification in implementation prompts**

Instead of each `02-implement-*.md` containing its own verification commands, have `03-validate.md` independently verify every step's success criteria. The implementation agent should only implement; a separate agent verifies.

**C. Add git checkpoints to run.sh**

```bash
# Before execution
git stash --include-untracked -m "mini-epic-pre-$(date +%s)"

# After each implementation step
git add -A && git commit -m "wip(mini-epic): step $(basename "$f" .md)"
```

This gives you rollback points and a diff-per-step audit trail.

**D. Resolve the 00-decompose paradox**

Either:
- Remove `00-decompose` and have Claude generate all implementation prompts in Phase 4 (simpler, already validated by Phase 5), **or**
- Add a lightweight validation after `00-decompose` and `01-verify-plan` complete but before `02-implement-*` starts

I'd recommend the former. Phase 4 already decomposes. Having Step 0 re-decompose at runtime creates two sources of truth.

**E. Add failure classification to run.sh**

```bash
if ! cat "$f" | codex --quiet --approval-mode full-auto; then
    # Classify: env (Docker), scope (file not found), implementation (test fail)
    # Log to output/failures.jsonl
    # Decide: retry (implementation) or exit (env/upstream)
fi
```

**F. Structured gap output**

If post-execution verification finds gaps, output YAML frontmatter (à la GSD) that can be fed back into a re-planning cycle:

```yaml
gaps:
  - requirement: "API returns paginated results"
    status: failed
    reason: "Endpoint exists but returns unpaginated list"
    artifacts:
      - path: "backend/gts_webapp/api/v1/routes.py"
        issue: "No LIMIT/OFFSET in query"
    fix: "Add pagination parameters to list endpoint"
```

**G. Evidence standards**

Adopt GTS's anti-generic-evidence rule. Verification must produce specific observed values, not "looks good" or "tests pass." For each success criterion, require: what command was run, what the output was, what was expected.

---

### Open Questions — My Recommendations

| # | Question | Recommendation |
|---|----------|---------------|
| 1 | Prompt optimiser source | Build from scratch in `references/`. It's 20 lines of criteria, not worth a dependency. |
| 2 | Codex prompt size limits | Summarise implementation prompts (title + success criteria only). Full content isn't needed for validation. |
| 3 | generate-pipeline.sh | Claude does template hydration directly. Shell text substitution is fragile and adds a debugging surface. |
| 4 | Gemini CLI | Keep to Claude + Codex for v1. Add Gemini as a `run.sh` swap, document in customisation section. |
| 5 | Error recovery in run.sh | Git checkpoints (above) + failure classification. `--from` flag is nice-to-have for v2. |

---

The plan is 80% there. The main gap is that verification currently front-loads (validates prompts) but doesn't back-validate (verify the codebase delivers the goal). Adding the three-layer post-execution verification would make this genuinely robust.

---

## Assistant (line 98, 262 chars, ts: 2026-02-18T23:34:48.709Z)

Could you clarify what "1" refers to? Are you saying:

- **Open Question #1** — you agree to build the prompt optimiser from scratch in `references/`?
- **Recommendation A** — you want to start with adding Phase 8 (Post-Execution Verification)?
- Something else?

---

## Assistant (line 193, 6467 chars, ts: 2026-02-19T01:17:55.316Z)

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

---

## Assistant (line 201, 1444 chars, ts: 2026-02-19T01:27:12.634Z)

That's the right call. You'd be maintaining two parallel systems otherwise, and the epic already has the hard parts solved.

What the epic needs to absorb the mini-epic's value:

1. **Codex as cross-model reviewer** — the genuinely novel bit. Claude plans, Codex critiques. Neither marks its own homework.
2. **Lighter-weight mode** — the planner already generates variable story counts. A small task just produces 1-2 stories with smaller budgets.

What it already handles fine at small scale:
- Phase A/B verification works on a 1-story plan the same as a 5-story plan
- Failure classification, evidence standards, JSONL logging — all scale-agnostic
- Context assembly already selects only relevant wiki/codebase sections
- Validation checkpoints already run per-story regardless of count

The real question is **where does Codex fit** in the existing pipeline. A few options:

- **Phase B replacement/augmentation** — Codex runs the plan verification instead of (or alongside) Sonnet
- **Post-story validation** — Codex reviews each story's output independently of Claude
- **Pre-execution plan critique** — a new phase between plan generation and Phase A, like the mini-epic's Phase 2
- **Post-execution goal-backward check** — Codex verifies the codebase delivers the intent after all stories complete

Want me to dig into the epic skill and workflow code to map exactly where Codex integration points would slot in, and draft the changes?

---

## Assistant (line 499, 869 chars, ts: 2026-02-19T01:47:06.235Z)

The plan covers 9 steps with full cross-model traceability in the JSONL logging. Key logging enhancements:

- **Every event gets `adapter` and `model` fields** — you can filter by `"adapter":"codex"` vs `"adapter":"claude"` to see exactly which CLI ran what
- **Critique events carry `critique_model` + `target_model`** — explicit cross-reference showing "Opus critiqued Codex's work"
- **`role` field** on dispatch events — `"planner"`, `"implementer"`, `"critique_story"`, `"critique_epic"` — so you can reconstruct the full workflow from the log
- **Schema version bumped to 2** — clean break for the enhanced events
- **`get_resumable_state()` updated** — recognises `critique_fail` as a retry trigger so crash recovery works across the new steps

The example JSONL trace in Step 8 shows what a complete story looks like with all the cross-model events interleaved.

---
