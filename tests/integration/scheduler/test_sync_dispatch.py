"""Integration tests for scheduler sync dispatch.

Tests that:
- ensure_source_sync_running dispatches sync via admin API when no Redis lock
- ensure_source_sync_running skips dispatch when Redis lock exists
- ensure_source_sync_running skips dispatch when T3K_SYNC_ENABLED=false
- ensure_source_sync_running skips dispatch when auth is invalid
- handle_source_sync job is registered as a TaskIQ broker task
"""

import pytest

# ---------------------------------------------------------------------------
# FakeRedis (same pattern as tests/unit/worker/test_admin_api_extensions.py)
# ---------------------------------------------------------------------------


class FakeRedis:
    """Fake Redis client for integration tests — not a mock."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def exists(self, key: str) -> int:
        """Check if key exists."""
        return 1 if key in self._data else 0

    async def set(self, key: str, value: str, **kwargs) -> None:
        """Set key."""
        self._data[key] = value

    async def delete(self, key: str) -> int:
        """Delete key."""
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def aclose(self) -> None:
        """Close connection (no-op for fake)."""


class FakeHttpResponse:
    """Fake httpx response for testing admin API calls."""

    def __init__(self, status_code: int = 200, text: str = "OK") -> None:
        self.status_code = status_code
        self.text = text


class FakeHttpClient:
    """Fake httpx.AsyncClient that records requests."""

    def __init__(self, response: FakeHttpResponse | None = None) -> None:
        self.response = response or FakeHttpResponse()
        self.requests: list[tuple[str, dict]] = []

    async def post(self, url: str, **kwargs) -> FakeHttpResponse:
        self.requests.append((url, kwargs))
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def scheduler_env(monkeypatch) -> None:
    """Set environment variables needed for scheduler imports."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db/gts_core")


@pytest.fixture
def fake_redis() -> FakeRedis:
    """FakeRedis with no keys set (no lock)."""
    return FakeRedis()


@pytest.fixture
def fake_redis_with_lock() -> FakeRedis:
    """FakeRedis with sync lock already set."""
    redis = FakeRedis()
    redis._data["t3k:sync:lock"] = "1"
    return redis


@pytest.fixture
def fake_http_client() -> FakeHttpClient:
    """FakeHttpClient that records admin API requests."""
    return FakeHttpClient()


# ---------------------------------------------------------------------------
# ensure_source_sync_running — dispatch tests
# ---------------------------------------------------------------------------


