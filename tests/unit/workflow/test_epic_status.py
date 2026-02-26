"""Tests for STORY_CONTEXT.md generation."""

import pytest

from workflow.orchestrator import generate_story_context
from workflow.prompt_builder import build_story_prompt


@pytest.fixture()
def epic_dir(tmp_path):
    """Create a minimal epic directory with plan.json."""
    epic = tmp_path / "E999"
    epic.mkdir()
    return epic


@pytest.fixture()
def plan():
    """Minimal plan.json dict with two stories."""
    return {
        "goal": "Implement queue topology for pgmq messaging",
        "stories": [
            {
                "story_id": "01-create-tables",
                "name": "Create pgmq tables",
                "purpose": "Set up queue infrastructure",
                "scope": {"create": ["migrations/0018.py"], "modify": []},
            },
            {
                "story_id": "02-publisher",
                "name": "Implement publisher adapter",
                "purpose": "Publish domain events to pgmq",
                "scope": {"create": [], "modify": ["sources/t3k/publisher.py"]},
            },
        ],
    }


def _make_events(run_id, completed_story_ids, commits=None):
    """Build a list of JSONL-style event dicts."""
    commits = commits or {}
    events = []
    for sid in completed_story_ids:
        events.append(
            {
                "event": "story_complete",
                "run_id": run_id,
                "story_id": sid,
                "commit": commits.get(sid, "abc12340"),
            }
        )
    return events


class TestGenerateStoryContext:
    """Tests for the generate_story_context function."""

    def test_generates_file(self, epic_dir, plan):
        """STORY_CONTEXT.md is written to the epic directory."""
        result = generate_story_context(epic_dir, plan, [], "run-1")
        assert result == epic_dir / "STORY_CONTEXT.md"
        assert result.is_file()

    def test_contains_goal(self, epic_dir, plan):
        """Output includes the epic goal from plan.json."""
        generate_story_context(epic_dir, plan, [], "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "Implement queue topology for pgmq messaging" in content

    def test_contains_epic_number(self, epic_dir, plan):
        """Output includes the epic number from directory name."""
        generate_story_context(epic_dir, plan, [], "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "#999" in content

    def test_contains_github_link(self, epic_dir, plan):
        """Output includes a GitHub issue link."""
        generate_story_context(epic_dir, plan, [], "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "GitHub Issue" in content
        assert "issues/999" in content

    def test_progress_count_no_stories_done(self, epic_dir, plan):
        """Progress shows 0/2 when no stories are complete."""
        generate_story_context(epic_dir, plan, [], "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "0/2 stories complete" in content

    def test_progress_count_one_story_done(self, epic_dir, plan):
        """Progress shows 1/2 when one story is complete."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_story_context(epic_dir, plan, events, "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "1/2 stories complete" in content

    def test_completed_story_checked(self, epic_dir, plan):
        """Completed stories show ✅ prefix with story ID."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_story_context(epic_dir, plan, events, "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "✅ 01-create-tables:" in content

    def test_pending_story_unchecked(self, epic_dir, plan):
        """Pending stories show ⏳ prefix with story ID."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_story_context(epic_dir, plan, events, "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "⏳ 02-publisher:" in content

    def test_scoped_to_run_id(self, epic_dir, plan):
        """Only stories completed in the specified run_id are marked done."""
        events = _make_events("old-run", ["01-create-tables"])
        generate_story_context(epic_dir, plan, events, "new-run")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "0/2 stories complete" in content
        assert "⏳ 01-create-tables:" in content

    def test_completed_story_shows_key_files(self, epic_dir, plan):
        """Completed stories list key files from scope."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_story_context(epic_dir, plan, events, "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "migrations/0018.py" in content

    def test_advisory_notes_from_critique_fail(self, epic_dir, plan):
        """Critique findings appear in the advisory notes section."""
        events = [
            {
                "event": "critique_fail",
                "run_id": "run-1",
                "story_id": "01-create-tables",
                "findings": [
                    {"severity": "medium", "issue": "Missing error handling in publisher"},
                ],
            },
        ]
        generate_story_context(epic_dir, plan, events, "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "Advisory Notes" in content
        assert "Missing error handling in publisher" in content

    def test_no_advisory_section_when_clean(self, epic_dir, plan):
        """No advisory section when there are no critique failures."""
        generate_story_context(epic_dir, plan, [], "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "Advisory Notes" not in content

    def test_idempotent_regeneration(self, epic_dir, plan):
        """Calling twice overwrites cleanly with no duplication."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_story_context(epic_dir, plan, events, "run-1")
        generate_story_context(epic_dir, plan, events, "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert content.count("01-create-tables") == 1

    def test_migration_head_included(self, epic_dir, plan):
        """Migration head line is present in output."""
        generate_story_context(epic_dir, plan, [], "run-1")
        content = (epic_dir / "STORY_CONTEXT.md").read_text()
        assert "**Migration head:**" in content


class TestPromptBuilderStoryContext:
    """Tests for epic_dir integration in build_story_prompt."""

    def test_no_reference_without_epic_dir(self, tmp_path):
        """No STORY_CONTEXT.md reference when epic_dir is not provided."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        story = {"story_id": "test", "name": "Test", "purpose": "test", "scope": {}}
        prompt = build_story_prompt(story, rules_dir, wiki_dir)
        assert "STORY_CONTEXT.md" not in prompt

    def test_no_reference_without_context_file(self, tmp_path):
        """No reference when epic_dir exists but STORY_CONTEXT.md does not."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        epic_dir = tmp_path / "E999"
        epic_dir.mkdir()
        story = {"story_id": "test", "name": "Test", "purpose": "test", "scope": {}}
        prompt = build_story_prompt(story, rules_dir, wiki_dir, epic_dir=epic_dir)
        assert "STORY_CONTEXT.md" not in prompt

    def test_reference_when_context_exists(self, tmp_path):
        """Prompt references STORY_CONTEXT.md when the file exists."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        epic_dir = tmp_path / "E999"
        epic_dir.mkdir()
        (epic_dir / "STORY_CONTEXT.md").write_text("# Story Context\n")
        story = {"story_id": "test", "name": "Test", "purpose": "test", "scope": {}}
        prompt = build_story_prompt(story, rules_dir, wiki_dir, epic_dir=epic_dir)
        assert "STORY_CONTEXT.md" in prompt
        assert "epic context" in prompt
        assert "prior story changes" in prompt
