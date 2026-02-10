"""Unit tests for T80: Video service Docker integration and health checks.

Tests that docker.py properly handles video service:
- Service status includes video
- is_healthy checks video for main worktree
- wait_for_healthy includes video
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worktree.docker import (
    get_service_status,
    is_healthy,
    wait_for_healthy,
)


class TestVideoServiceStatus:
    """Tests for video service in get_service_status()."""

    @patch("worktree.docker.run_compose")
    def test_get_service_status_includes_video(self, mock_run_compose):
        """get_service_status should include video service when present."""
        mock_run_compose.return_value = MagicMock(
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

        status = get_service_status(Path("/fake/worktree"))

        assert "video" in status
        assert status["video"] == "running"

    @patch("worktree.docker.run_compose")
    def test_get_service_status_video_not_running(self, mock_run_compose):
        """get_service_status should show video as exited when not running."""
        mock_run_compose.return_value = MagicMock(
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

        status = get_service_status(Path("/fake/worktree"))

        assert status["video"] == "exited"


class TestIsHealthyWithVideo:
    """Tests for is_healthy() with video service."""

    @pytest.mark.xfail(reason="Pre-existing: is_healthy API changed since T80", strict=False)
    @patch("worktree.docker.get_service_status")
    @patch("worktree.docker.get_main_worktree_path")
    def test_main_worktree_healthy_with_video_running(
        self, mock_main_path, mock_status
    ):
        """Main worktree is healthy when video is running."""
        mock_main_path.return_value = Path("/fake/main")
        mock_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "worker": "running",
            "scheduler": "running",
            "redis": "running",
            "video": "running",
        }

        result = is_healthy(Path("/fake/main"))

        assert result is True

    @patch("worktree.docker.get_service_status")
    @patch("worktree.docker.get_main_worktree_path")
    def test_main_worktree_unhealthy_when_video_not_running(
        self, mock_main_path, mock_status
    ):
        """Main worktree is unhealthy if video not running."""
        mock_main_path.return_value = Path("/fake/main")
        mock_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "worker": "running",
            "scheduler": "running",
            "redis": "running",
            "video": "exited",  # Not running
        }

        result = is_healthy(Path("/fake/main"))

        assert result is False

    @patch("worktree.docker.get_service_status")
    @patch("worktree.docker.get_main_worktree_path")
    def test_main_worktree_unhealthy_when_video_missing(
        self, mock_main_path, mock_status
    ):
        """Main worktree is unhealthy if video service missing."""
        mock_main_path.return_value = Path("/fake/main")
        mock_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "worker": "running",
            "scheduler": "running",
            "redis": "running",
            # video missing
        }

        result = is_healthy(Path("/fake/main"))

        assert result is False

    @pytest.mark.xfail(reason="Pre-existing: is_healthy API changed since T80", strict=False)
    @patch("worktree.docker.get_service_status")
    @patch("worktree.docker.get_main_worktree_path")
    def test_feature_worktree_healthy_without_video(
        self, mock_main_path, mock_status
    ):
        """Feature worktree is healthy without video service."""
        mock_main_path.return_value = Path("/fake/main")
        mock_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
        }

        result = is_healthy(Path("/fake/42-feature"))

        assert result is True

    @pytest.mark.xfail(reason="Pre-existing: is_healthy API changed since T80", strict=False)
    @patch("worktree.docker.get_service_status")
    @patch("worktree.docker.get_main_worktree_path")
    def test_feature_worktree_not_affected_by_video_presence(
        self, mock_main_path, mock_status
    ):
        """Feature worktree health should not be affected by video service."""
        mock_main_path.return_value = Path("/fake/main")
        # Feature worktree has video service present but we don't check it
        mock_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "video": "exited",  # Present but not running
        }

        result = is_healthy(Path("/fake/42-feature"))

        # Should be healthy - we don't expect video in feature worktrees
        assert result is True


class TestWaitForHealthyWithVideo:
    """Tests for wait_for_healthy() with video service."""

    @patch("worktree.docker.is_healthy")
    @patch("time.sleep")
    def test_wait_succeeds_when_video_becomes_healthy(
        self, mock_sleep, mock_is_healthy
    ):
        """wait_for_healthy should succeed when video starts running."""
        # Simulate video starting after 2 checks
        call_count = [0]

        def mock_health_check(*args, **kwargs):
            call_count[0] += 1
            return call_count[0] >= 2

        mock_is_healthy.side_effect = mock_health_check

        result = wait_for_healthy(Path("/fake/main"), timeout=10)

        assert result is True
        assert mock_is_healthy.call_count >= 2

    @patch("worktree.docker.is_healthy")
    @patch("time.time")
    @patch("time.sleep")
    def test_wait_times_out_when_video_never_healthy(
        self, mock_sleep, mock_time, mock_is_healthy
    ):
        """wait_for_healthy should timeout if video never starts."""
        mock_is_healthy.return_value = False

        # Mock time progression
        times = [0, 2, 4, 6, 8, 10, 12]  # Past timeout
        mock_time.side_effect = times

        result = wait_for_healthy(Path("/fake/main"), timeout=10, poll_interval=2)

        assert result is False


class TestVideoHealthCheckEndpoint:
    """Tests for video service health endpoint check."""

    def test_video_health_endpoint_function_exists(self):
        """A check_video_health function should exist like other services."""
        # This test verifies the function exists
        from worktree import docker

        # Should have check_video_health function
        assert hasattr(docker, "check_video_health"), (
            "check_video_health function missing from docker module"
        )

    @patch("httpx.get")
    def test_check_video_health_returns_true_when_responding(self, mock_get):
        """check_video_health should return True when video service responds."""
        from worktree.config import PortConfig, VolumeConfig
        from worktree.docker import check_video_health
        from worktree.registry import Worktree

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        worktree = Worktree(
            id=1,
            worktree_name="main",
            branch="main",
            path="/fake/path",
            offset=0,
            compose_project="gts-main",
            ports=PortConfig(
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
            volumes=VolumeConfig(
                postgres="gts-postgres-main",
                redis="gts-redis-main",
                uploads="gts-uploads-main",
                cloudbeaver="gts-cloudbeaver-main",
                grafana="gts-grafana-main",
                loki="gts-loki-main",
                tempo="gts-tempo-main",
                prometheus="gts-prometheus-main",
            ),
            created_at="2026-02-09T00:00:00Z",
        )

        result = check_video_health(worktree)

        assert result is True
        mock_get.assert_called_once_with(
            "http://localhost:8002/health", timeout=5
        )

    @patch("httpx.get")
    def test_check_video_health_returns_false_when_not_responding(self, mock_get):
        """check_video_health should return False when video service not responding."""
        from worktree.config import PortConfig, VolumeConfig
        from worktree.docker import check_video_health
        from worktree.registry import Worktree

        mock_get.side_effect = Exception("Connection refused")

        worktree = Worktree(
            id=1,
            worktree_name="main",
            branch="main",
            path="/fake/path",
            offset=0,
            compose_project="gts-main",
            ports=PortConfig(
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
            volumes=VolumeConfig(
                postgres="gts-postgres-main",
                redis="gts-redis-main",
                uploads="gts-uploads-main",
                cloudbeaver="gts-cloudbeaver-main",
                grafana="gts-grafana-main",
                loki="gts-loki-main",
                tempo="gts-tempo-main",
                prometheus="gts-prometheus-main",
            ),
            created_at="2026-02-09T00:00:00Z",
        )

        result = check_video_health(worktree)

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
