"""Command-based validation checkpoint system.

All validation runs commands directly — no LLM agent dispatch. Each
criterion resolves to a shell command (via the explicit ``command`` field
or keyword matching) and pass/fail is determined by exit code. Test output
(assertion errors, tracebacks) flows into retry prompts as actionable
feedback.

Reference: Research doc Section 8.4 Decisions 4, 5. Section 8.5 Decision 5.
No dependency on run_epic.py or any V1 code.
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from workflow.jsonl_logger import EventLogger
from workflow.models import CheckCriterion, ValidationCheckpoint

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Check type configuration (retained as documentation/metadata)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckTypeConfig:
    """Configuration for a validation check type."""

    model: str
    tool_role: str
    pre_conditions: str


CHECK_TYPE_CONFIGS: dict[str, CheckTypeConfig] = {
    "http": CheckTypeConfig(
        model="haiku",
        tool_role="validation_api",
        pre_conditions="webapp + nginx running",
    ),
    "http+dom": CheckTypeConfig(
        model="haiku",
        tool_role="validation_browser",
        pre_conditions="webapp + nginx running",
    ),
    "browser+db": CheckTypeConfig(
        model="sonnet",
        tool_role="validation_browser",
        pre_conditions="webapp + nginx + db running",
    ),
    "api+response": CheckTypeConfig(
        model="haiku",
        tool_role="validation_api",
        pre_conditions="webapp running",
    ),
    "process": CheckTypeConfig(
        model="haiku",
        tool_role="validation_api",
        pre_conditions="target service running",
    ),
    "screenshot": CheckTypeConfig(
        model="sonnet",
        tool_role="validation_browser",
        pre_conditions="webapp + nginx running",
    ),
    "regression": CheckTypeConfig(
        model="haiku",
        tool_role="validation_api",
        pre_conditions="all services running, E2E deps on host",
    ),
    "quality": CheckTypeConfig(
        model="haiku",
        tool_role="validation_api",
        pre_conditions="webapp container running",
    ),
}


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of a validation checkpoint execution."""

    passed: bool
    check_type: str
    results: list[dict]
    failure_reason: str | None = None
    failure_category: str | None = None
    raw_output: str = ""


# ---------------------------------------------------------------------------
# Direct command execution for all check types
# ---------------------------------------------------------------------------

_CRITERION_COMMANDS: dict[str, str] = {
    "just check": "just check",
    "just test-regression": "just test-regression",
    "just test-golden-path": "just test-golden-path",
    "import-linter": "just check-imports",
    "lint": "just check-lint",
    "astro build": "just build-astro",
    "alembic migration": "just migrate",
    "migrations apply": "just migrate",
    "quality gates pass": "just check",
}


def _match_command(criterion: str) -> str | None:
    """Extract the just command from a criterion string."""
    for key, cmd in _CRITERION_COMMANDS.items():
        if key in criterion.lower():
            return cmd
    return None


def _resolve_command(check: CheckCriterion) -> str | None:
    """Resolve a criterion to its shell command.

    Checks the explicit ``command`` field first, then falls back to
    keyword matching against ``_CRITERION_COMMANDS``.
    """
    if check.command:
        return check.command
    return _match_command(check.criterion)


def _run_checks_directly(
    checks: list[CheckCriterion],
    check_type: str,
    story_id: str,
) -> ValidationResult:
    """Run validation checks directly via subprocess.

    For each criterion, resolves a command (explicit or keyword-matched),
    runs it, and determines pass/fail from the exit code. Combined test
    output is stored in ``raw_output`` so it flows into retry prompts.
    """
    per_criterion_results: list[dict] = []
    all_pass = True
    all_output_parts: list[str] = []

    for check in checks:
        criterion = check.criterion
        cmd = _resolve_command(check)

        if cmd is None:
            logger.warning("Cannot map criterion to command (failing): %s", criterion)
            per_criterion_results.append(
                {
                    "criterion": criterion,
                    "status": "fail",
                    "evidence": {"note": f"No command mapping for: {criterion}"},
                }
            )
            all_pass = False
            continue

        logger.info("Running direct check for story '%s': %s", story_id, cmd)

        try:
            completed = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=PROJECT_ROOT,
            )
        except subprocess.TimeoutExpired:
            per_criterion_results.append(
                {
                    "criterion": criterion,
                    "status": "fail",
                    "evidence": {"error": f"Command timed out: {cmd}"},
                }
            )
            all_pass = False
            all_output_parts.append(f"[TIMEOUT] {cmd}")
            continue

        passed = completed.returncode == 0
        if not passed:
            all_pass = False

        output = (completed.stdout or "") + (completed.stderr or "")
        all_output_parts.append(output)

        per_criterion_results.append(
            {
                "criterion": criterion,
                "status": "pass" if passed else "fail",
                "evidence": {
                    "command": cmd,
                    "exit_code": completed.returncode,
                    "output_tail": output[-2000:] if output else "",
                },
            }
        )

    combined_output = "\n".join(all_output_parts)

    return ValidationResult(
        passed=all_pass,
        check_type=check_type,
        results=per_criterion_results,
        failure_reason=None if all_pass else "One or more checks failed",
        failure_category=None if all_pass else "implementation",
        raw_output=combined_output,
    )


# ---------------------------------------------------------------------------
# Core validation function
# ---------------------------------------------------------------------------


