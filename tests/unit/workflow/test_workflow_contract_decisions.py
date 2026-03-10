"""Tests for typed contract decisions in workflow plan models and artefacts."""

import json

import pytest
from pydantic import ValidationError

from workflow.artifacts import PlanArtifact
from workflow.models import Plan


def _sample_plan_dict(*, contract_decisions: list[dict] | None = None) -> dict:
    return {
        "schema_v": 1,
        "epic_number": 146,
        "goal": "Preserve the epic contract while landing the feature.",
        "observable_truths": [{"id": 1, "statement": "A user can update a comment."}],
        "user_journeys": [
            {
                "journey_id": "J1",
                "persona": "User",
                "narrative": "The user updates a comment from the comment editor.",
                "truths_covered": [1],
                "entry_point": "/comments",
                "critical_transitions": [
                    {"source": "/comments", "to": "/comments/saved", "mechanism": "submit"}
                ],
            }
        ],
        "contract_decisions": contract_decisions or [],
        "stories": [
            {
                "story_id": "01-comments",
                "name": "Comments API bridge",
                "purpose": "Implement the comment update flow.",
                "agent": {"model": "sonnet"},
                "scope": {"modify": ["workflow/plan_validator.py"]},
                "acceptance_criteria": ["The epic-facing contract remains available to users."],
                "architectural_context": ["Keep epic-facing API routes stable."],
                "navigation_hints": ["workflow/plan_validator.py"],
                "truths_addressed": [1],
            }
        ],
        "validation_checkpoints": [
            {
                "after_story": "01-comments",
                "check_type": "api+response",
                "checks": [{"criterion": "Comment update contract works"}],
            }
        ],
    }


def test_plan_schema_exposes_contract_decisions_without_repo_canonical() -> None:
    schema = Plan.model_json_schema()

    assert "contract_decisions" in schema["properties"]
    canonical = schema["$defs"]["ContractDecision"]["properties"]["canonical"]
    assert canonical["enum"] == ["epic", "bridge"]


def test_bridge_decision_requires_bridge_details() -> None:
    with pytest.raises(ValidationError):
        Plan.model_validate(
            _sample_plan_dict(
                contract_decisions=[
                    {
                        "decision_id": "CD1",
                        "epic_contract": "PATCH /api/v1/comments/<id> with body",
                        "repo_convention": (
                            "PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with content"
                        ),
                        "canonical": "bridge",
                        "affected_stories": ["01-comments"],
                    }
                ]
            )
        )


def test_repo_canonical_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        Plan.model_validate(
            _sample_plan_dict(
                contract_decisions=[
                    {
                        "decision_id": "CD1",
                        "epic_contract": "PATCH /api/v1/comments/<id> with body",
                        "repo_convention": (
                            "PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with content"
                        ),
                        "canonical": "repo",
                        "affected_stories": ["01-comments"],
                    }
                ]
            )
        )


def test_plan_artifact_renders_and_compacts_contract_decisions() -> None:
    artifact = PlanArtifact.from_dict(
        _sample_plan_dict(
            contract_decisions=[
                {
                    "decision_id": "CD1",
                    "epic_contract": "PATCH /api/v1/comments/<id> with body",
                    "repo_convention": (
                        "PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with content"
                    ),
                    "canonical": "bridge",
                    "bridge": (
                        "Keep PATCH /api/v1/comments/<id> canonical and bridge the nested repo route."
                    ),
                    "affected_stories": ["01-comments"],
                }
            ]
        )
    )

    assert (
        artifact.review_payload["contract_decisions"]
        == json.loads(artifact.json_text)["contract_decisions"]
    )
    assert "## Contract Decisions" in artifact.markdown
    assert "PATCH /api/v1/comments/<id> with body" in artifact.markdown
    assert "bridge: Keep PATCH /api/v1/comments/<id> canonical" in artifact.markdown
