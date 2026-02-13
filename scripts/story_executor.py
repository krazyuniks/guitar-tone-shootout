"""V2 story execution loop with failure handling.

The inner loop that executes a single story: pre-flight -> dispatch ->
validate -> retry/proceed. Includes the full failure model with 5-type
classification (env, scope, implementation, upstream, unknown) and
category-aware retry policy.

Reference: Research doc Section 2 (Story Flow, Failure Model,
File-to-story ownership). Section 8.5 Decision 2 (failure feedback).
No dependency on run_epic.py or any V1 code.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scripts.dispatch import (
    FALLBACK_MODELS,
    dispatch_with_fallback,
    get_dispatch_metadata,
)
from scripts.jsonl_logger import EventLogger
from scripts.prompt_builder import (
    PromptContext,
    RetryContext,
    StorySpec,
    build_agent_prompt,
    find_checkpoint_for_story,
    log_prompt,
)
from scripts.validation import run_validation_checkpoint

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Maximum retry attempts per story.
# The plan specifies "2 retries" for scope, implementation, and unknown
# failure categories. Total attempts = 1 initial + 2 retries = 3.
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# File-to-story ownership map (Section 2)
# ---------------------------------------------------------------------------


def build_file_ownership_map(plan: dict) -> dict[str, str]:
    """Map file paths to owning story IDs from plan.json.

    For files listed in multiple stories' scopes, the last writer wins --
    later stories that modify the same file own it. This is used to detect
    upstream failures: if an error references a file owned by a completed
    earlier story, the failure is classified as 'upstream'.

    Args:
        plan: The full plan.json dict.

    Returns:
        Dict mapping file path strings to story_id strings.
    """
    ownership: dict[str, str] = {}
    for story in plan.get("stories", []):
        story_id = story.get("story_id", "")
        for path in story.get("scope", {}).get("create", []):
            ownership[path] = story_id
        for path in story.get("scope", {}).get("modify", []):
            # Last writer wins -- later stories own shared files
            ownership[path] = story_id
    return ownership


# ---------------------------------------------------------------------------
# Failure classification (Section 2)
# ---------------------------------------------------------------------------


@dataclass
class FailureClassification:
    """Result of classifying a failure event.

    Contains both the category and the matched evidence so the JSONL
    failure_category entry is auditable.
    """

    category: str  # env, scope, implementation, upstream, unknown
    evidence: str  # The matched pattern + source text
    pattern: str  # The specific pattern that triggered classification


# Explicit pattern tables for failure classification.
# Each entry is (pattern_regex_or_string, human_description).

ENV_PATTERNS: list[tuple[str, str]] = [
    (r"Cannot connect to the Docker daemon", "Docker daemon not running"),
    (r"docker: command not found", "Docker not installed"),
    (r"docker compose.*not found", "Docker Compose not found"),
    (r"Cannot start service", "Docker service start failure"),
    (r"port is already allocated", "Port conflict"),
    (r"address already in use", "Address/port already in use"),
    (r"Bind for .+ failed: port is already allocated", "Port bind failure"),
    (r"MCP server .* unavailable", "MCP server unavailable"),
    (r"MCP.*connection refused", "MCP connection refused"),
    (r"MCP.*refused", "MCP refused"),
    (r"npx not found", "npx not available for MCP"),
    (r"No Chrome/Chromium executable found", "Chrome not found for MCP"),
    (r"command not found", "Required command not found"),
    (r"ECONNREFUSED.*:9010", "Webapp not reachable"),
    (r"ECONNREFUSED.*:5432", "Database not reachable"),
    (r"Connection refused.*:6379", "Redis not reachable"),
    (r"network timeout", "Network timeout"),
    (r"Could not resolve host", "DNS resolution failure"),
    (r"network unreachable", "Network unreachable"),
    (r"just: command not found", "just not installed"),
    (r"just db-reset.*failed", "Database reset failed"),
]

SCOPE_PATTERNS: list[tuple[str, str]] = [
    (r"FileNotFoundError: \[Errno 2\].*No such file or directory", "File not found"),
    (r"ModuleNotFoundError: No module named", "Module not found"),
    (r"No such file or directory", "Expected file missing"),
    (r"ImportError: cannot import name", "Import name not found"),
    (r"cannot find module", "Module path not found"),
]

IMPLEMENTATION_PATTERNS: list[tuple[str, str]] = [
    (r"TypeError:", "Python TypeError"),
    (r"ValueError:", "Python ValueError"),
    (r"AttributeError:", "Python AttributeError"),
    (r"KeyError:", "Python KeyError"),
    (r"IndexError:", "Python IndexError"),
    (r"NameError:", "Python NameError"),
    (r"RuntimeError:", "Python RuntimeError"),
    (r"NotImplementedError:", "Not implemented"),
    (r"ZeroDivisionError:", "Division by zero"),
    (r"RecursionError:", "Recursion limit"),
    (r"SyntaxError:", "Python syntax error"),
    (r"IndentationError:", "Python indentation error"),
    (r"Traceback \(most recent call last\)", "Python traceback"),
    (r"AssertionError", "Assertion failure"),
    (r"assert .+ ==", "Assertion equality failure"),
    (r"FAILED tests/", "Test failure"),
    (r"HTTP 500", "Server error 500"),
    (r"Internal Server Error", "Internal server error"),
    (r"500 Internal Server Error", "HTTP 500 response"),
    (r"status_code.*500", "HTTP 500 status"),
    (r"sqlalchemy\.exc\.", "SQLAlchemy error"),
    (r"IntegrityError", "Database integrity error"),
    (r"OperationalError", "Database operational error"),
    (r"pydantic.*validation.*error", "Pydantic validation error"),
    (r"ValidationError", "Validation error"),
]


def _match_patterns(
    text: str,
    patterns: list[tuple[str, str]],
) -> tuple[str, str] | None:
    """Try to match text against a list of (regex, description) patterns.

    Args:
        text: The text to search (error output, traceback, etc.).
        patterns: List of (pattern, description) tuples.

    Returns:
        Tuple of (matched_text, description) or None if no match.
    """
    for pattern, description in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract context around the match (up to 200 chars)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 150)
            context = text[start:end].strip()
            return (context, description)
    return None


def _check_upstream_failure(
    error_text: str,
    current_story_id: str,
    file_ownership: dict[str, str],
    completed_stories: list[str],
) -> tuple[str, str] | None:
    """Check if the error references a file owned by a completed earlier story.

    This is the upstream failure detection mechanism. It does not use
    string matching patterns -- it uses the file ownership map built from
    plan.json to trace file references in the error text back to their
    owning stories.

    Args:
        error_text: The error output from the agent or validation.
        current_story_id: The currently executing story.
        file_ownership: Map of file paths to owning story IDs.
        completed_stories: List of already-completed story IDs.

    Returns:
        Tuple of (evidence, description) if upstream, None otherwise.
    """
    for file_path, owning_story in file_ownership.items():
        # Skip files owned by the current story
        if owning_story == current_story_id:
            continue
        # Only flag if the owning story is already completed
        if owning_story not in completed_stories:
            continue
        # Check if this file path appears in the error text
        if file_path in error_text:
            evidence = (
                f"Error references '{file_path}' which is owned by "
                f"completed story '{owning_story}'"
            )
            return (evidence, f"File owned by earlier story: {owning_story}")
    return None


def classify_failure(
    error_text: str,
    current_story_id: str,
    file_ownership: dict[str, str],
    completed_stories: list[str],
    plan_scope_paths: list[str] | None = None,
) -> FailureClassification:
    """Classify a failure into one of 5 categories with evidence.

    The classification order matters -- earlier checks take priority:
    1. env (infrastructure) -- unrecoverable, exit immediately
    2. upstream (file ownership) -- exit to human
    3. scope (plan references wrong things) -- retryable
    4. implementation (code errors) -- retryable
    5. unknown (fallback) -- retryable

    For scope classification, we additionally check if FileNotFoundError
    or ModuleNotFoundError references paths listed in plan.json scope.
    This distinguishes "plan references a wrong path" (scope) from
    "agent wrote bad import" (implementation).

    Args:
        error_text: The error output to classify.
        current_story_id: The story being executed.
        file_ownership: Map from build_file_ownership_map().
        completed_stories: List of completed story IDs.
        plan_scope_paths: Optional list of file paths from the current
            story's scope (create + modify) for scope-vs-implementation
            disambiguation.

    Returns:
        FailureClassification with category, evidence, and pattern.
    """
    if not error_text:
        return FailureClassification(
            category="unknown",
            evidence="No error text available",
            pattern="empty_error",
        )

    # 1. Check env patterns first (infrastructure problems)
    env_match = _match_patterns(error_text, ENV_PATTERNS)
    if env_match:
        return FailureClassification(
            category="env",
            evidence=env_match[0],
            pattern=env_match[1],
        )

    # 2. Check upstream (file ownership map)
    upstream_match = _check_upstream_failure(
        error_text, current_story_id, file_ownership, completed_stories
    )
    if upstream_match:
        return FailureClassification(
            category="upstream",
            evidence=upstream_match[0],
            pattern=upstream_match[1],
        )

    # 3. Check scope patterns (plan references wrong things)
    # For scope classification, we also check if the missing file/module
    # is one that the plan.json says should exist.
    scope_match = _match_patterns(error_text, SCOPE_PATTERNS)
    if scope_match and plan_scope_paths:
        # Check if the error references a plan scope path
        for scope_path in plan_scope_paths:
            if scope_path in error_text:
                return FailureClassification(
                    category="scope",
                    evidence=f"{scope_match[0]} (references plan scope path: {scope_path})",
                    pattern=scope_match[1],
                )
    # If we matched a scope pattern but can't confirm it references plan paths,
    # still classify as scope (the pattern itself is strong enough)
    if scope_match:
        return FailureClassification(
            category="scope",
            evidence=scope_match[0],
            pattern=scope_match[1],
        )

    # 4. Check implementation patterns (code errors)
    impl_match = _match_patterns(error_text, IMPLEMENTATION_PATTERNS)
    if impl_match:
        return FailureClassification(
            category="implementation",
            evidence=impl_match[0],
            pattern=impl_match[1],
        )

    # 5. Fallback: unknown
    # Include the first 300 chars of error text as evidence
    truncated = error_text[:300].strip()
    return FailureClassification(
        category="unknown",
        evidence=truncated,
        pattern="no_pattern_matched",
    )


def get_retry_budget(category: str) -> int:
    """Return the number of allowed retries for a failure category.

    Args:
        category: One of env, scope, implementation, upstream, unknown.

    Returns:
        Number of retries (0 means no retries -- exit immediately).
    """
    if category == "env":
        return 0  # Exit immediately -- infrastructure problem
    if category == "upstream":
        return 0  # Exit to human -- earlier story bug
    # scope, implementation, unknown all get retries
    return MAX_RETRIES


# ---------------------------------------------------------------------------
# Pre-flight checks (Section 2)
# ---------------------------------------------------------------------------


@dataclass
class PreflightResult:
    """Result of pre-flight checks for a story."""

    passed: bool
    issues: list[str]
    is_minor: bool = False  # True if all issues are minor (agent can self-fix)


def _get_scope_paths(story: dict) -> list[str]:
    """Extract all file paths from a story's scope."""
    scope = story.get("scope", {})
    paths = list(scope.get("create", []))
    paths.extend(scope.get("modify", []))
    return paths


