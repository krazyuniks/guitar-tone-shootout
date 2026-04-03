"""Regression tests for workflow architecture reference and canonical epic skill docs."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_workflow_architecture_reference_documents_issue_166_contracts() -> None:
    text = (PROJECT_ROOT / "workflow" / "references" / "workflow-architecture.md").read_text(
        encoding="utf-8"
    )

    assert "## Invocation Modes" in text
    assert "Autonomous" in text
    assert "Gate" in text
    assert "Interactive" in text
    assert "## Workflow Types" in text
    assert "Skill" in text
    assert "`just` command" in text
    assert "Hook" in text
    assert "Rule" in text
    assert "Do not create new top-level artefact directories" in text
    assert "Every autonomous workflow artefact must have a defined schema" in text
    assert "Interactive skills do not have a formal contract system." in text
    assert "`/research` and `/epic brainstorm` are intentionally independent." in text
    assert "Architecture-Mapper-Workflow Contract" in text
    assert "run `just map-codebase`" in text
    assert "## Autonomous Stage Contracts" in text
    assert "RepoFactsArtifact" in text
    assert "CurationArtifact" in text
    assert "PlanArtifact" in text
    assert "If verification still fails, stop at the human decision gate" in text


def test_epic_skill_docs_match_current_pipeline_contract() -> None:
    expected_present = (
        "`just epic <N>` | Full pipeline: ingest -> repo-facts -> curation -> plan -> verify -> execute (gate only on unresolved planning failures)",
        "just map-codebase",
        "repo_facts.json",
        "curation.json",
        "workflow/references/workflow-architecture.md",
        "Do not pipe `yes` into it.",
        "If verification still fails, stop at the decision gate",
    )
    expected_absent = (
        "yes \\| just epic <N>",
        "workflow/context_assembler.py",
        "  CONTEXT.md        # Assembled context for planner",
        "Interactive Scope",
        "tests_approved",
        "gap detection",
    )

    claude_text = (PROJECT_ROOT / ".claude" / "skills" / "epic" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for needle in expected_present:
        assert needle in claude_text

    for needle in expected_absent:
        assert needle not in claude_text
