"""Unit tests for T80: Video service Docker integration and health checks.

Tests that docker.py properly handles video service:
- Service status includes video
- is_healthy checks video for main worktree
- wait_for_healthy includes video

Uses monkeypatch instead of unittest.mock.
"""

import types
from pathlib import Path

import pytest

from worktree.config import PortConfig, VolumeConfig
from worktree.docker import (
    get_service_status,
    is_healthy,
    wait_for_healthy,
)
from worktree.registry import Worktree


def _make_worktree(**overrides) -> Worktree:
    """Create a Worktree with default test values."""
    defaults = {
        "id": 1,
        "worktree_name": "main",
        "branch": "main",
        "path": "/fake/path",
        "offset": 0,
        "compose_project": "gts-main",
        "ports": PortConfig(
            nginx=9000,
            astro=4321,
            webapp=8000,
            db=5432,
            redis=6379,
            cloudbeaver=8978,
            grafana=3000,
            prometheus=9090,
            loki=3100,
            tempo=3200,
            otlp_grpc=4317,
            otlp_http=4318,
            alloy=12345,
            video=8002,
        ),
        "volumes": VolumeConfig(
            postgres="gts-postgres-main",
            redis="gts-redis-main",
            uploads="gts-uploads-main",
            cloudbeaver="gts-cloudbeaver-main",
            grafana="gts-grafana-main",
            loki="gts-loki-main",
            tempo="gts-tempo-main",
            prometheus="gts-prometheus-main",
        ),
        "created_at": "2026-02-09T00:00:00Z",
    }
    defaults.update(overrides)
    return Worktree(**defaults)


class TestVideoServiceStatus:
    """Tests for video service in get_service_status()."""

    def test_get_service_status_includes_video(self, monkeypatch: pytest.MonkeyPatch):
        """get_service_status should include video service when present."""
        result = types.SimpleNamespace(
            stdout=(
                "nginx:running\n"
                "webapp:running\n"
                "db:running\n"
                "astro:running\n"
                "redis:running\n"
                "worker:running\n"
                "scheduler:running\n"
                "video:running\n"
            )
        )
        monkeypatch.setattr("worktree.docker.run_compose", lambda *_a, **_kw: result)

        status = get_service_status(Path("/fake/worktree"))

        assert "video" in status
        assert status["video"] == "running"

    def test_get_service_status_video_not_running(self, monkeypatch: pytest.MonkeyPatch):
        """get_service_status should show video as exited when not running."""
        result = types.SimpleNamespace(
            stdout=(
                "nginx:running\n"
                "webapp:running\n"
                "db:running\n"
                "astro:running\n"
                "redis:running\n"
                "worker:running\n"
                "scheduler:running\n"
                "video:exited\n"
            )
        )
        monkeypatch.setattr("worktree.docker.run_compose", lambda *_a, **_kw: result)

        status = get_service_status(Path("/fake/worktree"))

        assert status["video"] == "exited"


class TestIsHealthyWithVideo:
    """Tests for is_healthy() with video service."""

    def test_main_worktree_unhealthy_when_video_not_running(self, monkeypatch: pytest.MonkeyPatch):
        """Main worktree is unhealthy if video not running."""
        monkeypatch.setattr("worktree.docker.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.docker.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "worker": "running",
                "scheduler": "running",
                "redis": "running",
                "video": "exited",
            },
        )

        result = is_healthy(Path("/fake/main"))
        assert result is False

    def test_main_worktree_unhealthy_when_video_missing(self, monkeypatch: pytest.MonkeyPatch):
        """Main worktree is unhealthy if video service missing."""
        monkeypatch.setattr("worktree.docker.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.docker.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "worker": "running",
                "scheduler": "running",
                "redis": "running",
            },
        )

        result = is_healthy(Path("/fake/main"))
        assert result is False


class TestWaitForHealthyWithVideo:
    """Tests for wait_for_healthy() with video service."""

    def test_wait_succeeds_when_video_becomes_healthy(self, monkeypatch: pytest.MonkeyPatch):
        """wait_for_healthy should succeed when video starts running."""
        call_count = 0

        def mock_health_check(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return call_count >= 2

        monkeypatch.setattr("worktree.docker.is_healthy", mock_health_check)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = wait_for_healthy(Path("/fake/main"), timeout=10)

        assert result is True
        assert call_count >= 2

    def test_wait_times_out_when_video_never_healthy(self, monkeypatch: pytest.MonkeyPatch):
        """wait_for_healthy should timeout if video never starts."""
        monkeypatch.setattr("worktree.docker.is_healthy", lambda *_a, **_kw: False)

        # Mock time progression
        times = iter([0, 2, 4, 6, 8, 10, 12])
        monkeypatch.setattr("time.time", lambda: next(times))
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = wait_for_healthy(Path("/fake/main"), timeout=10, poll_interval=2)

        assert result is False


class TestVideoHealthCheckEndpoint:
    """Tests for video service health endpoint check."""

    def test_video_health_endpoint_function_exists(self):
        """A check_video_health function should exist like other services."""
        from worktree import docker

        assert hasattr(docker, "check_video_health"), (
            "check_video_health function missing from docker module"
        )

    def test_check_video_health_returns_true_when_responding(self, monkeypatch: pytest.MonkeyPatch):
        """check_video_health should return True when video service responds."""
        from worktree.docker import check_video_health

        monkeypatch.setattr(
            "httpx.get",
            lambda _url, **_kw: types.SimpleNamespace(status_code=200),
        )

        worktree = _make_worktree()
        result = check_video_health(worktree)

        assert result is True

    def test_check_video_health_returns_false_when_not_responding(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """check_video_health should return False when video service not responding."""
        from worktree.docker import check_video_health

        def raise_error(*args, **kwargs):
            raise Exception("Connection refused")

        monkeypatch.setattr("httpx.get", raise_error)

        worktree = _make_worktree()
        result = check_video_health(worktree)

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
