import json
from pathlib import Path

from workflow.artifacts import (
    PhaseAValidationEventArtifact,
    PhaseBVerificationEventArtifact,
    PlanDecisionArtifact,
    PlannerCompleteArtifact,
    PlannerDispatchedArtifact,
    PlannerFailedArtifact,
    PlanVerificationResultArtifact,
    PreflightArtifact,
    PreflightEventArtifact,
    RunEventArtifact,
    StoryFailureContextArtifact,
    StoryRunArtifact,
    VerifierFeedbackArtifact,
)
from workflow.jsonl_logger import EventLogger
from workflow.orchestrator import (
    build_failure_comment,
    build_story_comment,
    generate_summary,
    show_status,
)
from workflow.report import (
    _build_story_runs,
    _render_event_details,
    _render_metadata_header,
    _render_story_nav,
)


def _event(ts: str, event: str, **data: object) -> dict:
    return RunEventArtifact(run_id="run-1", ts=ts, event=event, data=data).to_dict()


def _plan() -> dict:
    return {
        "stories": [
            {
                "story_id": "01-setup",
                "name": "Setup",
                "agent": {"model": "sonnet"},
                "scope": {"create": ["apps/setup.py"], "modify": ["apps/shared.py"]},
            },
            {
                "story_id": "02-ui",
                "name": "UI",
                "agent": {"model": "sonnet"},
                "scope": {"create": [], "modify": ["apps/ui.py"]},
            },
        ]
    }


