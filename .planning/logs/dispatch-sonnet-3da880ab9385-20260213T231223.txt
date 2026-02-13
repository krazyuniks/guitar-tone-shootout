# Role: Regression Test Agent

You are writing regression tests that capture the current working behaviour of the system. The product already works -- your tests lock in that behaviour as a safety net against future regressions.

Read the existing test patterns, follow the conventions, and write tests that verify observable behaviour. Do NOT modify production code.

---

# Context

## Goal
All Phase 4 web application features work end-to-end: DI track upload/browse/playback, signal chain group CRUD with permutation generation, shootout wizard creating shootouts, comments on shootouts, tag/preset/block-type APIs responding, custom error pages rendering, settings page showing providers, notification API functional, and all quality gates passing.

## Story: API Endpoint Smoke Tests
**Purpose:** Verify all Phase 4 API endpoints respond correctly by running the E2E test suite. Fix any endpoint-level issues (wrong status codes, missing validations, broken template rendering).

**Truths Addressed:**
- Truth 1: A user can upload a DI track with metadata (name, guitar, pickup) and see it listed in their library
- Truth 2: A user can browse public DI tracks with pagination and see track details including waveform
- Truth 3: A user can upload a community IR file and see it appear as gear in their library
- Truth 4: A user can create, list, update, and delete signal chain groups via the API
- Truth 5: A user can generate permutations from a signal chain group and receive chain IDs
- Truth 6: A user can navigate the shootout creation wizard: select chains (step 1), select DI track (step 2), review and submit (step 3)
- Truth 7: A user can view a shootout detail page showing chains, DI track info, and processing status
- Truth 8: A user can post, view, and delete comments on a shootout
- Truth 9: A user can create, list, and delete tags via the API with lowercase normalisation
- Truth 10: A user can create, list, update, and delete presets via the API with parameter validation
- Truth 11: A guest can list block types via the API (public, cached endpoint)
- Truth 12: Visiting a non-existent page shows a styled 404 error page (not a raw JSON error)
- Truth 13: A server error shows a styled 500 error page for page routes and JSON for API routes
- Truth 14: A user can visit /settings/account and see their connected OAuth providers
- Truth 15: A user can list, mark-read, and mark-all-read notifications via the API
- Truth 16: The file serving endpoint streams files via HMAC-signed URLs with range support

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

## Modify
- `apps/webapp/src/webapp/api/v1/shootouts.py`
- `apps/webapp/src/webapp/api/v1/di_tracks.py`
- `apps/webapp/src/webapp/api/v1/signal_chain_groups.py`
- `apps/webapp/src/webapp/api/v1/html.py`
- `apps/webapp/src/webapp/api/pages.py`

---

# Implementation Notes

- Run `just test-golden-path` and analyse failures
- Fix endpoint-level bugs: wrong status codes, missing template variables, broken HTMX fragment responses
- Verify shootout create wizard steps work end-to-end
- Verify comments HTMX fragment loads on shootout detail page
- Verify settings/account page renders with provider status
- Verify 404/500 error pages render via nginx and FastAPI
- Do NOT refactor — fix only what is broken

---

# Verification

After completing your work, verify:
- just test-golden-path passes with all E2E tests green
- just test-regression still passes after endpoint fixes

---

# Constraints

- Do NOT modify production code. Only create/modify test files.
- Do NOT mock internal services. Test against real services.
- Follow existing test patterns and fixtures in the codebase.
- Commit your work when done. The pre-commit hooks handle formatting.