class TestEnsureSourceSyncRunningDispatches:
    """ensure_source_sync_running must dispatch sync via admin API when appropriate."""

    async def test_dispatches_when_no_lock_and_sync_enabled(
        self,
        fake_redis: FakeRedis,
        fake_http_client: FakeHttpClient,
        monkeypatch,
        tmp_path,
    ) -> None:
        """With no Redis lock and T3K_SYNC_ENABLED=true, calls admin API."""
        monkeypatch.setenv("T3K_SYNC_ENABLED", "true")

        # Write a valid auth file
        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"access_token": "test", "username": "test"}')
        monkeypatch.setenv("GTS_AUTH_FILE", str(auth_file))

        from scheduler.schedules.jobs import ensure_source_sync_running

        monkeypatch.setattr(
            "scheduler.schedules.jobs.get_redis_client",
            lambda: fake_redis,
        )
        monkeypatch.setattr(
            "scheduler.schedules.jobs.httpx.AsyncClient",
            lambda: fake_http_client,
        )

        await ensure_source_sync_running()

        assert len(fake_http_client.requests) == 1, (
            "ensure_source_sync_running must call admin API exactly once"
        )
        url, _ = fake_http_client.requests[0]
        assert "/api/admin/sources/t3k/sync" in url

    async def test_does_not_dispatch_when_lock_exists(
        self,
        fake_redis_with_lock: FakeRedis,
        monkeypatch,
        tmp_path,
    ) -> None:
        """With existing Redis lock, does NOT dispatch a duplicate sync job."""
        monkeypatch.setenv("T3K_SYNC_ENABLED", "true")

        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"access_token": "test", "username": "test"}')
        monkeypatch.setenv("GTS_AUTH_FILE", str(auth_file))

        from scheduler.schedules.jobs import ensure_source_sync_running

        monkeypatch.setattr(
            "scheduler.schedules.jobs.get_redis_client",
            lambda: fake_redis_with_lock,
        )

        http_client = FakeHttpClient()
        monkeypatch.setattr(
            "scheduler.schedules.jobs.httpx.AsyncClient",
            lambda: http_client,
        )

        await ensure_source_sync_running()

        assert len(http_client.requests) == 0, (
            "ensure_source_sync_running must NOT dispatch when Redis lock exists"
        )

    async def test_does_not_dispatch_when_sync_disabled(
        self,
        fake_redis: FakeRedis,
        monkeypatch,
        tmp_path,
    ) -> None:
        """With T3K_SYNC_ENABLED=false, does NOT dispatch even without lock."""
        monkeypatch.setenv("T3K_SYNC_ENABLED", "false")

        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"access_token": "test", "username": "test"}')
        monkeypatch.setenv("GTS_AUTH_FILE", str(auth_file))

        from scheduler.schedules.jobs import ensure_source_sync_running

        monkeypatch.setattr(
            "scheduler.schedules.jobs.get_redis_client",
            lambda: fake_redis,
        )

        http_client = FakeHttpClient()
        monkeypatch.setattr(
            "scheduler.schedules.jobs.httpx.AsyncClient",
            lambda: http_client,
        )

        await ensure_source_sync_running()

        assert len(http_client.requests) == 0, (
            "ensure_source_sync_running must NOT dispatch when T3K_SYNC_ENABLED=false"
        )

    async def test_does_not_dispatch_when_auth_invalid(
        self,
        fake_redis: FakeRedis,
        monkeypatch,
        tmp_path,
    ) -> None:
        """With invalid auth, does NOT dispatch even without lock."""
        monkeypatch.setenv("T3K_SYNC_ENABLED", "true")

        # Write an empty/invalid auth file
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("{}")
        monkeypatch.setenv("GTS_AUTH_FILE", str(auth_file))

        from scheduler.schedules.jobs import ensure_source_sync_running

        http_client = FakeHttpClient()
        monkeypatch.setattr(
            "scheduler.schedules.jobs.httpx.AsyncClient",
            lambda: http_client,
        )

        await ensure_source_sync_running()

        assert len(http_client.requests) == 0, (
            "ensure_source_sync_running must NOT dispatch when auth is invalid"
        )


# ---------------------------------------------------------------------------
# ensure_source_sync_running — schedule configuration
# ---------------------------------------------------------------------------


class TestEnsureSourceSyncScheduleConfig:
    """ensure_source_sync_running schedule metadata."""

    def test_has_schedule_label(self) -> None:
        """ensure_source_sync_running has a TaskIQ schedule label."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        assert hasattr(ensure_source_sync_running, "labels")
        assert "schedule" in ensure_source_sync_running.labels

    def test_schedule_interval_is_60_seconds(self) -> None:
        """ensure_source_sync_running runs every 60 seconds."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        schedule = ensure_source_sync_running.labels["schedule"][0]
        assert schedule["interval"] == 60


# ---------------------------------------------------------------------------
# handle_source_sync — job wiring
# ---------------------------------------------------------------------------


class TestHandleSourceSyncJob:
    """handle_source_sync job must be a registered TaskIQ broker task."""

    def test_handle_source_sync_is_broker_task(self) -> None:
        """handle_source_sync is registered as a TaskIQ broker task."""
        from worker.jobs.source_sync import handle_source_sync

        assert hasattr(handle_source_sync, "task_name")

    def test_handle_source_sync_accepts_job_id(self) -> None:
        """handle_source_sync accepts a job_id: UUID parameter."""
        import inspect

        from worker.jobs.source_sync import handle_source_sync

        sig = inspect.signature(handle_source_sync.__wrapped__)
        params = list(sig.parameters.keys())
        assert "job_id" in params