class TestTypedStoryConsumers:
    def test_story_run_artifact_composes_failure_reason_category_and_context(self) -> None:
        failure_context = StoryFailureContextArtifact(
            story_id="02-ui",
            attempt=2,
            last_error="AssertionError: boom",
            files_affected=("apps/ui.py",),
            jsonl_excerpt='{"event":"validation_fail"}',
        )
        events = [
            _event(
                "2026-03-07T12:00:00+00:00",
                "validation_fail",
                story_id="02-ui",
                attempt=2,
                check_type="http+dom",
                results=[],
                failure_reason="Golden path gate failed (just test-golden-path)",
                failure_category="implementation",
            ),
            _event(
                "2026-03-07T12:01:00+00:00",
                "exit_to_human",
                story_id="02-ui",
                attempt=2,
                reason="Golden path gate failed (just test-golden-path)",
                failure_category="implementation",
                context=failure_context.to_dict(),
            ),
        ]

        story_run = StoryRunArtifact.from_events(events, "02-ui")

        assert story_run.failure_reason == "Golden path gate failed (just test-golden-path)"
        assert story_run.failure_category == "implementation"
        assert story_run.failure_context == failure_context

    def test_story_run_artifact_composes_latest_checkpoint_summary_lines(self) -> None:
        events = [
            _event(
                "2026-03-07T12:00:00+00:00",
                "validation_pass",
                story_id="01-setup",
                attempt=1,
                check_type="http+dom",
                results=[
                    {"criterion": "Page renders", "status": "pass", "evidence": {"exit_code": 0}},
                    {
                        "criterion": "Golden path passes",
                        "status": "pass",
                        "evidence": {"exit_code": 0},
                    },
                ],
            ),
            _event(
                "2026-03-07T12:01:00+00:00",
                "story_complete",
                story_id="01-setup",
                attempt=1,
                commit="abc12345",
            ),
        ]

        story_run = StoryRunArtifact.from_events(events, "01-setup")

        assert story_run.checkpoint_summary_lines == (
            "- [PASS] Page renders",
            "- [PASS] Golden path passes",
        )

    def test_orchestrator_comments_use_typed_story_run_views(self) -> None:
        failure_context = StoryFailureContextArtifact(
            story_id="02-ui",
            attempt=2,
            last_error="AssertionError: boom",
            files_affected=("apps/ui.py",),
            jsonl_excerpt='{"event":"validation_fail"}',
        )
        success_events = [
            _event(
                "2026-03-07T12:00:00+00:00",
                "agent_complete",
                story_id="01-setup",
                attempt=1,
                commit="abc12345",
                turns=4,
            ),
            _event(
                "2026-03-07T12:01:00+00:00",
                "validation_pass",
                story_id="01-setup",
                attempt=1,
                check_type="http+dom",
                results=[
                    {"criterion": "Page renders", "status": "pass", "evidence": {"exit_code": 0}}
                ],
            ),
        ]
        failure_events = [
            _event(
                "2026-03-07T12:00:00+00:00",
                "validation_fail",
                story_id="02-ui",
                attempt=2,
                check_type="http+dom",
                results=[],
                failure_reason="Golden path gate failed (just test-golden-path)",
                failure_category="implementation",
            ),
            _event(
                "2026-03-07T12:01:00+00:00",
                "exit_to_human",
                story_id="02-ui",
                attempt=2,
                reason="Golden path gate failed (just test-golden-path)",
                failure_category="implementation",
                context=failure_context.to_dict(),
            ),
        ]

        story_comment = build_story_comment(_plan()["stories"][0], success_events)
        failure_comment = build_failure_comment(_plan()["stories"][1], failure_events)

        assert "- [PASS] Page renders" in story_comment
        assert "**Failure category:** implementation" in failure_comment
        assert "**Reason:** Golden path gate failed (just test-golden-path)" in failure_comment

    def test_generate_summary_uses_typed_checkpoint_and_failure_composition(self, tmp_path) -> None:
        plan = _plan()
        summary_events = [
            _event(
                "2026-03-07T12:00:00+00:00",
                "validation_pass",
                story_id="01-setup",
                attempt=1,
                check_type="http+dom",
                results=[
                    {"criterion": "Page renders", "status": "pass", "evidence": {"exit_code": 0}}
                ],
            ),
            _event(
                "2026-03-07T12:01:00+00:00",
                "story_complete",
                story_id="01-setup",
                attempt=1,
                commit="abc12345",
            ),
            _event(
                "2026-03-07T12:02:00+00:00",
                "validation_fail",
                story_id="02-ui",
                attempt=2,
                check_type="http+dom",
                results=[],
                failure_reason="Golden path gate failed (just test-golden-path)",
                failure_category="implementation",
            ),
            _event(
                "2026-03-07T12:03:00+00:00",
                "exit_to_human",
                story_id="02-ui",
                attempt=2,
                reason="Golden path gate failed (just test-golden-path)",
                failure_category="implementation",
                context=StoryFailureContextArtifact(
                    story_id="02-ui",
                    attempt=2,
                    last_error="AssertionError: boom",
                    files_affected=("apps/ui.py",),
                    jsonl_excerpt='{"event":"validation_fail"}',
                ).to_dict(),
            ),
        ]

        summary_path = generate_summary(tmp_path, plan, summary_events)
        summary_text = summary_path.read_text(encoding="utf-8")

        assert "| 01-setup | http+dom | PASS | 1 |" in summary_text
        assert "| 02-ui | http+dom | FAIL | 0 |" in summary_text
        assert (
            "- **02-ui** [implementation]: Golden path gate failed (just test-golden-path)"
            in summary_text
        )


