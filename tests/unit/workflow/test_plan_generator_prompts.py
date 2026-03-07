"""Tests for plan-generator prompt construction."""

import json

from workflow.artifacts import VerifierFeedbackArtifact
from workflow.plan_generator import (
    _build_planner_prompt,
    build_targeted_phase_b_revision_prompt,
)


def _sample_plan_json() -> str:
    return json.dumps(
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
    )


class TestPlannerPrompt:
    """Planner prompt should push the model toward verifier-grade plans."""

    def test_epic_contract_is_present_and_schema_dump_is_not(self):
        prompt = _build_planner_prompt("## Summary\nTest epic\n", 146)

        assert "## Epic Contract" in prompt
        assert "<json_schema>" not in prompt
        assert "Output only a single JSON object matching the provided schema." in prompt
        assert "Use the StructuredOutput tool for the" in prompt

    def test_self_check_requires_route_transition_and_transport_validation(self):
        prompt = _build_planner_prompt("## Summary\nTest epic\n", 146)

        assert "entry point and source page/state" in prompt
        assert "source page/state renders, transition mechanism works" in prompt
        assert "If the UX uses HTMX/Alpine/fetch and the API contract is JSON" in prompt
        assert "redirect mechanism and the renderability of the destination page" in prompt

    def test_journey_and_checkpoint_guidance_mentions_source_to_target_coverage(self):
        prompt = _build_planner_prompt("## Summary\nTest epic\n", 146)

        assert "Do NOT invent entry points or source pages without tool evidence" in prompt
        assert "the source page/state renders with the expected control" in prompt
        assert "the target page/state renders correctly afterward" in prompt

    def test_dead_dependency_summary_metadata_is_not_requested(self):
        prompt = _build_planner_prompt("## Summary\nTest epic\n", 146)

        assert "depends_on_summary" not in prompt


class TestPhaseBRevisionPrompt:
    """Verifier feedback prompt should include all must-fix dimensions."""

    def test_gap_sufficiency_findings_are_included(self):
        verifier_feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "gap_sufficiency": {
                        "status": "fail",
                        "findings": [
                            {
                                "severity": "must_fix",
                                "missed_gap": "Planner missed the broken source route",
                            }
                        ],
                    }
                },
            }
        )

        prompt = build_targeted_phase_b_revision_prompt(
            "## Summary\nEpic\n",
            _sample_plan_json(),
            verifier_feedback,
        )

        assert "### Missed Gaps" in prompt
        assert "Planner missed the broken source route" in prompt

    def test_revision_prompt_reanchors_to_epic_and_allows_rewrites(self):
        verifier_feedback = VerifierFeedbackArtifact.from_dict(
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
        )

        prompt = build_targeted_phase_b_revision_prompt(
            "## Summary\nUse HTMX\n",
            _sample_plan_json(),
            verifier_feedback,
        )

        assert "## Original Epic Contract" in prompt
        assert "The epic contract wins over the current plan." in prompt
        assert (
            "You MAY rewrite any affected story, journey, checkpoint, or validation path." in prompt
        )
        assert "Use the StructuredOutput tool for the final answer." in prompt
