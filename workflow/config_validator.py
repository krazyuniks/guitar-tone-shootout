"""Pre-execution configuration validation.

Runs once at the beginning of Stage 4, before any story dispatch.
Checks infrastructure health and agent readiness. Hard failure on
any check — no partial execution, no degraded mode.

Reference: wiki/Epic-Workflow.md, Stage 4 Configuration Validation.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ValidationCheck:
    """Result of a single validation check."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class ConfigValidationResult:
    """Aggregate result of all configuration validation checks."""

    checks: list[ValidationCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> str:
        lines = []
        for check in self.checks:
            icon = "PASS" if check.passed else "FAIL"
            lines.append(f"  [{icon}] {check.name}")
            if check.detail and not check.passed:
                lines.append(f"         {check.detail}")
        return "\n".join(lines)


def _run_just(recipe: str, project_root: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a just recipe and return the completed process."""
    return subprocess.run(
        ["just", recipe],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=timeout,
    )


def check_docker_services(project_root: Path) -> ValidationCheck:
    """Check that Docker services are running and healthy."""
    try:
        result = _run_just("health", project_root)
        if result.returncode != 0:
            return ValidationCheck(
                "docker_services", False, f"just health failed: {result.stderr[:200]}"
            )
        if "No healthy services" in result.stdout:
            return ValidationCheck("docker_services", False, "No healthy Docker services found")
        return ValidationCheck("docker_services", True)
    except subprocess.TimeoutExpired:
        return ValidationCheck("docker_services", False, "just health timed out")
    except FileNotFoundError:
        return ValidationCheck("docker_services", False, "just command not found")


def check_database(project_root: Path) -> ValidationCheck:
    """Check that the database is accessible."""
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "webapp",
                "python",
                "-c",
                "from sqlalchemy import text; "
                "from infrastructure.database import sync_engine; "
                "with sync_engine.connect() as c: c.execute(text('SELECT 1'))",
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=30,
        )
        if result.returncode != 0:
            return ValidationCheck("database", False, f"DB check failed: {result.stderr[:200]}")
        return ValidationCheck("database", True)
    except subprocess.TimeoutExpired:
        return ValidationCheck("database", False, "Database check timed out")
    except FileNotFoundError:
        return ValidationCheck("database", False, "docker command not found")


def check_auth_tokens(project_root: Path) -> ValidationCheck:
    """Check that auth tokens are valid (T3K sync requires valid tokens)."""
    try:
        result = _run_just("t3k-auth-status", project_root)
        if result.returncode != 0:
            return ValidationCheck(
                "auth_tokens", False, f"Auth check failed: {result.stderr[:200]}"
            )
        combined = result.stdout + result.stderr
        if "expired" in combined.lower() or "invalid" in combined.lower():
            return ValidationCheck("auth_tokens", False, "Auth tokens expired or invalid")
        return ValidationCheck("auth_tokens", True)
    except subprocess.TimeoutExpired:
        return ValidationCheck("auth_tokens", False, "Auth check timed out")
    except FileNotFoundError:
        return ValidationCheck("auth_tokens", False, "just command not found")


def check_website(project_root: Path) -> ValidationCheck:
    """Check that the website is responding."""
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "webapp",
                "python",
                "-c",
                "import urllib.request; "
                "r = urllib.request.urlopen('http://localhost:8000/api/health', timeout=5); "
                "assert r.status == 200",
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=15,
        )
        if result.returncode != 0:
            return ValidationCheck("website", False, f"Website check failed: {result.stderr[:200]}")
        return ValidationCheck("website", True)
    except subprocess.TimeoutExpired:
        return ValidationCheck("website", False, "Website check timed out")
    except FileNotFoundError:
        return ValidationCheck("website", False, "docker command not found")


def check_golden_path(project_root: Path) -> ValidationCheck:
    """Run golden path tests to verify known-good codebase state."""
    try:
        result = _run_just("test-golden-path", project_root, timeout=300)
        if result.returncode != 0:
            output = (result.stdout + result.stderr)[-500:]
            return ValidationCheck("golden_path", False, f"Golden path tests failed:\n{output}")
        return ValidationCheck("golden_path", True)
    except subprocess.TimeoutExpired:
        return ValidationCheck("golden_path", False, "Golden path tests timed out (>5min)")
    except FileNotFoundError:
        return ValidationCheck("golden_path", False, "just command not found")


def validate_config(
    project_root: Path,
    skip_golden_path: bool = False,
) -> ConfigValidationResult:
    """Run all pre-execution configuration validation checks.

    Args:
        project_root: Project root directory.
        skip_golden_path: Skip the expensive golden path test run.

    Returns:
        ConfigValidationResult with all check results.
    """
    result = ConfigValidationResult()

    # Infrastructure checks
    result.checks.append(check_docker_services(project_root))
    result.checks.append(check_database(project_root))
    result.checks.append(check_auth_tokens(project_root))
    result.checks.append(check_website(project_root))

    if not skip_golden_path:
        result.checks.append(check_golden_path(project_root))

    return result
