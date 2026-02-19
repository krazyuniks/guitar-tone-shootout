<!-- domains: testing -->
# Test Database Rules
- ALL tests use real PostgreSQL via shared fixtures in tests/conftest.py.
- SQLite is BANNED. Never use sqlite+aiosqlite, in-memory SQLite, or PRAGMA.
- Never create inline db_engine/db_session fixtures. Use root conftest fixtures.
- Never mark tests as xfail with "pre-existing" reasons. Fix the test.
- Test isolation uses the SAVEPOINT rollback pattern (see tests/conftest.py).
