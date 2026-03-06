# Testing Strategy

Testing uses pytest with Playwright for browser automation. The suite is structured in layers, with regression tests providing fast stack validation and E2E tests validating user journeys.

## Test Levels

| Level | Purpose | Infrastructure | Location |
|-------|---------|----------------|----------|
| Regression | Stack connectivity (ORM -> Repo -> DB) | Real PostgreSQL | `tests/regression/` |
| Unit | Domain logic, validators | None | `tests/unit/` |
| Integration | Repository operations, services | Real PostgreSQL, pgmq | `tests/integration/` |
| E2E | User journeys, UI flows | Browser + full stack | `tests/e2e/python/` |

## Test Execution

**Clear boundary: Regression/Unit/Integration in Docker, E2E on Host.**

| Test Type | Location | Runs In | Command | Purpose |
|-----------|----------|---------|---------|---------|
| Regression | `tests/regression/` | Docker | `just test-regression` | Stack connectivity (ORM -> Repo -> DB) |
| Unit | `tests/unit/` | Docker | `just test-unit` | Isolated logic, no I/O |
| Integration | `tests/integration/` | Docker | `just test-integration` | Real DB, pgmq |
| E2E | `tests/e2e/python/` | Host | `just test-golden-path` | Full user journey |

## Regression Tests

Fast validation that the ORM -> Repository -> Database stack works correctly:

- **User round-trip** -- Create, save, retrieve by ID/email/identity
- **Job round-trip** -- Create, save, state transitions, retrieve
- Uses real PostgreSQL with SAVEPOINT rollback isolation
- Run before commits to catch fundamental breaks

```bash
just test-regression  # Stack connectivity (< 1s)
```

## Three-Layer E2E Validation

E2E tests validate each interaction at three levels:

1. **UI Action** -- Navigate and interact like a real user
2. **DOM Update** -- Assert visible state changes
3. **Database State** -- Verify data persistence

This pattern catches issues at any layer: frontend rendering, API communication, or data persistence.

## Mocking Policy

**No mocking.** Tests use real services — real databases, real T3K API, real pgmq. The `test_quality_check.py` gate bans all `unittest.mock` imports with zero exceptions.

| Category | Approach |
|----------|----------|
| PostgreSQL | Real database — all test levels use PostgreSQL with SAVEPOINT isolation |
| T3K API | Real T3K API with auth tokens |
| pgmq | Real pgmq extension in PostgreSQL |

**Rationale:** Mocking hides integration bugs. Real services catch schema mismatches, connection problems, auth failures, and timing issues that mocks would mask. All GTS services are available in the Docker test environment.

## Running Tests

```bash
just test-regression  # Stack connectivity (< 1s) - before commits
just test             # Unit + Integration (< 30s) - before PRs
just tdd <path>       # Single test during development
just test-golden-path # Golden path tests (MANDATORY before story completion)
```

**Why E2E on host?**
- E2E tests use Playwright to hit running containers from outside
- Isolated dependencies in `tests/e2e/python/pyproject.toml`
- No pollution of main workspace venv

## Contract Tests

Core schemas (`libs/core/records/`) are treated as contracts between bounded contexts:

- All source adapters validate output against current core schemas in CI.
- Compatibility checks ensure new schema versions meet backward-compatibility requirements.
- Breaking changes fail source adapter tests immediately, preventing deployment of incompatible adapters.

**Example:** `GearSyncRecord` is the contract between source adapters and core. If a required field is added, source adapter tests break until the adapter populates it.

## Data Quality Tests

Automated data quality validation at the persistence boundary:

| Expectation | What It Checks |
|-------------|----------------|
| Schema | Required columns exist, types correct |
| Completeness | Non-null constraints on mandatory fields |
| Uniqueness | Composite key uniqueness (`source_name` + `source_record_id`) |
| Distribution drift | Key field value distributions remain within expected ranges |

Quality test failures increment the `data_quality_quarantine_total` metric and prevent bad data from reaching consumers.

## Replay Tests

Replay and recovery workflows are exercised with realistic data volumes:

- **Reingest workflows** -- Bulk reingest exercised with full pack catalogs to verify idempotent upserts produce identical state.
- **Checkpoint resume** -- Simulated failures mid-sync verify that checkpoint recovery resumes from the correct position without data loss or duplication.
- **DLQ replay** -- Partial failure recovery tested: poison messages isolated, remaining messages redriven and processed successfully.

## E2E Canary Tests

Synthetic validation of the complete ingestion pipeline:

- **Canary Source** -- Generates predictable data patterns (known pack counts, model names, checksums).
- **Critical path verification** -- Validates fetch -> transform -> enqueue -> consume -> persist in staging.
- **Scheduled verification** -- Core database queried on schedule to confirm canary data arrived within SLO freshness target.

Canary test failures trigger P2 alerts (significant degradation).

## Fixture Catalogue

Factory fixtures in `tests/integration/webapp/conftest.py` provide canonical test data setup:

- **Factory fixtures:** `make_user`, `make_di_track`, `make_shootout`, `make_gear`, `make_signal_chain` — create entities with customisable parameters
- **Singleton fixtures:** `test_user`, `test_di_track`, `test_gear`, `test_shootout`, `test_signal_chain` — pre-built instances using the factories
- **`authenticated_client`** — single canonical definition for authenticated HTTP client

All factory fixtures are documented in `tests/FIXTURES.md`. Tests must use these fixtures rather than ad-hoc setup. Duplicate fixture definitions across test files are prohibited.

## Test Generation Pipeline

Step 5b in the epic workflow generates test code from approved `test_spec` fields in `plan.json`, before story execution begins.

- **`test_writer`** (default: sonnet) writes test code from the test_spec + fixture catalogue
- **`test_reviewer`** (default: codex) reviews against a 5-item binary checklist (assertion coverage, factory fixtures used, no mocks, data flows verified, tests would fail without feature)
- Max 3 retries per story — reviewer feedback fed back to writer
- Output: `tests/epic/E{N}/test_{story_id}.py` per story
- Config roles defined in `workflow/default_config.toml` under `[budgets.test_writing]` and `[budgets.test_review]`
- Cross-model warning if `test_writer == test_reviewer`

**Module:** `workflow/test_generator.py`

## Test File Protection

Implementing agents cannot modify pre-written test files. Before agent dispatch, the pipeline takes a SHA-256 hash snapshot of all `tests/**/*.py` files. After the agent completes, hashes are re-verified. If any pre-existing test file was modified or deleted, the story fails with `scope_violation` (0 retries, immediate exit to human).

## Golden Path Gate

`just test-golden-path` runs as a mandatory gate after every story execution. If any existing golden path test fails, the story fails with category `implementation` (retryable). This ensures implementing agents do not break existing functionality.

**Reference:**
- Markers defined in `tests/conftest.py`
- Fixtures in `tests/fixtures/`
- Fixture catalogue in `tests/FIXTURES.md`
- Structure documented in `tests/AGENTS.md`
