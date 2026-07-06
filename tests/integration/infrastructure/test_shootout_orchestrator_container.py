"""Integration tests for the shootout-orchestrator Docker container configuration."""

from pathlib import Path

import pytest
import yaml

DOCKERFILE = Path("/app/infrastructure/docker/Dockerfile.shootout-orchestrator")


class TestOrchestratorDockerfile:
    """Test Dockerfile.shootout-orchestrator configuration."""

    def test_dockerfile_exists(self):
        assert DOCKERFILE.exists(), "Dockerfile.shootout-orchestrator must exist"

    def test_dockerfile_is_slim_python_base(self):
        """The orchestrator runs on the slim Python base: no Node, Chromium, or ffmpeg."""
        content = DOCKERFILE.read_text()

        assert "python:" in content and "-slim" in content, "must build from a slim Python base"
        for banned in ("node", "chromium", "ffmpeg", "libsndfile"):
            assert banned not in content.lower(), (
                f"orchestrator image must not carry {banned}; it renders nothing"
            )

    def test_dockerfile_has_uv(self):
        assert "uv sync" in DOCKERFILE.read_text(), "must install workspace deps via uv"

    def test_dockerfile_valid_structure(self):
        content = DOCKERFILE.read_text()
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert lines[0].startswith("FROM"), "Dockerfile must start with FROM instruction"
        instructions = {line.split()[0] for line in lines}
        assert "WORKDIR" in instructions, "Dockerfile must set WORKDIR"
        assert "EXPOSE" in instructions, "Dockerfile must EXPOSE a port"

    def test_dockerfile_runs_orchestrator_app(self):
        assert "shootout_orchestrator.main:app" in DOCKERFILE.read_text()


class TestOrchestratorComposeService:
    """Test docker-compose.yml shootout-orchestrator service configuration."""

    @pytest.fixture
    def service(self) -> dict:
        compose_file = Path("/app/docker-compose.yml")
        with compose_file.open() as f:
            config = yaml.safe_load(f)
        assert "shootout-orchestrator" in config["services"], (
            "shootout-orchestrator service must be defined"
        )
        return config["services"]["shootout-orchestrator"]

    def test_service_replaces_video_worker(self):
        compose_file = Path("/app/docker-compose.yml")
        with compose_file.open() as f:
            config = yaml.safe_load(f)
        assert "video-worker" not in config["services"], (
            "the misnamed video-worker service must be gone"
        )

    def test_service_builds_from_orchestrator_dockerfile(self, service: dict):
        assert "Dockerfile.shootout-orchestrator" in service["build"]["dockerfile"]

    def test_service_mounts_orchestrator_app(self, service: dict):
        mounts = [str(volume) for volume in service["volumes"]]
        assert any("apps/shootout_orchestrator" in mount for mount in mounts)
        assert not any("model/video" in mount for mount in mounts), (
            "orchestrator must not mount the video model package"
        )

    def test_service_has_health_check(self, service: dict):
        healthcheck = service["healthcheck"]
        for key in ("test", "interval", "timeout", "retries"):
            assert key in healthcheck

    def test_service_has_restart_policy(self, service: dict):
        assert service["restart"] in ["unless-stopped", "always", "on-failure"]

    def test_service_depends_on_database(self, service: dict):
        assert "db" in service["depends_on"]


class TestOrchestratorGateIsolation:
    """Test the orchestrator stays off the feature-worktree gate path."""

    @pytest.fixture
    def service(self) -> dict:
        compose_file = Path("/app/docker-compose.yml")
        with compose_file.open() as f:
            config = yaml.safe_load(f)
        return config["services"]["shootout-orchestrator"]

    def test_orchestrator_is_jobs_profile_only(self, service: dict):
        """Feature worktrees do not start BC workers during the deterministic gate."""
        assert service.get("profiles") == ["jobs"], (
            "shootout-orchestrator must stay on the jobs profile, not the default gate path"
        )

    def test_orchestrator_has_no_host_port_mapping(self, service: dict):
        """The worktree engine allocates host ports only for webapp and db."""
        assert "ports" not in service, (
            "shootout-orchestrator must not publish a host port in feature worktrees"
        )
