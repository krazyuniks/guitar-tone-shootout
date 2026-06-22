"""Tests for the public Traefik Compose overlay."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def _traefik_overlay_path() -> Path:
    candidates = [
        REPO_ROOT / "docker-compose.traefik.yml",
        Path("/worktrees/main/docker-compose.traefik.yml"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise AssertionError("docker-compose.traefik.yml is not visible to the test runner")


def test_traefik_overlay_sets_public_services_to_production() -> None:
    overlay = yaml.safe_load(_traefik_overlay_path().read_text())

    for service_name in ["webapp", "t3k-sync", "audio-worker", "video-worker"]:
        environment = overlay["services"][service_name]["environment"]
        assert environment["ENV"] == "production"
