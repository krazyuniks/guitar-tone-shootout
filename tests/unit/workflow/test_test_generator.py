"""Tests for workflow.test_generator module.

Tests prompt building, result types, JSONL resume logic, and batch
orchestration. Dispatch functions are NOT tested here (they require
real claude -p); these tests verify the deterministic logic.
"""

from workflow.jsonl_logger import EventLogger
from workflow.test_generator import (
    MAX_ATTEMPTS,
    TEST_REVIEW_SCHEMA,
    TestGenReport,
    TestGenResult,
    _build_reviewer_prompt,
    _build_writer_prompt,
    _is_test_already_passing,
)


class TestWriterPromptBuilder:
    """_build_writer_prompt produces correct prompts."""

    def _make_story(self, **overrides):
        base = {
            "story_id": "01-setup",
            "name": "Initial Setup",
            "purpose": "Set up the project",
            "acceptance_criteria": ["Page renders", "DB seeded"],
            "test_spec": {
                "test_type": "integration",
                "fixtures": ["make_user", "make_shootout"],
                "assertions": [
                    {
                        "type": "http_status",
                        "details": {"route": "/api/v1/foo", "expected_status": 200},
                    },
                    {"type": "db_state", "details": {"table": "users", "count": 1}},
                ],
            },
        }
        base.update(overrides)
        return base

    def test_includes_story_context(self):
        """Prompt contains story ID, name, and purpose."""
        story = self._make_story()
        prompt = _build_writer_prompt(story["test_spec"], story, 134)
        assert "01-setup" in prompt
        assert "Initial Setup" in prompt
        assert "Set up the project" in prompt

    def test_includes_acceptance_criteria(self):
        """Prompt lists acceptance criteria."""
        story = self._make_story()
        prompt = _build_writer_prompt(story["test_spec"], story, 134)
        assert "Page renders" in prompt
        assert "DB seeded" in prompt

    def test_includes_fixtures(self):
        """Prompt lists required fixtures."""
        story = self._make_story()
        prompt = _build_writer_prompt(story["test_spec"], story, 134)
        assert "make_user" in prompt
        assert "make_shootout" in prompt

    def test_includes_assertions(self):
        """Prompt lists assertions with types and details."""
        story = self._make_story()
        prompt = _build_writer_prompt(story["test_spec"], story, 134)
        assert "http_status" in prompt
        assert "db_state" in prompt
        assert "/api/v1/foo" in prompt

    def test_includes_rules(self):
        """Prompt contains the mandatory rules."""
        story = self._make_story()
        prompt = _build_writer_prompt(story["test_spec"], story, 134)
        assert "unittest.mock" in prompt
        assert "factory fixtures" in prompt.lower()

    def test_includes_output_path(self):
        """Prompt references the correct output file path."""
        story = self._make_story()
        prompt = _build_writer_prompt(story["test_spec"], story, 134)
        assert "tests/epic/E134/test_01_setup.py" in prompt

    def test_includes_prior_feedback(self):
        """Retry prompt includes previous reviewer feedback."""
        story = self._make_story()
        feedback = [
            {
                "verdict": "fail",
                "checklist": [
                    {
                        "item": "assertions covered",
                        "passed": False,
                        "note": "Missing db_state assert",
                    },
                ],
                "suggestions": ["Add an assert for user count"],
            }
        ]
        prompt = _build_writer_prompt(story["test_spec"], story, 134, prior_feedback=feedback)
        assert "Previous Reviewer Feedback" in prompt
        assert "Missing db_state assert" in prompt
        assert "Add an assert for user count" in prompt

    def test_no_feedback_section_on_first_attempt(self):
        """First attempt prompt does not include feedback section."""
        story = self._make_story()
        prompt = _build_writer_prompt(story["test_spec"], story, 134)
        assert "Previous Reviewer Feedback" not in prompt


