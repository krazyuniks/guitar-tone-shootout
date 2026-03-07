"""Test generation pipeline — Step 5b of the epic workflow.

Generates integration/E2E tests for stories that have a test_spec in the plan.
Uses a write-review-retry loop with cross-model verification:

    1. test_writer dispatches claude -p to generate test code
    2. test_reviewer dispatches claude -p to review against a binary checklist
    3. On failure, reviewer feedback is appended and the writer retries (max 3)

All AI reasoning goes through ``claude -p`` CLI dispatch. No SDK calls.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from workflow.artifacts import (
    DispatchResultArtifact,
    StoryRunArtifact,
    TestReviewArtifact,
)
from workflow.dispatch import (
    dispatch_agent,
    extract_json_from_text,
    get_dispatch_params,
)
from workflow.jsonl_logger import EventLogger, find_last_event, read_log

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MAX_ATTEMPTS = 3

# JSON schema for reviewer structured output
TEST_REVIEW_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "checklist": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "note": {"type": "string"},
                },
                "required": ["item", "passed"],
            },
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["verdict", "checklist", "suggestions"],
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class TestGenResult:
    """Result of a single story's test generation attempt."""

    __test__ = False  # prevent pytest collection

    story_id: str
    success: bool
    test_file_path: str | None = None
    attempts: int = 0
    feedback_trail: list[TestReviewArtifact] = field(default_factory=list)


