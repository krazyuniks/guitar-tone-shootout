"""Tests for typed workflow artifacts."""

import pytest

from workflow.artifacts import (
    DispatchArtifact,
    DispatchResultArtifact,
    EpicArtifact,
    PlanArtifact,
    RevisionRequestArtifact,
    RunArtifact,
    RunEventArtifact,
    StoryRunArtifact,
    TestReviewArtifact,
    VerifierFeedbackArtifact,
)
from workflow.plan_generator import make_phase_b_revision_prompt


def _sample_plan() -> dict:
    return {
        "schema_v": 1,
        "epic_number": 146,
        "goal": "Sample goal",
        "observable_truths": [{"id": 1, "statement": "A user can do the thing"}],
        "user_journeys": [
            {
                "journey_id": "J1",
                "persona": "User",
                "narrative": "User does the thing",
                "truths_covered": [1],
                "entry_point": "/start",
                "critical_transitions": [
                    {"source": "/start", "to": "/done", "mechanism": "Click submit"}
                ],
            }
        ],
        "stories": [
            {
                "story_id": "01-sample",
                "name": "Sample story",
                "purpose": "Deliver the thing",
                "agent": {"model": "sonnet", "skills": ["gts-frontend-dev"]},
                "scope": {"modify": ["apps/webapp/src/webapp/api/pages/chains.py"]},
                "acceptance_criteria": ["Thing works"],
                "architectural_context": ["Very long architectural guidance" * 20],
                "navigation_hints": ["frontend/astro/src/pages/pages/library/chains.html.ts"],
                "implementation_notes": ["Very long implementation note" * 20],
                "truths_addressed": [1],
                "test_spec": {
                    "test_type": "integration",
                    "assertions": [{"type": "http_status", "details": {"expected_status": 200}}],
                },
            }
        ],
        "validation_checkpoints": [
            {
                "after_story": "01-sample",
                "check_type": "http+dom",
                "checks": [{"criterion": "Page renders"}],
            }
        ],
    }


class TestEpicArtifact:
    def test_from_epic_dir_reads_epic_number_and_body(self, tmp_path) -> None:
        epic_dir = tmp_path / "E146"
        epic_dir.mkdir()
        (epic_dir / "EPIC.md").write_text("## Summary\nTest epic\n", encoding="utf-8")

        artifact = EpicArtifact.from_epic_dir(epic_dir)

        assert artifact.epic_number == 146
        assert artifact.body == "## Summary\nTest epic\n"
        assert artifact.prompt_block == "<epic>\n## Summary\nTest epic\n\n</epic>"


class TestPlanArtifact:
    def test_json_round_trip_and_compact_review_payload_are_deterministic(self) -> None:
        artifact = PlanArtifact.from_dict(_sample_plan())
        round_tripped = PlanArtifact.from_json_text(artifact.json_text)

        assert round_tripped.to_dict() == artifact.to_dict()
        assert "architectural_context" not in artifact.review_payload["stories"][0]
        assert "implementation_notes" not in artifact.review_payload["stories"][0]

    def test_write_renders_json_and_plan_markdown(self, tmp_path) -> None:
        epic_dir = tmp_path / "E146"
        epic_dir.mkdir()
        artifact = PlanArtifact.from_dict(_sample_plan())

        plan_md_path, plan_json_path = artifact.write(epic_dir)

        assert plan_json_path.read_text(encoding="utf-8") == artifact.json_text
        assert plan_md_path.read_text(encoding="utf-8") == artifact.markdown
        assert "# Plan: Epic #146" in artifact.markdown


class TestVerifierFeedbackArtifact:
    def test_failed_dimensions_and_extractable_findings_use_typed_accessors(self) -> None:
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "intent_alignment": {
                        "status": "fail",
                        "findings": [{"severity": "must_fix", "epic_requirement": "Use HTMX"}],
                    },
                    "gap_detection": {
                        "status": "pass",
                        "findings": [],
                    },
                },
                "summary": "Needs changes",
            }
        )

        assert feedback.failed_dimensions() == ["intent_alignment"]
        assert feedback.has_extractable_findings() is True
        assert feedback.summary == "Needs changes"

    def test_legacy_flat_dimension_layout_is_supported(self) -> None:
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "intent_alignment": {
                    "status": "fail",
                    "scope_creep": ["Unexpected route"],
                },
            }
        )

        assert feedback.dimension("intent_alignment")["scope_creep"] == ["Unexpected route"]
        assert feedback.has_extractable_findings() is True


