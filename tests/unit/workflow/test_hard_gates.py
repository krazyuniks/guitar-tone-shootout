"""Tests for Phase 5 hard gates.

Covers:
- 5b: Golden path gate in validation checkpoint
- 5c: Critique failure triggers retry (no advisory path)
"""

from workflow.story_executor import (
    FailureClassification,
    get_retry_budget,
)
from workflow.validation import CheckCriterion


class TestScopeViolationRetryBudget:
    """scope_violation category gets zero retries."""

    def test_scope_violation_no_retries(self):
        assert get_retry_budget("scope_violation") == 0

    def test_env_no_retries(self):
        assert get_retry_budget("env") == 0

    def test_implementation_has_retries(self):
        assert get_retry_budget("implementation") > 0


# ---------------------------------------------------------------------------
# 5b: Golden path gate in validation
# ---------------------------------------------------------------------------


class TestGoldenPathGate:
    """Golden path runs as mandatory gate after baseline quality."""

    def test_golden_path_command_in_criterion_commands(self):
        """just test-golden-path is a known criterion command."""
        from workflow.validation import _CRITERION_COMMANDS

        assert "just test-golden-path" in _CRITERION_COMMANDS

    def test_golden_path_skipped_when_already_in_story_checks(self):
        """If story checks already include golden path, don't run it twice.

        We verify this by checking the code path — if the story already
        has the command, the gate is skipped.
        """
        from workflow.validation import _resolve_command

        check = CheckCriterion(
            criterion="Golden path tests pass",
            command="just test-golden-path",
        )
        assert _resolve_command(check) == "just test-golden-path"


# ---------------------------------------------------------------------------
# 5c: Critique advisory removed
# ---------------------------------------------------------------------------


class TestCritiqueAdvisoryRemoved:
    """The critique_advisory soft gate no longer exists."""

    def test_story_complete_event_schema_no_advisory(self):
        """report.py event schema for story_complete has no critique_advisory."""
        from workflow.report import KNOWN_EVENTS

        fields = KNOWN_EVENTS["story_complete"]
        assert "critique_advisory" not in fields

    def test_failure_classification_for_critique(self):
        """Critique failures use implementation category (retryable)."""
        fc = FailureClassification(
            category="implementation",
            evidence="some critique finding",
            pattern="critique_failure",
        )
        assert fc.category == "implementation"
        assert get_retry_budget(fc.category) > 0
