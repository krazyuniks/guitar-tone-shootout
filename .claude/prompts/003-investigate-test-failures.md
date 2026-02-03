<objective>
Investigate why `just test` fails and fix the failing tests. The test failures are related to missing migration files.

This investigation will fix the immediate failures and inform what gaps exist between documented artifacts and actual codebase state.
</objective>

<context>
**The failure:**
```
FAILED tests/integration/webapp/test_migration.py::test_migration_creates_all_tables
  AssertionError: Migration directory should exist
  assert PosixPath('infrastructure/migrations/versions').exists() == False

FAILED tests/integration/webapp/test_migration.py::test_alembic_config_exists
  AssertionError: alembic.ini should exist
  assert PosixPath('infrastructure/migrations/alembic.ini').exists() == False
```

**What this means:**
- STORY-020 (Alembic Migrations) is marked as `passes: true` in prd.json
- But the migration files don't exist at the expected paths
- Either the files were created elsewhere, or the story completion was premature

**prd.json STORY-020 claims:**
```json
{
  "id": "STORY-020",
  "title": "Alembic Migrations",
  "passes": true,
  "notes": "Alembic configuration created with initial migration..."
}
```

**What we need to verify:**
1. Do migration files exist anywhere in the codebase?
2. Is the alembic configuration in a different location?
3. Did the tests get written against wrong paths?
4. What is the actual state of database migrations?
</context>

<research_tasks>
1. **Find existing migrations**
   - Search for `alembic.ini` anywhere in the repo
   - Search for `versions/` directories that might contain migrations
   - Check if migrations are in `backend/alembic/` (archive location)

2. **Verify test expectations**
   - Read `tests/integration/webapp/test_migration.py`
   - Understand what paths the tests expect
   - Compare to where files actually are

3. **Check spec.md/IMPLEMENTATION.md**
   - What path does the documentation specify for migrations?
   - `infrastructure/migrations/` per GTS-Technical-Architecture

4. **Determine fix approach**
   - Option A: Move existing migrations to expected path
   - Option B: Update tests to point to actual path
   - Option C: Create the migrations if they don't exist
</research_tasks>

<investigation_steps>
1. Search for alembic.ini:
   ```bash
   find . -name "alembic.ini" -type f 2>/dev/null
   ```

2. Search for migration versions:
   ```bash
   find . -path "*/versions/*.py" -type f 2>/dev/null | head -20
   ```

3. Read the failing test to understand expectations:
   ```
   Read tests/integration/webapp/test_migration.py
   ```

4. Check what IMPLEMENTATION.md says about migrations path

5. Determine the correct fix
</investigation_steps>

<fix_requirements>
After investigation, implement the fix:

**If migrations exist elsewhere:**
- Either move them to `infrastructure/migrations/` (per architecture)
- Or update tests to match actual location (if there's a good reason)

**If migrations don't exist:**
- This is a gap - STORY-020 shouldn't be marked complete
- Document this finding
- DO NOT create migrations in this prompt (separate task)

**Either way:**
- Update prd.json to reflect actual state
- `just test` should pass after the fix
</fix_requirements>

<output>
Create a findings report:
- `./analyses/test-failure-investigation.md`

Include:
1. Root cause of the test failures
2. Actual location of migration files (if any)
3. Discrepancy between prd.json status and reality
4. Recommended fix
5. Whether STORY-020 should be marked incomplete

If a simple fix is possible (moving files or updating paths):
- Implement the fix
- Run `just test` to verify
- Update prd.json if needed
</output>

<verification>
Before declaring complete:
- [ ] Root cause identified
- [ ] Actual migration file locations documented
- [ ] Fix applied OR documented as needing separate work
- [ ] prd.json reflects actual state
- [ ] `just test` status known (passing or documented failures)
</verification>

<success_criteria>
- Clear explanation of why tests failed
- prd.json accurately reflects STORY-020 status
- If fixable: `just test` passes
- If not fixable: clear documentation of remaining work
</success_criteria>