def _find_story_index(plan: dict, story_id: str) -> int:
    """Find the index of a story in the plan's story list."""
    for i, s in enumerate(plan.get("stories", [])):
        if s.get("story_id") == story_id:
            return i
    return -1


def _get_files_from_previous_stories(plan: dict, current_story_id: str) -> list[str]:
    """Get all files that should have been created by stories before the current one.

    Args:
        plan: The full plan.json dict.
        current_story_id: The current story's ID.

    Returns:
        List of file paths that earlier stories should have created.
    """
    current_idx = _find_story_index(plan, current_story_id)
    if current_idx <= 0:
        return []

    expected_files: list[str] = []
    for story in plan.get("stories", [])[:current_idx]:
        for path in story.get("scope", {}).get("create", []):
            expected_files.append(path)
    return expected_files


def run_preflight_checks(
    story: dict,
    plan: dict,
) -> PreflightResult:
    """Run pre-flight checks before dispatching a story's agent.

    Verifies that inputs from previous stories are present: files that
    should have been created, routes that should be registered, etc.
    This is a quick filesystem check, not a full validation.

    Args:
        story: The current story dict from plan.json.
        plan: The full plan.json dict.

    Returns:
        PreflightResult with pass/fail status and any issues found.
    """
    story_id = story.get("story_id", "")
    issues: list[str] = []

    # Check that files created by earlier stories exist
    expected_files = _get_files_from_previous_stories(plan, story_id)
    for file_path in expected_files:
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            issues.append(f"Expected file from earlier story missing: {file_path}")

    # Check that files the current story wants to modify exist
    for file_path in story.get("scope", {}).get("modify", []):
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            issues.append(f"File to modify does not exist: {file_path}")

    # Check that parent directories for files to create exist
    for file_path in story.get("scope", {}).get("create", []):
        full_path = PROJECT_ROOT / file_path
        parent = full_path.parent
        if not parent.exists():
            issues.append(f"Parent directory for file to create missing: {parent}")

    if not issues:
        return PreflightResult(passed=True, issues=[])

    # Apply minor/major heuristic
    is_minor = _is_minor_preflight_issue(issues, story)

    return PreflightResult(
        passed=False,
        issues=issues,
        is_minor=is_minor,
    )


