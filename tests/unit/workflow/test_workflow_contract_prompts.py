"""Tests for contract-fidelity prompt hardening across workflow stages."""

import json

from workflow.prompt_suite import (
    compile_curation_prompt,
    compile_planner_prompt,
    compile_verifier_prompt,
)


def _write_epic_dir(tmp_path):
    epic_dir = tmp_path / "E146"
    epic_dir.mkdir()
    (epic_dir / "EPIC.md").write_text(
        "Implement PATCH /api/v1/comments/<id> with body for comment edits.\n",
        encoding="utf-8",
    )
    (epic_dir / "repo_facts.json").write_text(
        json.dumps(
            {
                "schema_v": 1,
                "epic_number": 146,
                "contradicted_assumptions": [
                    {
                        "statement": (
                            "Epic cites /api/v1/comments/<id>, but repo currently uses nested comment routes."
                        ),
                        "evidence": [
                            {
                                "path": "workflow/plan_validator.py",
                                "line": 1,
                                "detail": "Nested comment route reference",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (epic_dir / "curation.json").write_text(
        json.dumps(
            {
                "schema_v": 1,
                "epic_number": 146,
                "candidate_journeys": [],
                "story_slices": [],
                "missing_assumptions": [
                    {
                        "assumption": "Epic route and repo route differ.",
                        "why_it_matters": "Planner must preserve the epic contract explicitly.",
                        "planner_action": "Surface the mismatch without choosing a winner.",
                    }
                ],
                "scope_tensions": [],
                "planner_handoff": {
                    "priority_order": ["Preserve epic contract"],
                    "watchouts": ["Do not silently rename the route"],
                    "recommended_story_shape": "One explicit bridge slice",
                },
            }
        ),
        encoding="utf-8",
    )
    (epic_dir / "plan.json").write_text(
        json.dumps(
            {
                "schema_v": 1,
                "epic_number": 146,
                "goal": "Preserve the epic-facing route and bridge repo internals.",
                "observable_truths": [{"id": 1, "statement": "A user can update a comment."}],
                "user_journeys": [
                    {
                        "journey_id": "J1",
                        "persona": "User",
                        "narrative": "The user updates a comment.",
                        "truths_covered": [1],
                        "entry_point": "/comments",
                        "critical_transitions": [
                            {"source": "/comments", "to": "/comments/saved", "mechanism": "submit"}
                        ],
                    }
                ],
                "contract_decisions": [
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
                ],
                "stories": [
                    {
                        "story_id": "01-comments",
                        "name": "Comment bridge",
                        "purpose": "Bridge the repo route behind the epic contract.",
                        "agent": {"model": "sonnet"},
                        "scope": {"modify": ["workflow/plan_validator.py"]},
                        "acceptance_criteria": [
                            "PATCH /api/v1/comments/<id> remains the canonical route."
                        ],
                        "architectural_context": ["Keep contract decisions explicit."],
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
        ),
        encoding="utf-8",
    )
    return epic_dir


def test_compiled_curation_prompt_is_neutral_on_mismatch_resolution(tmp_path) -> None:
    prompt = compile_curation_prompt(_write_epic_dir(tmp_path)).text

    assert "surface that mismatch\n   explicitly and factually" in prompt
    assert "Do NOT recommend which contract should win." in prompt
    assert "preferred canonical contract" not in prompt


def test_compiled_planner_prompt_requires_structured_contract_decisions(tmp_path) -> None:
    prompt = compile_planner_prompt(_write_epic_dir(tmp_path)).text

    assert "the only valid canonical outcomes are `epic` or `bridge`" in prompt
    assert "`contract_decisions` entry" in prompt
    assert "There is no\n  `repo` option." in prompt or "There is no `repo` option." in prompt


def test_compiled_verifier_prompt_reviews_contract_decisions_explicitly(tmp_path) -> None:
    prompt = compile_verifier_prompt(_write_epic_dir(tmp_path)).text

    assert '"contract_decisions": [' in prompt
    assert "## Contract Decisions Review" in prompt
    assert "If the plan silently substitutes a repo convention" in prompt
    assert "If canonical is `bridge`, the bridge must be concrete" in prompt
