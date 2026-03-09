"""Tests for deterministic Phase A contract-fidelity validation."""

import json

from workflow.plan_validator import _extract_route_like_surfaces, validate_plan


def _write_epic_dir(tmp_path, *, plan_payload: dict, epic_body: str):
    epic_dir = tmp_path / "E146"
    epic_dir.mkdir()
    (epic_dir / "EPIC.md").write_text(epic_body, encoding="utf-8")
    (epic_dir / "plan.json").write_text(json.dumps(plan_payload), encoding="utf-8")
    return epic_dir


def _plan_payload(*, contract_decisions: list[dict] | None = None) -> dict:
    return {
        "schema_v": 1,
        "epic_number": 146,
        "goal": "Ship the redesigned comment update flow.",
        "observable_truths": [{"id": 1, "statement": "A user can update a comment."}],
        "user_journeys": [
            {
                "journey_id": "J1",
                "persona": "User",
                "narrative": "A user edits a comment from the shootout page.",
                "truths_covered": [1],
                "entry_point": "/shootouts/123",
                "critical_transitions": [
                    {
                        "source": "/shootouts/123",
                        "to": "/shootouts/123/comments",
                        "mechanism": "submit comment form",
                    }
                ],
            }
        ],
        "contract_decisions": contract_decisions or [],
        "stories": [
            {
                "story_id": "01-comments",
                "name": "Nested comment update flow",
                "purpose": "Wire the repo-shaped update endpoint and UI.",
                "agent": {"model": "sonnet"},
                "scope": {"modify": ["workflow/plan_validator.py"]},
                "acceptance_criteria": [
                    "PATCH /api/shootouts/{shootout_id}/comments/{comment_id} updates comment content."
                ],
                "architectural_context": [
                    "Preserve epic contract fidelity while landing repo bridges."
                ],
                "navigation_hints": ["workflow/plan_validator.py"],
                "truths_addressed": [1],
            }
        ],
        "validation_checkpoints": [
            {
                "after_story": "01-comments",
                "check_type": "api+response",
                "checks": [{"criterion": "Comment update flow passes"}],
            }
        ],
    }


def test_extract_route_like_surfaces_keeps_routes_and_drops_files() -> None:
    surfaces = _extract_route_like_surfaces(
        """
        Implement PATCH /api/v1/comments/<id> for the user contract.
        Reference workflow/plan_validator.py for the validator code.
        Also confirm /comments and /shootouts/{shootout_id}/comments stay coherent.
        """
    )

    assert "/api/v1/comments/<id>" in surfaces
    assert "/comments" in surfaces
    assert "/shootouts/{shootout_id}/comments" in surfaces
    assert all(not surface.endswith(".py") for surface in surfaces)


def test_phase_a_fails_when_epic_route_is_silently_substituted(tmp_path) -> None:
    epic_dir = _write_epic_dir(
        tmp_path,
        epic_body="Implement PATCH /api/v1/comments/<id> with body for comment edits.\n",
        plan_payload=_plan_payload(),
    )

    result = validate_plan(epic_dir)

    assert result.valid is False
    assert any(error.check == "contract_fidelity" for error in result.errors)
    assert any("/api/v1/comments/<id>" in error.message for error in result.errors)


def test_phase_a_accepts_explicit_bridge_contract_decision(tmp_path) -> None:
    epic_dir = _write_epic_dir(
        tmp_path,
        epic_body="Implement PATCH /api/v1/comments/<id> with body for comment edits.\n",
        plan_payload=_plan_payload(
            contract_decisions=[
                {
                    "decision_id": "CD1",
                    "epic_contract": "PATCH /api/v1/comments/<id> with body",
                    "repo_convention": (
                        "PATCH /api/shootouts/{shootout_id}/comments/{comment_id} with content"
                    ),
                    "canonical": "bridge",
                    "bridge": (
                        "Keep PATCH /api/v1/comments/<id> canonical and adapt to the nested repo route."
                    ),
                    "affected_stories": ["01-comments"],
                }
            ]
        ),
    )

    result = validate_plan(epic_dir)

    assert result.valid is True
    assert result.errors == []