class TestTypedReportConsumers:
    def test_render_event_details_uses_typed_planner_reconstruction(self, tmp_path) -> None:
        planner_dispatch = PlannerDispatchedArtifact(
            epic_number=155,
            attempt=1,
            model="sonnet",
            prompt_tokens=512,
        )
        planner_complete = PlannerCompleteArtifact(
            epic_number=155,
            attempt=1,
            response_path=".planning/epics/E155/plan.json",
        )
        planner_failed = PlannerFailedArtifact(
            epic_number=155,
            attempt=2,
            error="Planner output was not valid JSON",
        )

        dispatch_html = _render_event_details(
            _event(
                "2026-03-07T12:00:00+00:00",
                planner_dispatch.event_name,
                **planner_dispatch.event_payload,
            ),
            tmp_path,
        )
        complete_html = _render_event_details(
            _event(
                "2026-03-07T12:01:00+00:00",
                planner_complete.event_name,
                **planner_complete.event_payload,
            ),
            tmp_path,
        )
        failed_html = _render_event_details(
            _event(
                "2026-03-07T12:02:00+00:00",
                planner_failed.event_name,
                **planner_failed.event_payload,
            ),
            tmp_path,
        )

        assert "model=sonnet, ~512 tokens" in dispatch_html
        assert ".planning/epics/E155/plan.json" in complete_html
        assert "Planner output was not valid JSON" in failed_html

    def test_render_event_details_uses_typed_validation_and_failure_context(self, tmp_path) -> None:
        failure_context = StoryFailureContextArtifact(
            story_id="02-ui",
            attempt=2,
            last_error="AssertionError: boom",
            files_affected=("apps/ui.py",),
            jsonl_excerpt='{"event":"validation_fail"}',
        )
        validation_event = _event(
            "2026-03-07T12:00:00+00:00",
            "validation_fail",
            story_id="02-ui",
            attempt=2,
            check_type="http+dom",
            results=[],
            failure_reason="Golden path gate failed (just test-golden-path)",
            failure_category="implementation",
        )
        exit_event = _event(
            "2026-03-07T12:01:00+00:00",
            "exit_to_human",
            story_id="02-ui",
            attempt=2,
            reason="Golden path gate failed (just test-golden-path)",
            failure_category="implementation",
            context=failure_context.to_dict(),
        )
        events = [validation_event, exit_event]

        validation_html = _render_event_details(
            validation_event,
            tmp_path,
            story_run=StoryRunArtifact.from_events(events[:1], "02-ui"),
        )
        exit_html = _render_event_details(
            exit_event,
            tmp_path,
            story_run=StoryRunArtifact.from_events(events, "02-ui"),
        )

        assert "Golden path gate failed (just test-golden-path)" in validation_html
        assert "AssertionError: boom" in exit_html
        assert "apps/ui.py" in exit_html

    def test_render_event_details_uses_typed_critique_reconstruction(self, tmp_path) -> None:
        critique_event = _event(
            "2026-03-07T12:02:00+00:00",
            "critique_fail",
            story_id="02-ui",
            attempt=2,
            critique_type="story",
            critique_model="opus",
            turns=4,
            findings_count=1,
            findings=[
                {
                    "file": "workflow/report.py",
                    "line": 644,
                    "issue": "Report renders critique details from raw dict access",
                    "severity": "major",
                }
            ],
            summary="One critique issue remains",
            raw_response='{"status":"fail"}',
        )

        critique_html = _render_event_details(critique_event, tmp_path)

        assert "model=opus, 1 findings" in critique_html
        assert "One critique issue remains" in critique_html
        assert "workflow/report.py:644 - Report renders critique details from raw dict access" in (
            critique_html
        )
        assert "Show raw response" in critique_html

    def test_render_event_details_uses_typed_phase_b_feedback(self, tmp_path) -> None:
        phase_b_event = PhaseBVerificationEventArtifact.from_event(
            _event(
                "2026-03-07T12:03:00+00:00",
                "phase_b_fail",
                epic=155,
                attempt=1,
                scores={"intent_alignment": "fail"},
                feedback={
                    "status": "fail",
                    "summary": "Intent alignment needs revision",
                    "dimensions": {
                        "intent_alignment": {
                            "status": "fail",
                            "findings": [{"severity": "must_fix", "epic_requirement": "Use HTMX"}],
                        }
                    },
                },
            )
        )

        phase_b_html = _render_event_details(
            _event(
                "2026-03-07T12:03:00+00:00", phase_b_event.event_name, **phase_b_event.event_payload
            ),
            tmp_path,
        )

        assert "Show critique feedback" in phase_b_html
        assert "Intent alignment needs revision" in phase_b_html

    def test_render_event_details_uses_typed_phase_a_reconstruction(self, tmp_path) -> None:
        phase_a_event = PhaseAValidationEventArtifact.failed_event(
            155,
            1,
            ["Story 01 missing checkpoint", "Story 02 missing acceptance criteria"],
        )

        phase_a_html = _render_event_details(
            _event(
                "2026-03-07T12:02:00+00:00", phase_a_event.event_name, **phase_a_event.event_payload
            ),
            tmp_path,
        )

        assert "Story 01 missing checkpoint" in phase_a_html
        assert "Show failures" in phase_a_html

    def test_render_event_details_uses_typed_plan_rejection_reconstruction(self, tmp_path) -> None:
        rejection = PlanDecisionArtifact.for_rejection(
            epic_number=155,
            reason="Structural issues remain",
            verification_result=VerifierFeedbackArtifact.from_dict(
                {
                    "status": "fail",
                    "summary": "Intent alignment needs revision",
                    "dimensions": {"intent_alignment": {"status": "fail"}},
                }
            ),
        )
        rejection_event = _event(
            "2026-03-07T12:04:00+00:00",
            rejection.event_name,
            **rejection.event_payload,
        )

        rejection_html = _render_event_details(rejection_event, tmp_path)

        assert "Structural issues remain" in rejection_html
        assert "Show rejection details" in rejection_html
        assert "Intent alignment needs revision" in rejection_html

    def test_render_event_details_uses_typed_preflight_reconstruction(self, tmp_path) -> None:
        preflight_event = PreflightEventArtifact.from_preflight(
            "02-ui",
            1,
            PreflightArtifact(
                passed=False,
                issues=("Expected file from earlier story missing: apps/setup.py",),
                is_minor=False,
            ),
        )
        rendered_event = _event(
            "2026-03-07T12:05:00+00:00",
            preflight_event.event_name,
            **preflight_event.event_payload,
        )

        preflight_html = _render_event_details(rendered_event, tmp_path)

        assert "Expected file from earlier story missing: apps/setup.py" in preflight_html
        assert "Show checks" in preflight_html

    def test_report_header_and_nav_use_final_typed_story_status(self) -> None:
        plan = {"stories": [{"story_id": "01-setup", "name": "Setup"}]}
        events = [
            _event(
                "2026-03-07T12:00:00+00:00",
                "story_failed",
                story_id="01-setup",
                attempt=1,
                reason="Initial failure",
            ),
            _event(
                "2026-03-07T12:01:00+00:00",
                "story_complete",
                story_id="01-setup",
                attempt=2,
                commit="abc12345",
            ),
        ]

        story_runs = _build_story_runs(events, plan)
        header_html = _render_metadata_header(Path("E155"), events, plan, story_runs=story_runs)
        nav_html = _render_story_nav(plan, events, story_runs=story_runs)

        assert "1/1 complete, 0 failed" in header_html
        assert "DONE" in nav_html
        assert "FAIL" not in nav_html


