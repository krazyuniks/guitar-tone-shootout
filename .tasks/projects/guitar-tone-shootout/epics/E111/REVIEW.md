# Epic Review: E111 — Phase 5 Pipeline — Job System, T3K Source, pgmq Consumer

## 1. Traceability

| Artifact | Reference |
|----------|-----------|
| PRD | IMPLEMENTATION.md Phases 5A, 5B, 5D |
| GitHub Issue | [#111](https://github.com/krazyuniks/guitar-tone-shootout/issues/111) |
| Epic Definition | `.tasks/projects/guitar-tone-shootout/epics/E111/index.md` |
| Tasks | T112–T120 (9 tasks) |
| Key Commits | `bad800a3`..`f3e6bb44` (28 E111-specific impl/lock commits, 62 total including chore) |
| PR | None created (work done on main via TDD state machine) |

## 2. Plan vs Execution

| Metric | Planned | Actual |
|--------|---------|--------|
| Tasks | 9 | 9 |
| Files created | 7 | 7 |
| Files modified | 9 | 11 |
| Tests written | — | 175 across 10 files |
| Test lines | — | 4,141 |
| Sessions | — | 3 (2 halted, 1 completed) |
| Wall clock | — | ~3h 13m |
| Errors | 0 | 3 (1 lock x2, 1 green x3) |

The epic completed all 9 planned tasks. Two sessions halted early due to pre-commit hook failures and pre-existing test failures, requiring manual intervention before the third session completed the remaining work.

## 3. Per-Task Metrics

| Task | Tests | Lines | State | Attempts | Bounces | Duration | Mock Density | Notes |
|------|-------|-------|-------|----------|---------|----------|-------------|-------|
| T112 | 17 | 267 | complete | 4 | 0 | 39m | 0% | **3 green failures** — pre-existing failures from other epics |
| T113 | 16 | 305 | complete | 2 | 0 | 13m | 11.8% | Lock failure (ruff TC004) |
| T114 | 12 | 125 | complete | 1 | 0 | 4m | 0% | Clean |
| T115 | 28 | 475 | complete | 1 | 0 | 10m | 0% | Clean, **oversized** (28 tests) |
| T116 | 24 | 743 | complete | 1 | 0 | 12m | 11.2% | **Oversized** (24 tests, 743 lines), **heavy internal mocking** |
| T117 | 21 | 547 | complete | 1 | 0 | 6m | 3.1% | External API mock only (acceptable) |
| T118 | 23 | 833 | complete | 2 | 1 | 16m | 10.0% | **Oversized** (23 tests, 833 lines), **heavy internal mocking**, test bug bounce |
| T119 | 11 | 278 | complete | 1 | 0 | 11m | 6.1% | **Internal mocking** of Redis, sessions, handlers |
| T120 | 23 | 568 | complete | 1 | 0 | 16m | 8.3% | External HTTP mock (acceptable) |

**Flagged tasks:**
- **T115** (28 tests): Oversized. 11 endpoints + 10 schemas in one task. Should be split into enqueue, source dashboard, and job management tasks.
- **T116** (24 tests, 743 lines): Oversized. Complex sync loop with many states. Tests mock internal services.
- **T118** (23 tests, 833 lines): Oversized. Consumer + mapper in one task crosses multiple layers. Tests mock both DB sessions.

## 4. Agent Effectiveness

| Metric | Value |
|--------|-------|
| Test-author first-pass rate (lock on first try) | 7/9 (78%) |
| Implementer first-pass rate (green on first try) | 7/9 (78%) |
| Bounce-back rate | 1/9 (11%) |
| Average attempts per task | 1.44 |
| Sessions required | 3 |

**Test-author failures:**
- T112: Ruff SIM117 (nested `async with` should be combined) — lint knowledge gap
- T113: Ruff TC004 (imports in `TYPE_CHECKING` block used at runtime) — lint knowledge gap

Both lock failures were lint issues, not test quality issues. The test-author agent needs better awareness of ruff rules, specifically SIM117 (combine `with` statements) and TC004 (type-checking imports).

**Implementer failures:**
- T112: 3 green failures caused by 46 pre-existing test failures from earlier epics (E94/E95). The implementer's changes were correct but unrelated test failures blocked the green gate.

**Resolution:** Pre-existing failures were manually added to `tests/known_failures.txt` and marked as xfail, allowing the pipeline to proceed.

## 5. Mock Analysis

### Summary

| Metric | Value |
|--------|-------|
| Mock-free test files | 4/10 (40%) |
| Files with mocks | 6/10 (60%) |
| Total mock lines | 283 / 4,141 (6.8%) |
| Real assertion ratio | 73% |

### Mock Violations (Internal Service Mocking)

| File | Mock Lines | Pattern | Severity |
|------|-----------|---------|----------|
| `tests/unit/t3k/test_catalog_sync.py` | 83 | `AsyncMock(spec=AsyncSession)`, `AsyncMock(spec=T3KAPIClient)` | error |
| `tests/unit/worker/test_gear_sync_consumer.py` | 83 | `Mock(spec=AsyncSession)` for both core and t3k, `patch.object(mapper)` | error |
| `tests/unit/worker/test_source_sync_jobs.py` | 17 | `AsyncMock` for Redis, session, API client, OAuth, TaskIQ | error |

### Acceptable Mocks (External API / Subprocess)

| File | Mock Lines | Pattern | Severity |
|------|-----------|---------|----------|
| `tests/unit/worker/test_entrypoint.py` | 36 | `MagicMock` for subprocess processes | warning |
| `tests/unit/t3k/test_model_downloader.py` | 17 | `AsyncMock(spec=AsyncClient)` for external HTTP | info |
| `tests/unit/worker/test_gts_admin_cli.py` | 47 | `AsyncMock(spec=AsyncClient)` for admin API HTTP | info |

### Assessment

Three test files have **error-severity** mock violations totalling 183 mock lines. These tests mock internal services (database sessions, internal API clients, message publishers, Redis) rather than testing against real infrastructure. This is a direct violation of the project's no-mock policy.

The most concerning are:
1. **test_catalog_sync.py** — Mocks `AsyncSession` and `T3KAPIClient`. The sync service tests verify mock call patterns rather than actual data flow. The T3K API client mock is borderline (external API), but the session mocking is a clear violation.
2. **test_gear_sync_consumer.py** — Mocks both database sessions and the internal `GearMapperService.process_pack_sync` method. These tests cannot catch real integration bugs.
3. **test_source_sync_jobs.py** — Mocks Redis, sessions, API clients, OAuth, and TaskIQ handlers. Almost everything is mocked, making these tests near-useless for catching real bugs.

**Could these be rewritten?** Yes. All three should use real database fixtures (SQLite or PostgreSQL) and real service instances. The T3K API client mock in test_catalog_sync.py is the only one where mocking is appropriate (external network API).

## 6. Product Functionality Assessment

| Task | Implementation | Wired In? | Score |
|------|---------------|-----------|-------|
| T112 | `get_core_session()` + `get_t3k_session()` in worker/db.py | Yes — `get_db_session` uses `get_core_session()` | **FUNCTIONAL** |
| T113 | `entrypoint.py` runs 3 processes | Yes — `docker-compose.yml` updated | **FUNCTIONAL** |
| T114 | `0002_oauth_tokens.py` migration | Yes — applies after 0001 | **FUNCTIONAL** |
| T115 | 11 admin endpoints + 10 Pydantic schemas | Yes — routes in `admin.py` | **FUNCTIONAL** |
| T116 | `run_catalog_sync()` in sync_service.py | Yes — called by source_sync job | **FUNCTIONAL** |
| T117 | `model_downloader.py` | Yes — integrated into sync_service.py | **FUNCTIONAL** |
| T118 | `gear_sync.py` consumer + `gear_mapper.py` service | Yes — `run_pgmq_consumer()` called in entrypoint.py | **FUNCTIONAL** |
| T119 | `source_sync.py` job + `auth.py` schedule + `ensure_source_sync_running` | Yes — registered in `main.py` and `schedules/jobs.py` | **FUNCTIONAL** |
| T120 | `gts_admin.py` CLI + justfile registration | Yes — `just admin` registered in justfile | **FUNCTIONAL** |

**Score: 9/9 FUNCTIONAL** — All implementations are wired into the application at the correct registration points. No orphaned code.

## 7. Test Quality Score

| Metric | Value |
|--------|-------|
| Mock-free test percentage | 4/10 files (40%) |
| Real assertion ratio | 73% |
| Mock density | 6.8% |
| **Quality grade** | **C+ (borderline B)** |

Grade breakdown:
- 4 files (T112 integration tests, T114, T115) are completely mock-free = excellent
- 2 files (T117, T120) use acceptable external API mocks = good
- 1 file (T113) mocks subprocesses = acceptable
- 3 files (T116, T118, T119) mock internal services = violation

The 3 violation files drag the overall score down from what would otherwise be a solid B.

## 8. Task Complexity Analysis

### Oversized Tasks

**T115 — Admin API (28 tests, 475 lines)**
- Covers 11 endpoints + 10 Pydantic schemas
- Recommendation: Split into 3 tasks: (a) enqueue endpoint, (b) source dashboard endpoints, (c) job management + lock endpoints

**T116 — Sync Loop (24 tests, 743 lines)**
- Complex state machine with backfill, newest, skip-recently-synced, stale detection
- Recommendation: Split into 2 tasks: (a) backfill + newest alternation, (b) skip-recently-synced + stale detection

**T118 — pgmq Consumer + GearMapper (23 tests, 833 lines)**
- Crosses 3 layers: consumer loop, mapper service, dead-letter handling
- Recommendation: Split into 3 tasks: (a) consumer polling loop, (b) GearMapperService, (c) dead-letter + file migration

### Correctly Sized Tasks

T112 (17 tests), T113 (16 tests), T114 (12 tests), T117 (21 tests), T119 (11 tests), T120 (23 tests) — all within acceptable bounds.

## 9. Infrastructure Issues

### Pre-Existing Test Failures (CRITICAL)

The T112 green phase failed 3 times due to **46 pre-existing test failures** from earlier epics (E94/E95). These failures existed before E111 started but were not marked as known failures. The TDD pipeline treated them as regressions, blocking progress.

**Resolution:** Manually added 49 tests to `tests/known_failures.txt` and marked them as xfail.

**Impact:** ~25 minutes wasted (3 implementer retries at ~7min each + manual investigation).

### Pre-Commit Hook Lint Failures

Two lock phases failed due to ruff lint errors the test-author agent did not catch:
- T112: SIM117 (combine nested `with` statements)
- T113: TC004 (imports in TYPE_CHECKING block used at runtime)

**Impact:** ~5 minutes per failure (re-run required after manual fix).

### Session Log Trailing Whitespace

The session log files themselves triggered the `trailing-whitespace` pre-commit hook when committed alongside test files. This is a systemic issue — the TDD pipeline writes log files that get staged in the same commit.

**Recommendation:** Exclude `.tasks/**/logs/` from pre-commit hooks, or commit log files separately.

## 10. Learnings

### Promote to Agent Instructions

1. **Ruff SIM117 awareness:** Test-author must combine nested `async with` statements into single `with` blocks.
2. **Ruff TC004 awareness:** Test-author must not place runtime imports inside `TYPE_CHECKING` blocks.
3. **Pre-existing failure handling:** The pipeline should detect and skip known failures automatically, not halt.

### Promote to MEMORY.md

1. **E111 completed all 9 tasks successfully** — the Phase 5 data pipeline is wired end-to-end.
2. **Pre-existing test failures must be resolved before starting an epic** — or added to `known_failures.txt` proactively.
3. **Lock failures from lint are the most common halting cause** — investin in lint-aware test generation.

### Promote to Rules (.claude/rules/)

1. **No-mock policy enforcement is incomplete** — 3 of 10 test files mock internal services. The test-author agent needs stronger enforcement in its instructions.
2. **Task size limit:** Tasks with >20 tests or >500 test lines should be flagged during planning.

## 11. Recommendations (ranked by impact)

| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| 1 | **Rewrite T116/T118/T119 tests without internal mocks** — use real DB fixtures and service instances. These 3 files (183 mock lines) undermine confidence in the data pipeline. | Med | High |
| 2 | **Add pre-existing failure detection to the TDD pipeline** — before starting an epic, run the full test suite and auto-mark pre-existing failures as xfail. Prevents the T112 scenario. | Med | High |
| 3 | **Add ruff lint check to test-author agent** — run `ruff check` on test files before completing the test phase. Catches SIM117/TC004 before lock. | Low | High |
| 4 | **Enforce task size limits in planning** — flag tasks with >20 acceptance criteria or tasks that span >2 layers. T115/T116/T118 were all oversized. | Low | Med |
| 5 | **Exclude session logs from pre-commit hooks** — add `.tasks/**/logs/` to `.pre-commit-config.yaml` exclude patterns. | Low | Med |
| 6 | **Close GitHub issue #111** — the epic is complete but the issue remains open. | Low | Low |
| 7 | **Add integration tests for T116/T118/T119** — the unit tests mock everything; adding integration tests against real DB would provide actual coverage. | High | High |
