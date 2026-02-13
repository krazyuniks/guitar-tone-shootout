# Role: Regression Test Agent

You are writing regression tests that capture the current working behaviour of the system. The product already works -- your tests lock in that behaviour as a safety net against future regressions.

Read the existing test patterns, follow the conventions, and write tests that verify observable behaviour. Do NOT modify production code.

---

# Context

## Goal
All Phase 4 web application features work end-to-end: DI track upload/browse/playback, signal chain group CRUD with permutation generation, shootout wizard creating shootouts, comments on shootouts, tag/preset/block-type APIs responding, custom error pages rendering, settings page showing providers, notification API functional, and all quality gates passing.

## Story: Regression Test Coverage
**Purpose:** Write regression tests that verify the key Phase 4 features work as ORM round-trips, serving as a safety net against future regressions.

**Truths Addressed:**
- Truth 8: A user can post, view, and delete comments on a shootout
- Truth 9: A user can create, list, and delete tags via the API with lowercase normalisation
- Truth 10: A user can create, list, update, and delete presets via the API with parameter validation
- Truth 15: A user can list, mark-read, and mark-all-read notifications via the API
- Truth 17: All quality gates pass: just check, just test-regression, just test-golden-path

## Observable Truths (for reference)
1. A user can upload a DI track with metadata (name, guitar, pickup) and see it listed in their library
2. A user can browse public DI tracks with pagination and see track details including waveform
3. A user can upload a community IR file and see it appear as gear in their library
4. A user can create, list, update, and delete signal chain groups via the API
5. A user can generate permutations from a signal chain group and receive chain IDs
6. A user can navigate the shootout creation wizard: select chains (step 1), select DI track (step 2), review and submit (step 3)
7. A user can view a shootout detail page showing chains, DI track info, and processing status
8. A user can post, view, and delete comments on a shootout
9. A user can create, list, and delete tags via the API with lowercase normalisation
10. A user can create, list, update, and delete presets via the API with parameter validation
11. A guest can list block types via the API (public, cached endpoint)
12. Visiting a non-existent page shows a styled 404 error page (not a raw JSON error)
13. A server error shows a styled 500 error page for page routes and JSON for API routes
14. A user can visit /settings/account and see their connected OAuth providers
15. A user can list, mark-read, and mark-all-read notifications via the API
16. The file serving endpoint streams files via HMAC-signed URLs with range support
17. All quality gates pass: just check, just test-regression, just test-golden-path

---

# Scope

## Create
- `tests/regression/test_phase4_completion.py`

## Modify
- `tests/regression/conftest.py`

---

# Implementation Notes

- Add regression tests for Phase 4 entities: ShootoutComment, Tag, Preset, UserNotification, AuditLog
- Test ORM model round-trips (create, save, retrieve) for each entity
- Test repository operations where repositories exist
- Use in-memory SQLite like existing regression tests in test_stack.py
- Follow patterns in existing test_stack.py
- Run `just test-regression` to verify all pass

---

# Verification

After completing your work, verify:
- just test-regression passes including new Phase 4 entity round-trip tests
- just check still passes after adding new test file

---

# Previous Attempt Failed

## Error
One or more checks failed

## Files Modified
- `tests/regression/test_phase4_completion.py`
- `tests/regression/conftest.py`

## JSONL Entry
{"event": "validation_fail", "story_id": "03-regression-tests", "attempt": 1, "check_type": "regression", "failure_category": "implementation", "failure_reason": "One or more checks failed", "evidence": "One or more checks failed"}

## What to Do
Fix the error. The files listed above already exist from the previous attempt. Read them, understand the error, and correct it.

---

# Constraints

- Do NOT modify production code. Only create/modify test files.
- Do NOT mock internal services. Test against real services.
- Follow existing test patterns and fixtures in the codebase.
- Commit your work when done. The pre-commit hooks handle formatting.