@dataclass
class TestGenReport:
    """Aggregate report from batch test generation."""

    __test__ = False  # prevent pytest collection

    passed: list[TestGenResult] = field(default_factory=list)
    failed: list[TestGenResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return len(self.failed) == 0


# ---------------------------------------------------------------------------
# Fixture catalogue loader
# ---------------------------------------------------------------------------


def _load_fixtures_md() -> str:
    """Load the FIXTURES.md catalogue content."""
    fixtures_path = PROJECT_ROOT / "tests" / "FIXTURES.md"
    if fixtures_path.is_file():
        return fixtures_path.read_text(encoding="utf-8")
    logger.warning("FIXTURES.md not found at %s", fixtures_path)
    return "(Fixture catalogue not available)"


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_writer_prompt(
    test_spec: dict,
    story: dict,
    epic_number: int,
    prior_feedback: list[TestReviewArtifact | dict] | None = None,
) -> str:
    """Build the prompt for the test_writer agent.

    Args:
        test_spec: The test_spec dict from the story.
        story: The full story dict from the plan.
        epic_number: Epic number for output path.
        prior_feedback: Previous reviewer feedback (for retry attempts).

    Returns:
        Full prompt text.
    """
    fixtures_md = _load_fixtures_md()
    story_id = story.get("story_id", "unknown")
    test_type = test_spec.get("test_type", "integration")

    lines = [
        "# Task: Write a pytest test file",
        "",
        "You are writing a test for a story in the GTS (Guitar Tone Shootout) project.",
        "",
        "## Story Context",
        "",
        f"**Story ID:** {story_id}",
        f"**Name:** {story.get('name', '')}",
        f"**Purpose:** {story.get('purpose', '')}",
        "",
        "### Acceptance Criteria",
        "",
    ]
    for criterion in story.get("acceptance_criteria", []):
        lines.append(f"- {criterion}")

    lines.extend(
        [
            "",
            "## Test Specification",
            "",
            f"**Test Type:** {test_type}",
            "",
            "### Fixtures to Use",
            "",
        ]
    )
    for fixture in test_spec.get("fixtures", []):
        lines.append(f"- `{fixture}`")

    lines.extend(
        [
            "",
            "### Assertions to Verify",
            "",
        ]
    )
    for assertion in test_spec.get("assertions", []):
        a_type = assertion.get("type", "unknown")
        details = assertion.get("details", {})
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        lines.append(f"- [{a_type}] {detail_str}")

    lines.extend(
        [
            "",
            "## Fixture Catalogue",
            "",
            fixtures_md,
            "",
            "## Rules",
            "",
            "1. Use factory fixtures from the catalogue above. NEVER define inline fixtures.",
            "2. NEVER use `unittest.mock`, `MagicMock`, `patch`, or any mocking.",
            "3. Test against real services (database, HTTP client).",
            "4. Every assertion from the test spec MUST have a corresponding `assert` statement.",
            "5. Tests should fail if the feature is not implemented.",
            f"6. Output a single Python file suitable for `tests/epic/E{epic_number}/test_{story_id.replace('-', '_')}.py`.",
            "7. Use `pytest.mark.asyncio` for async tests.",
            "8. Import paths use the project's package structure (e.g., `from webapp.main import app`).",
            "",
            "## Output",
            "",
            "Output ONLY the Python test file content. No explanation, no markdown fences.",
        ]
    )

    if prior_feedback:
        lines.extend(
            [
                "",
                "## Previous Reviewer Feedback (fix these issues)",
                "",
            ]
        )
        for i, feedback in enumerate(prior_feedback, 1):
            fb = feedback.to_dict() if isinstance(feedback, TestReviewArtifact) else feedback
            lines.append(f"### Attempt {i} Feedback")
            verdict = fb.get("verdict", "fail")
            lines.append(f"**Verdict:** {verdict}")
            for item in fb.get("checklist", []):
                status = "PASS" if item.get("passed") else "FAIL"
                lines.append(f"- [{status}] {item.get('item', '')}")
                if item.get("note"):
                    lines.append(f"  Note: {item['note']}")
            if fb.get("suggestions"):
                lines.append("**Suggestions:**")
                for suggestion in fb["suggestions"]:
                    lines.append(f"- {suggestion}")
            lines.append("")

    return "\n".join(lines)


def _build_reviewer_prompt(test_code: str, test_spec: dict) -> str:
    """Build the prompt for the test_reviewer agent.

    Args:
        test_code: The generated test file content.
        test_spec: The test_spec dict from the story.

    Returns:
        Full prompt text.
    """
    lines = [
        "# Task: Review a generated pytest test file",
        "",
        "You are reviewing a test file against a test specification.",
        "Evaluate EACH item on the checklist below. Be strict.",
        "",
        "## Test Specification",
        "",
        f"**Test Type:** {test_spec.get('test_type', 'integration')}",
        "",
        "### Required Fixtures",
        "",
    ]
    for fixture in test_spec.get("fixtures", []):
        lines.append(f"- `{fixture}`")

    lines.extend(
        [
            "",
            "### Required Assertions",
            "",
        ]
    )
    for assertion in test_spec.get("assertions", []):
        a_type = assertion.get("type", "unknown")
        details = assertion.get("details", {})
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        lines.append(f"- [{a_type}] {detail_str}")

    lines.extend(
        [
            "",
            "## Checklist (evaluate each)",
            "",
            "1. Every assertion from `test_spec` has a corresponding test assertion",
            "2. Tests use factory fixtures from catalogue (no inline definitions)",
            "3. No mocks, fakes, or `unittest.mock` imports",
            "4. Tests verify data flows through the system",
            "5. Tests would fail without the feature implemented",
            "",
            "## Test Code Under Review",
            "",
            "```python",
            test_code,
            "```",
            "",
            "## Output Format",
            "",
            "Respond with a JSON object matching this schema:",
            "",
            "```json",
            json.dumps(TEST_REVIEW_SCHEMA, indent=2),
            "```",
            "",
            'Set verdict to "pass" ONLY if ALL 5 checklist items pass.',
            "Include specific suggestions for any failures.",
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Writer dispatch
# ---------------------------------------------------------------------------


def write_test_for_story(
    story: dict,
    test_spec: dict,
    epic_dir: Path,
    config: object,
    prior_feedback: list[dict] | None = None,
) -> tuple[str, str]:
    """Dispatch the test_writer agent to generate a test file.

    Args:
        story: Story dict from the plan.
        test_spec: The test_spec dict.
        epic_dir: Path to the epic directory.
        config: EpicConfig instance.
        prior_feedback: Previous reviewer feedback for retry.

    Returns:
        Tuple of (test_file_path, test_code).
    """
    from workflow.epic_config import EpicConfig

    assert isinstance(config, EpicConfig)

    epic_number = int(epic_dir.name.lstrip("E"))
    story_id = story.get("story_id", "unknown")
    safe_id = story_id.replace("-", "_")

    # Build output path
    test_dir = PROJECT_ROOT / "tests" / "epic" / f"E{epic_number}"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / f"test_{safe_id}.py"

    prompt = _build_writer_prompt(test_spec, story, epic_number, prior_feedback)

    model = config.models.test_writer
    mcp_servers, timeout = get_dispatch_params("test_writing", config)

    result: DispatchResultArtifact = dispatch_agent(
        prompt=prompt,
        model=model,
        mcp_servers=mcp_servers,
        timeout=timeout,
        role="test_writer",
    )

    if not result.success:
        raise RuntimeError(
            f"test_writer dispatch failed for {story_id}: exit_code={result.exit_code}"
        )

    # Extract the test code from the agent output
    test_code = result.output.strip()

    # Strip markdown fences if present
    if test_code.startswith("```"):
        code_lines = test_code.split("\n")
        if code_lines[-1].strip() == "```":
            test_code = "\n".join(code_lines[1:-1])

    # Write the test file
    test_file.write_text(test_code + "\n", encoding="utf-8")
    logger.info("Test written: %s", test_file)

    return str(test_file.relative_to(PROJECT_ROOT)), test_code


# ---------------------------------------------------------------------------
# Reviewer dispatch
# ---------------------------------------------------------------------------


def review_test(
    test_code: str,
    test_spec: dict,
    config: object,
) -> TestReviewArtifact:
    """Dispatch the test_reviewer agent to review generated test code.

    Args:
        test_code: The test file content.
        test_spec: The test_spec dict.
        config: EpicConfig instance.

    Returns:
        Typed review artifact with verdict, checklist, and suggestions.

    Raises:
        RuntimeError: If the reviewer dispatch fails.
        ValueError: If the reviewer output cannot be parsed.
    """
    from workflow.epic_config import EpicConfig

    assert isinstance(config, EpicConfig)

    prompt = _build_reviewer_prompt(test_code, test_spec)

    model = config.models.test_writer
    mcp_servers, timeout = get_dispatch_params("test_writing", config)

    result: DispatchResultArtifact = dispatch_agent(
        prompt=prompt,
        model=model,
        json_schema=TEST_REVIEW_SCHEMA,
        mcp_servers=mcp_servers,
        timeout=timeout,
        role="test_reviewer",
    )

    if not result.success:
        raise RuntimeError(f"test_reviewer dispatch failed: exit_code={result.exit_code}")

    # Parse the structured review output
    try:
        payload = result.structured_output or extract_json_from_text(result.output)
    except ValueError as exc:
        raise ValueError(
            f"Failed to parse reviewer output: {exc}\nRaw: {result.output[:500]}"
        ) from exc

    return TestReviewArtifact.from_dict(payload)


# ---------------------------------------------------------------------------
# Retry loop
# ---------------------------------------------------------------------------


def generate_and_review_test(
    story: dict,
    test_spec: dict,
    epic_dir: Path,
    config: object,
    event_logger: EventLogger,
) -> TestGenResult:
    """Generate a test with write-review-retry loop.

    Runs up to MAX_ATTEMPTS iterations:
    1. Dispatch test_writer to generate test code
    2. Dispatch test_reviewer to review it
    3. On pass: return success
    4. On fail: append feedback and retry

    Args:
        story: Story dict from the plan.
        test_spec: The test_spec dict.
        epic_dir: Path to the epic directory.
        config: EpicConfig instance.
        event_logger: JSONL event logger.

    Returns:
        TestGenResult with success status and feedback trail.
    """
    story_id = story.get("story_id", "unknown")
    feedback_trail: list[TestReviewArtifact] = []

    event_logger.log_event("test_gen_started", story_id=story_id)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info(
            "Test generation attempt %d/%d for %s",
            attempt,
            MAX_ATTEMPTS,
            story_id,
        )

        # Write
        try:
            test_file_path, test_code = write_test_for_story(
                story=story,
                test_spec=test_spec,
                epic_dir=epic_dir,
                config=config,
                prior_feedback=feedback_trail if feedback_trail else None,
            )
        except RuntimeError as exc:
            logger.error("test_writer failed for %s: %s", story_id, exc)
            event_logger.log_event(
                "test_gen_attempt",
                story_id=story_id,
                attempt=attempt,
                test_file_path=None,
                error=str(exc),
            )
            continue

        event_logger.log_event(
            "test_gen_attempt",
            story_id=story_id,
            attempt=attempt,
            test_file_path=test_file_path,
        )

        # Review
        try:
            review = review_test(test_code, test_spec, config)
        except (RuntimeError, ValueError) as exc:
            logger.error("test_reviewer failed for %s: %s", story_id, exc)
            feedback_trail.append(
                TestReviewArtifact.from_dict(
                    {
                    "verdict": "fail",
                    "checklist": [],
                    "suggestions": [f"Reviewer error: {exc}"],
                    }
                )
            )
            event_logger.log_event(
                "test_review_fail",
                story_id=story_id,
                attempt=attempt,
                reviewer_feedback={"error": str(exc)},
            )
            continue

        if review.passed:
            logger.info("Test review PASSED for %s (attempt %d)", story_id, attempt)
            event_logger.log_event(
                "test_review_pass",
                story_id=story_id,
                test_file_path=test_file_path,
            )
            return TestGenResult(
                story_id=story_id,
                success=True,
                test_file_path=test_file_path,
                attempts=attempt,
                feedback_trail=feedback_trail,
            )

        # Fail — collect feedback for next attempt
        logger.warning(
            "Test review FAILED for %s (attempt %d/%d)",
            story_id,
            attempt,
            MAX_ATTEMPTS,
        )
        feedback_trail.append(review)
        event_logger.log_event(
            "test_review_fail",
            story_id=story_id,
            attempt=attempt,
            reviewer_feedback=review.to_dict(),
        )

    # Exhausted all attempts
    logger.error(
        "Test generation failed for %s after %d attempts",
        story_id,
        MAX_ATTEMPTS,
    )
    return TestGenResult(
        story_id=story_id,
        success=False,
        test_file_path=None,
        attempts=MAX_ATTEMPTS,
        feedback_trail=feedback_trail,
    )


# ---------------------------------------------------------------------------
# Batch orchestration
# ---------------------------------------------------------------------------


def _is_test_already_passing(events: list[dict], story_id: str) -> bool:
    """Check if a test_review_pass event exists for a story in the JSONL log."""
    return StoryRunArtifact.from_events(events, story_id).has_passing_test


def run_test_generation(
    epic_dir: Path,
    plan: dict,
    config: object,
    event_logger: EventLogger,
) -> TestGenReport:
    """Run test generation for all stories with test_specs.

    Pre-flight: refuses to run if ``tests_approved`` event is not in the
    JSONL log. This ensures the interactive CC review has been completed.

    Processes stories sequentially. Skips stories that already have a
    test_review_pass event in the JSONL log (resume support).

    Args:
        epic_dir: Path to the epic directory.
        plan: The parsed plan.json dict.
        config: EpicConfig instance.
        event_logger: JSONL event logger.

    Returns:
        TestGenReport with passed and failed results.

    Raises:
        RuntimeError: If tests_approved event is missing from JSONL.
    """
    stories = plan.get("stories", [])
    log_path = event_logger.log_path
    events = read_log(log_path)

    # Pre-flight: require tests_approved gate
    if find_last_event(events, "tests_approved") is None:
        raise RuntimeError(
            "Cannot run test generation: tests_approved event not found in JSONL. "
            "Run /epic review-tests N to review and approve test specs first."
        )

    report = TestGenReport()

    stories_with_specs = [s for s in stories if s.get("test_spec") is not None]

    if not stories_with_specs:
        logger.info("No stories with test_specs found. Skipping test generation.")
        return report

    logger.info(
        "Running test generation for %d/%d stories with test_specs",
        len(stories_with_specs),
        len(stories),
    )

    for story in stories_with_specs:
        story_id = story.get("story_id", "unknown")
        test_spec = story["test_spec"]
        story_run = StoryRunArtifact.from_events(events, story_id)

        # Resume support: skip already-passing tests
        if story_run.has_passing_test:
            logger.info("Skipping %s — test already passing", story_id)
            report.passed.append(
                TestGenResult(
                    story_id=story_id,
                    success=True,
                    test_file_path=story_run.latest_test_file_path,
                    attempts=story_run.attempt,
                )
            )
            continue

        result = generate_and_review_test(
            story=story,
            test_spec=test_spec,
            epic_dir=epic_dir,
            config=config,
            event_logger=event_logger,
        )

        if result.success:
            report.passed.append(result)
        else:
            report.failed.append(result)

    logger.info(
        "Test generation complete: %d passed, %d failed",
        len(report.passed),
        len(report.failed),
    )

    return report
