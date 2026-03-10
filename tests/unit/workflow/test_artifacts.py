"""Tests for typed workflow artifacts."""

import pytest

from workflow.artifacts import (
    CheckpointRunArtifact,
    CritiqueFindingArtifact,
    CritiqueRunArtifact,
    CurationArtifact,
    CurationCompleteArtifact,
    CurationDispatchedArtifact,
    CurationFailedArtifact,
    DispatchArtifact,
    DispatchResultArtifact,
    EpicArtifact,
    FailureClassificationArtifact,
    PhaseAValidationEventArtifact,
    PhaseBVerificationEventArtifact,
    PlanArtifact,
    PlanDecisionArtifact,
    PlannerCompleteArtifact,
    PlannerDispatchedArtifact,
    PlannerFailedArtifact,
    PlanVerificationResultArtifact,
    PreflightArtifact,
    PreflightEventArtifact,
    RepoFactArtifact,
    RepoFactEvidenceArtifact,
    RepoFactsArtifact,
    RevisionRequestArtifact,
    RunArtifact,
    RunEventArtifact,
    StoryFailureContextArtifact,
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


class TestRepoFactsArtifact:
    def test_json_round_trip_and_prompt_block_are_deterministic(self, tmp_path) -> None:
        artifact = RepoFactsArtifact(
            epic_number=146,
            current_entry_points=(
                RepoFactArtifact(
                    statement="Workflow entry point `just epic 146` is already surfaced in the repo.",
                    evidence=(
                        RepoFactEvidenceArtifact(
                            path="workflow/cli.py",
                            line=1,
                            detail="CLI entry point",
                        ),
                    ),
                ),
            ),
        )
        epic_dir = tmp_path / "E146"
        epic_dir.mkdir()

        path = artifact.write(epic_dir)
        round_tripped = RepoFactsArtifact.from_epic_dir(epic_dir)

        assert path.read_text(encoding="utf-8") == artifact.json_text
        assert round_tripped.to_dict() == artifact.to_dict()
        assert "<repo_facts>" in artifact.prompt_block


class TestCurationArtifact:
    def test_json_round_trip_and_prompt_block_are_deterministic(self, tmp_path) -> None:
        artifact = CurationArtifact.from_dict(
            {
                "schema_v": 1,
                "epic_number": 146,
                "candidate_journeys": [
                    {
                        "journey_id": "CJ1",
                        "title": "Journey candidate",
                        "entry_point": "/start",
                        "desired_outcome": "Reach /done",
                        "key_steps": ["Load source", "Trigger transition"],
                    }
                ],
                "story_slices": [
                    {
                        "slice_id": "SL1",
                        "title": "Slice one",
                        "objective": "Build the first vertical slice",
                        "likely_surfaces": ["workflow/plan_generator.py"],
                        "dependencies": [],
                    }
                ],
                "missing_assumptions": [
                    {
                        "assumption": "Source page exists",
                        "why_it_matters": "Planner must verify it",
                        "planner_action": "Check the source route before planning",
                    }
                ],
                "scope_tensions": [
                    {
                        "tension": "Small slices vs real behaviour",
                        "tradeoff": "Avoid fake-green checkpoints",
                        "planner_guidance": "Prefer thin vertical slices",
                    }
                ],
                "planner_handoff": {
                    "priority_order": ["Fix source route", "Then wire transition"],
                    "watchouts": ["Do not invent alternate routes"],
                    "recommended_story_shape": "Two focused slices",
                },
            }
        )
        epic_dir = tmp_path / "E146"
        epic_dir.mkdir()

        path_md, path_json = artifact.write(epic_dir)
        round_tripped = CurationArtifact.from_epic_dir(epic_dir)

        assert path_json.read_text(encoding="utf-8") == artifact.json_text
        assert path_md.read_text(encoding="utf-8") == artifact.markdown
        assert round_tripped.to_dict() == artifact.to_dict()
        assert "<curation>" in artifact.prompt_block


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

    def test_dimension_statuses_compose_deterministic_score_map(self) -> None:
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "journey_completeness": {"status": "pass"},
                    "intent_alignment": {"status": "fail"},
                },
            }
        )

        assert feedback.dimension_statuses == {
            "journey_completeness": "pass",
            "transition_coverage": "unknown",
            "intent_alignment": "fail",
            "gap_detection": "unknown",
            "validation_sufficiency": "unknown",
            "gap_sufficiency": "unknown",
        }


