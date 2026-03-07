import json
from pathlib import Path

from workflow.artifacts import (
    PlanVerificationResultArtifact,
    VerifierFeedbackArtifact,
)
from workflow.plan_verifier import present_decision_gate


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
