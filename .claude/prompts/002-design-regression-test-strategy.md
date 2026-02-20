<objective>
Design and implement a simple, reliable regression test for the GTS rewrite that validates the service → ORM → database stack is working, providing Claude with a clear "success signal" for work completion.

The goal is to replace the current unit-only `test-regression` command with a meaningful happy-path test that exercises real code paths until the frontend is operational.
</objective>

<context>
**Problem:**
- Current `just test-regression` runs only unit tests (`pytest tests/unit/ -v -m "not slow"`)
- The archive's `test-regression` ran E2E Playwright tests against the live site
- The new site's frontend isn't working yet, so E2E tests aren't applicable
- Claude needs an explicit success signal to know when work is "done"

**Current state:**
- Phase 3 (Adapters) is nearly complete: ORM models, repositories, audio processing
- Phase 4 (Webapp) hasn't started: no FastAPI app, no services, no API
- Docker services are running (db, webapp, nginx)
- Integration tests exist for repositories and work against real PostgreSQL

**Archive reference:**
The archive's test-regression (see `../../guitar-tone-worktrees-archive-20260202/main/justfile` lines 305-335) ran:
- E2E_BASE_URL health check
- Playwright regression tests (`-m regression`)

**What we need:**
A test that validates: Service layer → Repository → ORM → PostgreSQL is connected and working
</context>

<requirements>
Design a regression test that:

1. **Validates the stack is connected**
   - ORM models can be imported
   - Database session can be created
   - A basic entity can be saved and retrieved

2. **Is simple and fast**
   - Single test file: `tests/regression/test_stack.py`
   - Runs in < 10 seconds
   - No external dependencies (no frontend, only PostgreSQL required)

3. **Provides clear success signal**
   - Pass = stack works, code is functional
   - Fail = something fundamental is broken

4. **Uses existing infrastructure**
   - Uses the db_session fixture from `tests/integration/webapp/conftest.py`
   - Runs in Docker via `just test-regression`

5. **Is extensible**
   - Can be expanded as Phase 4 adds services
   - Follow the pattern: test service → repo → orm → db
</requirements>

<implementation>
Create:

1. **Test file** - `tests/regression/test_stack.py`
   ```python
   """
   Regression test: validates ORM → Repository → Database stack is working.

   Run with: just test-regression

   This test provides a quick "does the stack work?" check.
   It will be expanded as services are added in Phase 4.
   """
   ```

   The test should:
   - Import User model from webapp.adapters.persistence.models
   - Create a user entity
   - Save via repository
   - Retrieve via repository
   - Verify the round-trip worked

2. **Conftest** - `tests/regression/conftest.py`
   - Re-use fixtures from integration tests or create minimal fixtures

3. **Update justfile** - Change `test-regression` to run:
   ```
   docker compose exec -T webapp pytest tests/regression/ -v --tb=short
   ```

4. **Update prd.json successCriteria** - Point to the new test:
   ```json
   "successCriteria": {
     "command": "just test-regression",
     "timeout": 60
   }
   ```
</implementation>

<constraints>
- Do NOT modify existing integration tests
- Do NOT add dependencies
- Do NOT require frontend or external services
- Keep the test file under 100 lines
- WHY: This test is a quick smoke test, not comprehensive coverage. Integration tests provide depth.
</constraints>

<output>
Create/modify these files:
- `./tests/regression/test_stack.py` - The regression test
- `./tests/regression/conftest.py` - Test fixtures
- Update `./justfile` - Change test-regression command
- Update `./.ralph-hybrid/main/prd.json` - Update successCriteria if needed

After implementation:
- Run `just test-regression` to verify it works
- Confirm the test actually exercises ORM → DB
</output>

<verification>
Before declaring complete, verify:
- [ ] `just test-regression` passes
- [ ] Test creates and retrieves an entity from real PostgreSQL
- [ ] Test runs in under 10 seconds
- [ ] Failure produces a clear error message
</verification>

<success_criteria>
- `just test-regression` executes the new regression test
- Test validates User → UserRepository → PostgreSQL round-trip
- Test is simple enough to understand in 30 seconds
- Test can be extended when services are added
</success_criteria>
