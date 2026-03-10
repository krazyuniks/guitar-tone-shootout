"""Tests for epic status surfaces."""

import json

from workflow import orchestrator


def test_show_status_lists_repo_facts_and_not_planning_context(
    tmp_path, monkeypatch, capsys
) -> None:
    planning_dir = tmp_path / ".planning" / "epics"
    epic_dir = planning_dir / "E155"
    epic_dir.mkdir(parents=True)
    (epic_dir / "EPIC.md").write_text("## Summary\nRepo facts\n", encoding="utf-8")
    (epic_dir / "repo_facts.json").write_text(
        json.dumps({"schema_v": 1, "epic_number": 155}),
        encoding="utf-8",
    )
    (epic_dir / "curation.json").write_text(
        json.dumps(
            {
                "schema_v": 1,
                "epic_number": 155,
                "candidate_journeys": [],
                "story_slices": [],
                "missing_assumptions": [],
                "scope_tensions": [],
                "planner_handoff": {
                    "priority_order": [],
                    "watchouts": [],
                    "recommended_story_shape": "One focused slice",
                },
            }
        ),
        encoding="utf-8",
    )
    (epic_dir / "CURATION.md").write_text("# Curation", encoding="utf-8")

    monkeypatch.setattr(orchestrator, "PLANNING_DIR", planning_dir)

    orchestrator.show_status(155)
    output = capsys.readouterr().out

    assert "[EXISTS] repo_facts.json" in output
    assert "[EXISTS] curation.json" in output
    assert "[EXISTS] CURATION.md" in output
    assert "CONTEXT.md" not in output