class TestPlanVerificationResultArtifact:
    def test_phase_b_result_wraps_typed_verifier_feedback(self) -> None:
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "summary": "Intent alignment needs revision",
                "dimensions": {
                    "intent_alignment": {
                        "status": "fail",
                        "findings": [{"severity": "must_fix", "epic_requirement": "Use HTMX"}],
                    }
                },
            }
        )

        result = PlanVerificationResultArtifact.from_verifier_feedback(feedback)

        assert result.phase == "phase_b"
        assert result.passed is False
        assert result.summary == "Intent alignment needs revision"
        assert result.phase_b_scores["intent_alignment"] == "fail"
        assert result.feedback_payload == feedback.to_dict()
        assert result.to_dict()["verifier_feedback"]["summary"] == "Intent alignment needs revision"

    def test_phase_a_result_keeps_validation_errors_typed(self) -> None:
        result = PlanVerificationResultArtifact.from_phase_a_errors(
            ["Story 01 missing checkpoint", "Story 02 missing acceptance criteria"]
        )

        assert result.phase == "phase_a"
        assert result.passed is False
        assert result.phase_a_errors == (
            "Story 01 missing checkpoint",
            "Story 02 missing acceptance criteria",
        )
        assert result.feedback_payload is None


class TestPlanDecisionArtifact:
    def test_non_rejected_decisions_round_trip_without_extra_payload(self) -> None:
        approved = PlanDecisionArtifact(epic_number=155, decision="approved")
        revised = PlanDecisionArtifact(epic_number=155, decision="revised")

        assert approved.event_payload == {"epic": 155}
        assert (
            PlanDecisionArtifact.from_event(
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T11:59:00+00:00",
                    event=approved.event_name,
                    data=approved.event_payload,
                )
            ).decision
            == "approved"
        )
        assert (
            PlanDecisionArtifact.from_event(
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T12:00:00+00:00",
                    event=revised.event_name,
                    data=revised.event_payload,
                )
            ).decision
            == "revised"
        )

    def test_rejection_from_phase_a_result_serializes_structured_details(self) -> None:
        verification = PlanVerificationResultArtifact.from_phase_a_errors(
            ["Story 01 missing checkpoint", "Story 02 missing acceptance criteria"]
        )

        rejection = PlanDecisionArtifact.for_rejection(
            epic_number=155,
            reason="Structural issues remain",
            verification_result=verification,
        )

        assert rejection.event_name == "plan_rejected"
        assert rejection.event_payload["reason"] == "Structural issues remain"
        assert rejection.event_payload["details"]["phase_a_errors"] == [
            "Story 01 missing checkpoint",
            "Story 02 missing acceptance criteria",
        ]
        assert PlanDecisionArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:00:00+00:00",
                event=rejection.event_name,
                data=rejection.event_payload,
            )
        ).detail_payload["phase_a_errors"] == [
            "Story 01 missing checkpoint",
            "Story 02 missing acceptance criteria",
        ]

    def test_rejection_from_verifier_feedback_round_trips_typed_feedback(self) -> None:
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "summary": "Intent alignment needs revision",
                "dimensions": {"intent_alignment": {"status": "fail"}},
            }
        )

        rejection = PlanDecisionArtifact.for_rejection(
            epic_number=155,
            reason="Verifier findings remain",
            verification_result=feedback,
        )
        round_tripped = PlanDecisionArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:01:00+00:00",
                event=rejection.event_name,
                data=rejection.event_payload,
            )
        )

        assert round_tripped.verifier_feedback is not None
        assert round_tripped.verifier_feedback.summary == "Intent alignment needs revision"
        assert round_tripped.detail_payload == feedback.to_dict()


