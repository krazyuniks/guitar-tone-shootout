"""Unit tests for Worker configuration.

Tests that WorkerSettings loads from environment variables and provides
required configuration for Redis broker and database connections.
"""

import pytest


class TestWorkerSettings:
    """Test WorkerSettings configuration loading."""

    def test_settings_module_exists(self) -> None:
        """config module exists in worker package."""
        from worker import config  # noqa: F401

    def test_worker_settings_class_exists(self) -> None:
        """WorkerSettings class exists in config module."""
        from worker.config import WorkerSettings

        assert WorkerSettings is not None

    def test_settings_has_redis_url_field(self) -> None:
        """WorkerSettings has redis_url field."""
        from worker.config import WorkerSettings

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            t3k_database_url="postgresql+asyncpg://user:pass@localhost/t3k_db",
        )
        assert hasattr(settings, "redis_url")
        assert settings.redis_url == "redis://localhost:6379"

    def test_settings_has_database_url_field(self) -> None:
        """WorkerSettings has database_url field."""
        from worker.config import WorkerSettings

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            t3k_database_url="postgresql+asyncpg://user:pass@localhost/t3k_db",
        )
        assert hasattr(settings, "database_url")
        assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/db"

    def test_settings_has_t3k_database_url_field(self) -> None:
        """WorkerSettings has t3k_database_url field."""
        from worker.config import WorkerSettings

        settings = WorkerSettings(
            redis_url="redis://localhost:6379",
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            t3k_database_url="postgresql+asyncpg://user:pass@localhost/t3k_db",
        )
        assert hasattr(settings, "t3k_database_url")
        assert settings.t3k_database_url == "postgresql+asyncpg://user:pass@localhost/t3k_db"

    def test_settings_loads_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WorkerSettings loads values from environment variables."""
        from worker.config import WorkerSettings

        monkeypatch.setenv("REDIS_URL", "redis://test-redis:6380")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:pass@testdb/core")
        monkeypatch.setenv("T3K_DATABASE_URL", "postgresql+asyncpg://test:pass@testdb/t3k")

        settings = WorkerSettings()

        assert settings.redis_url == "redis://test-redis:6380"
        assert settings.database_url == "postgresql+asyncpg://test:pass@testdb/core"
        assert settings.t3k_database_url == "postgresql+asyncpg://test:pass@testdb/t3k"

    def test_settings_inherits_from_base_settings(self) -> None:
        """WorkerSettings inherits from pydantic_settings.BaseSettings."""
        from pydantic_settings import BaseSettings

        from worker.config import WorkerSettings

        assert issubclass(WorkerSettings, BaseSettings)

    def test_redis_url_field_is_required(self) -> None:
        """redis_url field is required (no default)."""
        from pydantic import ValidationError

        from worker.config import WorkerSettings

        with pytest.raises(ValidationError) as exc_info:
            WorkerSettings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                t3k_database_url="postgresql+asyncpg://user:pass@localhost/t3k_db",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("redis_url",) for error in errors)

    def test_database_url_field_is_required(self) -> None:
        """database_url field is required (no default)."""
        from pydantic import ValidationError

        from worker.config import WorkerSettings

        with pytest.raises(ValidationError) as exc_info:
            WorkerSettings(
                redis_url="redis://localhost:6379",
                t3k_database_url="postgresql+asyncpg://user:pass@localhost/t3k_db",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("database_url",) for error in errors)

    def test_t3k_database_url_field_is_required(self) -> None:
        """t3k_database_url field is required (no default)."""
        from pydantic import ValidationError

        from worker.config import WorkerSettings

        with pytest.raises(ValidationError) as exc_info:
            WorkerSettings(
                redis_url="redis://localhost:6379",
                database_url="postgresql+asyncpg://user:pass@localhost/db",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("t3k_database_url",) for error in errors)


class TestWorkerBrokerConfiguration:
    """Test that worker main.py uses Redis broker instead of InMemoryBroker."""

    @pytest.mark.xfail(reason="Pre-existing: requires Redis (feature worktrees have no Redis)")
    def test_broker_is_not_in_memory_broker(self) -> None:
        """broker is not InMemoryBroker (should be ListQueueBroker)."""
        from taskiq import InMemoryBroker

        from worker.main import broker

        assert not isinstance(broker, InMemoryBroker), (
            "Worker should use Redis ListQueueBroker, not InMemoryBroker"
        )

    @pytest.mark.xfail(reason="Pre-existing: requires Redis (feature worktrees have no Redis)")
    def test_broker_uses_redis_list_queue_broker(self) -> None:
        """broker is a ListQueueBroker instance from taskiq-redis."""
        from taskiq_redis import ListQueueBroker

        from worker.main import broker

        assert isinstance(broker, ListQueueBroker), (
            "Worker broker must be ListQueueBroker from taskiq-redis"
        )

    @pytest.mark.xfail(reason="Pre-existing: requires Redis (feature worktrees have no Redis)")
    def test_broker_connects_to_redis_from_settings(self) -> None:
        """broker connects to Redis using URL from WorkerSettings."""
        from worker.main import broker

        assert hasattr(broker, "_redis_url"), "Broker should store Redis URL from settings"

        redis_url = getattr(broker, "_redis_url", None)
        assert redis_url is not None, "Broker must have Redis URL configured"
        assert isinstance(redis_url, str), "Redis URL must be a string"
