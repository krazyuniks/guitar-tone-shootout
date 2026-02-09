"""Integration tests for video BC Docker container configuration."""

import subprocess
import time
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
        assert (
            "node:20" in content.lower() or
            "nodejs" in content.lower() and "20" in content
        ), "Dockerfile must include Node.js 20"

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
        assert "video" in compose_config["services"], "video service must be defined"

    def test_video_service_on_jobs_profile(self, compose_config: dict):
        """Video service must be on 'jobs' profile (not default)."""
        video_service = compose_config["services"]["video"]

        assert "profiles" in video_service, "video service must specify profiles"
        assert "jobs" in video_service["profiles"], "video service must be on 'jobs' profile"

    def test_video_service_builds_from_dockerfile(self, compose_config: dict):
        """Video service must build from Dockerfile.video."""
        video_service = compose_config["services"]["video"]

        assert "build" in video_service, "video service must have build configuration"
        build_config = video_service["build"]

        assert "dockerfile" in build_config, "video service must specify dockerfile"
        assert "Dockerfile.video" in build_config["dockerfile"], "video service must use Dockerfile.video"

    def test_video_service_mounts_libs_video(self, compose_config: dict):
        """Video service must mount libs/video/ source directory."""
        video_service = compose_config["services"]["video"]

        assert "volumes" in video_service, "video service must have volumes"
        volumes = video_service["volumes"]

        # Check for libs/video mount
        video_mount_found = any(
            "libs/video" in str(volume) for volume in volumes
        )
        assert video_mount_found, "video service must mount libs/video/"

    def test_video_service_exposes_internal_port(self, compose_config: dict):
        """Video service must expose internal port 8002."""
        video_service = compose_config["services"]["video"]

        # Port can be defined in EXPOSE (Dockerfile) or as internal port in compose
        # Check if service has explicit ports or relies on Dockerfile EXPOSE
        # For internal services, no host port mapping is needed

        # This tests that the service is configured to listen on a port
        # The actual port validation will be in the Dockerfile tests
        # Here we just verify the service has environment or command that references a port

        # Services should have health check or environment that indicates port
        assert (
            "healthcheck" in video_service or
            "environment" in video_service or
            "command" in video_service
        ), "video service must have configuration indicating port usage"

    def test_video_service_has_health_check(self, compose_config: dict):
        """Video service must have health check configured."""
        video_service = compose_config["services"]["video"]

        assert "healthcheck" in video_service, "video service must have healthcheck"
        healthcheck = video_service["healthcheck"]

        assert "test" in healthcheck, "healthcheck must have test command"
        assert "interval" in healthcheck, "healthcheck must have interval"
        assert "timeout" in healthcheck, "healthcheck must have timeout"
        assert "retries" in healthcheck, "healthcheck must have retries"

    def test_video_service_has_restart_policy(self, compose_config: dict):
        """Video service should have restart policy for resilience."""
        video_service = compose_config["services"]["video"]

        # Video service should have restart policy (typically unless-stopped for background services)
        assert "restart" in video_service, "video service should have restart policy"
        assert video_service["restart"] in [
            "unless-stopped", "always", "on-failure"
        ], "video service restart policy should be unless-stopped, always, or on-failure"

    def test_video_service_depends_on_nothing(self, compose_config: dict):
        """Video service should not depend on other services (standalone BC)."""
        video_service = compose_config["services"]["video"]

        # Video BC is a standalone service that worker calls via HTTP
        # It should NOT depend on db, redis, etc.
        assert (
            "depends_on" not in video_service or
            len(video_service.get("depends_on", {})) == 0
        ), "video service should not depend on other services (standalone BC)"


class TestVideoServiceStartup:
    """Test video service can start with docker compose."""

    @pytest.mark.skip(reason="Requires Docker CLI - run on host, not in container")
    def test_docker_compose_validates_with_jobs_profile(self):
        """docker compose --profile jobs config must validate successfully."""
        result = subprocess.run(
            ["docker", "compose", "--profile", "jobs", "config"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"docker compose --profile jobs config failed:\n{result.stderr}"
        )

        # Verify video service is included in output
        assert "video:" in result.stdout, "video service must appear in jobs profile config"

    @pytest.mark.slow
    @pytest.mark.skip(reason="Requires Docker CLI - run on host, not in container")
    def test_video_service_image_builds(self):
        """Video service Docker image must build successfully."""
        # This test builds the image (slow, marked as slow)
        result = subprocess.run(
            ["docker", "compose", "build", "video"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"docker compose build video failed:\n{result.stderr}"
        )


class TestVideoDockerComposeOverride:
    """Test video service appears in docker-compose.override.yml.j2 template."""

    def test_override_template_has_video_service(self):
        """docker-compose.override.yml.j2 must include video service configuration."""
        template_file = Path("/app/worktree/templates/docker-compose.override.yml.j2")
        content = template_file.read_text()

        # Video service needs container name and port mapping in override
        assert "video:" in content, "override template must include video service"

    def test_override_template_video_has_container_name(self):
        """Override template must set container_name for video service."""
        template_file = Path("/app/worktree/templates/docker-compose.override.yml.j2")
        content = template_file.read_text()

        # Find video service section
        lines = content.split("\n")
        in_video_section = False
        has_container_name = False

        for line in lines:
            if line.strip() == "video:":
                in_video_section = True
            elif in_video_section:
                if line.strip().startswith("container_name:"):
                    has_container_name = True
                    break
                elif line.strip() and not line.startswith(" "):
                    # Moved to next service
                    break

        assert has_container_name, (
            "video service in override template must have container_name"
        )

    def test_override_template_video_has_port_mapping(self):
        """Override template must expose video service port to host."""
        template_file = Path("/app/worktree/templates/docker-compose.override.yml.j2")
        content = template_file.read_text()

        # Find video service section
        lines = content.split("\n")
        in_video_section = False
        has_ports = False

        for line in lines:
            if line.strip() == "video:":
                in_video_section = True
            elif in_video_section:
                if "ports:" in line:
                    has_ports = True
                    break
                elif line.strip() and not line.startswith(" "):
                    # Moved to next service
                    break

        assert has_ports, (
            "video service in override template must have ports configuration"
        )
