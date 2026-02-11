"""Unit tests for Scheduler configuration.

Tests that SchedulerSettings loads from environment variables and provides
required configuration for Redis broker connection.
"""

import os
from unittest.mock import patch

import pytest


class TestSchedulerSettings:
    """Test SchedulerSettings configuration loading."""

    def test_settings_module_exists(self) -> None:
        """config module exists in scheduler package."""
        from scheduler import config  # noqa: F401

    def test_scheduler_settings_class_exists(self) -> None:
        """SchedulerSettings class exists in config module."""
        from scheduler.config import SchedulerSettings

        assert SchedulerSettings is not None

    def test_settings_has_redis_url_field(self) -> None:
        """SchedulerSettings has redis_url field."""
        from scheduler.config import SchedulerSettings

        # Create settings with explicit value
        settings = SchedulerSettings(redis_url="redis://localhost:6379")
        assert hasattr(settings, "redis_url")
        assert settings.redis_url == "redis://localhost:6379"

    def test_settings_loads_from_environment(self) -> None:
        """SchedulerSettings loads redis_url from environment variable."""
        from scheduler.config import SchedulerSettings

        # Set environment variable
        env_vars = {
            "REDIS_URL": "redis://test-redis:6380",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = SchedulerSettings()

            assert settings.redis_url == "redis://test-redis:6380"

    def test_settings_inherits_from_base_settings(self) -> None:
        """SchedulerSettings inherits from pydantic_settings.BaseSettings."""
        from pydantic_settings import BaseSettings

        from scheduler.config import SchedulerSettings

        assert issubclass(SchedulerSettings, BaseSettings)

    def test_redis_url_field_is_required(self) -> None:
        """redis_url field is required (no default)."""
        from pydantic import ValidationError

        from scheduler.config import SchedulerSettings

        # Attempt to create settings without redis_url
        with pytest.raises(ValidationError) as exc_info:
            SchedulerSettings()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("redis_url",) for error in errors)
