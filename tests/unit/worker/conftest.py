"""Fixtures for worker unit tests.

Provides test isolation by managing environment variables that could interfere
with worker settings validation tests.
"""

from __future__ import annotations

import pytest


def pytest_configure(config):
    """Configure pytest hooks for worker unit tests.

    This hook sets up SQLAlchemy event listeners BEFORE any tests run.
    """
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

    from webapp.adapters.persistence.models.shootout import Shootout

    # Disable FK constraints for SQLite in unit tests
    # This allows tests to create Jobs/Shootouts with non-existent user_ids
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Disable foreign key constraints for SQLite test databases."""
        try:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=OFF")
            cursor.close()
        except (AttributeError, TypeError):
            pass

    @event.listens_for(Session, "after_flush")
    def load_test_relationships(session, flush_context):
        """After flush, manually load Shootout.chains to bypass lazy='raise'.

        This is needed because tests create Shootout + ShootoutChain objects
        without explicitly loading the relationship, but Shootout.chains has
        lazy='raise' which prevents lazy loading. We manually query and set
        the chains list to make them accessible during tests.
        """
        from webapp.adapters.persistence.models.shootout import ShootoutChain

        for obj in session.new:
            if isinstance(obj, Shootout):
                # Load chains for this shootout
                chains = (
                    session.query(ShootoutChain).filter(ShootoutChain.shootout_id == obj.id).all()
                )
                # Bypass lazy='raise' by setting the attribute directly
                obj.__dict__["chains"] = chains


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
