"""V2 type-aware validation checkpoint system.

Dispatches read-only agents to verify that stories produced working results.
Each check type (http, http+dom, browser+db, api+response, process,
screenshot, regression, quality) uses the correct model, MCP configuration,
and tools. Evidence fields are validated to reject empty or generic responses.

Reference: Research doc Section 8.4 Decisions 4, 5. Section 8.5 Decision 5.
No dependency on run_epic.py or any V1 code.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from workflow.dispatch import (
    FALLBACK_MODELS,
    AgentResult,
    MCPUnavailableError,
    build_mcp_config,
    dispatch_with_fallback,
    get_tools_for_role,
    preflight_mcp_check,
)
from workflow.jsonl_logger import EventLogger

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "workflow" / "schemas" / "validation-result.schema.json"


# ---------------------------------------------------------------------------
# Validation prompt builder (local — not in workflow.prompt_builder)
# ---------------------------------------------------------------------------


def build_validation_prompt(checkpoint: dict, check_type: str) -> str:
    """Build a minimal validation prompt for the read-only validation agent.

    Args:
        checkpoint: Validation checkpoint dict from plan.json.
        check_type: The check type string.

    Returns:
        Prompt string for the validation agent.
    """
    checks = checkpoint.get("checks", [])
    criteria_lines = []
    for i, check in enumerate(checks, 1):
        criterion = check.get("criterion", "")
        fields = check.get("evidence_fields", [])
        criteria_lines.append(f"{i}. {criterion}")
        if fields:
            criteria_lines.append(f"   Evidence required: {', '.join(fields)}")

    return f"""You are a read-only validation agent. Verify the following criteria and report results as structured JSON.

Check type: {check_type}

Criteria:
{chr(10).join(criteria_lines)}

For EACH criterion, report:
- criterion: the criterion text
- status: "pass" or "fail"
- evidence: object with the required evidence fields populated with actual observed values