class TestPlanningStatusConsumers:
    def test_show_status_uses_typed_planner_and_gate_reconstruction(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ) -> None:
        epic_dir = tmp_path / "E155"
        epic_dir.mkdir()
        (epic_dir / "plan.json").write_text(
            json.dumps(
                {
                    "stories": [
                        {
                            "story_id": "01-setup",
                            "name": "Setup",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        log_path = epic_dir / "epic.jsonl"
        logger = EventLogger(log_path, "run-1")

        planner_dispatch = PlannerDispatchedArtifact(
            epic_number=155,
            attempt=1,
            model="sonnet",
        )
        planner_complete = PlannerCompleteArtifact(
            epic_number=155,
            attempt=1,
            response_path=".planning/epics/E155/plan.json",
        )
        phase_a_event = PhaseAValidationEventArtifact.passed_event(155, 1)
        phase_b_event = PhaseBVerificationEventArtifact.from_result(
            155,
            1,
            PlanVerificationResultArtifact.from_verifier_feedback(
                VerifierFeedbackArtifact.from_dict(
                    {
                        "status": "pass",
                        "summary": "Plan verified",
                        "dimensions": {"journey_completeness": {"status": "pass"}},
                    }
                )
            ),
        )
        approved = PlanDecisionArtifact(epic_number=155, decision="approved")

        for event_name, payload in (
            (planner_dispatch.event_name, planner_dispatch.event_payload),
            (planner_complete.event_name, planner_complete.event_payload),
            (phase_a_event.event_name, phase_a_event.event_payload),
            (phase_b_event.event_name, phase_b_event.event_payload),
            (approved.event_name, approved.event_payload),
        ):
            logger.log_event(event_name, **payload)

        monkeypatch.setattr("workflow.orchestrator.PLANNING_DIR", tmp_path)

        show_status(155)
        output = capsys.readouterr().out

        assert "Planner attempts: 1" in output
        assert "Planner: COMPLETE" in output
        assert "Phase A: PASS" in output
        assert "Phase B: PASS" in output
        assert "Decision gate: APPROVED" in output