def _is_minor_preflight_issue(issues: list[str], story: dict) -> bool:
    """Determine if pre-flight issues are minor (agent can self-fix).

    A pre-flight issue is minor only if ALL of:
    (a) The fix modifies only files within the agent's assigned scope
    (b) The fix touches fewer than 10 lines total
    (c) The fix is mechanical (import path, missing comma, wrong variable name)

    For pre-flight filesystem checks, most issues are about missing files
    or directories. These are typically NOT minor because:
    - Missing files from earlier stories = major (upstream issue)
    - Missing parent directories = major (plan structure issue)
    - Missing files to modify = could be minor if it's a new file the agent creates

    Args:
        issues: List of issue description strings.
        story: The current story dict.

    Returns:
        True if all issues are minor.
    """
    scope_create = set(story.get("scope", {}).get("create", []))

    for issue in issues:
        # Missing files from earlier stories is always major
        if "Expected file from earlier story missing" in issue:
            return False

        # Missing parent directories is always major
        if "Parent directory for file to create missing" in issue:
            return False

        # Missing file to modify: minor only if the file is also in create scope
        # (the agent would create it first, then modify it)
        if "File to modify does not exist" in issue:
            # Extract the file path from the issue string
            path_part = issue.replace("File to modify does not exist: ", "")
            if path_part not in scope_create:
                return False

    # If we get here, all issues are potentially minor
    # But we're conservative -- only if there are few issues
    return len(issues) <= 3


