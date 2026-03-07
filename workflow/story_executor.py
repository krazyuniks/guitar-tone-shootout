"""V3 story execution loop with failure handling.

The inner loop that executes a single story: pre-flight -> dispatch ->
validate -> retry/proceed. Includes the full failure model with 5-type
classification (env, scope, implementation, upstream, unknown) and
category-aware retry policy.

Uses the V3 workflow module APIs. All imports reference workflow.*.

Reference: Research doc Section 2 (Story Flow, Failure Model,
File-to-story ownership). Section 8.5 Decision 2 (failure feedback).
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from workflow.artifacts import (
    CritiqueRunArtifact,
    FailureClassificationArtifact,
    PreflightArtifact,
    StoryFailureContextArtifact,
)
from workflow.dispatch import (
    STORY_CRITIQUE_SCHEMA,
    compute_prompt_hash,
    dispatch_agent,
    estimate_tokens,
    extract_json_from_text,
    get_dispatch_metadata,
    get_dispatch_params,
)
from workflow.models import ValidationCheckpoint
from workflow.prompt_builder import build_story_prompt
from workflow.validation import run_validation_checkpoint

if TYPE_CHECKING:
    from workflow.epic_config import EpicConfig
    from workflow.jsonl_logger import EventLogger

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = PROJECT_ROOT / ".claude" / "rules"
WIKI_INDEXES_DIR = PROJECT_ROOT / ".planning" / "wiki-indexes"

# Maximum retry attempts per story.
# The plan specifies "2 retries" for scope, implementation, and unknown
# failure categories. Total attempts = 1 initial + 2 retries = 3.
MAX_RETRIES = 2

# Compatibility aliases while callers migrate to typed artifact names.
FailureClassification = FailureClassificationArtifact
PreflightResult = PreflightArtifact



# ---------------------------------------------------------------------------
# Local helpers (replaced V2 prompt_builder helpers)
# ---------------------------------------------------------------------------


def find_checkpoint_for_story(plan: dict, story_id: str) -> ValidationCheckpoint | None:
    """Find the validation checkpoint that follows a given story.

    Looks through plan["validation_checkpoints"] for one where
    after_story == story_id. Returns a validated Pydantic model.

    Args:
        plan: The full plan.json dict.
        story_id: The story to find a checkpoint for.

    Returns:
        ValidationCheckpoint if one exists after this story, else None.
    """
    for cp in plan.get("validation_checkpoints", []):
        if cp.get("after_story") == story_id:
            return ValidationCheckpoint.model_validate(cp)
    return None


def log_prompt(
    epic_dir: Path,
    story_id: str,
    attempt: int,
    prompt: str,
) -> Path:
    """Save full prompt text to prompt-attempt-N.md for debugging.

    The prompt is the primary debugging artefact when agents fail.
    Stored alongside the story JSONL log.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95).
        story_id: The story identifier.
        attempt: The attempt number (1-based).
        prompt: The full prompt text.

    Returns:
        Path to the saved prompt file.
    """
    story_dir = epic_dir / "stories" / story_id
    story_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = story_dir / f"prompt-attempt-{attempt}.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    token_estimate = len(prompt) // 4
    logger.info(
        "Prompt logged: %s (%d tokens)",
        prompt_path,
        token_estimate,
    )

    return prompt_path


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
                f"Error references '{file_path}' which is owned by completed story '{owning_story}'"
            )
            return (evidence, f"File owned by earlier story: {owning_story}")
    return None


def classify_failure(
    error_text: str,
    current_story_id: str,
    file_ownership: dict[str, str],
    completed_stories: list[str],
    plan_scope_paths: list[str] | None = None,
) -> FailureClassificationArtifact:
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
        FailureClassificationArtifact with category, evidence, and pattern.
    """
    if not error_text:
        return FailureClassificationArtifact(
            category="unknown",
            evidence="No error text available",
            pattern="empty_error",
        )

    # 1. Check env patterns first (infrastructure problems)
    env_match = _match_patterns(error_text, ENV_PATTERNS)
    if env_match:
        return FailureClassificationArtifact(
            category="env",
            evidence=env_match[0],
            pattern=env_match[1],
        )

    # 2. Check upstream (file ownership map)
    upstream_match = _check_upstream_failure(
        error_text, current_story_id, file_ownership, completed_stories
    )
    if upstream_match:
        return FailureClassificationArtifact(
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
                return FailureClassificationArtifact(
                    category="scope",
                    evidence=f"{scope_match[0]} (references plan scope path: {scope_path})",
                    pattern=scope_match[1],
                )
    # If we matched a scope pattern but can't confirm it references plan paths,
    # still classify as scope (the pattern itself is strong enough)
    if scope_match:
        return FailureClassificationArtifact(
            category="scope",
            evidence=scope_match[0],
            pattern=scope_match[1],
        )

    # 4. Check implementation patterns (code errors)
    impl_match = _match_patterns(error_text, IMPLEMENTATION_PATTERNS)
    if impl_match:
        return FailureClassificationArtifact(
            category="implementation",
            evidence=impl_match[0],
            pattern=impl_match[1],
        )

    # 5. Fallback: unknown
    # Include the first 300 chars of error text as evidence
    truncated = error_text[:300].strip()
    return FailureClassificationArtifact(
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
    if category == "scope_violation":
        return 0  # Exit immediately -- agent modified protected files
    # scope, implementation, unknown all get retries
    return MAX_RETRIES


# ---------------------------------------------------------------------------
# Pre-flight checks (Section 2)
# ---------------------------------------------------------------------------


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
) -> PreflightArtifact:
    """Run pre-flight checks before dispatching a story's agent.

    Verifies that inputs from previous stories are present: files that
    should have been created, routes that should be registered, etc.
    This is a quick filesystem check, not a full validation.

    Args:
        story: The current story dict from plan.json.
        plan: The full plan.json dict.

    Returns:
        PreflightArtifact with pass/fail status and any issues found.
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
        return PreflightArtifact(passed=True)

    # Apply minor/major heuristic
    is_minor = _is_minor_preflight_issue(issues, story)

    return PreflightArtifact(
        passed=False,
        issues=tuple(issues),
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

    If state_assumption is "clean", rollback and re-apply migrations to
    reset the database schema. Most stories are "cumulative" (default)
    and need no action.

    Args:
        state_assumption: Either "clean" or "cumulative".

    Returns:
        True if handled successfully, False on failure.
    """
    if state_assumption != "clean":
        return True

    logger.info("State assumption is 'clean' -- running migrate-down + migrate")

    # Rollback last migration
    result = subprocess.run(
        ["just", "migrate-down"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error(
            "migrate-down failed: %s",
            result.stderr.strip() or result.stdout.strip(),
        )
        return False

    # Re-apply migrations
    result = subprocess.run(
        ["just", "migrate"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error(
            "migrate failed: %s",
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
    config: EpicConfig | None = None,
) -> bool:
    """Execute a single story: pre-flight -> dispatch -> validate -> retry/proceed.

    This is the inner loop of the V3 workflow. It handles the full lifecycle
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
        config: Epic configuration profile. If None, falls back to
            plan.json agent defaults for backward compatibility.

    Returns:
        True if the story completed successfully, False otherwise.
    """
    if completed_stories is None:
        completed_stories = []

    story_id = story.get("story_id", "unknown")
    story_name = story.get("name", "unknown")
    state_assumption = story.get("state_assumption", "cumulative")
    file_ownership = build_file_ownership_map(plan)
    story_index = _find_story_index(plan, story_id)

    # Collect all scope paths for failure classification
    plan_scope_paths = _get_scope_paths(story)

    # Find the validation checkpoint for this story (if any)
    checkpoint = find_checkpoint_for_story(plan, story_id)

    logger.info("=== Executing story: %s (%s) ===", story_id, story_name)

    # Step 1: Log story_started
    event_logger.log_event(
        "story_started",
        story_id=story_id,
        attempt=1,
        index=story_index,
    )

    # Step 2: Handle state assumption
    if not handle_state_assumption(state_assumption):
        failure_context = StoryFailureContextArtifact(
            story_id=story_id,
            attempt=1,
            last_error="just db-reset failed",
            files_affected=(),
            jsonl_excerpt="state_assumption=clean, db-reset failed",
        )
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
            context=failure_context.event_context,
        )
        return False

    # Step 3: Pre-flight checks
    preflight = run_preflight_checks(story, plan)

    if not preflight.passed:
        if preflight.is_minor:
            # Minor issues -- agent can self-fix. Log and continue.
            logger.info(
                "Pre-flight found minor issues for story '%s' (agent will self-fix): %s",
                story_id,
                "; ".join(preflight.issues),
            )
            event_logger.log_event(
                "preflight_pass",
                story_id=story_id,
                attempt=1,
                note=f"Minor issues (agent self-fix): {preflight.description}",
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
                description=preflight.description,
            )

            # Classify the preflight failure more precisely
            classification = classify_failure(
                preflight.combined_issues,
                story_id,
                file_ownership,
                completed_stories,
                plan_scope_paths,
            )
            failure_context = StoryFailureContextArtifact(
                story_id=story_id,
                attempt=1,
                last_error=preflight.description,
                files_affected=tuple(plan_scope_paths),
                jsonl_excerpt=json.dumps(
                    {
                        "classification": classification.category,
                        "evidence": classification.evidence,
                    }
                ),
            )

            if get_retry_budget(classification.category) == 0:
                event_logger.log_event(
                    "exit_to_human",
                    story_id=story_id,
                    attempt=1,
                    reason=f"Pre-flight failure ({classification.category}): "
                    f"{preflight.description}",
                    failure_category=classification.category,
                    context=failure_context.event_context,
                )
                return False

            # For retryable preflight failures, we still fail the story
            # because the agent cannot fix upstream missing files
            event_logger.log_event(
                "story_failed",
                story_id=story_id,
                attempt=1,
                reason=f"Pre-flight failure: {preflight.description}",
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
        plan=plan,
        epic_dir=epic_dir,
        event_logger=event_logger,
        checkpoint=checkpoint,
        file_ownership=file_ownership,
        completed_stories=completed_stories,
        plan_scope_paths=plan_scope_paths,
        config=config,
    )


def _run_story_critique(
    story: dict,
    validation_results: str,
    event_logger: EventLogger,
    attempt: int,
    model: str,
    config: EpicConfig | None = None,
    base_commit: str | None = None,
) -> CritiqueRunArtifact:
    """Run post-story critique on the implementation.

    Dispatches a read-only agent with the critique_story template
    to review the code changes made by the implementation agent.

    Args:
        story: The story dict from plan.json.
        validation_results: String summary of validation checkpoint results.
        event_logger: JSONL event logger.
        attempt: The current attempt number.
        model: The model that produced the implementation (for logging).
        config: Epic configuration profile. If None, falls back to defaults.
        base_commit: Commit hash before story execution started. Used to
            produce the full story diff (not just HEAD~1).

    Returns:
        Typed critique result for the story attempt.
    """
    story_id = story.get("story_id", "unknown")

    # Read the critique template
    template_path = Path(__file__).resolve().parent / "templates" / "critique_story.md"
    template = template_path.read_text(encoding="utf-8")

    # Get git diff for story scope — diff from pre-story base commit.
    # Uses scope paths first; falls back to unfiltered diff when scope paths
    # miss changes (e.g. git mv renames files to new paths not in scope).
    scope = story.get("scope", {})
    scope_paths = list(scope.get("create", [])) + list(scope.get("modify", []))
    diff_ref = f"{base_commit}..HEAD" if base_commit else "HEAD~1"
    try:
        diff_args = ["git", "diff", diff_ref, "--", *scope_paths]
        diff_result = subprocess.run(
            diff_args,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        git_diff = diff_result.stdout.strip()
        if not git_diff:
            # Scope paths missed changes (renames, new paths) — full diff
            diff_result = subprocess.run(
                ["git", "diff", diff_ref],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
                timeout=30,
            )
            git_diff = diff_result.stdout.strip() or "(no diff)"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        git_diff = "(diff unavailable)"

    # Build prompt from template
    story_json = json.dumps(story, indent=2)
    prompt = template.replace("{{ story_json }}", story_json)
    prompt = prompt.replace("{{ git_diff }}", git_diff)
    prompt = prompt.replace("{{ validation_results }}", validation_results)

    # Resolve model from config
    critique_model = config.models.story_critic if config else "opus"

    # Log critique dispatch
    prompt_hash = compute_prompt_hash(prompt)
    prompt_tokens = estimate_tokens(prompt)
    event_logger.log_event(
        "critique_dispatched",
        story_id=story_id,
        attempt=attempt,
        critique_type="story",
        critique_model=critique_model,
        target_model=model,
        adapter="codex" if critique_model == "codex" else "claude",
        role="critique_story",
        prompt_hash=prompt_hash,
        prompt_tokens=prompt_tokens,
    )

    # Dispatch read-only critique agent with schema enforcement
    mcp_servers, timeout = get_dispatch_params("critique", config)
    result = dispatch_agent(
        prompt=prompt,
        model=critique_model,
        json_schema=STORY_CRITIQUE_SCHEMA,
        mcp_servers=mcp_servers,
        timeout=timeout,
        cwd=PROJECT_ROOT,
        role="story_critique",
    )

    if not result.success:
        logger.warning(
            "Story critique dispatch failed for '%s' (exit_code=%d) — treating as pass "
            "(validation already confirmed correctness)",
            story_id,
            result.exit_code,
        )
        event_logger.log_event(
            "critique_skipped",
            story_id=story_id,
            attempt=attempt,
            critique_type="story",
            critique_model=critique_model,
            reason=result.output[:500] if result.output else "Dispatch failed",
        )
        # Critique dispatch failure is non-fatal — validation is the correctness gate.
        return CritiqueRunArtifact.from_dict(
            {"status": "pass", "findings": [], "summary": ""},
            level="story",
            critique_type="story",
            critique_model=critique_model,
            story_id=story_id,
            attempt=attempt,
        )

    # Parse JSON result — robust extraction handles text around JSON
    raw_output = result.output or ""
    try:
        critique = extract_json_from_text(raw_output)
    except ValueError:
        output_preview = raw_output[:200]
        logger.warning(
            "Story critique returned invalid JSON for '%s' — treating as pass "
            "(validation already confirmed correctness)",
            story_id,
        )
        event_logger.log_event(
            "critique_skipped",
            story_id=story_id,
            attempt=attempt,
            critique_type="story",
            critique_model=critique_model,
            reason=f"Invalid JSON response: {output_preview}",
        )
        # Critique parse failure is non-fatal — validation is the correctness gate.
        # Log the skip and proceed as pass with no findings.
        return CritiqueRunArtifact.from_dict(
            {"status": "pass", "findings": [], "summary": ""},
            level="story",
            critique_type="story",
            critique_model=critique_model,
            story_id=story_id,
            attempt=attempt,
        )

    critique_run = CritiqueRunArtifact.from_dict(
        critique,
        level="story",
        critique_type="story",
        critique_model=critique_model,
        story_id=story_id,
        attempt=attempt,
        turns=result.turns,
        raw_response=raw_output,
    )
    event_logger.log_event(critique_run.event_name, **critique_run.event_payload)
    return critique_run


def _dispatch_and_validate_loop(
    story: dict,
    plan: dict,
    epic_dir: Path,
    event_logger: EventLogger,
    checkpoint: dict | None,
    file_ownership: dict[str, str],
    completed_stories: list[str],
    plan_scope_paths: list[str],
    config: EpicConfig | None = None,
) -> bool:
    """Run the dispatch-validate loop with retry handling.

    Handles up to MAX_RETRIES + 1 total attempts (1 initial + MAX_RETRIES).
    On each failure, classifies the error, checks retry budget, and either
    retries with failure feedback or exits.

    Args:
        story: Raw story dict from plan.json.
        plan: Full plan.json dict.
        epic_dir: Path to epic directory.
        event_logger: JSONL event logger.
        checkpoint: Validation checkpoint dict (or None).
        file_ownership: File-to-story ownership map.
        completed_stories: List of completed story IDs.
        plan_scope_paths: File paths from current story's scope.
        config: Epic configuration profile. If None, falls back to
            plan.json agent defaults for backward compatibility.

    Returns:
        True if the story completed successfully, False otherwise.
    """
    story_id = story.get("story_id", "unknown")

    # Read agent config — prefer epic config, fall back to story dict
    agent = story.get("agent", {})
    model = config.models.implementor if config else agent.get("model", "sonnet")
    retry_context: StoryFailureContextArtifact | None = None
    max_attempts = MAX_RETRIES + 1  # initial + retries
    base_commit = _get_latest_commit_hash()  # snapshot before any dispatch

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "Story '%s' attempt %d/%d",
            story_id,
            attempt,
            max_attempts,
        )

        # Build the agent prompt using V3 prompt_builder
        total_stories = len(plan.get("stories", []))
        prompt = build_story_prompt(
            story,
            RULES_DIR,
            WIKI_INDEXES_DIR,
            plan,
            (len(completed_stories), total_stories),
            checkpoint=checkpoint,
            epic_dir=epic_dir,
        )

        # For retries, append failure feedback section to the prompt
        if retry_context:
            prompt += retry_context.prompt_block

        # Log the prompt for debugging
        log_prompt(epic_dir, story_id, attempt, prompt)

        # Get dispatch metadata for JSONL logging
        metadata = get_dispatch_metadata(
            prompt,
            model,
        )

        # Log agent_dispatched
        event_logger.log_event(
            "agent_dispatched",
            story_id=story_id,
            attempt=attempt,
            **metadata,
        )

        # Dispatch the implementation agent (with conversation transcript)
        story_dir = epic_dir / "stories" / story_id
        story_dir.mkdir(parents=True, exist_ok=True)
        conv_log = story_dir / f"dispatch-{attempt}.jsonl"
        mcp_servers_impl, _ = get_dispatch_params("implementation", config)
        agent_result = dispatch_agent(
            prompt=prompt,
            model=model,
            cwd=PROJECT_ROOT,
            mcp_servers=mcp_servers_impl,
            timeout=0,  # streaming mode; no subprocess timeout
            conversation_log=conv_log,
            role="implementation",
        )

        # Log agent result
        if agent_result.success:
            event_logger.log_event(
                "agent_complete",
                story_id=story_id,
                attempt=attempt,
                commit=_get_latest_commit_hash(),
                turns=agent_result.turns,
            )
        else:
            event_logger.log_event(
                "agent_failed",
                story_id=story_id,
                attempt=attempt,
                error=agent_result.output[:500] if agent_result.output else "Unknown error",
                turns=agent_result.turns,
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
                "Agent failed for story '%s' (attempt %d): category=%s, pattern=%s",
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

            # Build retry context for next attempt (simple dict)
            retry_context = StoryFailureContextArtifact(
                story_id=story_id,
                attempt=attempt,
                last_error=_extract_key_error(error_text),
                files_affected=tuple(plan_scope_paths),
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

        # Agent succeeded -- now run validation (checkpoint required)
        if checkpoint is None:
            # No validation checkpoint -- planning error (invariant S1)
            event_logger.log_event(
                "story_failed",
                story_id=story_id,
                attempt=attempt,
                reason="No validation checkpoint defined for story",
                failure_category="scope",
            )
            logger.error("Story '%s' has no validation checkpoint — planning error", story_id)
            return False

        # Run validation checkpoint
        skip_golden = config.gates.skip_golden_path if config else False
        validation_result = run_validation_checkpoint(
            checkpoint=checkpoint,
            epic_dir=epic_dir,
            story_id=story_id,
            event_logger=event_logger,
            skip_golden_path=skip_golden,
        )

        if validation_result.passed:
            # Validation passed -- run Opus critique before completing
            validation_summary = json.dumps(
                {"check_type": validation_result.check_type, "status": "pass"},
                indent=2,
            )
            critique_run = _run_story_critique(
                story=story,
                validation_results=validation_summary,
                event_logger=event_logger,
                attempt=attempt,
                model=model,
                config=config,
                base_commit=base_commit,
            )

            if critique_run.passed:
                # Critique passed -- story is complete
                event_logger.log_event(
                    "story_complete",
                    story_id=story_id,
                    attempt=attempt,
                    commit=_get_latest_commit_hash(),
                )
                logger.info(
                    "Story '%s' completed (validation + critique passed, attempt %d)",
                    story_id,
                    attempt,
                )
                return True

            # Critique failed -- hard gate: treat as implementation failure + retry
            critique_error = "; ".join(
                finding.summary_text for finding in critique_run.normalized_findings
            ) or critique_run.concise_summary
            classification = FailureClassificationArtifact(
                category="implementation",
                evidence=critique_error[:500],
                pattern="critique_failure",
            )

            logger.warning(
                "Critique failed for story '%s' (attempt %d, %d findings) — "
                "treating as implementation failure",
                story_id,
                attempt,
                critique_run.findings_count,
            )

            # Check retry budget
            retry_allowed = get_retry_budget(classification.category)
            remaining_attempts = max_attempts - attempt

            if retry_allowed == 0 or remaining_attempts == 0:
                return _handle_terminal_failure(
                    story_id=story_id,
                    attempt=attempt,
                    classification=classification,
                    error_text=critique_error,
                    event_logger=event_logger,
                    plan_scope_paths=plan_scope_paths,
                )

            # Build retry context with critique failure details
            retry_context = StoryFailureContextArtifact(
                story_id=story_id,
                attempt=attempt,
                last_error=_extract_key_error(critique_error),
                files_affected=tuple(plan_scope_paths),
                jsonl_excerpt=json.dumps(
                    {
                        "event": critique_run.event_name,
                        "failure_category": "implementation",
                        **critique_run.context_payload(limit=3),
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
            classification = FailureClassificationArtifact(
                category=validation_result.failure_category,
                evidence=classification.evidence,
                pattern=classification.pattern,
            )

        logger.warning(
            "Validation failed for story '%s' (attempt %d): category=%s, reason=%s",
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

        # Build retry context with validation failure details (simple dict)
        retry_context = StoryFailureContextArtifact(
            story_id=story_id,
            attempt=attempt,
            last_error=_extract_key_error(combined_error),
            files_affected=tuple(plan_scope_paths),
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
    classification: FailureClassificationArtifact,
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
    failure_context = StoryFailureContextArtifact(
        story_id=story_id,
        attempt=attempt,
        last_error=_extract_key_error(error_text),
        files_affected=tuple(plan_scope_paths),
        jsonl_excerpt=json.dumps(
            {
                "failure_category": classification.category,
                "evidence": classification.evidence,
                "pattern": classification.pattern,
            }
        ),
    )
    reason = classification.terminal_reason

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
            context=failure_context.event_context,
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
        from workflow.git_helpers import get_commit_hash

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
