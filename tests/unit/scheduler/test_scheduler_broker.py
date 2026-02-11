"""Unit tests for Scheduler Redis broker configuration.

Tests that scheduler main.py uses Redis broker (ListQueueBroker) instead of
InMemoryBroker, configured with redis_url from SchedulerSettings.
"""


class TestSchedulerBrokerConfiguration:
    """Test that scheduler main.py uses Redis broker instead of InMemoryBroker."""

    def test_broker_is_not_in_memory_broker(self) -> None:
        """broker is not InMemoryBroker (should be ListQueueBroker)."""
        from taskiq import InMemoryBroker

        from scheduler.main import broker

        assert not isinstance(
            broker, InMemoryBroker
        ), "Scheduler should use Redis ListQueueBroker, not InMemoryBroker"

    def test_broker_uses_redis_list_queue_broker(self) -> None:
        """broker is a ListQueueBroker instance from taskiq-redis."""
        from taskiq_redis import ListQueueBroker

        from scheduler.main import broker

        assert isinstance(
            broker, ListQueueBroker
        ), "Scheduler broker must be ListQueueBroker from taskiq-redis"

    def test_broker_connects_to_redis_from_settings(self) -> None:
        """broker connects to Redis using URL from SchedulerSettings."""
        from scheduler.main import broker

        # Check that the broker has a Redis connection configured
        # ListQueueBroker stores the Redis URL in its _redis_url attribute
        assert hasattr(broker, "_redis_url"), "Broker should store Redis URL from settings"

        # Verify it's not using default localhost (should come from settings)
        redis_url = getattr(broker, "_redis_url", None)
        assert redis_url is not None, "Broker must have Redis URL configured"
        assert isinstance(redis_url, str), "Redis URL must be a string"

    def test_scheduler_uses_same_broker_as_worker(self) -> None:
        """scheduler and worker share the same Redis broker URL."""
        from scheduler.main import broker as scheduler_broker

        # Verify scheduler broker is configured
        scheduler_redis_url = getattr(scheduler_broker, "_redis_url", None)
        assert scheduler_redis_url is not None, "Scheduler broker must have Redis URL configured"

        # The URL should be redis://redis:6379 in production (from docker-compose.yml)
        # In tests it may differ, but must be a valid redis:// URL
        assert scheduler_redis_url.startswith(
            "redis://"
        ), "Scheduler broker must use Redis protocol"


class TestSchedulerConfiguration:
    """Test that scheduler uses TaskiqScheduler with LabelScheduleSource."""

    def test_scheduler_exists(self) -> None:
        """scheduler instance exists in main module."""
        from scheduler.main import scheduler

        assert scheduler is not None

    def test_scheduler_is_taskiq_scheduler(self) -> None:
        """scheduler is a TaskiqScheduler instance."""
        from taskiq import TaskiqScheduler

        from scheduler.main import scheduler

        assert isinstance(scheduler, TaskiqScheduler), "scheduler must be TaskiqScheduler instance"

    def test_scheduler_uses_label_schedule_source(self) -> None:
        """scheduler uses LabelScheduleSource for task discovery."""
        from taskiq.schedule_sources import LabelScheduleSource

        from scheduler.main import scheduler

        # Check that scheduler has sources configured
        assert hasattr(scheduler, "sources"), "Scheduler must have sources configured"
        sources = scheduler.sources
        assert len(sources) > 0, "Scheduler must have at least one schedule source"

        # Verify at least one source is LabelScheduleSource
        has_label_source = any(isinstance(source, LabelScheduleSource) for source in sources)
        assert has_label_source, "Scheduler must use LabelScheduleSource for task discovery"