# ---------------------------------------------------------------------------
# State assumption handling (Section 8.4 Decision 7)
# ---------------------------------------------------------------------------


def handle_state_assumption(state_assumption: str) -> bool:
    """Handle the story's state assumption before dispatch.

    If state_assumption is "clean", run just db-reset to reset the
    database to a clean state. Most stories are "cumulative" (default)
    and need no action.

    Args:
        state_assumption: Either "clean" or "cumulative".

    Returns:
        True if handled successfully, False on failure.
    """
    if state_assumption != "clean":
        return True

    logger.info("State assumption is 'clean' -- running database reset")

    result = subprocess.run(
        ["just", "db-reset"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        logger.error(
            "Database reset failed: %s",
            result.stderr.strip() or result.stdout.strip(),
        )
        return False

    logger.info("Database reset complete")
    return True


# ---------------------------------------------------------------------------
# Core execution loop
# ---------------------------------------------------------------------------


def execute_story(
    story: dict,
    plan: dict,
    epic_dir: Path,
    event_logger: EventLogger,
    completed_stories: list[str] | None = None,
) -> bool:
    """Execute a single story: pre-flight -> dispatch -> validate -> retry/proceed.

    This is the inner loop of the V2 workflow. It handles the full lifecycle
    of a story from start to completion or failure.

    The flow:
    1. Log story_started event
    2. Handle state_assumption (if "clean", run just db-reset)
    3. Run pre-flight checks on inputs from previous stories
    4. Construct agent prompt (via prompt_builder)
    5. Log agent_dispatched event
    6. Dispatch implementation agent
    7. Log agent_complete or agent_failed
    8. If validation checkpoint exists after this story:
       a. Run validation checkpoint
       b. If pass: log validation_pass, log story_complete, return True
       c. If fail: classify failure, retry or exit (see failure model)
    9. If no checkpoint: log story_complete, return True

    Args:
        story: The story dict from plan.json.
        plan: The full plan.json dict.
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95).
        event_logger: JSONL event logger for recording events.
        completed_stories: List of already-completed story IDs (for
            upstream failure detection). If None, defaults to empty list.

    Returns:
        True if the story completed successfully, False otherwise.
    """
    if completed_stories is None:
        completed_stories = []

    story_id = story.get("story_id", "unknown")
    story_spec = StorySpec.from_dict(story)
    file_ownership = build_file_ownership_map(plan)
    story_index = _find_story_index(plan, story_id)

    # Collect all scope paths for failure classification
    plan_scope_paths = _get_scope_paths(story)

    # Find the validation checkpoint for this story (if any)
    checkpoint = find_checkpoint_for_story(plan, story_id)

    logger.info("=== Executing story: %s (%s) ===", story_id, story_spec.name)

    # Step 1: Log story_started
    event_logger.log_event(
        "story_started",
        story_id=story_id,
        attempt=1,
        index=story_index,
    )

    # Step 2: Handle state assumption
    if not handle_state_assumption(story_spec.state_assumption):
        event_logger.log_event(
            "preflight_fail",
            story_id=story_id,
            attempt=1,
            failure_category="env",
            description="Database reset failed (state_assumption='clean')",
        )
        event_logger.log_event(
            "exit_to_human",
            story_id=story_id,
            attempt=1,
            reason="Database reset failed",
            failure_category="env",
            context={
                "story_id": story_id,
                "attempt": 1,
                "last_error": "just db-reset failed",
                "files_affected": [],
                "jsonl_excerpt": "state_assumption=clean, db-reset failed",
            },
        )
        return False

    # Step 3: Pre-flight checks
    preflight = run_preflight_checks(story, plan)

    if not preflight.passed:
        if preflight.is_minor:
            # Minor issues -- agent can self-fix. Log and continue.
            logger.info(
                "Pre-flight found minor issues for story '%s' " "(agent will self-fix): %s",
                story_id,
                "; ".join(preflight.issues),
            )
            event_logger.log_event(
                "preflight_pass",
                story_id=story_id,
                attempt=1,
                note=f"Minor issues (agent self-fix): {'; '.join(preflight.issues)}",
            )
        else:
            # Major issues -- cannot proceed
            logger.error(
                "Pre-flight failed for story '%s': %s",
                story_id,
                "; ".join(preflight.issues),
            )
            event_logger.log_event(
                "preflight_fail",
                story_id=story_id,
                attempt=1,
                failure_category="scope",
                description="; ".join(preflight.issues),
            )

            # Classify the preflight failure more precisely
            combined_issues = "\n".join(preflight.issues)
            classification = classify_failure(
                combined_issues,
                story_id,
                file_ownership,
                completed_stories,
                plan_scope_paths,
            )

            if get_retry_budget(classification.category) == 0:
                event_logger.log_event(
                    "exit_to_human",
                    story_id=story_id,
                    attempt=1,
                    reason=f"Pre-flight failure ({classification.category}): "
                    f"{'; '.join(preflight.issues)}",
                    failure_category=classification.category,
                    context={
                        "story_id": story_id,
                        "attempt": 1,
                        "last_error": "; ".join(preflight.issues),
                        "files_affected": plan_scope_paths,
                        "jsonl_excerpt": json.dumps(
                            {
                                "classification": classification.category,
                                "evidence": classification.evidence,
                            }
                        ),
                    },
                )
                return False

            # For retryable preflight failures, we still fail the story
            # because the agent cannot fix upstream missing files
            event_logger.log_event(
                "story_failed",
                story_id=story_id,
                attempt=1,
                reason=f"Pre-flight failure: {'; '.join(preflight.issues)}",
            )
            return False
    else:
        event_logger.log_event(
            "preflight_pass",
            story_id=story_id,
            attempt=1,
        )

    # Step 4-9: Dispatch loop with retries
    return _dispatch_and_validate_loop(
        story=story,
        story_spec=story_spec,
        plan=plan,
        epic_dir=epic_dir,
        event_logger=event_logger,
        checkpoint=checkpoint,
        file_ownership=file_ownership,
        completed_stories=completed_stories,
        plan_scope_paths=plan_scope_paths,
    )


def _dispatch_and_validate_loop(
    story: dict,
    story_spec: StorySpec,
    plan: dict,
    epic_dir: Path,
    event_logger: EventLogger,
    checkpoint: dict | None,
    file_ownership: dict[str, str],
    completed_stories: list[str],
    plan_scope_paths: list[str],
) -> bool:
    """Run the dispatch-validate loop with retry handling.

    Handles up to MAX_RETRIES + 1 total attempts (1 initial + MAX_RETRIES).
    On each failure, classifies the error, checks retry budget, and either
    retries with failure feedback or exits.

    Args:
        story: Raw story dict from plan.json.
        story_spec: Parsed StorySpec.
        plan: Full plan.json dict.
        epic_dir: Path to epic directory.
        event_logger: JSONL event logger.
        checkpoint: Validation checkpoint dict (or None).
        file_ownership: File-to-story ownership map.
        completed_stories: List of completed story IDs.
        plan_scope_paths: File paths from current story's scope.

    Returns:
        True if the story completed successfully, False otherwise.
    """
    story_id = story_spec.story_id
    retry_context: RetryContext | None = None
    max_attempts = MAX_RETRIES + 1  # initial + retries

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "Story '%s' attempt %d/%d",
            story_id,
            attempt,
            max_attempts,
        )

        # Build the agent prompt
        prompt_context = PromptContext(
            plan=plan,
            checkpoint=checkpoint,
            retry=retry_context,
        )
        prompt = build_agent_prompt(story_spec, prompt_context)

        # Log the prompt for debugging
        log_prompt(epic_dir, story_id, attempt, prompt)

        # Get dispatch metadata for JSONL logging
        metadata = get_dispatch_metadata(
            prompt,
            story_spec.model,
            story_spec.skills,
        )

        # Log agent_dispatched
        event_logger.log_event(
            "agent_dispatched",
            story_id=story_id,
            attempt=attempt,
            **metadata,
        )

        # Determine fallback model
        fallback_model = FALLBACK_MODELS.get(story_spec.model, story_spec.model)

        # Build MCP config if needed
        mcp_config = None
        if story_spec.mcp:
            from scripts.dispatch import build_mcp_config

            mcp_config = build_mcp_config(story_spec.mcp)

        # Dispatch the implementation agent
        agent_result = dispatch_with_fallback(
            prompt=prompt,
            primary_model=story_spec.model,
            fallback_model=fallback_model,
            tools=story_spec.tools or ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
            skills=story_spec.skills,
            mcp_config=mcp_config,
            max_turns=story_spec.max_turns,
            max_budget_usd=story_spec.max_budget_usd,
            cwd=PROJECT_ROOT,
        )

        # Log agent result
        if agent_result.success:
            event_logger.log_event(
                "agent_complete",
                story_id=story_id,
                attempt=attempt,
                commit=_get_latest_commit_hash(),
                turns=agent_result.turns,
                cost_usd=agent_result.cost_usd,
            )
        else:
            event_logger.log_event(
                "agent_failed",
                story_id=story_id,
                attempt=attempt,
                error=agent_result.output[:500] if agent_result.output else "Unknown error",
                turns=agent_result.turns,
                cost_usd=agent_result.cost_usd,
            )

            # Classify the agent failure
            error_text = agent_result.output or ""
            classification = classify_failure(
                error_text,
                story_id,
                file_ownership,
                completed_stories,
                plan_scope_paths,
            )

            logger.warning(
                "Agent failed for story '%s' (attempt %d): " "category=%s, pattern=%s",
                story_id,
                attempt,
                classification.category,
                classification.pattern,
            )

            # Check if this category allows retries
            retry_allowed = get_retry_budget(classification.category)
            remaining_attempts = max_attempts - attempt

            if retry_allowed == 0 or remaining_attempts == 0:
                # No retries allowed or budget exhausted
                return _handle_terminal_failure(
                    story_id=story_id,
                    attempt=attempt,
                    classification=classification,
                    error_text=error_text,
                    event_logger=event_logger,
                    plan_scope_paths=plan_scope_paths,
                )

            # Build retry context for next attempt
            retry_context = RetryContext(
                attempt=attempt,
                error=_extract_key_error(error_text),
                files_modified=plan_scope_paths,
                jsonl_excerpt=json.dumps(
                    {
                        "event": "agent_failed",
                        "story_id": story_id,
                        "attempt": attempt,
                        "failure_category": classification.category,
                        "evidence": classification.evidence,
                    }
                ),
            )

            # Log story_started for the retry attempt
            event_logger.log_event(
                "story_started",
                story_id=story_id,
                attempt=attempt + 1,
                index=_find_story_index(plan, story_id),
            )

            continue  # Retry

        # Agent succeeded -- now run validation if a checkpoint exists
        if checkpoint is None:
            # No validation checkpoint -- story is complete
            event_logger.log_event(
                "story_complete",
                story_id=story_id,
                attempt=attempt,
                commit=_get_latest_commit_hash(),
            )
            logger.info("Story '%s' completed (no validation checkpoint)", story_id)
            return True

        # Run validation checkpoint
        validation_result = run_validation_checkpoint(
            checkpoint=checkpoint,
            epic_dir=epic_dir,
            story_id=story_id,
            event_logger=event_logger,
        )

        if validation_result.passed:
            # Validation passed -- story is complete
            event_logger.log_event(
                "story_complete",
                story_id=story_id,
                attempt=attempt,
                commit=_get_latest_commit_hash(),
            )
            logger.info(
                "Story '%s' completed (validation passed, attempt %d)",
                story_id,
                attempt,
            )
            return True

        # Validation failed -- classify and decide whether to retry
        error_text = validation_result.failure_reason or ""
        raw_output = validation_result.raw_output or ""
        combined_error = f"{error_text}\n{raw_output}".strip()

        classification = classify_failure(
            combined_error,
            story_id,
            file_ownership,
            completed_stories,
            plan_scope_paths,
        )

        # Override classification if validation already set a category
        if validation_result.failure_category:
            classification = FailureClassification(
                category=validation_result.failure_category,
                evidence=classification.evidence,
                pattern=classification.pattern,
            )

        logger.warning(
            "Validation failed for story '%s' (attempt %d): " "category=%s, reason=%s",
            story_id,
            attempt,
            classification.category,
            validation_result.failure_reason,
        )

        # Check retry budget
        retry_allowed = get_retry_budget(classification.category)
        remaining_attempts = max_attempts - attempt

        if retry_allowed == 0 or remaining_attempts == 0:
            return _handle_terminal_failure(
                story_id=story_id,
                attempt=attempt,
                classification=classification,
                error_text=combined_error,
                event_logger=event_logger,
                plan_scope_paths=plan_scope_paths,
            )

        # Build retry context with validation failure details
        retry_context = RetryContext(
            attempt=attempt,
            error=_extract_key_error(combined_error),
            files_modified=plan_scope_paths,
            jsonl_excerpt=json.dumps(
                {
                    "event": "validation_fail",
                    "story_id": story_id,
                    "attempt": attempt,
                    "check_type": validation_result.check_type,
                    "failure_category": classification.category,
                    "failure_reason": validation_result.failure_reason,
                    "evidence": classification.evidence,
                }
            ),
        )

        # Log story_started for the retry attempt
        event_logger.log_event(
            "story_started",
            story_id=story_id,
            attempt=attempt + 1,
            index=_find_story_index(plan, story_id),
        )

    # Should not reach here, but safety net
    logger.error("Story '%s' exhausted all attempts", story_id)
    event_logger.log_event(
        "story_failed",
        story_id=story_id,
        attempt=max_attempts,
        reason="Exhausted all retry attempts",
    )
    return False


# ---------------------------------------------------------------------------
# Terminal failure handling
# ---------------------------------------------------------------------------


def _handle_terminal_failure(
    story_id: str,
    attempt: int,
    classification: FailureClassification,
    error_text: str,
    event_logger: EventLogger,
    plan_scope_paths: list[str],
) -> bool:
    """Handle a failure that cannot be retried.

    Logs the appropriate JSONL events (story_failed and/or exit_to_human)
    and returns False.

    Args:
        story_id: The failing story's ID.
        attempt: The attempt number that failed.
        classification: The failure classification.
        error_text: The error text for context.
        event_logger: JSONL event logger.
        plan_scope_paths: Files in the story's scope.

    Returns:
        Always False (story failed).
    """
    reason = (
        f"Failure ({classification.category}): {classification.pattern} "
        f"-- {classification.evidence[:200]}"
    )

    event_logger.log_event(
        "story_failed",
        story_id=story_id,
        attempt=attempt,
        reason=reason,
    )

    # For env and upstream failures, also log exit_to_human
    if classification.category in ("env", "upstream"):
        event_logger.log_event(
            "exit_to_human",
            story_id=story_id,
            attempt=attempt,
            reason=reason,
            failure_category=classification.category,
            context={
                "story_id": story_id,
                "attempt": attempt,
                "last_error": _extract_key_error(error_text),
                "files_affected": plan_scope_paths,
                "jsonl_excerpt": json.dumps(
                    {
                        "failure_category": classification.category,
                        "evidence": classification.evidence,
                        "pattern": classification.pattern,
                    }
                ),
            },
        )

    logger.error(
        "Story '%s' failed terminally: category=%s, pattern=%s",
        story_id,
        classification.category,
        classification.pattern,
    )

    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_latest_commit_hash() -> str:
    """Get the current HEAD short commit hash, or 'unknown' on failure."""
    try:
        from scripts.git_helpers import get_commit_hash

        return get_commit_hash()
    except Exception:
        return "unknown"


def _extract_key_error(error_text: str) -> str:
    """Extract the key error message from verbose output.

    Looks for Python tracebacks, assertion messages, and HTTP errors.
    Returns a concise summary (max 500 chars) rather than dumping
    the full output.

    Args:
        error_text: The full error output.

    Returns:
        A concise error summary.
    """
    if not error_text:
        return "Unknown error"

    # Try to find the last Python traceback line (the actual error)
    lines = error_text.strip().splitlines()

    # Look for the last line that starts with a known error type
    error_prefixes = [
        "TypeError:",
        "ValueError:",
        "AttributeError:",
        "KeyError:",
        "IndexError:",
        "NameError:",
        "RuntimeError:",
        "ImportError:",
        "ModuleNotFoundError:",
        "FileNotFoundError:",
        "SyntaxError:",
        "IndentationError:",
        "AssertionError:",
        "NotImplementedError:",
        "IntegrityError:",
        "OperationalError:",
        "ValidationError:",
    ]

    for line in reversed(lines):
        stripped = line.strip()
        for prefix in error_prefixes:
            if stripped.startswith(prefix):
                return stripped[:500]

    # Look for HTTP error patterns
    for line in reversed(lines):
        stripped = line.strip()
        if re.search(r"HTTP [45]\d\d|status[_\s]code.*[45]\d\d", stripped, re.IGNORECASE):
            return stripped[:500]

    # Look for "FAILED" lines (test failures)
    for line in reversed(lines):
        if "FAILED" in line:
            return line.strip()[:500]

    # Fallback: last non-empty line, truncated
    for line in reversed(lines):
        stripped = line.strip()
        if stripped:
            return stripped[:500]

    return error_text[:500]
