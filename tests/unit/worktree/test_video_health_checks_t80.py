"""Unit tests for T80: Video service health check integration.

Tests that health checks properly handle the video service:
- Main worktree (jobs profile active) expects video running
- Feature worktrees (jobs profile inactive) gracefully handle video absence
- Health check functions include video in service status
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worktree.health import (
    HealthCheckResult,
    _get_expected_services,
    check_worktree_health,
    quick_health_check,
)


class TestVideoServiceExpectations:
    """Tests for video service expectations based on worktree type."""

    def test_main_worktree_expects_video_service(self):
        """Main worktree should expect video service (jobs profile)."""
        # Mock the main worktree path
        with patch("worktree.health.get_main_worktree_path") as mock_main:
            mock_main.return_value = Path("/fake/main")
            expected = _get_expected_services(Path("/fake/main"))

            assert "video" in expected

    def test_feature_worktree_does_not_expect_video(self):
        """Feature worktrees should NOT expect video service."""
        with patch("worktree.health.get_main_worktree_path") as mock_main:
            mock_main.return_value = Path("/fake/main")
            expected = _get_expected_services(Path("/fake/42-feature"))

            assert "video" not in expected

    def test_video_included_with_other_jobs_profile_services(self):
        """Video should be expected alongside worker, scheduler, redis in main."""
        with patch("worktree.health.get_main_worktree_path") as mock_main:
            mock_main.return_value = Path("/fake/main")
            expected = _get_expected_services(Path("/fake/main"))

            # All jobs profile services
            assert "redis" in expected
            assert "worker" in expected
            assert "scheduler" in expected
            assert "video" in expected


class TestHealthCheckWithVideo:
    """Tests for health check integration with video service."""

    @patch("worktree.health.get_worktree_by_path")
    @patch("worktree.health.get_service_status")
    @patch("worktree.health.check_nginx_health")
    @patch("worktree.health.check_webapp_health")
    @patch("worktree.health.get_main_worktree_path")
    def test_main_worktree_health_includes_video_check(
        self,
        mock_main_path,
        mock_webapp_health,
        mock_nginx_health,
        mock_service_status,
        mock_get_worktree,
    ):
        """Health check for main worktree should check video service status."""
        mock_main_path.return_value = Path("/fake/main")
        mock_get_worktree.return_value = MagicMock(
            nginx_url="http://localhost:9000",
            webapp_url="http://localhost:8000",
        )
        mock_service_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "astro": "running",
            "redis": "running",
            "worker": "running",
            "scheduler": "running",
            "video": "running",
        }
        mock_nginx_health.return_value = True
        mock_webapp_health.return_value = True

        result = check_worktree_health(Path("/fake/main"))

        assert result.healthy is True
        assert "video" in result.services
        assert result.services["video"] == "running"

    @patch("worktree.health.get_worktree_by_path")
    @patch("worktree.health.get_service_status")
    @patch("worktree.health.check_nginx_health")
    @patch("worktree.health.check_webapp_health")
    @patch("worktree.health.get_main_worktree_path")
    def test_main_worktree_unhealthy_when_video_not_running(
        self,
        mock_main_path,
        mock_webapp_health,
        mock_nginx_health,
        mock_service_status,
        mock_get_worktree,
    ):
        """Health check should fail if video service not running in main worktree."""
        mock_main_path.return_value = Path("/fake/main")
        mock_get_worktree.return_value = MagicMock(
            nginx_url="http://localhost:9000",
            webapp_url="http://localhost:8000",
        )
        mock_service_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "astro": "running",
            "redis": "running",
            "worker": "running",
            "scheduler": "running",
            "video": "exited",  # Video not running
        }
        mock_nginx_health.return_value = True
        mock_webapp_health.return_value = True

        result = check_worktree_health(Path("/fake/main"))

        assert result.healthy is False
        assert any("video" in issue.lower() for issue in result.issues)

    @patch("worktree.health.get_worktree_by_path")
    @patch("worktree.health.get_service_status")
    @patch("worktree.health.check_nginx_health")
    @patch("worktree.health.check_webapp_health")
    @patch("worktree.health.get_main_worktree_path")
    def test_feature_worktree_healthy_without_video(
        self,
        mock_main_path,
        mock_webapp_health,
        mock_nginx_health,
        mock_service_status,
        mock_get_worktree,
    ):
        """Feature worktree should be healthy even without video service."""
        mock_main_path.return_value = Path("/fake/main")
        mock_get_worktree.return_value = MagicMock(
            nginx_url="http://localhost:9010",
            webapp_url="http://localhost:8010",
        )
        # Feature worktree only has core services, no video
        mock_service_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "astro": "running",
        }
        mock_nginx_health.return_value = True
        mock_webapp_health.return_value = True

        result = check_worktree_health(Path("/fake/42-feature"))

        assert result.healthy is True
        assert "video" not in result.services or result.services.get("video") is None

    @patch("worktree.health.get_worktree_by_path")
    @patch("worktree.health.get_service_status")
    @patch("worktree.health.check_nginx_health")
    @patch("worktree.health.check_webapp_health")
    @patch("worktree.health.get_main_worktree_path")
    def test_main_worktree_unhealthy_when_video_missing(
        self,
        mock_main_path,
        mock_webapp_health,
        mock_nginx_health,
        mock_service_status,
        mock_get_worktree,
    ):
        """Health check should fail if video service not found in main worktree."""
        mock_main_path.return_value = Path("/fake/main")
        mock_get_worktree.return_value = MagicMock(
            nginx_url="http://localhost:9000",
            webapp_url="http://localhost:8000",
        )
        # Video service not in status (container doesn't exist)
        mock_service_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "astro": "running",
            "redis": "running",
            "worker": "running",
            "scheduler": "running",
            # video missing
        }
        mock_nginx_health.return_value = True
        mock_webapp_health.return_value = True

        result = check_worktree_health(Path("/fake/main"))

        assert result.healthy is False
        assert any(
            "video" in issue.lower() and "not found" in issue.lower() for issue in result.issues
        )


class TestQuickHealthCheckWithVideo:
    """Tests for quick health check with video service."""

    @patch("worktree.health.get_service_status")
    @patch("worktree.health.get_main_worktree_path")
    def test_main_worktree_quick_check_includes_video(self, mock_main_path, mock_service_status):
        """Quick health check should verify video running in main worktree."""
        mock_main_path.return_value = Path("/fake/main")
        mock_service_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "astro": "running",
            "redis": "running",
            "worker": "running",
            "scheduler": "running",
            "video": "running",
        }

        result = quick_health_check(Path("/fake/main"))

        assert result is True

    @patch("worktree.health.get_service_status")
    @patch("worktree.health.get_main_worktree_path")
    def test_main_worktree_quick_check_fails_without_video(
        self, mock_main_path, mock_service_status
    ):
        """Quick health check should fail if video not running in main."""
        mock_main_path.return_value = Path("/fake/main")
        mock_service_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "astro": "running",
            "redis": "running",
            "worker": "running",
            "scheduler": "running",
            "video": "exited",  # Not running
        }

        result = quick_health_check(Path("/fake/main"))

        assert result is False

    @patch("worktree.health.get_service_status")
    @patch("worktree.health.get_main_worktree_path")
    def test_feature_worktree_quick_check_without_video(self, mock_main_path, mock_service_status):
        """Quick health check should pass for feature worktree without video."""
        mock_main_path.return_value = Path("/fake/main")
        mock_service_status.return_value = {
            "nginx": "running",
            "webapp": "running",
            "db": "running",
            "astro": "running",
        }

        result = quick_health_check(Path("/fake/42-feature"))

        assert result is True


class TestHealthCheckResultWithVideo:
    """Tests for HealthCheckResult with video service."""

    @patch("worktree.health.get_main_worktree_path")
    def test_containers_running_includes_video_for_main(self, mock_main_path):
        """containers_running should check video for main worktree."""
        mock_main_path.return_value = Path("/fake/main")

        result = HealthCheckResult(
            healthy=True,
            services={
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "scheduler": "running",
                "video": "running",
            },
            nginx_responding=True,
            webapp_responding=True,
            issues=[],
            worktree_path=Path("/fake/main"),
        )

        assert result.containers_running is True

    @patch("worktree.health.get_main_worktree_path")
    def test_containers_running_false_when_video_not_running_main(self, mock_main_path):
        """containers_running should be False if video not running in main."""
        mock_main_path.return_value = Path("/fake/main")

        result = HealthCheckResult(
            healthy=False,
            services={
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "scheduler": "running",
                "video": "exited",  # Not running
            },
            nginx_responding=True,
            webapp_responding=True,
            issues=["Service video is exited"],
            worktree_path=Path("/fake/main"),
        )

        assert result.containers_running is False

    @patch("worktree.health.get_main_worktree_path")
    def test_containers_running_true_for_feature_without_video(self, mock_main_path):
        """containers_running should be True for feature worktree without video."""
        mock_main_path.return_value = Path("/fake/main")

        result = HealthCheckResult(
            healthy=True,
            services={
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
            },
            nginx_responding=True,
            webapp_responding=True,
            issues=[],
            worktree_path=Path("/fake/42-feature"),
        )

        assert result.containers_running is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