class TestPhaseBVerificationEventArtifact:
    def test_from_result_round_trips_typed_feedback_and_scores(self) -> None:
        result = PlanVerificationResultArtifact.from_verifier_feedback(
            VerifierFeedbackArtifact.from_dict(
                {
                    "status": "fail",
                    "summary": "Intent alignment needs revision",
                    "dimensions": {"intent_alignment": {"status": "fail"}},
                }
            )
        )

        event = PhaseBVerificationEventArtifact.from_result(155, 1, result)
        round_tripped = PhaseBVerificationEventArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:00:00+00:00",
                event=event.event_name,
                data=event.event_payload,
            )
        )

        assert event.event_name == "phase_b_fail"
        assert event.event_payload["scores"]["intent_alignment"] == "fail"
        assert round_tripped.verifier_feedback is not None
        assert round_tripped.verifier_feedback.summary == "Intent alignment needs revision"
        assert round_tripped.summary_text == "Intent alignment needs revision"

    def test_from_result_round_trips_error_details_without_typed_feedback(self) -> None:
        result = PlanVerificationResultArtifact.from_error("Verifier dispatch failed")

        event = PhaseBVerificationEventArtifact.from_result(155, 1, result)
        round_tripped = PhaseBVerificationEventArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:01:00+00:00",
                event=event.event_name,
                data=event.event_payload,
            )
        )

        assert event.event_name == "phase_b_fail"
        assert round_tripped.verifier_feedback is None
        assert round_tripped.detail_payload["error"] == "Verifier dispatch failed"
        assert round_tripped.summary_text == "Verifier dispatch failed"


class TestPhaseAValidationEventArtifact:
    def test_pass_and_fail_events_round_trip(self) -> None:
        passed_event = PhaseAValidationEventArtifact.passed_event(155, 1)
        failed_event = PhaseAValidationEventArtifact.failed_event(
            155,
            1,
            ["Story 01 missing checkpoint", "Story 02 missing acceptance criteria"],
        )

        assert passed_event.event_name == "phase_a_pass"
        assert passed_event.event_payload == {"epic": 155, "attempt": 1}
        assert failed_event.summary_text == (
            "Story 01 missing checkpoint; Story 02 missing acceptance criteria"
        )
        assert PhaseAValidationEventArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:02:00+00:00",
                event=failed_event.event_name,
                data=failed_event.event_payload,
            )
        ).failures == ("Story 01 missing checkpoint", "Story 02 missing acceptance criteria")


class TestPlannerEventArtifacts:
    def test_curation_events_round_trip(self) -> None:
        dispatched = CurationDispatchedArtifact(
            epic_number=155,
            attempt=1,
            model="sonnet",
            prompt_hash="abc123",
            prompt_tokens=256,
        )
        completed = CurationCompleteArtifact(
            epic_number=155,
            attempt=1,
            response_path=".planning/epics/E155/curation.json",
        )
        failed = CurationFailedArtifact(
            epic_number=155,
            attempt=2,
            error="Curation output was not valid JSON",
        )

        assert (
            CurationDispatchedArtifact.from_event(
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T12:02:30+00:00",
                    event=dispatched.event_name,
                    data=dispatched.event_payload,
                )
            )
            == dispatched
        )
        assert (
            CurationCompleteArtifact.from_event(
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T12:02:31+00:00",
                    event=completed.event_name,
                    data=completed.event_payload,
                )
            )
            == completed
        )
        assert (
            CurationFailedArtifact.from_event(
                RunEventArtifact(
                    run_id="run-1",
                    ts="2026-03-07T12:02:32+00:00",
                    event=failed.event_name,
                    data=failed.event_payload,
                )
            )
            == failed
        )

    def test_planner_dispatched_round_trips_and_accepts_legacy_model_key(self) -> None:
        dispatched = PlannerDispatchedArtifact(
            epic_number=155,
            attempt=1,
            model="sonnet",
            prompt_hash="abc123",
            prompt_tokens=512,
        )

        round_tripped = PlannerDispatchedArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:03:00+00:00",
                event=dispatched.event_name,
                data=dispatched.event_payload,
            )
        )
        from_legacy_payload = PlannerDispatchedArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:03:01+00:00",
                event="planner_dispatched",
                data={"epic": 155, "attempt": 1, "planner_model": "opus"},
            )
        )

        assert round_tripped == dispatched
        assert round_tripped.summary_text == "model=sonnet, ~512 tokens"
        assert from_legacy_payload.model == "opus"

    def test_planner_complete_round_trips_response_path(self) -> None:
        completed = PlannerCompleteArtifact(
            epic_number=155,
            attempt=1,
            response_path=".planning/epics/E155/plan.json",
        )

        round_tripped = PlannerCompleteArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:04:00+00:00",
                event=completed.event_name,
                data=completed.event_payload,
            )
        )

        assert round_tripped == completed
        assert round_tripped.summary_text == ".planning/epics/E155/plan.json"

    def test_planner_failed_round_trips_error(self) -> None:
        failed = PlannerFailedArtifact(
            epic_number=155,
            attempt=2,
            error="Planner output was not valid JSON",
            response_path=".planning/epics/E155/plan.json",
        )

        round_tripped = PlannerFailedArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:05:00+00:00",
                event=failed.event_name,
                data=failed.event_payload,
            )
        )

        assert round_tripped == failed
        assert round_tripped.summary_text == "Planner output was not valid JSON"


