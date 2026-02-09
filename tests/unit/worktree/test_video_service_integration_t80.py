"""Unit tests for T80: Video service integration in worktree.py.

Tests that the video service is properly integrated into worktree management:
- Port allocation
- Override generation
- Health checks
- Status display
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worktree.config import PortConfig, VolumeConfig, calculate_ports
from worktree.registry import Worktree
from worktree.resources import (
    check_ports_available,
    format_ports_display,
    generate_compose_override,
    generate_env_local,
)


class TestVideoPortAllocation:
    """Tests for video port allocation in PortConfig."""

    def test_port_config_has_video_attribute(self):
        """PortConfig should have a video port attribute."""
        ports = calculate_ports(offset=0)
        assert hasattr(ports, "video"), "PortConfig missing video attribute"

    def test_video_port_calculated_for_main_worktree(self):
        """Main worktree (offset=0) should get base video port."""
        ports = calculate_ports(offset=0)
        # Video service runs on port 8002 internally
        # Expected: base_port_video (should be defined in settings)
        assert ports.video == 8002

    def test_video_port_calculated_for_feature_worktree(self):
        """Feature worktrees should get offset video ports."""
        ports_feature1 = calculate_ports(offset=1)
        ports_feature2 = calculate_ports(offset=2)

        # Video ports should be unique per worktree
        assert ports_feature1.video != 8002
        assert ports_feature2.video != 8002
        assert ports_feature1.video != ports_feature2.video

    def test_video_port_uses_http_offset_multiplier(self):
        """Video port should use HTTP offset multiplier (10) like other HTTP services."""
        ports_main = calculate_ports(offset=0)
        ports_feature = calculate_ports(offset=1)

        # HTTP services use offset * 10
        # If main is 8002, feature should be 8002 + 10 = 8012
        expected_offset = 10
        assert ports_feature.video == ports_main.video + expected_offset


class TestEnvLocalGeneration:
    """Tests for .env.local file generation with video port."""

    def test_env_local_includes_video_port(self, tmp_path: Path):
        """Generated .env.local should include VIDEO_PORT."""
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

        env_path = tmp_path / ".env.local"
        generate_env_local(worktree, env_path)

        content = env_path.read_text()
        assert "VIDEO_PORT=8002" in content

    def test_env_local_video_port_for_feature_worktree(self, tmp_path: Path):
        """Feature worktree .env.local should have offset video port."""
        worktree = Worktree(
            id=2,
            worktree_name="42-video-feature",
            branch="42-video-feature",
            path="/fake/path",
            offset=1,
            compose_project="gts-42-video-feature",
            ports=PortConfig(
                nginx=9010,
                astro=4331,
                webapp=8010,
                db=5433,
                redis=6380,
                cloudbeaver=8988,
                grafana=3010,
                prometheus=9100,
                loki=3110,
                tempo=3210,
                otlp_grpc=4327,
                otlp_http=4328,
                alloy=12355,
                video=8012,  # Base + offset * 10
            ),
            volumes=VolumeConfig(
                postgres="gts-postgres-42-video-feature",
                redis="gts-redis-42-video-feature",
                uploads="gts-uploads-42-video-feature",
                cloudbeaver="gts-cloudbeaver-42-video-feature",
                grafana="gts-grafana-42-video-feature",
                loki="gts-loki-42-video-feature",
                tempo="gts-tempo-42-video-feature",
                prometheus="gts-prometheus-42-video-feature",
            ),
            created_at="2026-02-09T00:00:00Z",
        )

        env_path = tmp_path / ".env.local"
        generate_env_local(worktree, env_path)

        content = env_path.read_text()
        assert "VIDEO_PORT=8012" in content


class TestComposeOverrideGeneration:
    """Tests for docker-compose.override.yml generation with video service."""

    def test_compose_override_includes_video_service(self, tmp_path: Path):
        """Generated override should include video service configuration."""
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

        override_path = tmp_path / "docker-compose.override.yml"
        generate_compose_override(worktree, override_path)

        content = override_path.read_text()
        assert "video:" in content

    def test_compose_override_video_port_mapping(self, tmp_path: Path):
        """Video service should have correct port mapping in override."""
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

        override_path = tmp_path / "docker-compose.override.yml"
        generate_compose_override(worktree, override_path)

        content = override_path.read_text()
        # Video service should expose port 8002 externally (jobs profile, main worktree)
        assert "127.0.0.1:8002:8002" in content or "8002:8002" in content

    def test_compose_override_video_container_name(self, tmp_path: Path):
        """Video service should have correct container name in override."""
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

        override_path = tmp_path / "docker-compose.override.yml"
        generate_compose_override(worktree, override_path)

        content = override_path.read_text()
        assert "gts-main-video" in content


class TestPortAvailabilityChecks:
    """Tests for port availability checking including video port."""

    def test_check_ports_includes_video(self):
        """Port availability check should include video port."""
        ports = PortConfig(
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
        )

        # Mock socket to avoid actual port binding
        with patch("socket.socket"):
            results = check_ports_available(ports)
            assert "video" in results

    def test_video_port_conflict_detection(self):
        """Should detect when video port is already in use."""
        ports = PortConfig(
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
        )

        # Mock video port as in use
        def mock_bind(*args):
            if args[0][1] == 8002:  # video port
                raise OSError("Port already in use")

        mock_socket = MagicMock()
        mock_socket_instance = MagicMock()
        mock_socket_instance.bind.side_effect = mock_bind
        mock_socket.return_value.__enter__.return_value = mock_socket_instance

        with patch("socket.socket", mock_socket):
            results = check_ports_available(ports)
            assert results.get("video") is False


class TestPortDisplayFormatting:
    """Tests for port display formatting including video port."""

    def test_format_ports_includes_video(self):
        """Port display should include video port abbreviation."""
        ports = PortConfig(
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
            alloy=12355,
            video=8002,
        )

        display = format_ports_display(ports)
        # Should include "vid:8002" or similar abbreviation
        assert "8002" in display
        assert "vid:" in display or "video:" in display


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
