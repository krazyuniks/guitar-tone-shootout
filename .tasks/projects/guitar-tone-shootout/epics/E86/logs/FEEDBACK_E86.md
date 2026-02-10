# E86 Post-Run Feedback Report

**Epic:** Phase 4 Remainder — DI Tracks, Chain Groups, Gear Library
**Run Date:** 2026-02-10
**Duration:** ~2h41m (14:48–18:29 UTC)
**Sessions:** 12
**Tasks:** 14 (T87–T100), all complete
**Result:** SUCCESS (with manual intervention for T99, T100)

---

## Error Summary

| Pattern | Count | Tasks | Phase | Severity |
|---------|-------|-------|-------|----------|
| test-author didn't create files | 5 | T91,T93,T95,T97,T99 | red | Medium |
| Implementer modified locked tests | 5 | T92,T93,T95,T97,T99 | validation | High |
| Missing router registration (404) | 3 | T90,T94,T96 | green | Medium |
| Missing response fields | 2 | T96,T99 | green | Low |
| Pre-existing test failures | ~20 | T87,T89 | full-suite | Low |

---

## Root Cause Analysis

### 1. test-author Intermittent Failures (36% first-attempt failure rate)

**What:** test-author agent exits without creating any test files. `tdd-red` finds no new files.

**Why:** Sonnet sometimes exhausts turns or gets confused by partially-implemented code context and exits before writing files.

**Impact:** Epic halts at red phase. Single retry resolves 4/5 times. T100 (regression tests) failed both attempts because the task requires cross-referencing all 9 prior tasks' endpoints — too complex for a single agent run.

**Fix applied:** Increased `MAX_TEST_AUTHOR_RETRIES` from 1 to 2 (covers T100-like cases).

**Future improvement:** Add a pre-check after dispatch to verify files were created before invoking `tdd-red`. This would allow a fast retry without running pytest unnecessarily.

### 2. Implementer Modifies Locked Test Files (5/14 tasks)

**What:** Despite explicit path restrictions in the agent instructions ("Forbidden: tests/**/test_*.py"), the implementer modifies locked test files. The snapshot verification catches this in the `tdd-complete` phase.

**Why:** The implementer agent (Sonnet) sometimes ignores the restriction when it sees failing tests and "helpfully" fixes them.

**Impact:** Epic halts at validation. Required manual intervention to restore files.

**Fix applied:** Added `restore_locked_test_files()` function. When `tdd-complete` detects MODIFIED/DELETED violations, it now:
1. Identifies modified files from snapshot output
2. Git-restores them from the lock commit
3. Re-runs validation
4. Only halts if tests fail with the restored originals

**Future improvement:** Enforce path restrictions at the Claude CLI level (--disallowedTools or file-level permissions) rather than relying on agent instructions alone.

### 3. Missing Router Registration (3 tasks)

**What:** Implementer creates route handlers but doesn't register them in the router, causing 404s.

**Why:** GTS has a manual router registration pattern — new route files need to be imported in the router's `__init__.py`. The implementer creates the file but forgets registration.

**Impact:** Green phase fails, costs 1-2 retry cycles.

**Future improvement:** Add a post-implementation check that greps for new route files and verifies they're imported in the relevant router init.

### 4. Missing `frontend/` in Auto-Commit (Bug)

**What:** The state machine's auto-commit after green phase omits `frontend/` from staged paths. Template tasks' astro changes weren't being committed by the state machine.

**Why:** Original `impl_paths` list didn't include `frontend/`. Worked accidentally because implementer agents sometimes commit directly.

**Fix applied:** Added `frontend/` to both `impl_paths` (line 1326) and `git_sync()` staging (line 145).

### 5. Duplicate Condition (Bug)

**What:** Line 603 checks `"AssertionError" in retry_context` twice (duplicate OR condition).

**Fix applied:** Removed the duplicate.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total iterations | 12 sessions |
| Single-pass tasks (no retry) | 6 (T87,T89,T90,T94,T96,T98) |
| Tasks needing test-author retry | 5 (T91,T93,T95,T97,T99) |
| Tasks needing validation restore | 5 (T92,T93,T95,T97,T99) |
| Tasks needing manual intervention | 2 (T99,T100) |
| Avg time per task | ~11.5 min |
| test-author first-attempt success | 64% (9/14) |
| Implementer test-modification rate | 36% (5/14) |

---

## Fixes Applied (This Session)

1. `scripts/run_epic.py` line 54: `MAX_TEST_AUTHOR_RETRIES` 1 → 2
2. `scripts/run_epic.py` line 603: Remove duplicate OR condition
3. `scripts/run_epic.py` line 145: Add `frontend/` to `git_sync()` staging
4. `scripts/run_epic.py` line 1326: Add `frontend/` to impl auto-commit paths
5. `scripts/run_epic.py` line 1197: Refactor red retry to use loop with `MAX_TEST_AUTHOR_RETRIES`
6. `scripts/run_epic.py`: New `restore_locked_test_files()` function
7. `scripts/run_epic.py` validation phase: Auto-restore on test file modification violations

---

## Recommendations for Future Epics

1. **Enforce file restrictions at CLI level** — Don't rely on agent instructions alone for path restrictions
2. **Add file-creation verification** — Check test files exist after test-author dispatch, before running pytest
3. **Break regression test tasks** — T100-style "update all regression tests" tasks are too broad for single agent runs
4. **Pre-existing failures** — Clean up xpassed tests before epic runs to reduce noise
5. **Router registration check** — Post-implementation grep for unregistered route files
