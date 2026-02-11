"""Fixtures for worker unit tests.

Provides test isolation by managing environment variables that could interfere
with worker settings validation tests.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_worker_env(monkeypatch):
    """Isolate worker tests from container environment variables.

    The webapp container has DATABASE_URL set, which interferes with tests
    that check if WorkerSettings fields are required. This fixture removes
    worker-specific environment variables before each test, ensuring tests
    start with a clean environment.

    Tests that need environment variables (like test_settings_loads_from_environment)
    use patch.dict with clear=True, so they're unaffected by this fixture.
    """
    # Remove worker-specific env vars that might interfere with validation tests
    for var in ["REDIS_URL", "T3K_DATABASE_URL"]:
        monkeypatch.delenv(var, raising=False)

    # Also remove DATABASE_URL during tests to ensure field requirement tests work
    # Tests that need it will set it explicitly via patch.dict
    monkeypatch.delenv("DATABASE_URL", raising=False)
