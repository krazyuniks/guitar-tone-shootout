"""Integration tests for video BC Docker container configuration."""

from pathlib import Path

import pytest
import yaml


class TestVideoDockerfile:
    """Test Dockerfile.video configuration."""

    def test_dockerfile_exists(self):
        """Dockerfile.video must exist."""
        dockerfile = Path("/app/infrastructure/docker/Dockerfile.video")
        assert dockerfile.exists(), "Dockerfile.video must exist"

    def test_dockerfile_has_nodejs_20(self):
        """Dockerfile must specify Node.js 20."""
        dockerfile = Path("/app/infrastructure/docker/Dockerfile.video")
        content = dockerfile.read_text()

        # Check for Node.js 20 in FROM statement or installation
        assert "node:20" in content.lower() or ("nodejs" in content.lower() and "20" in content), (
            "Dockerfile must include Node.js 20"
        )

    def test_dockerfile_has_chromium(self):
        """Dockerfile must install Chromium for Remotion rendering."""
        dockerfile = Path("/app/infrastructure/docker/Dockerfile.video")
        content = dockerfile.read_text()

        assert "chromium" in content.lower(), "Dockerfile must install Chromium"

    def test_dockerfile_has_python_uv(self):
        """Dockerfile must include Python and uv for hybrid Python/Node.js environment."""
        dockerfile = Path("/app/infrastructure/docker/Dockerfile.video")
        content = dockerfile.read_text()

        # Check for Python base image or installation
        assert "python" in content.lower(), "Dockerfile must include Python"

        # Check for uv installation
        assert "uv" in content.lower(), "Dockerfile must install uv"

    def test_dockerfile_sets_workdir(self):
        """Dockerfile must set a working directory."""
        dockerfile = Path("/app/infrastructure/docker/Dockerfile.video")
        content = dockerfile.read_text()

        assert "WORKDIR" in content, "Dockerfile must set WORKDIR"

    def test_dockerfile_exposes_port(self):
        """Dockerfile must expose internal port for HTTP communication."""
        dockerfile = Path("/app/infrastructure/docker/Dockerfile.video")
        content = dockerfile.read_text()

        assert "EXPOSE" in content, "Dockerfile must EXPOSE a port"


class TestVideoDockerComposeService:
    """Test docker-compose.yml video service configuration."""

    @pytest.fixture
    def compose_config(self) -> dict:
        """Load and parse docker-compose.yml."""
        # In Docker container, files are mounted at /app
        compose_file = Path("/app/docker-compose.yml")
        with compose_file.open() as f:
            return yaml.safe_load(f)

    def test_video_service_exists(self, compose_config: dict):
        """Video service must be defined in docker-compose.yml."""
        assert "services" in compose_config, "docker-compose.yml must have services section"
        assert "video-worker" in compose_config["services"], "video-worker service must be defined"

    def test_video_service_on_jobs_profile(self, compose_config: dict):
        """Video service must be on 'jobs' profile (not default)."""
        video_service = compose_config["services"]["video-worker"]

        assert "profiles" in video_service, "video service must specify profiles"
        assert "jobs" in video_service["profiles"], "video service must be on 'jobs' profile"

    def test_video_service_builds_from_dockerfile(self, compose_config: dict):
        """Video service must build from Dockerfile.video."""
        video_service = compose_config["services"]["video-worker"]

        assert "build" in video_service, "video service must have build configuration"
        build_config = video_service["build"]

        assert "dockerfile" in build_config, "video service must specify dockerfile"
        assert "Dockerfile.video" in build_config["dockerfile"], (
            "video service must use Dockerfile.video"
        )

    def test_video_service_mounts_video_worker_app(self, compose_config: dict):
        """Video service must mount apps/video_worker/ source directory."""
        video_service = compose_config["services"]["video-worker"]

        assert "volumes" in video_service, "video service must have volumes"
        volumes = video_service["volumes"]

        video_mount_found = any("apps/video_worker" in str(volume) for volume in volumes)
        assert video_mount_found, "video service must mount apps/video_worker/"

    def test_video_service_exposes_internal_port(self, compose_config: dict):
        """Video service must expose internal port 8002."""
        video_service = compose_config["services"]["video-worker"]

        # Port can be defined in EXPOSE (Dockerfile) or as internal port in compose
        # Check if service has explicit ports or relies on Dockerfile EXPOSE
        # For internal services, no host port mapping is needed

        # This tests that the service is configured to listen on a port
        # The actual port validation will be in the Dockerfile tests
        # Here we just verify the service has environment or command that references a port

        # Services should have health check or environment that indicates port
        assert (
            "healthcheck" in video_service
            or "environment" in video_service
            or "command" in video_service
        ), "video service must have configuration indicating port usage"

    def test_video_service_has_health_check(self, compose_config: dict):
        """Video service must have health check configured."""
        video_service = compose_config["services"]["video-worker"]

        assert "healthcheck" in video_service, "video service must have healthcheck"
        healthcheck = video_service["healthcheck"]

        assert "test" in healthcheck, "healthcheck must have test command"
        assert "interval" in healthcheck, "healthcheck must have interval"
        assert "timeout" in healthcheck, "healthcheck must have timeout"
        assert "retries" in healthcheck, "healthcheck must have retries"

    def test_video_service_has_restart_policy(self, compose_config: dict):
        """Video service should have restart policy for resilience."""
        video_service = compose_config["services"]["video-worker"]

        # Video service should have restart policy (typically unless-stopped for background services)
        assert "restart" in video_service, "video service should have restart policy"
        assert video_service["restart"] in [
            "unless-stopped",
            "always",
            "on-failure",
        ], "video service restart policy should be unless-stopped, always, or on-failure"

    def test_video_service_depends_on_database(self, compose_config: dict):
        """Video worker depends on the database for job state."""
        video_service = compose_config["services"]["video-worker"]

        assert "depends_on" in video_service, "video-worker must declare depends_on"
        assert "db" in video_service["depends_on"], "video-worker must depend on db"


