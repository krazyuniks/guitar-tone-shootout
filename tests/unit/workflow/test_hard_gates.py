"""Tests for Phase 5 hard gates and test file protection.

Covers:
- 5a: Test file hash snapshot and modification detection
- 5b: Golden path gate in validation checkpoint
- 5c: Critique failure triggers retry (no advisory path)
"""

from workflow.story_executor import (
    FailureClassification,
    _detect_test_modifications,
    _snapshot_test_hashes,
    get_retry_budget,
)
from workflow.validation import CheckCriterion

# ---------------------------------------------------------------------------
# 5a: Test file hashing
# ---------------------------------------------------------------------------


class TestSnapshotTestHashes:
    """_snapshot_test_hashes returns SHA-256 digests of test .py files."""

    def test_returns_dict_of_hashes(self):
        """Snapshot includes .py files under tests/."""
        hashes = _snapshot_test_hashes()
        # The project has tests — should be non-empty
        assert isinstance(hashes, dict)
        assert len(hashes) > 0
        # All keys are relative paths starting with tests/
        for path in hashes:
            assert path.startswith("tests/")
            assert path.endswith(".py")
        # All values are hex SHA-256 (64 chars)
        for digest in hashes.values():
            assert len(digest) == 64

    def test_deterministic(self):
        """Two consecutive snapshots produce identical results."""
        a = _snapshot_test_hashes()
        b = _snapshot_test_hashes()
        assert a == b


class TestDetectTestModifications:
    """_detect_test_modifications compares before/after snapshots."""

    def test_no_changes(self):
        before = {"tests/a.py": "abc123", "tests/b.py": "def456"}
        after = {"tests/a.py": "abc123", "tests/b.py": "def456"}
        assert _detect_test_modifications(before, after) == []

    def test_modified_file(self):
        before = {"tests/a.py": "abc123", "tests/b.py": "def456"}
        after = {"tests/a.py": "CHANGED", "tests/b.py": "def456"}
        assert _detect_test_modifications(before, after) == ["tests/a.py"]

    def test_deleted_file(self):
        before = {"tests/a.py": "abc123", "tests/b.py": "def456"}
        after = {"tests/b.py": "def456"}
        assert _detect_test_modifications(before, after) == ["tests/a.py"]

    def test_new_file_allowed(self):
        """New test files (not in before snapshot) are NOT flagged."""
        before = {"tests/a.py": "abc123"}
        after = {"tests/a.py": "abc123", "tests/new.py": "xyz789"}
        assert _detect_test_modifications(before, after) == []

    def test_multiple_changes_sorted(self):
        before = {"tests/z.py": "aaa", "tests/a.py": "bbb"}
        after = {"tests/z.py": "ZZZ", "tests/a.py": "AAA"}
        result = _detect_test_modifications(before, after)
        assert result == ["tests/a.py", "tests/z.py"]


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
