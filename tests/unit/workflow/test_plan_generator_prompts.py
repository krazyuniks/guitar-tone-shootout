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


def _sample_repo_facts_json() -> str:
    return json.dumps(
        {
            "schema_v": 1,
            "epic_number": 146,
            "current_entry_points": [
                {
                    "statement": "Workflow entry point `just epic 146` is already surfaced in the repo.",
                    "evidence": [
                        {"path": "workflow/cli.py", "line": 1, "detail": "CLI entry point"}
                    ],
                }
            ],
            "likely_edit_targets": [
                {
                    "statement": "`workflow/prompt_suite.py` is a likely edit target for this epic.",
                    "evidence": [
                        {"path": "workflow/prompt_suite.py", "line": 1, "detail": "Likely edit"}
                    ],
                }
            ],
        }
    )


def _sample_curation_json() -> str:
    return json.dumps(
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
                    "why_it_matters": "Planner must create it if missing",
                    "planner_action": "Verify source-state coverage explicitly",
                }
            ],
            "scope_tensions": [
                {
                    "tension": "Small slices vs real journeys",
                    "tradeoff": "Avoid fake-green checkpoints",
                    "planner_guidance": "Keep slices thin but end to end",
                }
            ],
            "planner_handoff": {
                "priority_order": ["Fix source route", "Then validate transition"],
                "watchouts": ["Do not invent new routes"],
                "recommended_story_shape": "Two focused vertical slices",
            },
        }
    )


class TestPlannerPrompt:
    """Planner prompt should push the model toward verifier-grade plans."""

    def test_epic_contract_is_present_and_schema_dump_is_not(self):
        prompt = _build_planner_prompt(
            "## Summary\nTest epic\n", json.loads(_sample_repo_facts_json()), 146
        )

        assert "## Epic Contract" in prompt
        assert "## Repo Facts" in prompt
        assert "<json_schema>" not in prompt
        assert "Output only a single JSON object matching the provided schema." in prompt
        assert "Use the StructuredOutput tool for the" in prompt
        assert "Do NOT wrap it in `result`, `plan`, `output`, or any outer key." in prompt

    def test_self_check_requires_route_transition_and_transport_validation(self):
        prompt = _build_planner_prompt(
            "## Summary\nTest epic\n", json.loads(_sample_repo_facts_json()), 146
        )

        assert "entry point and source page/state" in prompt
        assert "source page/state renders, transition mechanism works" in prompt
        assert "If the UX uses HTMX/Alpine/fetch and the API contract is JSON" in prompt
        assert "redirect mechanism and the renderability of the destination page" in prompt
        assert "preserve the epic contract or plan an explicit" in prompt
        assert "record an explicit contract" in prompt
        assert "epic contract, the repo convention, the chosen canonical contract" in prompt

    def test_journey_and_checkpoint_guidance_mentions_source_to_target_coverage(self):
        prompt = _build_planner_prompt(
            "## Summary\nTest epic\n", json.loads(_sample_repo_facts_json()), 146
        )

        assert "Do NOT invent entry points or source pages without tool evidence" in prompt
        assert "the source page/state renders with the expected control" in prompt
        assert "the target page/state renders correctly afterward" in prompt
        assert "make the\n  resolution explicit in the story" in prompt

    def test_dead_dependency_summary_metadata_is_not_requested(self):
        prompt = _build_planner_prompt(
            "## Summary\nTest epic\n", json.loads(_sample_repo_facts_json()), 146
        )

        assert "depends_on_summary" not in prompt

    def test_curation_section_is_included_when_present(self):
        prompt = _build_planner_prompt(
            "## Summary\nTest epic\n",
            json.loads(_sample_repo_facts_json()),
            146,
            json.loads(_sample_curation_json()),
        )

        assert "## Curated Planning Handoff" in prompt
        assert "<curation>" in prompt


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
            _sample_repo_facts_json(),
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
            _sample_repo_facts_json(),
            _sample_plan_json(),
            verifier_feedback,
        )

        assert "## Original Epic Contract" in prompt
        assert "## Repo Facts" in prompt
        assert "The epic contract wins over the current plan." in prompt
        assert (
            "You MAY rewrite any affected story, journey, checkpoint, or validation path." in prompt
        )
        assert "you MUST make the\n   contract resolution explicit" in prompt
        assert "Never silently replace an epic route, field, or transport" in prompt
        assert "Use the StructuredOutput tool for the final answer." in prompt

    def test_revision_prompt_includes_curation_when_present(self):
        verifier_feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "gap_detection": {
                        "status": "fail",
                        "findings": [
                            {"severity": "must_fix", "missing_link": "Transition uncovered"}
                        ],
                    }
                },
            }
        )

        prompt = build_targeted_phase_b_revision_prompt(
            "## Summary\nEpic\n",
            _sample_repo_facts_json(),
            _sample_plan_json(),
            verifier_feedback,
            _sample_curation_json(),
        )

        assert "## Curated Planning Handoff" in prompt
        assert "Two focused vertical slices" in prompt