class TestReviewerPromptBuilder:
    """_build_reviewer_prompt produces correct prompts."""

    def test_includes_test_code(self):
        """Prompt contains the test code under review."""
        test_code = "def test_example():\n    assert True"
        spec = {"test_type": "integration", "fixtures": [], "assertions": []}
        prompt = _build_reviewer_prompt(test_code, spec)
        assert "def test_example():" in prompt
        assert "assert True" in prompt

    def test_includes_checklist(self):
        """Prompt contains all 5 checklist items."""
        spec = {"test_type": "integration", "fixtures": [], "assertions": []}
        prompt = _build_reviewer_prompt("pass", spec)
        assert "Every assertion from `test_spec`" in prompt
        assert "factory fixtures" in prompt
        assert "unittest.mock" in prompt
        assert "data flows through the system" in prompt
        assert "fail without the feature" in prompt

    def test_includes_spec_fixtures(self):
        """Prompt lists the required fixtures from the spec."""
        spec = {
            "test_type": "integration",
            "fixtures": ["make_user", "db_session"],
            "assertions": [],
        }
        prompt = _build_reviewer_prompt("pass", spec)
        assert "make_user" in prompt
        assert "db_session" in prompt

    def test_includes_spec_assertions(self):
        """Prompt lists the required assertions from the spec."""
        spec = {
            "test_type": "e2e",
            "fixtures": [],
            "assertions": [
                {"type": "dom_element", "details": {"selector": "#title"}},
            ],
        }
        prompt = _build_reviewer_prompt("pass", spec)
        assert "dom_element" in prompt
        assert "#title" in prompt


class TestReviewSchema:
    """TEST_REVIEW_SCHEMA is valid JSON Schema."""

    def test_has_required_fields(self):
        """Schema requires verdict, checklist, suggestions."""
        assert "verdict" in TEST_REVIEW_SCHEMA["properties"]
        assert "checklist" in TEST_REVIEW_SCHEMA["properties"]
        assert "suggestions" in TEST_REVIEW_SCHEMA["properties"]
        assert set(TEST_REVIEW_SCHEMA["required"]) == {"verdict", "checklist", "suggestions"}

    def test_verdict_enum(self):
        """Verdict is restricted to pass/fail."""
        verdict_schema = TEST_REVIEW_SCHEMA["properties"]["verdict"]
        assert verdict_schema["enum"] == ["pass", "fail"]


class TestTestGenResult:
    """TestGenResult and TestGenReport data classes."""

    def test_result_defaults(self):
        """TestGenResult has sensible defaults."""
        r = TestGenResult(story_id="01-x", success=True)
        assert r.test_file_path is None
        assert r.attempts == 0
        assert r.feedback_trail == []

    def test_report_all_passed_true(self):
        """all_passed is True when no failures."""
        report = TestGenReport(
            passed=[TestGenResult(story_id="01", success=True)],
            failed=[],
        )
        assert report.all_passed is True

    def test_report_all_passed_false(self):
        """all_passed is False when there are failures."""
        report = TestGenReport(
            passed=[],
            failed=[TestGenResult(story_id="01", success=False)],
        )
        assert report.all_passed is False

    def test_report_empty_is_all_passed(self):
        """Empty report (no stories with specs) counts as all passed."""
        report = TestGenReport()
        assert report.all_passed is True


class TestResumeLogic:
    """_is_test_already_passing checks JSONL events correctly."""

    def test_returns_true_when_pass_event_exists(self, tmp_path):
        """Returns True if test_review_pass event found for story."""
        log_path = tmp_path / "epic.jsonl"
        logger = EventLogger(log_path, "run-1")
        logger.log_event("test_review_pass", story_id="01-setup", test_file_path="tests/x.py")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        assert _is_test_already_passing(events, "01-setup") is True

    def test_returns_false_when_no_pass_event(self, tmp_path):
        """Returns False if no test_review_pass event for story."""
        log_path = tmp_path / "epic.jsonl"
        logger = EventLogger(log_path, "run-1")
        logger.log_event("test_gen_started", story_id="01-setup")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        assert _is_test_already_passing(events, "01-setup") is False

    def test_returns_false_for_different_story(self, tmp_path):
        """Returns False when pass event exists for a different story."""
        log_path = tmp_path / "epic.jsonl"
        logger = EventLogger(log_path, "run-1")
        logger.log_event("test_review_pass", story_id="02-other", test_file_path="tests/x.py")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        assert _is_test_already_passing(events, "01-setup") is False

    def test_empty_log_returns_false(self):
        """Returns False for empty events list."""
        assert _is_test_already_passing([], "01-setup") is False


class TestMaxAttempts:
    """MAX_ATTEMPTS constant is set correctly."""

    def test_max_attempts_is_three(self):
        assert MAX_ATTEMPTS == 3
