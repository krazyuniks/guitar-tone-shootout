# Epic Review: E70 — Video BC Integration — Remotion-Powered Composition

## 1. Traceability

| Artifact | Reference |
|----------|-----------|
| Epic Issue | #70 (GitHub unavailable at review time) |
| Branch | `70/epic-video-bc-integration-remotion-power` |
| Task Files | `.tasks/projects/guitar-tone-shootout/epics/E70/tasks/T71-T84.md` |
| First Commit | `f97d5092` (T71 test-lock, 2026-02-09 00:31) |
| Final Commit | `471d7ed9` (T84 complete, 2026-02-09 05:51) |
| Session Logs | 9 sessions (2 dry-run, 7 live) |
| Error Reports | 5 errors across T73, T80, T81, T82, T84 |
| Health Report | UNHEALTHY (lint errors, E2E failures remain) |

**Note:** GitHub issue and PR data unavailable at review time (repository access issue). Traceability limited to local artifacts.

## 2. Plan vs Execution

| Metric | Planned | Actual |
|--------|---------|--------|
| Tasks | 13 | 13 (12 complete, 1 pending: T84) |
| Files created | ~30 | 90 |
| Files changed | - | 129 (12,023 insertions, 241 deletions) |
| Total duration | - | 5h 22m (wall clock) |
| Sessions | 1 | 9 (2 dry-run + 7 live) |
| Test files created | ~13 | 33 (across T71-T83, excluding T84 full snapshot) |

**Observations:**
- T84 (Integration Test) is marked `complete` in the task file but listed as `pending` in `index.md` -- likely a state sync issue.
- File creation was ~3x the rough plan estimate, driven by comprehensive test suites and supporting tooling.
- The epic required 7 live sessions rather than running in one pass, indicating the state machine was interrupted and resumed multiple times.

## 3. Per-Task Metrics

| Task | Title | Test Files | State | Attempts | Bounces | Duration | Notes |
|------|-------|------------|-------|----------|---------|----------|-------|
| T71 | Core Domain -- Generic Composition Port | 4 | complete | 1 | 0 | 10m | Clean first pass |
| T72 | libs/video/ Scaffold + Audio Cleanup | 3 | complete | 1 | 0 | 20m | Clean |
| T73 | Docker Integration -- Video BC Container | 1 | complete | 2 | 1 | 10m | Validation failed: test file modified during impl |
| T74 | Video BC -- Python Implementation | 4 | complete | 1 | 0 | 88m | **Long duration** -- largest impl task |
| T75 | Video BC -- Remotion Components | 2 | complete | 1 | 0 | 51m | 31 failing tests at red phase |
| T76 | Worker Integration -- Video Render Pipeline | 3 | complete | 1 | 0 | 6m | Quick -- interface-only task |
| T77 | Frontend -- Remotion Player | 2 | complete | 1 | 0 | 5m | Quick -- frontend components |
| T78 | Tooling & Just Commands | 4 | complete | 1 | 0 | 5m | Quick -- justfile updates |
| T80 | worktree.py -- Video Service Integration | 4 | complete | 2 | 1 | 18m | Validation failed: test file modified |
| T81 | Documentation -- DEVELOPMENT.md, AGENTS.md | 3 | complete | 2 | 1 | 29m | Validation failed: 3 test files modified |
| T82 | .claude Skills/Agents -- Video Dev Support | 2 | complete | 2 | 1 | 16m | Green failed: webapp not running |
| T83 | Alembic Migration -- Shootout Video Fields | 1 | complete | 1 | 0 | 15m | Clean |
| T84 | Integration Test -- E2E Render Pipeline | 1 | pending* | 1 | 1 | 12m | Red failed: conftest ImportError |

\* T84 task file says `complete` but `index.md` says `pending`. The final commit exists but health check shows failures.

### Flagged Tasks

- **T74 (88m):** Longest task. Contains API, image prep, props, and schemas -- 4 implementation files. Not oversized by test count (4 files) but high by duration. Consider splitting API endpoint from data processing.
- **T75 (51m):** Second longest. 31 tests at red phase is the highest test count. 7 TSX/TS files created. Acceptable for a single composition layer but borderline.
- **T80 (4 test files):** 4 test files with 1,102 lines of test code for worktree.py integration. Volume was high but task was well-scoped.

## 4. Agent Effectiveness

| Metric | Value |
|--------|-------|
| Test-author success rate (red gate, first try) | 12/13 = **92%** |
| Implementer success rate (green gate, first try) | 9/13 = **69%** |
| Validation pass rate (first try) | 9/13 = **69%** |
| Bounce-back rate (test modified during impl) | 3/13 = **23%** |
| Average retries per task | 1.23 |
| Tasks with zero retries | 8/13 = **62%** |

