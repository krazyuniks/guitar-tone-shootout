# Codebase Concerns

**Analysis Date:** 2026-02-05

## Tech Debt

**Missing Relationship in User Model:**
- Issue: User model has TODO comment for Gear relationship that hasn't been implemented
- Files: `apps/webapp/src/webapp/adapters/persistence/models/user.py:103`
- Impact: Foreign key relationships incomplete; queries for user gear will require joins or separate queries
- Fix approach: Add relationship definition once Gear model finalized, create migration to add FK if needed

**NAM Model Processing Performance:**
- Issue: NAM model processing uses sample-by-sample iteration instead of batched processing
- Files: `libs/audio/src/audio/processing/processor.py:236-271`
- Impact: Extremely slow for long audio files (real-time or longer); unsuitable for production
- Current state: Marked as "simplified implementation" with TODO-style comments about buffering
- Fix approach: Implement proper batch processing with PyTorch tensor operations; benchmark against expected processing times

**Incomplete FastAPI Endpoint Implementation:**
- Issue: Main application factory only implements health check endpoint; no API routes defined
- Files: `apps/webapp/src/webapp/main.py` (26 lines total)
- Impact: No user-facing API endpoints for jobs, shootouts, gear, or authentication exist yet
- Blocks: All client-side integration; frontend cannot fetch data
- Fix approach: Wire up API routers in main.py using separate route modules

## Known Gaps

**Missing API Endpoints:**
- What's not implemented: All `/api/v1/` endpoints for jobs, shootouts, gear, signal chains, user library
- Files: `apps/webapp/src/webapp/main.py`
- Impact: Frontend templates exist but cannot be populated with data
- Workaround: None - endpoints must be implemented for application to function
- Priority: Critical - blocks feature delivery

**Missing Authentication Endpoints:**
- What's not implemented: OAuth flow endpoints, session management
- Expected at: `apps/webapp/src/webapp/auth/` (exists but empty)
- Impact: Users cannot authenticate; all protected endpoints fail
- Priority: Critical - required before any authenticated features work

**Incomplete Repository Contract:**
- What's not implemented: Some repository methods may only have stubs
- Files: `libs/core/src/core/ports/repositories.py` (593 lines)
- Impact: Services depending on complete repository interface will fail at runtime
- Validation: Run all integration tests to find missing implementations

## Performance Bottlenecks

**Audio Processing - Sample-by-Sample NAM:**
- Problem: NAM model applies to audio one sample at a time with tensor creation overhead
- Files: `libs/audio/src/audio/processing/processor.py:261-266`
- Cause: Loop iterates `audio_tensor` with `model(sample.view(1,1))` - creates new tensor per sample
- Expected impact: 10-100x slower than batched processing depending on file length
- Improvement path:
  1. Buffer samples into chunks (e.g., 1024 per batch)
  2. Create single tensor per batch
  3. Stack outputs and concatenate results
  4. Benchmark: target <1s for 30s audio file

**Audio Analysis Waveform Extraction:**
- Problem: Extracting 200 peak values from full audio may load entire file into memory
- Files: `libs/audio/src/audio/processing/processor.py:72-88`
- Cause: Delegates to `_extract_waveform` without streaming mechanism
- Scaling concern: Large files (100MB+) could exhaust memory on container
- Improvement path: Implement streaming waveform extraction with fixed memory window

## Fragile Areas

**Dual Database Architecture Bridge (Worker):**
- Files: Worker container as message consumer
- Why fragile: Worker is the only connection between `gts_core` and `gts_t3k_source` databases; if worker fails, T3K sync cannot occur
- Safe modification: Always test pgmq message flow before deploying worker changes; include health checks for both database connections
- Test coverage: Check `tests/integration/` for worker-specific tests
- Impact of failure: T3K catalog won't update; users can't browse new models

**Signal Chain Validation:**
- Files: `libs/core/src/core/services/signal_chain_validator.py` (301 lines)
- Why fragile: Central point for all signal chain business logic; complex validation with many edge cases
- Safe modification: Add unit tests for each validation rule before changing logic; ensure test coverage >90%
- Current coverage: Check test files in `tests/unit/core/`

