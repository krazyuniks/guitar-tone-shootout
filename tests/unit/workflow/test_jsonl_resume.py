"""Tests for JSONL resume state logic in workflow.jsonl_logger.

Tests get_resumable_state's handling of test generation events and
is_test_generation_complete for pipeline-level resume decisions.
"""

from workflow.jsonl_logger import (
    EventLogger,
    build_run_artifact,
    get_resumable_state,
    is_test_generation_complete,
)


class TestGetResumableStateTestGenEvents:
    """get_resumable_state recognises test generation events."""

    def test_test_gen_started_sets_test_generation_action(self, tmp_path):
        """Crash during test_gen_started => next_action is test_generation."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("plan_committed", epic=99)
        el.log_event("test_gen_started", story_id="01-setup")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        state = get_resumable_state(events, "run-1")

        assert state["next_action"] == "test_generation"

    def test_test_gen_attempt_sets_test_generation_action(self, tmp_path):
        """Crash during test_gen_attempt => next_action is test_generation."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("plan_committed", epic=99)
        el.log_event("test_gen_started", story_id="01-setup")
        el.log_event(
            "test_gen_attempt",
            story_id="01-setup",
            attempt=1,
            test_file_path="tests/epic/E99/test_01_setup.py",
        )

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        state = get_resumable_state(events, "run-1")

        assert state["next_action"] == "test_generation"

    def test_test_review_fail_sets_test_generation_action(self, tmp_path):
        """Crash after test_review_fail => next_action is test_generation."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("plan_committed", epic=99)
        el.log_event("test_gen_started", story_id="01-setup")
        el.log_event(
            "test_review_fail",
            story_id="01-setup",
            attempt=1,
            reviewer_feedback={"verdict": "fail"},
        )

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        state = get_resumable_state(events, "run-1")

        assert state["next_action"] == "test_generation"

    def test_test_review_pass_sets_continue_action(self, tmp_path):
        """After test_review_pass => next_action is continue (not test_generation)."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("plan_committed", epic=99)
        el.log_event("test_gen_started", story_id="01-setup")
        el.log_event(
            "test_review_pass",
            story_id="01-setup",
            test_file_path="tests/epic/E99/test_01_setup.py",
        )

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        state = get_resumable_state(events, "run-1")

        assert state["next_action"] == "continue"

    def test_stories_with_passing_tests_tracked(self, tmp_path):
        """stories_with_passing_tests lists stories with test_review_pass."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("test_review_pass", story_id="01-setup", test_file_path="a.py")
        el.log_event("test_review_pass", story_id="02-api", test_file_path="b.py")
        el.log_event("test_review_fail", story_id="03-ui", attempt=1, reviewer_feedback={})

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        state = get_resumable_state(events, "run-1")

        assert state["stories_with_passing_tests"] == ["01-setup", "02-api"]

    def test_passing_tests_not_scoped_to_run(self, tmp_path):
        """stories_with_passing_tests includes passes from any run."""
        log_path = tmp_path / "epic.jsonl"
        # Pass from a different run
        el_old = EventLogger(log_path, "run-0")
        el_old.log_event("test_review_pass", story_id="01-setup", test_file_path="a.py")
        # Current run has a different event
        el = EventLogger(log_path, "run-1")
        el.log_event("epic_started", epic=99)

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        state = get_resumable_state(events, "run-1")

        assert "01-setup" in state["stories_with_passing_tests"]

    def test_empty_run_includes_passing_tests_key(self):
        """Empty state includes stories_with_passing_tests as empty list."""
        state = get_resumable_state([], "run-1")

        assert state["stories_with_passing_tests"] == []

    def test_epic_complete_still_recognised(self, tmp_path):
        """epic_complete action still works with new state fields."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("epic_complete", epic=99, stories_completed=3)

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        state = get_resumable_state(events, "run-1")

        assert state["next_action"] == "epic_complete"
        assert "stories_with_passing_tests" in state


class TestIsTestGenerationComplete:
    """is_test_generation_complete checks all stories with specs have passing tests."""

    def test_complete_when_all_stories_have_pass(self, tmp_path):
        """Returns True when every story with a spec has a test_review_pass."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("test_review_pass", story_id="01-setup", test_file_path="a.py")
        el.log_event("test_review_pass", story_id="02-api", test_file_path="b.py")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        assert is_test_generation_complete(events, ["01-setup", "02-api"]) is True

    def test_incomplete_when_story_missing_pass(self, tmp_path):
        """Returns False when a story with a spec has no test_review_pass."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("test_review_pass", story_id="01-setup", test_file_path="a.py")
        el.log_event("test_gen_started", story_id="02-api")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        assert is_test_generation_complete(events, ["01-setup", "02-api"]) is False

    def test_complete_when_no_specs(self):
        """Returns True when no stories have test_specs."""
        assert is_test_generation_complete([], []) is True

    def test_complete_with_extra_passes(self, tmp_path):
        """Extra passes for stories not in the spec list don't affect result."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("test_review_pass", story_id="01-setup", test_file_path="a.py")
        el.log_event("test_review_pass", story_id="99-extra", test_file_path="c.py")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        assert is_test_generation_complete(events, ["01-setup"]) is True

    def test_not_scoped_to_run(self, tmp_path):
        """Passes from any run count towards completion."""
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-old")
        el.log_event("test_review_pass", story_id="01-setup", test_file_path="a.py")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        assert is_test_generation_complete(events, ["01-setup"]) is True

    def test_incomplete_with_empty_events(self):
        """Returns False when events are empty but specs exist."""
        assert is_test_generation_complete([], ["01-setup"]) is False


class TestRunArtifact:
    """Typed run snapshots should match resumable-state semantics."""

    def test_build_run_artifact_derives_stage_gate_and_completed_stories(self, tmp_path):
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("plan_committed", epic=99)
        el.log_event("plan_approved", epic=99)
        el.log_event("story_complete", story_id="01-setup", attempt=1, commit="abc123")

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        run = build_run_artifact(events, "run-1", epic_number=99, has_plan=True)

        assert run.epic_number == 99
        assert run.stage == "execution"
        assert run.decision_gate == "approved"
        assert list(run.completed_stories) == ["01-setup"]
        assert run.next_action == "continue"

    def test_build_run_artifact_reconstructs_rejected_gate_from_typed_event_shape(self, tmp_path):
        log_path = tmp_path / "epic.jsonl"
        el = EventLogger(log_path, "run-1")
        el.log_event("plan_rejected", epic=99, reason="Verifier findings remain", feedback={})

        from workflow.jsonl_logger import read_log

        events = read_log(log_path)
        run = build_run_artifact(events, "run-1", epic_number=99, has_plan=True)

        assert run.stage == "planned"
        assert run.decision_gate == "rejected"
        assert run.next_action == "continue"

    def test_build_run_artifact_returns_planned_when_plan_exists_without_commit(self):
        run = build_run_artifact([], "run-1", epic_number=99, has_plan=True)

        assert run.stage == "planned"
        assert run.next_action == "start"