**Analysis:**
- Test-author agents performed well: only T84 failed red gate (conftest ImportError, not a test quality issue).
- Implementer agents modified locked test files in 3 tasks (T73, T80, T81), which caused validation failures. This is the dominant failure mode.
- T82 failed green because the webapp container was not running -- an infrastructure issue, not an agent competence issue.
- T84 red failure was due to a conftest import path error, suggesting the test-author placed the test in a location with incompatible conftest configuration.

## 5. Task Complexity Analysis

### Appropriately Sized (8 tasks)
T71, T72, T76, T77, T78, T82, T83, T84

### Borderline (3 tasks)
- **T73:** 1 test file but touched Docker infra (Dockerfile + docker-compose), which is inherently brittle.
- **T80:** 4 test files (1,102 lines), high test volume for a single Python script modification.
- **T81:** 3 test files spanning 3 documentation files. Each doc file has different structure, making tests fragile.

### Oversized (2 tasks)
- **T74 (88m, 4 impl files):** API + image prep + props serialiser + schemas. Should be split into:
  1. T74a: Pydantic schemas
  2. T74b: Image preparation (Pillow)
  3. T74c: Props serialiser
  4. T74d: FastAPI endpoints
- **T75 (51m, 7 impl files, 31 tests):** 5 React components + Root + index. Could be split into:
  1. T75a: GearBlock + MetadataOverlay (presentational)
  2. T75b: SlideTransition + SignalChainSegment (animated)
  3. T75c: ShootoutVideo (composition) + Root/index

## 6. Infrastructure Issues

| Issue | Task | Impact | Root Cause |
|-------|------|--------|------------|
| webapp container not running | T82 | green_failed | Docker service crashed or was stopped between sessions |
| conftest ImportError | T84 | red_failed | Test placed in `tests/integration/video/` but conftest uses `integration.webapp.conftest` plugin path |
| XPASS (31 tests unexpectedly passing) | T73, T80, T81 | Validation noise | Pre-existing xfail tests from earlier epics now passing due to code changes |
| Test file modification during impl | T73, T80, T81 | validation_failed | Implementer agent edited locked test files |

**XPASS Problem:** 31 tests across multiple test files are marked `xfail` with reasons like "Pre-existing: T3K provider API changed" and "Pre-existing: template assertions need update". These pass on every run, generating noise in validation output. They should be un-xfailed or fixed.

## 7. Learnings

### Promote to Rules (.claude/rules/)

1. **Test file immutability enforcement:** The implementer agent modified locked test files in 3/13 tasks. The validation caught it, but the agent should be blocked from writing to test files entirely. Add a rule: "During implementation phase, NEVER modify files matching `tests/**/*.py` that were created in the test-author phase."

2. **Container health pre-check:** T82 failed because webapp was not running. Add a pre-flight check before dispatching agents: verify all required Docker services are healthy.

### Promote to MEMORY.md

1. **T84 conftest import path:** Integration tests in `tests/integration/video/` need their own conftest or must not import from `tests/integration/webapp/conftest.py`.

2. **XPASS noise:** 31 xfail tests from earlier epics are now passing. These need cleanup in a maintenance task.

### Promote to Agent Instructions

1. **Implementer:** "You MUST NOT modify any file that was committed in the test-lock commit. If tests cannot pass without modification, report the issue and stop."

2. **Test-author:** "Before placing integration tests, verify the conftest.py in the target directory does not have incompatible plugin imports."

### Promote to Skills

1. **Video BC patterns:** The `gts-video` skill was created (T82). Verify it covers all patterns discovered during implementation.

## 8. Recommendations (ranked by impact)

| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| 1 | Fix 31 XPASS tests (un-xfail or update assertions) | Low | High -- reduces validation noise for every future epic |
| 2 | Add pre-flight Docker health check to `run_epic.py` | Low | High -- prevents T82-type failures |
| 3 | Enforce test file immutability in implementer agent prompt, not just validation | Low | High -- prevents 23% bounce-back rate |
| 4 | Split T74-sized tasks in future plans (max 2 impl files per task) | Med | Med -- reduces duration variance |
| 5 | Fix T84 conftest import issue and complete integration test | Med | Med -- epic cannot be merged without passing health check |
| 6 | Resolve health check failures (lint + E2E) before merge | Med | High -- blocking for merge |
| 7 | Add `index.md` state sync to `tdd-complete` command | Low | Low -- prevents T84 index/task state mismatch |
| 8 | Consider parallel task execution for independent branches (T77/T78 could run alongside T74/T75) | High | Med -- could reduce wall clock from 5h to ~3.5h |