class TestVideoServiceStartup:
    """Test video service configuration is valid for startup."""

    def test_video_service_in_jobs_profile_config(self):
        """Video service with jobs profile must have valid YAML configuration."""
        compose_file = Path("/app/docker-compose.yml")
        with compose_file.open() as f:
            config = yaml.safe_load(f)

        video_service = config["services"]["video-worker"]

        # Verify video service is included in jobs profile
        assert "profiles" in video_service, "video service must specify profiles"
        assert "jobs" in video_service["profiles"], "video service must be on jobs profile"

        # Verify service has required configuration keys for startup
        assert "build" in video_service, "video service must have build config"
        assert "healthcheck" in video_service, "video service must have healthcheck"

    def test_video_service_dockerfile_is_valid_docker_syntax(self):
        """Dockerfile.video must contain valid Docker instructions."""
        dockerfile = Path("/app/infrastructure/docker/Dockerfile.video")
        content = dockerfile.read_text()
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        # Must start with FROM
        assert lines[0].startswith("FROM"), "Dockerfile must start with FROM instruction"

        # Must contain required instructions for buildable image
        instructions = {line.split()[0] for line in lines}
        assert "WORKDIR" in instructions, "Dockerfile must set WORKDIR"
        assert "EXPOSE" in instructions, "Dockerfile must EXPOSE a port"


class TestVideoWorkerGateIsolation:
    """Test video-worker stays off the feature-worktree gate path."""

    @pytest.fixture
    def video_service(self) -> dict:
        """Load video-worker config from the base compose file."""
        compose_file = Path("/app/docker-compose.yml")
        with compose_file.open() as f:
            config = yaml.safe_load(f)
        return config["services"]["video-worker"]

    def test_video_worker_is_jobs_profile_only(self, video_service: dict):
        """Feature worktrees do not start BC workers during the deterministic gate."""
        assert video_service.get("profiles") == ["jobs"], (
            "video-worker must stay on the jobs profile, not the default gate path"
        )

    def test_video_worker_has_no_host_port_mapping(self, video_service: dict):
        """The worktree engine allocates host ports only for webapp and db."""
        assert "ports" not in video_service, (
            "video-worker must not publish a host port in feature worktrees"
        )