**Unit of Work Pattern:**
- Files: `apps/webapp/src/webapp/adapters/persistence/unit_of_work.py`
- Why fragile: Transaction boundaries must be correctly placed or data can be lost
- Safe modification: Always test with actual database transactions; use regression tests (`tests/regression/`)
- Risk: Incorrect transaction placement leaves partial updates committed

## Scaling Limits

**Audio Processing Container Resources:**
- Current capacity: Assumes files fit in memory after resampling
- Limit: Large audio files (>500MB uncompressed) may exhaust container memory
- Container memory: Likely 2-4GB based on standard Docker defaults
- Scaling path:
  1. Implement streaming audio processing
  2. Add memory limit monitoring
  3. Consider GPU acceleration for NAM inference

**Database Connection Pool:**
- Current capacity: Not explicitly configured; likely SQLAlchemy defaults
- Limit: If many concurrent requests hit database, connection pool exhaustion possible
- Scaling path:
  1. Configure explicit pool size in connection string
  2. Monitor active connections with postgres monitoring
  3. Adjust based on concurrent user count

**Message Queue Capacity (pgmq):**
- Current capacity: PostgreSQL-backed queue; limited by disk space
- Limit: If job processing slower than submission, queue backs up indefinitely
- Scaling path:
  1. Monitor queue depth with admin endpoint
  2. Implement backpressure (reject jobs if queue >N)
  3. Add circuit breaker if workers are down

## Dependencies at Risk

**PyTorch (torch):**
- Risk: Heavy dependency; large binary size; GPU support optional
- Impact: If torch incompatibilities arise, NAM processing breaks
- Current status: Only used in audio processing
- Migration plan: Could switch to ONNX runtime if performance issues arise

**Pedalboard:**
- Risk: External audio effects library; may have platform-specific issues
- Impact: HighpassFilter and other effects won't work if library breaks
- Current status: Used for highpass filtering only; could be replaced with scipy filters
- Alternative: `scipy.signal.iirfilter` for highpass implementation

**SQLAlchemy 2.0:**
- Risk: Major version; some projects report breaking changes
- Impact: ORM queries and relationship loading could break on upgrade
- Current status: Actively used throughout persistence layer
- Mitigation: Pin exact version in requirements; test carefully before upgrading

## Test Coverage Gaps

**API Endpoint Coverage:**
- What's not tested: No API integration tests exist (endpoints don't exist yet)
- Files: Covered once endpoints implemented
- Risk: API bugs won't be caught by tests
- Priority: High - add API tests before feature release

**Worker Message Processing:**
- What's not tested: pgmq consumer logic for T3K sync messages
- Files: `apps/worker/` - check for consumer tests
- Risk: Message corruption, lost messages, or incorrect processing undetected
- Priority: High - worker reliability critical for feature

**Authentication Flow:**
- What's not tested: OAuth flow, token refresh, session management
- Files: `apps/webapp/src/webapp/auth/` (currently empty)
- Risk: Auth bugs cause security issues
- Priority: Critical - must have >95% coverage

**Frontend Navigation (data-testid):**
- What's not tested: E2E tests for Astro navigation with `data-astro-reload`
- Files: Template files in `frontend/astro/src/pages/`
- Risk: Links to SSR pages silently fail in Astro's ClientRouter
- Priority: Medium - covered by E2E tests once implemented

## Architecture & Design Issues

**API Endpoint Location Not Finalized:**
- Issue: Unclear where API routers will be defined; no pattern established
- Files: `apps/webapp/src/webapp/main.py` is minimal stub
- Impact: Different developers may create endpoints inconsistently
- Fix approach: Create `apps/webapp/src/webapp/api/v1/` directory structure with route modules

**Missing Application Services Layer:**
- Issue: Services directory exists but unclear how business logic coordinates between repositories
- Files: `apps/webapp/src/webapp/services/` (likely empty)
- Impact: Business logic may end up in repositories or endpoints
- Fix approach: Define service classes for core workflows (create shootout, process job, etc.)