class TestCritiqueArtifacts:
    def test_critique_run_composes_findings_count_summary_and_event_payload(self) -> None:
        critique = CritiqueRunArtifact.from_dict(
            {
                "status": "fail",
                "findings": [
                    {
                        "file": "workflow/orchestrator.py",
                        "line": 1311,
                        "issue": "Epic exit payload drops critique summary",
                        "severity": "major",
                    },
                    {
                        "file": "workflow/report.py",
                        "line": 644,
                        "issue": "Report reads findings_count directly from raw event",
                        "severity": "major",
                    },
                ],
                "summary": "Two critique issues remain",
            },
            level="story",
            critique_type="story",
            critique_model="opus",
            story_id="01-sample",
            attempt=2,
            turns=5,
            raw_response='{"status":"fail"}',
        )

        assert critique.passed is False
        assert critique.findings_count == 2
        assert critique.concise_summary == "Two critique issues remain"
        assert critique.normalized_findings[0].summary_text == (
            "workflow/orchestrator.py:1311 - Epic exit payload drops critique summary"
        )
        assert critique.event_name == "critique_fail"
        assert critique.event_payload["findings_count"] == 2
        assert critique.event_payload["raw_response"] == '{"status":"fail"}'
        assert critique.context_payload(limit=1) == {
            "critique_summary": "Two critique issues remain",
            "findings_count": 2,
            "critique_findings": [
                {
                    "file": "workflow/orchestrator.py",
                    "line": 1311,
                    "issue": "Epic exit payload drops critique summary",
                    "severity": "major",
                }
            ],
        }

    @pytest.mark.parametrize(
        ("event_name", "data", "expected_level", "expected_status", "expected_count"),
        [
            (
                "critique_pass",
                {
                    "story_id": "01-sample",
                    "attempt": 1,
                    "critique_type": "story",
                    "critique_model": "opus",
                    "turns": 3,
                    "findings_count": 0,
                    "summary": "Looks good",
                    "raw_response": '{"status":"pass"}',
                },
                "story",
                "pass",
                0,
            ),
            (
                "critique_fail",
                {
                    "story_id": "01-sample",
                    "attempt": 1,
                    "critique_type": "story",
                    "critique_model": "opus",
                    "turns": 3,
                    "findings_count": 1,
                    "findings": [
                        {
                            "file": "workflow/story_executor.py",
                            "line": 1197,
                            "issue": "Retry context drops critique details",
                            "severity": "major",
                        }
                    ],
                    "summary": "Needs one fix",
                },
                "story",
                "fail",
                1,
            ),
            (
                "critique_failed",
                {
                    "story_id": "01-sample",
                    "attempt": 1,
                    "critique_type": "story",
                    "critique_model": "opus",
                    "error": "Dispatch failed",
                    "findings_count": 0,
                },
                "story",
                "fail",
                0,
            ),
            (
                "epic_critique_pass",
                {
                    "critique_type": "epic",
                    "critique_model": "opus",
                    "turns": 4,
                    "findings_count": 0,
                    "summary": "Epic passes critique",
                },
                "epic",
                "pass",
                0,
            ),
            (
                "epic_critique_fail",
                {
                    "critique_type": "epic",
                    "critique_model": "opus",
                    "turns": 4,
                    "findings_count": 1,
                    "findings": [
                        {
                            "file": "workflow/report.py",
                            "line": 644,
                            "issue": "Epic critique report path is untyped",
                            "severity": "major",
                        }
                    ],
                    "summary": "Epic critique failed",
                },
                "epic",
                "fail",
                1,
            ),
        ],
    )
    def test_critique_run_reconstructs_supported_event_variants(
        self,
        event_name: str,
        data: dict,
        expected_level: str,
        expected_status: str,
        expected_count: int,
    ) -> None:
        critique = CritiqueRunArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:00:00+00:00",
                event=event_name,
                data=data,
            )
        )

        assert critique.level == expected_level
        assert critique.status == expected_status
        assert critique.findings_count == expected_count
        assert critique.event_name == event_name


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
                    ts="2026-03-07T11:59:00+00:00",
                    event="validation_fail",
                    data={
                        "story_id": "01-sample",
                        "check_type": "http+dom",
                        "results": [
                            {
                                "criterion": "Page renders",
                                "status": "fail",
                                "evidence": {"command": "just check", "exit_code": 1},
                            }
                        ],
                        "failure_reason": "Baseline quality gate failed",
                        "failure_category": "implementation",
                    },
                ),
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
        assert run.last_checkpoint is not None
        assert run.last_checkpoint.check_type == "http+dom"
        assert run.last_checkpoint.failure_reason == "Baseline quality gate failed"


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


