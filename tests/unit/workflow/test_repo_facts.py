"""Tests for deterministic repo-facts generation."""

import json

from workflow.repo_facts import build_repo_facts


def test_build_repo_facts_writes_compact_evidence_backed_artifact(tmp_path) -> None:
    project_root = tmp_path
    epic_dir = project_root / ".planning" / "epics" / "E155"
    epic_dir.mkdir(parents=True)
    (epic_dir / "EPIC.md").write_text(
        "\n".join(
            [
                "## Summary",
                "Use `just epic 155` and update `workflow/plan_generator.py`.",
                "Ground the redesign around `/gear` and `workflow/plan_verifier.py`.",
                "The old contract mentions `legacy/plan_generator.py`.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    workflow_dir = project_root / "workflow"
    workflow_dir.mkdir()
    (workflow_dir / "cli.py").write_text('print("just epic 155")\n', encoding="utf-8")
    (workflow_dir / "plan_generator.py").write_text('ROUTE = "/gear"\n', encoding="utf-8")
    (workflow_dir / "plan_verifier.py").write_text('TARGET = "repo_facts.json"\n', encoding="utf-8")

    codebase_dir = project_root / ".planning" / "codebase"
    codebase_dir.mkdir(parents=True)
    (codebase_dir / "STRUCTURE.md").write_text("- workflow/plan_verifier.py\n", encoding="utf-8")
    (codebase_dir / "ENDPOINTS.md").write_text("GET /gear\n", encoding="utf-8")

    path = build_repo_facts(epic_dir, project_root=project_root)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "repo_facts.json"
    assert payload["epic_number"] == 155
    assert any("just epic 155" in fact["statement"] for fact in payload["current_entry_points"])
    assert any("/gear" in fact["statement"] for fact in payload["current_entry_points"])
    assert any(
        "workflow/plan_generator.py" in fact["statement"]
        for fact in payload["relevant_existing_surfaces"]
    )
    assert any(
        "legacy/plan_generator.py" in fact["statement"]
        for fact in payload["contradicted_assumptions"]
    )
    assert any(
        "workflow/plan_verifier.py" in fact["statement"] for fact in payload["likely_edit_targets"]
    )


def test_build_repo_facts_ignores_prompt_and_virtualenv_noise(tmp_path) -> None:
    project_root = tmp_path
    epic_dir = project_root / ".planning" / "epics" / "E155"
    epic_dir.mkdir(parents=True)
    (epic_dir / "EPIC.md").write_text(
        "\n".join(
            [
                "## Summary",
                "Investigate `legacy/context.py` and update `workflow/plan_generator.py`.",
                "Keep `/gear` working.",
                "Limit `Cleanup` to live code surfaces.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    workflow_dir = project_root / "workflow"
    workflow_dir.mkdir()
    (workflow_dir / "cli.py").write_text('print("just epic 155")\n', encoding="utf-8")
    (workflow_dir / "plan_generator.py").write_text('ROUTE = "/gear"\n', encoding="utf-8")
    apps_dir = project_root / "apps" / "webapp" / "src" / "webapp"
    apps_dir.mkdir(parents=True)
    (apps_dir / "context.py").write_text("CONTEXT = True\n", encoding="utf-8")

    codebase_dir = project_root / ".planning" / "codebase"
    codebase_dir.mkdir(parents=True)
    (codebase_dir / "STRUCTURE.md").write_text("- workflow/plan_generator.py\n", encoding="utf-8")
    (codebase_dir / "ENDPOINTS.md").write_text("GET /gear\n", encoding="utf-8")

    compiled_dir = epic_dir / "compiled-prompts"
    compiled_dir.mkdir()
    (compiled_dir / "planner.txt").write_text("legacy/context.py\n", encoding="utf-8")
    claude_dir = project_root / ".claude" / "prompts"
    claude_dir.mkdir(parents=True)
    (claude_dir / "note.md").write_text("legacy/context.py\nCleanup\n", encoding="utf-8")
    venv_dir = project_root / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "context.py").write_text("legacy context\n", encoding="utf-8")

    path = build_repo_facts(epic_dir, project_root=project_root)
    payload = json.loads(path.read_text(encoding="utf-8"))

    evidence_paths = [
        evidence["path"]
        for section in payload.values()
        if isinstance(section, list)
        for fact in section
        for evidence in fact.get("evidence", [])
    ]

    assert "apps/webapp/src/webapp/context.py" in evidence_paths
    assert not any(path.startswith(".claude/") for path in evidence_paths)
    assert not any(path.startswith(".venv/") for path in evidence_paths)
    assert not any("compiled-prompts" in path for path in evidence_paths)
