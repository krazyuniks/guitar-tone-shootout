"""Unit tests for T80: Video service health check integration.

Tests that health checks properly handle the video service:
- Main worktree (jobs profile active) expects video running
- Feature worktrees (jobs profile inactive) gracefully handle video absence
- Health check functions include video in service status

Uses monkeypatch instead of unittest.mock.
"""

import types
from pathlib import Path

import pytest

from worktree.health import (
    HealthCheckResult,
    _get_expected_services,
    check_worktree_health,
    quick_health_check,
)


class TestVideoServiceExpectations:
    """Tests for video service expectations based on worktree type."""

    def test_main_worktree_expects_video_service(self, monkeypatch: pytest.MonkeyPatch):
        """Main worktree should expect video-worker service (jobs profile)."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        expected = _get_expected_services(Path("/fake/main"))
        assert "video-worker" in expected

    def test_feature_worktree_does_not_expect_video(self, monkeypatch: pytest.MonkeyPatch):
        """Feature worktrees should NOT expect video-worker service."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        expected = _get_expected_services(Path("/fake/42-feature"))
        assert "video-worker" not in expected

    def test_video_included_with_other_jobs_profile_services(self, monkeypatch: pytest.MonkeyPatch):
        """Video-worker should be expected alongside t3k-sync and audio-worker in main."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        expected = _get_expected_services(Path("/fake/main"))

        assert "t3k-sync" in expected
        assert "audio-worker" in expected
        assert "video-worker" in expected


class TestHealthCheckWithVideo:
    """Tests for health check integration with video service."""

    def test_main_worktree_health_includes_video_check(self, monkeypatch: pytest.MonkeyPatch):
        """Health check for main worktree should check video service status."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.health.get_worktree_by_path",
            lambda _path: types.SimpleNamespace(
                nginx_url="http://localhost:9000",
                webapp_url="http://localhost:8000",
            ),
        )
        monkeypatch.setattr(
            "worktree.health.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "t3k-sync": "running",
                "audio-worker": "running",
                "video-worker": "running",
            },
        )
        monkeypatch.setattr("worktree.health.check_nginx_health", lambda _url: True)
        monkeypatch.setattr("worktree.health.check_webapp_health", lambda _url: True)

        result = check_worktree_health(Path("/fake/main"))

        assert result.healthy is True
        assert "video-worker" in result.services
        assert result.services["video-worker"] == "running"

    def test_main_worktree_unhealthy_when_video_not_running(self, monkeypatch: pytest.MonkeyPatch):
        """Health check should fail if video service not running in main worktree."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.health.get_worktree_by_path",
            lambda _path: types.SimpleNamespace(
                nginx_url="http://localhost:9000",
                webapp_url="http://localhost:8000",
            ),
        )
        monkeypatch.setattr(
            "worktree.health.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "t3k-sync": "running",
                "audio-worker": "running",
                "video-worker": "exited",
            },
        )
        monkeypatch.setattr("worktree.health.check_nginx_health", lambda _url: True)
        monkeypatch.setattr("worktree.health.check_webapp_health", lambda _url: True)

        result = check_worktree_health(Path("/fake/main"))

        assert result.healthy is False
        assert any("video" in issue.lower() for issue in result.issues)

    def test_feature_worktree_healthy_without_video(self, monkeypatch: pytest.MonkeyPatch):
        """Feature worktree should be healthy even without video service."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.health.get_worktree_by_path",
            lambda _path: types.SimpleNamespace(
                nginx_url="http://localhost:9010",
                webapp_url="http://localhost:8010",
            ),
        )
        monkeypatch.setattr(
            "worktree.health.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
            },
        )
        monkeypatch.setattr("worktree.health.check_nginx_health", lambda _url: True)
        monkeypatch.setattr("worktree.health.check_webapp_health", lambda _url: True)

        result = check_worktree_health(Path("/fake/42-feature"))

        assert result.healthy is True
        assert "video-worker" not in result.services or result.services.get("video-worker") is None

    def test_main_worktree_unhealthy_when_video_missing(self, monkeypatch: pytest.MonkeyPatch):
        """Health check should fail if video service not found in main worktree."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.health.get_worktree_by_path",
            lambda _path: types.SimpleNamespace(
                nginx_url="http://localhost:9000",
                webapp_url="http://localhost:8000",
            ),
        )
        monkeypatch.setattr(
            "worktree.health.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "t3k-sync": "running",
                "audio-worker": "running",
            },
        )
        monkeypatch.setattr("worktree.health.check_nginx_health", lambda _url: True)
        monkeypatch.setattr("worktree.health.check_webapp_health", lambda _url: True)

        result = check_worktree_health(Path("/fake/main"))

        assert result.healthy is False
        assert any(
            "video" in issue.lower() and "not found" in issue.lower() for issue in result.issues
        )


class TestQuickHealthCheckWithVideo:
    """Tests for quick health check with video service."""

    def test_main_worktree_quick_check_includes_video(self, monkeypatch: pytest.MonkeyPatch):
        """Quick health check should verify video running in main worktree."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.health.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "t3k-sync": "running",
                "audio-worker": "running",
                "video-worker": "running",
            },
        )

        result = quick_health_check(Path("/fake/main"))
        assert result is True

    def test_main_worktree_quick_check_fails_without_video(self, monkeypatch: pytest.MonkeyPatch):
        """Quick health check should fail if video not running in main."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.health.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "t3k-sync": "running",
                "audio-worker": "running",
                "video-worker": "exited",
            },
        )

        result = quick_health_check(Path("/fake/main"))
        assert result is False

    def test_feature_worktree_quick_check_without_video(self, monkeypatch: pytest.MonkeyPatch):
        """Quick health check should pass for feature worktree without video."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))
        monkeypatch.setattr(
            "worktree.health.get_service_status",
            lambda _path: {
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
            },
        )

        result = quick_health_check(Path("/fake/42-feature"))
        assert result is True


class TestHealthCheckResultWithVideo:
    """Tests for HealthCheckResult with video service."""

    def test_containers_running_includes_video_for_main(self, monkeypatch: pytest.MonkeyPatch):
        """containers_running should check video for main worktree."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))

        result = HealthCheckResult(
            healthy=True,
            services={
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "t3k-sync": "running",
                "audio-worker": "running",
                "video-worker": "running",
            },
            nginx_responding=True,
            webapp_responding=True,
            issues=[],
            worktree_path=Path("/fake/main"),
        )

        assert result.containers_running is True

    def test_containers_running_false_when_video_not_running_main(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """containers_running should be False if video not running in main."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))

        result = HealthCheckResult(
            healthy=False,
            services={
                "nginx": "running",
                "webapp": "running",
                "db": "running",
                "astro": "running",
                "redis": "running",
                "worker": "running",
                "t3k-sync": "running",
                "audio-worker": "running",
                "video-worker": "exited",
            },
            nginx_responding=True,
            webapp_responding=True,
            issues=["Service video-worker is exited"],
            worktree_path=Path("/fake/main"),
        )

        assert result.containers_running is False

    def test_containers_running_true_for_feature_without_video(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """containers_running should be True for feature worktree without video."""
        monkeypatch.setattr("worktree.health.get_main_worktree_path", lambda: Path("/fake/main"))

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