class TestExecutionArtifacts:
    def test_failure_classification_round_trips_and_formats_terminal_reason(self) -> None:
        classification = FailureClassificationArtifact(
            category="upstream",
            evidence="Earlier story owns apps/webapp/main.py",
            pattern="File owned by earlier story: 01-setup",
        )

        assert FailureClassificationArtifact.from_dict(classification.to_dict()) == classification
        assert classification.terminal_reason.startswith("Failure (upstream):")

    def test_preflight_artifact_round_trips_and_exposes_joined_views(self) -> None:
        preflight = PreflightArtifact(
            passed=False,
            issues=("Missing file a.py", "Missing file b.py"),
            is_minor=False,
        )

        assert PreflightArtifact.from_dict(preflight.to_dict()) == preflight
        assert preflight.description == "Missing file a.py; Missing file b.py"
        assert preflight.combined_issues == "Missing file a.py\nMissing file b.py"

    def test_preflight_event_artifact_round_trips_pass_and_fail_event_payloads(self) -> None:
        minor_preflight = PreflightArtifact(
            passed=False,
            issues=("File to modify does not exist: apps/ui.py",),
            is_minor=True,
        )
        fail_preflight = PreflightArtifact(
            passed=False,
            issues=("Expected file from earlier story missing: apps/setup.py",),
            is_minor=False,
        )

        minor_event = PreflightEventArtifact.from_preflight("02-ui", 1, minor_preflight)
        fail_event = PreflightEventArtifact.from_preflight("02-ui", 1, fail_preflight)

        assert minor_event.event_name == "preflight_pass"
        assert minor_event.event_payload["note"].startswith("Minor issues (agent self-fix):")
        assert minor_event.event_payload["checks"] == ["File to modify does not exist: apps/ui.py"]
        assert PreflightEventArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:00:00+00:00",
                event=minor_event.event_name,
                data=minor_event.event_payload,
            )
        ).checks == ("File to modify does not exist: apps/ui.py",)

        assert fail_event.event_name == "preflight_fail"
        assert fail_event.event_payload["failure_category"] == "scope"
        assert fail_event.event_payload["description"] == (
            "Expected file from earlier story missing: apps/setup.py"
        )

    def test_story_failure_context_round_trips_and_builds_prompt_block(self) -> None:
        context = StoryFailureContextArtifact(
            story_id="01-sample",
            attempt=2,
            last_error="AssertionError: boom",
            files_affected=("apps/webapp/main.py",),
            jsonl_excerpt='{"event":"validation_fail"}',
        )

        assert StoryFailureContextArtifact.from_dict(context.to_dict()) == context
        assert "Failure Feedback (Attempt 2)" in context.prompt_block
        assert context.event_context["files_affected"] == ["apps/webapp/main.py"]

    def test_critique_finding_round_trips_and_formats_views(self) -> None:
        finding = CritiqueFindingArtifact.from_dict(
            {
                "file": "workflow/report.py",
                "line": 644,
                "issue": "Critique render path is untyped",
                "severity": "major",
            }
        )

        assert finding.to_dict()["file"] == "workflow/report.py"
        assert finding.summary_text == "workflow/report.py:644 - Critique render path is untyped"
        assert finding.markdown_text == (
            "- **[major]** `workflow/report.py:644` — Critique render path is untyped"
        )

    def test_checkpoint_run_artifact_round_trips_and_reconstructs_from_event(self) -> None:
        checkpoint = CheckpointRunArtifact.from_dict(
            {
                "story_id": "01-sample",
                "check_type": "http+dom",
                "passed": False,
                "results": [
                    {
                        "criterion": "Page renders",
                        "status": "fail",
                        "evidence": {"command": "just check", "exit_code": 1},
                    }
                ],
                "failure_reason": "Baseline quality gate failed",
                "failure_category": "implementation",
                "raw_output": "Traceback...",
            }
        )

        round_tripped = CheckpointRunArtifact.from_dict(checkpoint.to_dict())
        from_event = CheckpointRunArtifact.from_event(
            RunEventArtifact(
                run_id="run-1",
                ts="2026-03-07T12:00:00+00:00",
                event=round_tripped.event_name,
                data=round_tripped.event_payload,
            )
        )

        assert round_tripped.story_id == "01-sample"
        assert round_tripped.results[0].criterion == "Page renders"
        assert from_event.failure_category == "implementation"
        assert from_event.raw_output == ""