def run_validation_checkpoint(
    checkpoint: ValidationCheckpoint,
    epic_dir: Path,
    story_id: str,
    event_logger: EventLogger | None = None,
    *,
    skip_golden_path: bool = False,
) -> ValidationResult:
    """Execute a validation checkpoint by running commands directly.

    All check types are routed through ``_run_checks_directly()``.
    Each criterion resolves to a shell command (explicit ``command``
    field or keyword matching) and pass/fail is determined by exit code.

    Args:
        checkpoint: Validation checkpoint from plan.json.
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95).
        story_id: The story_id this checkpoint follows.
        event_logger: Optional JSONL logger for recording results.
        skip_golden_path: If True, skip the mandatory golden path gate.

    Returns:
        ValidationResult with pass/fail status, per-criterion results,
        and any failure details.
    """
    _ = epic_dir  # Retained for API compatibility (callers pass it)
    check_type = checkpoint.check_type
    checks = checkpoint.checks

    if not checks:
        logger.warning(
            "Validation checkpoint for story '%s' has no checks; treating as pass",
            story_id,
        )
        result = ValidationResult(
            passed=True,
            check_type=check_type,
            results=[],
        )
        if event_logger:
            _log_validation_event(event_logger, story_id, result)
        return result

    # Verify check type is known (fail explicitly for unknown types)
    if check_type not in CHECK_TYPE_CONFIGS:
        logger.error(
            "Unknown check type '%s' for story '%s'; failing validation",
            check_type,
            story_id,
        )
        result = ValidationResult(
            passed=False,
            check_type=check_type,
            results=[],
            failure_reason=f"Unknown check type: {check_type}",
            failure_category="scope",
        )
        if event_logger:
            _log_validation_event(event_logger, story_id, result)
        return result

    # All check types go through direct command execution
    logger.info(
        "Running %d checks directly for story '%s' (check_type=%s)",
        len(checks),
        story_id,
        check_type,
    )

    result = _run_checks_directly(checks, check_type, story_id)
    if event_logger:
        _log_validation_event(event_logger, story_id, result)

    if not result.passed:
        return result

    # Mandatory baseline quality gate: always run `just check` after
    # per-story checks pass, unless the story checks already included it.
    story_commands = {_resolve_command(c) for c in checks}
    if "just check" not in story_commands:
        logger.info(
            "Running mandatory baseline quality gate for story '%s': just check",
            story_id,
        )
        baseline_check = CheckCriterion(
            criterion="Baseline quality gates pass (lint, types, unit tests, imports)",
            command="just check",
        )
        baseline_result = _run_checks_directly([baseline_check], "quality_baseline", story_id)
        if event_logger:
            _log_validation_event(event_logger, story_id, baseline_result)
        if not baseline_result.passed:
            # Merge baseline failure into the result
            return ValidationResult(
                passed=False,
                check_type=check_type,
                results=result.results + baseline_result.results,
                failure_reason="Baseline quality gate failed (just check)",
                failure_category="implementation",
                raw_output=result.raw_output + "\n" + baseline_result.raw_output,
            )

    # Mandatory golden path gate: run after baseline quality gate passes.
    if not skip_golden_path and "just test-golden-path" not in story_commands:
        logger.info(
            "Running mandatory golden path gate for story '%s': just test-golden-path",
            story_id,
        )
        golden_check = CheckCriterion(
            criterion="Golden path integration tests pass",
            command="just test-golden-path",
        )
        golden_result = _run_checks_directly([golden_check], "golden_path", story_id)
        if event_logger:
            _log_validation_event(event_logger, story_id, golden_result)
        if not golden_result.passed:
            return ValidationResult(
                passed=False,
                check_type=check_type,
                results=result.results + golden_result.results,
                failure_reason="Golden path gate failed (just test-golden-path)",
                failure_category="implementation",
                raw_output=result.raw_output + "\n" + golden_result.raw_output,
            )
    elif skip_golden_path:
        logger.info(
            "Skipping golden path gate for story '%s' (disabled in epic config)",
            story_id,
        )

    return result


# ---------------------------------------------------------------------------
# JSONL logging helpers
# ---------------------------------------------------------------------------


def _log_validation_event(
    event_logger: EventLogger,
    story_id: str,
    result: ValidationResult,
) -> None:
    """Log a validation_pass or validation_fail event to JSONL.

    Args:
        event_logger: The JSONL event logger instance.
        story_id: The story this validation applies to.
        result: The validation result to log.
    """
    event_type = "validation_pass" if result.passed else "validation_fail"

    # Build the event-specific fields
    event_fields: dict = {
        "story_id": story_id,
        "check_type": result.check_type,
        "results": [
            {
                "criterion": r.get("criterion", ""),
                "status": r.get("status", "unknown"),
                "evidence": r.get("evidence", {}),
            }
            for r in result.results
        ],
    }

    if not result.passed and result.failure_category:
        event_fields["failure_category"] = result.failure_category

    if not result.passed and result.failure_reason:
        event_fields["failure_reason"] = result.failure_reason

    event_logger.log_event(event_type, **event_fields)

    logger.info(
        "Validation %s for story '%s' (check_type=%s, criteria=%d)",
        "PASSED" if result.passed else "FAILED",
        story_id,
        result.check_type,
        len(result.results),
    )