**Logging Not Configured:**
- Issue: Only 1 reference to logging in entire webapp codebase
- Files: Widespread across `apps/webapp/`
- Impact: Debugging production issues will be difficult; no audit trail
- Fix approach: Add structured logging with `structlog` or `loguru`; log at service boundaries

## Missing Critical Features

**Admin API Endpoints:**
- Problem: Admin API should serve jobs, sync status, auth status endpoints from worker
- Expected location: `apps/worker/src/worker/` (check if present)
- Blocks: Ability to monitor system health and manage jobs
- Priority: Medium - needed for operations

**Job Status Webhook Callbacks:**
- Problem: No mechanism for background jobs to notify external systems of completion
- Blocks: User notifications, downstream processing
- Priority: Low - can be added later if needed

**Error Recovery & Retry Logic:**
- Problem: No clear retry strategy for failed audio processing jobs
- Blocks: Resilience against transient failures
- Priority: Medium - should implement before production

## Security Concerns

**OAuth Token Storage Security:**
- Issue: `.gts-auth.json` permissions checked, but no encryption at rest
- Files: `worktree/auth.py`
- Risk: Token file readable by any process on system with user permissions
- Current mitigation: File permissions (600) prevent other users accessing
- Recommendation: Consider OS keychain integration for production; document security model

**Missing CORS Configuration:**
- Issue: FastAPI app created but CORS not explicitly configured
- Files: `apps/webapp/src/webapp/main.py`
- Risk: Browser-based clients may be blocked or incorrectly configured
- Fix approach: Add `fastapi.middleware.cors.CORSMiddleware` with explicit origin list

**No Rate Limiting:**
- Issue: Audio processing is resource-intensive but no rate limiting implemented
- Files: `apps/webapp/` (API endpoints not yet built)
- Risk: Users could submit unlimited processing jobs, exhausting resources
- Fix approach: Implement rate limiting per user once auth is complete

**Missing Input Validation on File Uploads:**
- Issue: Audio processor checks format but file size not validated
- Files: `libs/audio/src/audio/processing/processor.py`
- Risk: Large files could exhaust container memory before processing
- Fix approach: Add maximum file size check before loading

## Deployment & Maintenance Concerns

**Astro Build Sync Between Source & Dist:**
- Issue: `frontend/astro/dist/` must stay in sync with `frontend/astro/src/`
- Files: Both `src/` and `dist/` directories
- Risk: Out-of-sync dist/ means production differs from development
- Mitigation: CI check enforces sync; `just verify-astro-sync` prevents commits
- Process: Always run `just build-astro` after template changes

**Database Migration Management:**
- Issue: Only one migration file exists; unclear how future migrations will be organized
- Files: `infrastructure/migrations/versions/b4a1fd310cb9_initial_schema.py` (932 lines - very large)
- Risk: Single large migration is difficult to debug if it fails partially
- Recommendation: Break future migrations into smaller, more focused changes

**Docker Compose Override Files Generated:**
- Issue: `docker-compose.override.yml` is auto-generated and should not be manually edited
- Files: Generated by `worktree.py setup`
- Risk: Manual edits get overwritten on next setup
- Mitigation: Enforced by infrastructure protection rules

## Recommendations (Priority Order)

| Area | Action | Priority | Effort |
|------|--------|----------|--------|
| API Endpoints | Implement missing `/api/v1/*` endpoints | Critical | High |
| Authentication | Build OAuth flow and session management | Critical | High |
| NAM Processing | Optimize sample-by-sample to batched processing | High | Medium |
| Logging | Add structured logging throughout webapp | High | Medium |
| API Tests | Create comprehensive API integration tests | High | Medium |
| CORS Configuration | Explicit CORS setup with allowed origins | High | Low |
| Rate Limiting | Per-user rate limiting on audio processing | High | Medium |
| Services Layer | Define application service classes | Medium | Medium |
| File Upload Validation | Add file size and format validation | Medium | Low |
| Keychain Integration | OS-specific credential storage for production | Medium | High |

---

*Concerns audit: 2026-02-05*
