"""Tests for compile-only prompt suite helpers."""

import json

from workflow.artifacts import VerifierFeedbackArtifact
from workflow.prompt_suite import (
    compile_phase_a_revision_prompt,
    compile_phase_b_revision_prompt,
    compile_planner_prompt,
    compile_prompt_suite,
    compile_verifier_prompt,
    write_prompt_suite,
)


def _write_epic_dir(tmp_path):
    epic_dir = tmp_path / "E146"
    epic_dir.mkdir()
    (epic_dir / "EPIC.md").write_text("## Summary\nTest epic\n", encoding="utf-8")
    (epic_dir / "plan.json").write_text(
        json.dumps(
            {
                "schema_v": 1,
                "epic_number": 146,
                "goal": "Test goal",
                "observable_truths": [{"id": 1, "statement": "Thing works"}],
                "user_journeys": [
                    {
                        "journey_id": "J1",
                        "persona": "User",
                        "narrative": "User does thing",
                        "truths_covered": [1],
                        "entry_point": "/start",
                        "critical_transitions": [
                            {"source": "/start", "to": "/done", "mechanism": "Click"}
                        ],
                    }
                ],
                "stories": [
                    {
                        "story_id": "01-sample",
                        "name": "Sample",
                        "purpose": "Deliver thing",
                        "agent": {"model": "sonnet"},
                        "scope": {"modify": ["apps/webapp/src/webapp/api/pages/chains.py"]},
                        "acceptance_criteria": ["Thing works"],
                        "truths_addressed": [1],
                    }
                ],
                "validation_checkpoints": [
                    {
                        "after_story": "01-sample",
                        "check_type": "http+dom",
                        "checks": [{"criterion": "Thing renders"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return epic_dir


def _verifier_feedback(dimension: str, finding: dict[str, str]) -> VerifierFeedbackArtifact:
    return VerifierFeedbackArtifact.from_dict(
        {
            "status": "fail",
            "dimensions": {
                dimension: {
                    "status": "fail",
                    "findings": [finding],
                }
            },
        }
    )


class TestPromptSuite:
    def test_compile_prompt_suite_builds_all_requested_stages(self, tmp_path) -> None:
        epic_dir = _write_epic_dir(tmp_path)
        verifier_feedback = _verifier_feedback(
            "intent_alignment",
            {"severity": "must_fix", "epic_requirement": "Use HTMX"},
        )

        suite = compile_prompt_suite(
            epic_dir,
            phase_a_errors=["story missing checkpoint"],
            verifier_feedback=verifier_feedback,
        )

        assert set(suite) == {
            "planner",
            "plan_verifier",
            "planner_revision_phase_a",
            "planner_revision_phase_b",
        }
        assert suite["planner"].approx_tokens > 0
        assert suite["plan_verifier"].approx_tokens > 0

    def test_individual_compilers_return_expected_roles(self, tmp_path) -> None:
        epic_dir = _write_epic_dir(tmp_path)
        verifier_feedback = _verifier_feedback(
            "gap_sufficiency",
            {"severity": "must_fix", "missed_gap": "Missing route"},
        )

        assert compile_planner_prompt(epic_dir).role == "planner"
        assert compile_verifier_prompt(epic_dir).role == "plan_verifier"
        assert compile_phase_a_revision_prompt(epic_dir, ["bad checkpoint"]).role == (
            "planner_revision_phase_a"
        )
        assert compile_phase_b_revision_prompt(
            epic_dir,
            verifier_feedback,
        ).role == ("planner_revision_phase_b")

    def test_write_prompt_suite_writes_phase_b_prompt_from_typed_feedback(self, tmp_path) -> None:
        epic_dir = _write_epic_dir(tmp_path)
        verifier_feedback = _verifier_feedback(
            "gap_detection",
            {"severity": "must_fix", "missing_link": "Route never reaches page"},
        )

        suite = write_prompt_suite(epic_dir, verifier_feedback=verifier_feedback)

        written_prompt = (epic_dir / "compiled-prompts" / "planner_revision_phase_b.txt").read_text(
            encoding="utf-8"
        )
        assert "planner_revision_phase_b" in suite
        assert "Route never reaches page" in written_prompt