class TestRevisionRequestArtifact:
    def test_phase_a_request_requires_errors(self) -> None:
        with pytest.raises(ValueError):
            RevisionRequestArtifact.for_phase_a(PlanArtifact.from_dict(_sample_plan()), [])

    def test_phase_b_request_serializes_nested_artifacts(self) -> None:
        plan = PlanArtifact.from_dict(_sample_plan())
        epic = EpicArtifact(epic_number=146, body="## Summary\nTest epic\n")
        repo_facts = RepoFactsArtifact(
            epic_number=146,
            likely_edit_targets=(
                RepoFactArtifact(
                    statement="`workflow/plan_generator.py` is a likely edit target for this epic.",
                    evidence=(
                        RepoFactEvidenceArtifact(
                            path="workflow/plan_generator.py",
                            line=1,
                            detail="Likely edit",
                        ),
                    ),
                ),
            ),
        )
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
        curation = CurationArtifact.from_dict(
            {
                "schema_v": 1,
                "epic_number": 146,
                "candidate_journeys": [],
                "story_slices": [],
                "missing_assumptions": [],
                "scope_tensions": [],
                "planner_handoff": {
                    "priority_order": ["Fix source route"],
                    "watchouts": ["Do not invent alternate routes"],
                    "recommended_story_shape": "One focused slice",
                },
            }
        )

        request = RevisionRequestArtifact.for_phase_b(epic, repo_facts, plan, feedback, curation)

        assert request.to_dict()["epic"]["epic_number"] == 146
        assert request.to_dict()["repo_facts"]["epic_number"] == 146
        assert request.to_dict()["curation"]["epic_number"] == 146
        assert request.to_dict()["verifier_feedback"]["status"] == "fail"

    def test_phase_b_request_composes_a_prompt_from_typed_artifacts(self) -> None:
        request = RevisionRequestArtifact.for_phase_b(
            EpicArtifact(epic_number=146, body="## Summary\nUse HTMX\n"),
            RepoFactsArtifact(
                epic_number=146,
                current_entry_points=(
                    RepoFactArtifact(
                        statement="Workflow entry point `just epic 146` is already surfaced in the repo.",
                        evidence=(
                            RepoFactEvidenceArtifact(
                                path="workflow/cli.py",
                                line=1,
                                detail="CLI entry point",
                            ),
                        ),
                    ),
                ),
            ),
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
            CurationArtifact.from_dict(
                {
                    "schema_v": 1,
                    "epic_number": 146,
                    "candidate_journeys": [],
                    "story_slices": [],
                    "missing_assumptions": [],
                    "scope_tensions": [],
                    "planner_handoff": {
                        "priority_order": ["Keep the source route"],
                        "watchouts": ["Do not invent alternate routes"],
                        "recommended_story_shape": "Two focused slices",
                    },
                }
            ),
        )

        prompt = make_phase_b_revision_prompt(request)

        assert prompt.role == "planner_revision_phase_b"
        assert '"acceptance_criteria": [' in prompt.text
        assert "## Repo Facts" in prompt.text
        assert "## Curated Planning Handoff" in prompt.text
        assert "Use HTMX inline update" in prompt.text
        assert "architectural_context" not in prompt.text