class TestDispatchAndRunArtifacts:
    def test_dispatch_artifact_round_trips_started_entry(self) -> None:
        dispatch = DispatchArtifact(
            ts="2026-03-07T12:00:00+00:00",
            run_id="run-1",
            dispatch_id="abc-123",
            status="started",
            role="planner",
            model="sonnet",
            prompt_hash="abc",
            prompt_tokens=123,
            prompt_file="dispatches/abc-prompt.txt",
            response_file="dispatches/abc-response.txt",
            conversation_file="dispatches/abc-conversation.jsonl",
        )

        assert DispatchArtifact.from_dict(dispatch.to_dict()) == dispatch

    def test_dispatch_result_artifact_round_trips_structured_output(self) -> None:
        result = DispatchResultArtifact(
            success=True,
            output='{"status":"ok"}',
            structured_output={"status": "ok"},
            exit_code=0,
            turns=4,
        )

        assert DispatchResultArtifact.from_dict(result.to_dict()) == result

    def test_run_event_artifact_round_trips_flat_jsonl_shape(self) -> None:
        event = RunEventArtifact(
            run_id="run-1",
            ts="2026-03-07T12:00:00+00:00",
            event="story_complete",
            data={"story_id": "01-setup", "attempt": 1},
        )

        assert RunEventArtifact.from_dict(event.to_dict()) == event

    def test_run_artifact_collects_dispatch_ids(self) -> None:
        run = RunArtifact.from_logs(
            [
                {
                    "schema_v": 2,
                    "run_id": "run-1",
                    "ts": "2026-03-07T12:00:00+00:00",
                    "event": "plan_committed",
                    "epic": 146,
                }
            ],
            "run-1",
            epic_number=146,
            has_plan=True,
            dispatches=[
                {
                    "ts": "2026-03-07T12:01:00+00:00",
                    "run_id": "run-1",
                    "dispatch_id": "dispatch-1",
                    "status": "completed",
                    "role": "planner",
                    "model": "sonnet",
                    "prompt_hash": "abc",
                    "prompt_tokens": 123,
                    "response_tokens": 45,
                    "success": True,
                    "exit_code": 0,
                    "duration_ms": 1000,
                    "prompt_file": "dispatches/abc-prompt.txt",
                    "response_file": "dispatches/abc-response.txt",
                    "conversation_file": "dispatches/abc-conversation.jsonl",
                }
            ],
        )

        assert run.stage == "execution"
        assert run.dispatch_ids == ("dispatch-1",)

    def test_story_run_artifact_reconstructs_test_generation_state(self) -> None:
        review = TestReviewArtifact.from_dict(
            {
                "verdict": "fail",
                "checklist": [
                    {
                        "item": "Every assertion from test_spec has a corresponding test assertion",
                        "passed": False,
                        "note": "Missing db assertion",
                    }
                ],
                "suggestions": ["Add the missing database assertion"],
            }
        )
        run = StoryRunArtifact.from_events(
            [
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T12:00:00+00:00",
                    event="test_gen_started",
                    data={"story_id": "01-sample"},
                ),
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T12:01:00+00:00",
                    event="test_gen_attempt",
                    data={
                        "story_id": "01-sample",
                        "attempt": 1,
                        "test_file_path": "tests/epic/E146/test_01_sample.py",
                    },
                ),
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T12:02:00+00:00",
                    event="test_review_fail",
                    data={
                        "story_id": "01-sample",
                        "attempt": 1,
                        "reviewer_feedback": review.to_dict(),
                    },
                ),
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T12:03:00+00:00",
                    event="test_review_pass",
                    data={
                        "story_id": "01-sample",
                        "test_file_path": "tests/epic/E146/test_01_sample.py",
                    },
                ),
            ],
            "01-sample",
        )

        assert run.status == "tests_passed"
        assert run.attempt == 1
        assert run.has_passing_test is True
        assert run.latest_test_file_path == "tests/epic/E146/test_01_sample.py"
        assert len(run.review_failures) == 1
        assert run.review_failures[0].checklist[0].note == "Missing db assertion"


class TestTestReviewArtifact:
    def test_round_trips_checklist_and_suggestions(self) -> None:
        review = TestReviewArtifact.from_dict(
            {
                "verdict": "fail",
                "checklist": [
                    {"item": "No mocks", "passed": True},
                    {"item": "Data flow verified", "passed": False, "note": "Only checks status"},
                ],
                "suggestions": ["Assert on persisted state"],
            }
        )

        assert TestReviewArtifact.from_dict(review.to_dict()) == review
        assert review.passed is False


class TestRevisionRequestArtifact:
    def test_phase_a_request_requires_errors(self) -> None:
        with pytest.raises(ValueError):
            RevisionRequestArtifact.for_phase_a(PlanArtifact.from_dict(_sample_plan()), [])

    def test_phase_b_request_serializes_nested_artifacts(self) -> None:
        plan = PlanArtifact.from_dict(_sample_plan())
        epic = EpicArtifact(epic_number=146, body="## Summary\nTest epic\n")
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "gap_sufficiency": {
                        "status": "fail",
                        "findings": [{"severity": "must_fix", "missed_gap": "Broken route"}],
                    }
                },
            }
        )

        request = RevisionRequestArtifact.for_phase_b(epic, plan, feedback)

        assert request.to_dict()["epic"]["epic_number"] == 146
        assert request.to_dict()["verifier_feedback"]["status"] == "fail"

    def test_phase_b_request_composes_a_prompt_from_typed_artifacts(self) -> None:
        request = RevisionRequestArtifact.for_phase_b(
            EpicArtifact(epic_number=146, body="## Summary\nUse HTMX\n"),
            PlanArtifact.from_dict(_sample_plan()),
            VerifierFeedbackArtifact.from_dict(
                {
                    "status": "fail",
                    "dimensions": {
                        "intent_alignment": {
                            "status": "fail",
                            "findings": [
                                {
                                    "severity": "must_fix",
                                    "unaddressed_requirement": "Use HTMX inline update",
                                }
                            ],
                        }
                    },
                }
            ),
        )

        prompt = make_phase_b_revision_prompt(request)

        assert prompt.role == "planner_revision_phase_b"
        assert '"acceptance_criteria": [' in prompt.text
        assert "Use HTMX inline update" in prompt.text
        assert "architectural_context" not in prompt.text
