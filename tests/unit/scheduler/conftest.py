"""Fixtures for t3k_sync tasks unit tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _register_test_session(request):
    """Inject the test session into t3k_sync.tasks for SAVEPOINT isolation."""
    if "session" not in request.fixturenames:
        yield
        return

    import t3k_sync.tasks as tasks

    try:
        session = request.getfixturevalue("session")
        tasks._test_session = session
    except Exception:
        yield
        return

    yield

    tasks._test_session = None
