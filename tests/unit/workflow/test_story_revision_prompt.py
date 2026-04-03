"""Tests for scoped story revision prompts."""

from __future__ import annotations

from workflow import prompt_builder, story_executor
from workflow.artifacts import CritiqueRunArtifact


def test_build_story_revision_prompt_scopes_to_story_diff_findings_and_agents(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(prompt_builder, "PROJECT_ROOT", tmp_path)
    (tmp_path / "AGENTS.md").write_text("Rule A\nRule B\n", encoding="utf-8")

    story = {
        "story_id": "01-sample",
        "name": "Sample story",
        "purpose": "Fix the workflow path",
        "scope": {"modify": ["workflow/story_executor.py"]},
    }
    critique_run = CritiqueRunArtifact.from_dict(
        {
            "status": "fail",
            "findings": [
                {
                    "file": "workflow/story_executor.py",
                    "line": "1187-1198",
                    "issue": "Unreachable branch should be an invariant",
                    "severity": "major",
                }
            ],
            "summary": "One major finding remains",
        },
        level="story",
        critique_type="story",
        critique_model="opus",
        story_id="01-sample",
        attempt=2,
    )

    prompt = prompt_builder.build_story_revision_prompt(
        story=story,
        critique_run=critique_run,
        git_diff="diff --git a/workflow/story_executor.py b/workflow/story_executor.py",
    )

    assert "## Story Block" in prompt
    assert '"story_id": "01-sample"' in prompt
    assert "## Implementation Diff" in prompt
    assert "diff --git a/workflow/story_executor.py" in prompt
    assert "## Critique Findings" in prompt
    assert "Unreachable branch should be an invariant" in prompt
    assert "## AGENTS.md" in prompt
    assert "Rule A" in prompt
    assert "Goal:" not in prompt
    assert "Observable Truths" not in prompt
    assert "STORY_CONTEXT.md" not in prompt


def test_story_executor_uses_revision_prompt_builder_for_advisory_retries() -> None:
    import inspect

    source = inspect.getsource(story_executor._dispatch_and_validate_loop)
    assert "build_story_revision_prompt(" in source
