"""Tests for deterministic prompt compilation helpers."""

import json

from workflow.artifacts import VerifierFeedbackArtifact
from workflow.plan_generator import build_targeted_phase_b_revision_prompt
from workflow.plan_verifier import _build_verifier_prompt
from workflow.prompt_compiler import (
    PromptSection,
    compact_plan_for_review,
    make_prompt_artifact,
)


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


def _sample_repo_facts() -> dict:
    return {
        "schema_v": 1,
        "epic_number": 146,
        "current_entry_points": [
            {
                "statement": "Workflow entry point `just epic 146` is already surfaced in the repo.",
                "evidence": [{"path": "workflow/cli.py", "line": 1, "detail": "CLI entry point"}],
            }
        ],
        "likely_edit_targets": [
            {
                "statement": "`workflow/plan_verifier.py` is a likely edit target for this epic.",
                "evidence": [
                    {"path": "workflow/plan_verifier.py", "line": 1, "detail": "Likely edit"}
                ],
            }
        ],
    }


def _sample_curation() -> dict:
    return {
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
                "assumption": "Source route is broken",
                "why_it_matters": "Planner must repair it",
                "planner_action": "Plan the source-state fix explicitly",
            }
        ],
        "scope_tensions": [
            {
                "tension": "Small slices vs real behaviour",
                "tradeoff": "Avoid fake-green checkpoints",
                "planner_guidance": "Keep vertical slices end to end",
            }
        ],
        "planner_handoff": {
            "priority_order": ["Fix source route", "Then wire transition"],
            "watchouts": ["Do not invent alternate routes"],
            "recommended_story_shape": "Two focused slices",
        },
    }


class TestPromptArtifact:
    def test_prompt_artifact_exposes_sections_and_text(self) -> None:
        artifact = make_prompt_artifact(
            role="planner",
            sections=[
                PromptSection("# Task", "Do the thing"),
                PromptSection("## Output", "Return JSON"),
            ],
        )

        assert artifact.role == "planner"
        assert len(artifact.sections) == 2
        assert "# Task" in artifact.text
        assert "## Output" in artifact.text
        assert artifact.approx_tokens > 0


class TestCompactPlanForReview:
    def test_drops_verbose_story_guidance_fields(self) -> None:
        compact = compact_plan_for_review(_sample_plan())
        story = compact["stories"][0]

        assert "architectural_context" not in story
        assert "navigation_hints" not in story
        assert "implementation_notes" not in story
        assert story["acceptance_criteria"] == ["Thing works"]
        assert story["test_spec"]["test_type"] == "integration"

    def test_compact_slice_is_smaller_than_full_plan(self) -> None:
        full = json.dumps(_sample_plan(), ensure_ascii=False)
        compact = json.dumps(compact_plan_for_review(_sample_plan()), ensure_ascii=False)

        assert len(compact) < len(full)


class TestCompiledVerifierPrompt:
    def test_verifier_prompt_uses_compact_plan_slice(self) -> None:
        prompt = _build_verifier_prompt(_sample_plan(), "## Summary\nEpic\n", _sample_repo_facts())

        assert "## Input 2: Generated Plan (review slice)" in prompt
        assert "## Input 3: Repo Facts" in prompt
        assert '"acceptance_criteria": [' in prompt
        assert '"validation_checkpoints": [' in prompt
        assert "architectural_context" not in prompt
        assert "implementation_notes" not in prompt

    def test_verifier_prompt_includes_curation_when_present(self) -> None:
        prompt = _build_verifier_prompt(
            _sample_plan(),
            "## Summary\nEpic\n",
            _sample_repo_facts(),
            _sample_curation(),
        )

        assert "## Input 4: Curated Planning Handoff" in prompt
        assert "Two focused slices" in prompt


class TestCompiledRevisionPrompt:
    def test_phase_b_revision_prompt_uses_compact_plan_slice(self) -> None:
        verifier_feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "intent_alignment": {
                        "status": "fail",
                        "findings": [
                            {
                                "severity": "must_fix",
                                "epic_requirement": "Use HTMX",
                            }
                        ],
                    }
                },
            }
        )

        prompt = build_targeted_phase_b_revision_prompt(
            "## Summary\nEpic\n",
            json.dumps(_sample_repo_facts()),
            json.dumps(_sample_plan()),
            verifier_feedback,
        )

        assert "## Current Plan" in prompt
        assert "## Repo Facts" in prompt
        assert "architectural_context" not in prompt
        assert "implementation_notes" not in prompt
        assert "chosen canonical contract" in prompt
        assert "Never silently replace an epic route, field, or transport" in prompt
        assert "Use the StructuredOutput tool for the final answer." in prompt
        assert "Do NOT wrap it" in prompt
        assert "`result`, `plan`, `output`" in prompt

    def test_phase_b_revision_prompt_includes_curation_when_present(self) -> None:
        verifier_feedback = VerifierFeedbackArtifact.from_dict(
            {
                "status": "fail",
                "dimensions": {
                    "gap_detection": {
                        "status": "fail",
                        "findings": [
                            {
                                "severity": "must_fix",
                                "missing_link": "Transition never reaches target",
                            }
                        ],
                    }
                },
            }
        )

        prompt = build_targeted_phase_b_revision_prompt(
            "## Summary\nEpic\n",
            json.dumps(_sample_repo_facts()),
            json.dumps(_sample_plan()),
            verifier_feedback,
            json.dumps(_sample_curation()),
        )

        assert "## Curated Planning Handoff" in prompt
        assert "Two focused slices" in prompt
