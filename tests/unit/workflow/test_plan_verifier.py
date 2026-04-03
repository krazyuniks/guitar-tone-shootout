import json
from pathlib import Path

from workflow.artifacts import (
    PlanVerificationResultArtifact,
    VerifierFeedbackArtifact,
)
from workflow.plan_validator import ValidationResult
from workflow.plan_verifier import (
    _extract_dimension_failures,
    _get_dimensions,
    _has_extractable_findings,
    _is_verifier_pass,
    present_decision_gate,
    verify_with_revision_cycle,
)


def _write_plan_files(tmp_path: Path) -> Path:
    epic_dir = tmp_path / "E155"
    epic_dir.mkdir()
    plan_md_path = epic_dir / "PLAN.md"
    plan_md_path.write_text("# Plan: Epic #155\n", encoding="utf-8")
    (epic_dir / "plan.json").write_text(
        json.dumps(
            {
                "goal": "Finish the planner typing migration",
                "stories": [
                    {
                        "story_id": "01-planner-events",
                        "name": "Planner events",
                        "purpose": "Type planner events end to end",
                        "scope": {"create": [], "modify": ["workflow/artifacts.py"]},
                    }
                ],
                "validation_checkpoints": [
                    {
                        "after_story": "01-planner-events",
                        "checks": [{"criterion": "just check-lint"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return plan_md_path


class TestPresentDecisionGate:
    def test_accepts_typed_verifier_feedback(self, tmp_path, monkeypatch, capsys) -> None:
        plan_md_path = _write_plan_files(tmp_path)
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "summary": "Intent alignment needs revision",
                "dimensions": {
                    "intent_alignment": {
                        "status": "fail",
                        "findings": [
                            {
                                "severity": "must_fix",
                                "unaddressed_requirement": "Use typed planner events",
                            }
                        ],
                    }
                },
            }
        )

        monkeypatch.setattr("builtins.input", lambda _: "a")

        result = present_decision_gate(plan_md_path, feedback)
        output = capsys.readouterr().out

        assert result.approved is True
        assert "Verifier status: fail" in output
        assert "[FAIL] intent_alignment" in output
        assert "Use typed planner events" in output

    def test_accepts_typed_phase_a_result(self, tmp_path, monkeypatch, capsys) -> None:
        plan_md_path = _write_plan_files(tmp_path)
        verification_result = PlanVerificationResultArtifact.from_phase_a_errors(
            ["Story 01 missing checkpoint", "Story 01 missing acceptance criteria"]
        )
        responses = iter(["x", "Structural issues remain"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))

        result = present_decision_gate(plan_md_path, verification_result)
        output = capsys.readouterr().out

        assert result.rejected is True
        assert result.reason == "Structural issues remain"
        assert "Phase A errors:" in output
        assert "Story 01 missing checkpoint" in output


class TestVerifierFeedbackHelpers:
    def test_helpers_use_typed_feedback_dimensions(self) -> None:
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "intent_alignment": {
                        "status": "fail",
                        "findings": [
                            {
                                "severity": "must_fix",
                                "unaddressed_requirement": "Type the prompt helpers",
                            }
                        ],
                    },
                    "gap_detection": {
                        "status": "pass",
                        "findings": [],
                    },
                },
            }
        )

        assert _is_verifier_pass(feedback) is False
        assert _get_dimensions(feedback)["intent_alignment"]["status"] == "fail"
        assert _extract_dimension_failures(feedback) == ["intent_alignment"]
        assert _has_extractable_findings(feedback) is True

    def test_helpers_report_no_extractable_findings_without_must_fix_items(self) -> None:
        feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "validation_sufficiency": {
                        "status": "fail",
                        "findings": [{"severity": "note", "weak_check": "just grep"}],
                    }
                },
            }
        )

        assert _is_verifier_pass(feedback) is False
        assert _extract_dimension_failures(feedback) == ["validation_sufficiency"]
        assert _has_extractable_findings(feedback) is False


class TestVerifyWithRevisionCycle:
    def test_phase_b_failure_then_phase_a_revalidation_success_returns_success(
        self, tmp_path, monkeypatch
    ) -> None:
        plan_md_path = _write_plan_files(tmp_path)
        epic_dir = plan_md_path.parent
        verifier_calls: list[Path] = []

        monkeypatch.setattr(
            "workflow.plan_verifier.validate_plan",
            lambda _epic_dir: ValidationResult(valid=True),
        )

        def fake_regenerate(_epic_dir: Path, _feedback, config=None) -> None:
            _ = config

        monkeypatch.setattr(
            "workflow.plan_verifier._regenerate_plan_with_verifier_feedback",
            fake_regenerate,
        )

        def fake_verify(epic_dir_arg: Path, config=None) -> VerifierFeedbackArtifact:
            verifier_calls.append(epic_dir_arg)
            return VerifierFeedbackArtifact.from_dict(
                {
                    "status": "fail",
                    "summary": "Intent alignment needs revision",
                    "dimensions": {
                        "intent_alignment": {
                            "status": "fail",
                            "findings": [
                                {
                                    "severity": "must_fix",
                                    "epic_requirement": "Keep the story sequence intact",
                                }
                            ],
                        }
                    },
                }
            )

        monkeypatch.setattr("workflow.plan_verifier._verify_plan_artifact", fake_verify)

        result, success = verify_with_revision_cycle(epic_dir)

        assert success is True
        assert result.passed is True
        assert result.revised_after_critique is True
        assert verifier_calls == [epic_dir]