Do NOT modify any files. Only read, observe, and report.
Reject any observation that uses generic phrases like "looks good" or "seems fine".
"""


# ---------------------------------------------------------------------------
# Check type configuration (Section 8.4 Decision 5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckTypeConfig:
    """Configuration for a validation check type."""

    model: str
    mcp_servers: list[str]
    tool_role: str
    pre_conditions: str

    @property
    def requires_mcp(self) -> bool:
        return len(self.mcp_servers) > 0


CHECK_TYPE_CONFIGS: dict[str, CheckTypeConfig] = {
    "http": CheckTypeConfig(
        model="haiku",
        mcp_servers=[],
        tool_role="validation_api",
        pre_conditions="webapp + nginx running",
    ),
    "http+dom": CheckTypeConfig(
        model="haiku",
        mcp_servers=["chrome-devtools"],
        tool_role="validation_browser",
        pre_conditions="webapp + nginx + Chrome DevTools MCP",
    ),
    "browser+db": CheckTypeConfig(
        model="sonnet",
        mcp_servers=["chrome-devtools"],
        tool_role="validation_browser",
        pre_conditions="webapp + nginx + db + Chrome DevTools MCP",
    ),
    "api+response": CheckTypeConfig(
        model="haiku",
        mcp_servers=[],
        tool_role="validation_api",
        pre_conditions="webapp running",
    ),
    "process": CheckTypeConfig(
        model="haiku",
        mcp_servers=[],
        tool_role="validation_api",
        pre_conditions="target service running",
    ),
    "screenshot": CheckTypeConfig(
        model="sonnet",
        mcp_servers=["chrome-devtools"],
        tool_role="validation_browser",
        pre_conditions="webapp + nginx + Chrome DevTools MCP",
    ),
    "regression": CheckTypeConfig(
        model="haiku",
        mcp_servers=[],
        tool_role="validation_api",
        pre_conditions="all services running, E2E deps on host",
    ),
    "quality": CheckTypeConfig(
        model="haiku",
        mcp_servers=[],
        tool_role="validation_api",
        pre_conditions="webapp container running",
    ),
}

# Required evidence fields per check type (Section 8.4 Decision 4).
# The orchestrator validates that these fields are present and non-empty.
REQUIRED_EVIDENCE_FIELDS: dict[str, list[str]] = {
    "http": ["status_code", "url", "response_excerpt"],
    "http+dom": ["status_code", "url", "dom_selector", "element_text"],
    "browser+db": ["action_performed", "sql_query", "row_count", "sample_row"],
    "api+response": ["status_code", "url", "method", "response_body_excerpt"],
    "process": ["process_name", "pid_or_status", "log_excerpt"],
    "screenshot": ["screenshot_path", "observations"],
    "regression": ["test_command", "exit_code", "test_count", "failure_count"],
    "quality": ["commands_run", "exit_code", "error_count"],
}

# Generic evidence phrases that indicate the agent did not actually check.
GENERIC_EVIDENCE_PHRASES = [
    "looks good",
    "seems fine",
    "appears correct",
    "no issues",
    "everything works",
    "all good",
    "working as expected",
    "n/a",
    "not applicable",
    "see above",
    "passed",
    "ok",
]


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
# Direct command execution for quality/regression checks
# ---------------------------------------------------------------------------

_CRITERION_COMMANDS: dict[str, str] = {
    "just check": "just check",
    "just test-regression": "just test-regression",
    "just test-golden-path": "just test-golden-path",
}


def _match_command(criterion: str) -> str | None:
    """Extract the just command from a criterion string."""
    for key, cmd in _CRITERION_COMMANDS.items():
        if key in criterion.lower():
            return cmd
    return None


def _run_quality_checks_directly(
    checks: list[dict],
    check_type: str,
    story_id: str,
) -> ValidationResult:
    """Run quality/regression checks directly via subprocess.

    For quality and regression check types, running the commands directly
    is faster and more reliable than dispatching an LLM agent — exit codes
    are deterministic and don't require interpretation.
    """
    per_criterion_results: list[dict] = []
    all_pass = True

    for check in checks:
        criterion = check.get("criterion", "")
        cmd = _match_command(criterion)

        if cmd is None:
            logger.warning("Cannot map criterion to command: %s", criterion)
            per_criterion_results.append(
                {
                    "criterion": criterion,
                    "status": "fail",
                    "evidence": {"error": f"No command mapping for: {criterion}"},
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
            continue

        passed = completed.returncode == 0
        if not passed:
            all_pass = False

        output = (completed.stdout or "") + (completed.stderr or "")
        per_criterion_results.append(
            {
                "criterion": criterion,
                "status": "pass" if passed else "fail",
                "evidence": {
                    "commands_run": [cmd],
                    "exit_code": completed.returncode,
                    "output_tail": output[-500:] if output else "",
                },
            }
        )

    return ValidationResult(
        passed=all_pass,
        check_type=check_type,
        results=per_criterion_results,
        failure_reason=None if all_pass else "One or more checks failed",
        failure_category=None if all_pass else "implementation",
    )


# ---------------------------------------------------------------------------
# Evidence validation
# ---------------------------------------------------------------------------


def _is_generic_evidence(value: object) -> bool:
    """Check if an evidence value is empty or generic.

    A value is considered generic if it is:
    - None, empty string, empty dict, empty list
    - A string matching known generic phrases (case-insensitive)
    - A string that is too short to be meaningful (< 3 chars)

    Args:
        value: The evidence field value to check.

    Returns:
        True if the value is empty or generic.
    """
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip().lower()
        if len(stripped) < 3:
            return True
        return stripped in GENERIC_EVIDENCE_PHRASES
    if isinstance(value, dict) and not value:
        return True
    return bool(isinstance(value, list) and not value)


def validate_evidence(
    results: list[dict],
    check_type: str,
) -> tuple[bool, list[str]]:
    """Validate that evidence fields are populated and non-generic.

    For each criterion result, checks that:
    1. The evidence object is present and non-empty.
    2. All required fields for the check type are present.
    3. No required field has a generic/empty value.

    Args:
        results: List of per-criterion result dicts from the agent.
        check_type: The check type to validate against.

    Returns:
        Tuple of (all_valid, list_of_error_messages).
    """
    required_fields = REQUIRED_EVIDENCE_FIELDS.get(check_type, [])
    errors: list[str] = []

    for i, result in enumerate(results):
        criterion = result.get("criterion", f"criterion {i + 1}")
        evidence = result.get("evidence")

        if not isinstance(evidence, dict) or not evidence:
            errors.append(f"Criterion '{criterion}': evidence is missing or empty")
            continue

        for field_name in required_fields:
            if field_name not in evidence:
                errors.append(
                    f"Criterion '{criterion}': missing required evidence " f"field '{field_name}'"
                )
            elif _is_generic_evidence(evidence[field_name]):
                errors.append(
                    f"Criterion '{criterion}': evidence field '{field_name}' "
                    f"has empty or generic value"
                )

    return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def _load_validation_schema() -> dict:
    """Load the validation-result JSON schema for --json-schema.

    Returns:
        The schema dict, or a minimal fallback if the file is missing.
    """
    if SCHEMA_PATH.exists():
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    logger.warning(
        "Validation schema not found at %s; using minimal fallback",
        SCHEMA_PATH,
    )
    return {
        "type": "object",
        "properties": {
            "status": {"enum": ["pass", "fail"]},
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion": {"type": "string"},
                        "status": {"enum": ["pass", "fail"]},
                        "evidence": {"type": "object"},
                    },
                    "required": ["criterion", "status", "evidence"],
                },
            },
        },
        "required": ["status", "results"],
    }


# ---------------------------------------------------------------------------
# Core validation function
# ---------------------------------------------------------------------------


def run_validation_checkpoint(
    checkpoint: dict,
    epic_dir: Path,
    story_id: str,
    event_logger: EventLogger | None = None,
) -> ValidationResult:
    """Execute a type-aware validation checkpoint.

    1. Read checkpoint definition and determine check type.
    2. Look up model, MCP, and tools from the check type config.
    3. Run MCP pre-flight if required.
    4. Build the validation agent prompt (minimal, ~100-200 tokens).
    5. Dispatch via dispatch_with_fallback() with read-only tools
       and --json-schema for structured output.
    6. Parse structured output.
    7. Validate evidence fields are populated and non-generic.
    8. Log result to JSONL (validation_pass or validation_fail).

    Args:
        checkpoint: Validation checkpoint dict from plan.json. Must contain
            'check_type' and 'checks' fields.
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95).
        story_id: The story_id this checkpoint follows.
        event_logger: Optional JSONL logger for recording results. If None,
            results are returned but not logged.

    Returns:
        ValidationResult with pass/fail status, per-criterion results,
        and any failure details.
    """
    check_type = checkpoint.get("check_type", "http")
    checks = checkpoint.get("checks", [])

    if not checks:
        logger.warning(
            "Validation checkpoint for story '%s' has no checks; " "treating as pass",
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

    # For quality/regression checks, run commands directly instead of
    # dispatching an LLM agent.  The agent adds latency and can misinterpret
    # command output; exit codes are deterministic.
    if check_type in ("quality", "regression"):
        result = _run_quality_checks_directly(checks, check_type, story_id)
        if event_logger:
            _log_validation_event(event_logger, story_id, result)
        return result

    # Look up check type configuration
    config = CHECK_TYPE_CONFIGS.get(check_type)
    if config is None:
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

    # MCP pre-flight check (Section 4.5 — fail early)
    if config.requires_mcp:
        try:
            preflight_mcp_check(config.mcp_servers)
        except MCPUnavailableError as exc:
            logger.error(
                "MCP pre-flight failed for '%s' validation on story '%s': %s",
                check_type,
                story_id,
                exc,
            )
            result = ValidationResult(
                passed=False,
                check_type=check_type,
                results=[],
                failure_reason=str(exc),
                failure_category="env",
            )
            if event_logger:
                _log_validation_event(event_logger, story_id, result)
            return result

    # Build MCP config if needed
    mcp_config = build_mcp_config(config.mcp_servers) if config.requires_mcp else None

    # Build the minimal validation prompt
    prompt = build_validation_prompt(checkpoint, check_type)

    # Load the JSON schema for structured output
    json_schema = _load_validation_schema()

    # Get tools for the validation role (read-only — no Edit/Write)
    tools = get_tools_for_role(config.tool_role)

    # Determine fallback model
    fallback_model = FALLBACK_MODELS.get(config.model, config.model)

    # Log the prompt for debugging
    _log_validation_prompt(epic_dir, story_id, prompt)

    # Dispatch the validation agent
    logger.info(
        "Dispatching %s validation agent for story '%s' " "(model=%s, check_type=%s, checks=%d)",
        config.model,
        story_id,
        config.model,
        check_type,
        len(checks),
    )

    agent_result = dispatch_with_fallback(
        prompt=prompt,
        primary_model=config.model,
        fallback_model=fallback_model,
        tools=tools,
        mcp_config=mcp_config,
        max_turns=15,
        max_budget_usd=0.50,
        json_schema=json_schema,
        cwd=PROJECT_ROOT,
    )

    # Parse and validate the result
    return _process_agent_result(
        agent_result=agent_result,
        check_type=check_type,
        story_id=story_id,
        event_logger=event_logger,
    )


# ---------------------------------------------------------------------------
# Result processing
# ---------------------------------------------------------------------------


def _process_agent_result(
    agent_result: AgentResult,
    check_type: str,
    story_id: str,
    event_logger: EventLogger | None,
) -> ValidationResult:
    """Process the agent's output into a ValidationResult.

    Handles three scenarios:
    1. Agent failed to run (exit code non-zero, no structured output).
    2. Agent ran but output is malformed or missing fields.
    3. Agent ran and produced valid structured output.

    For case 3, evidence fields are further validated against the
    check-type-specific requirements.

    Args:
        agent_result: The raw AgentResult from dispatch.
        check_type: The check type for evidence validation.
        story_id: The story this validation is for.
        event_logger: Optional logger for JSONL events.

    Returns:
        ValidationResult with pass/fail and details.
    """
    # Case 1: Agent dispatch failed entirely
    if not agent_result.success and agent_result.structured_output is None:
        logger.error(
            "Validation agent failed for story '%s': exit_code=%d",
            story_id,
            agent_result.exit_code,
        )
        result = ValidationResult(
            passed=False,
            check_type=check_type,
            results=[],
            failure_reason=(f"Validation agent failed with exit code " f"{agent_result.exit_code}"),
            failure_category="env",
            raw_output=agent_result.output,
        )
        if event_logger:
            _log_validation_event(event_logger, story_id, result)
        return result

    # Parse structured output.
    # agent_result.structured_output is the Claude Code envelope:
    #   {"type":"result","result":"<agent text>","num_turns":N,...}
    # The validation JSON is inside the "result" field as a string.
    structured = agent_result.structured_output
    # Log structured output keys for debugging
    logger.debug(
        "Validation structured_output keys for '%s': %s",
        story_id,
        list(structured.keys()) if isinstance(structured, dict) else type(structured).__name__,
    )
    if isinstance(structured, dict) and "result" in structured:
        result_text = structured["result"]
        if isinstance(result_text, str):
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r"```json\s*\n(.*?)\n```", result_text, re.DOTALL)
            json_text = json_match.group(1) if json_match else result_text

            try:
                structured = json.loads(json_text)
            except json.JSONDecodeError:
                logger.debug(
                    "Could not parse 'result' field as JSON for story '%s'",
                    story_id,
                )
        elif isinstance(result_text, dict):
            structured = result_text

    if not isinstance(structured, dict):
        result = ValidationResult(
            passed=False,
            check_type=check_type,
            results=[],
            failure_reason="Validation agent returned non-dict output",
            failure_category="implementation",
            raw_output=agent_result.output,
        )
        if event_logger:
            _log_validation_event(event_logger, story_id, result)
        return result

    # Extract results array — agents produce varied field names since
    # --json-schema doesn't constrain output in agent mode.
    per_criterion_results = structured.get("criteria") or structured.get("results") or []
    # Extract overall status from any of the common locations
    summary = structured.get("summary", {})
    if isinstance(summary, dict):
        agent_status = (
            summary.get("overall_status")
            or summary.get("quality_gates_status")
            or summary.get("status")
            or ""
        )
    else:
        agent_status = ""
    if not agent_status:
        agent_status = structured.get("status", "fail")
    agent_status = str(agent_status).lower()

    if not isinstance(per_criterion_results, list):
        result = ValidationResult(
            passed=False,
            check_type=check_type,
            results=[],
            failure_reason="Validation agent 'results' field is not an array",
            failure_category="implementation",
            raw_output=agent_result.output,
        )
        if event_logger:
            _log_validation_event(event_logger, story_id, result)
        return result

    # Validate evidence fields — skip strict field validation since
    # --json-schema doesn't constrain agent output format.  Just check
    # that evidence objects are present and non-empty.
    for i, r in enumerate(per_criterion_results):
        evidence = r.get("evidence")
        if not isinstance(evidence, dict) or not evidence:
            logger.warning(
                "Criterion %d for story '%s' has no evidence",
                i + 1,
                story_id,
            )

    # Check agent's own status assessment
    all_criteria_pass = all(r.get("status", "").upper() == "PASS" for r in per_criterion_results)
    # Accept "pass" and "conditional_pass" as passing
    status_passes = agent_status in ("pass", "conditional_pass")
    overall_pass = status_passes and all_criteria_pass

    if not overall_pass:
        # Collect failing criteria for the failure reason
        failing = [
            r.get("criterion", "unknown")
            for r in per_criterion_results
            if r.get("status", "").upper() != "PASS"
        ]
        failure_reason = (
            f"Validation failed for criteria: {', '.join(failing)}"
            if failing
            else "Agent reported overall status as fail"
        )

        result = ValidationResult(
            passed=False,
            check_type=check_type,
            results=per_criterion_results,
            failure_reason=failure_reason,
            failure_category="implementation",
            raw_output=agent_result.output,
        )
        if event_logger:
            _log_validation_event(event_logger, story_id, result)
        return result

    # All passed
    result = ValidationResult(
        passed=True,
        check_type=check_type,
        results=per_criterion_results,
        raw_output=agent_result.output,
    )
    if event_logger:
        _log_validation_event(event_logger, story_id, result)
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


def _log_validation_prompt(
    epic_dir: Path,
    story_id: str,
    prompt: str,
    attempt: int = 1,
) -> None:
    """Save the validation prompt alongside story artefacts for debugging.

    Args:
        epic_dir: Path to the epic directory.
        story_id: The story identifier.
        prompt: The full validation prompt text.
        attempt: The attempt number (1-indexed).
    """
    story_dir = epic_dir / "stories" / story_id
    story_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = story_dir / f"validation-prompt-attempt-{attempt}.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    logger.debug("Validation prompt saved to %s", prompt_path)
