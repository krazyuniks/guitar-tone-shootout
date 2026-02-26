"""Tests for EPIC_STATUS.md generation."""

import pytest

from workflow.orchestrator import generate_epic_status
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


class TestGenerateEpicStatus:
    """Tests for the generate_epic_status function."""

    def test_generates_file(self, epic_dir, plan):
        """EPIC_STATUS.md is written to the epic directory."""
        result = generate_epic_status(epic_dir, plan, [], "run-1")
        assert result == epic_dir / "EPIC_STATUS.md"
        assert result.is_file()

    def test_contains_goal(self, epic_dir, plan):
        """Output includes the epic goal from plan.json."""
        generate_epic_status(epic_dir, plan, [], "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "Implement queue topology for pgmq messaging" in content

    def test_progress_count_no_stories_done(self, epic_dir, plan):
        """Progress shows 0/2 when no stories are complete."""
        generate_epic_status(epic_dir, plan, [], "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "0/2 stories complete" in content

    def test_progress_count_one_story_done(self, epic_dir, plan):
        """Progress shows 1/2 when one story is complete."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_epic_status(epic_dir, plan, events, "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "1/2 stories complete" in content

    def test_completed_story_checked(self, epic_dir, plan):
        """Completed stories show [x] checkbox."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_epic_status(epic_dir, plan, events, "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "- [x] **01-create-tables**" in content

    def test_pending_story_unchecked(self, epic_dir, plan):
        """Pending stories show [ ] checkbox."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_epic_status(epic_dir, plan, events, "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "- [ ] **02-publisher**" in content

    def test_scoped_to_run_id(self, epic_dir, plan):
        """Only stories completed in the specified run_id are marked done."""
        events = _make_events("old-run", ["01-create-tables"])
        generate_epic_status(epic_dir, plan, events, "new-run")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "0/2 stories complete" in content
        assert "- [ ] **01-create-tables**" in content

    def test_deferred_critique_findings(self, epic_dir, plan):
        """Critique findings appear in the deferred section."""
        events = [
            {
                "event": "critique_fail",
                "run_id": "run-1",
                "findings": [
                    {"severity": "medium", "issue": "Missing error handling in publisher"},
                ],
            },
        ]
        generate_epic_status(epic_dir, plan, events, "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "Deferred Critique Findings" in content
        assert "Missing error handling in publisher" in content

    def test_no_deferred_section_when_clean(self, epic_dir, plan):
        """No deferred section when there are no critique failures."""
        generate_epic_status(epic_dir, plan, [], "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "Deferred Critique Findings" not in content

    def test_idempotent_regeneration(self, epic_dir, plan):
        """Calling twice overwrites cleanly with no duplication."""
        events = _make_events("run-1", ["01-create-tables"])
        generate_epic_status(epic_dir, plan, events, "run-1")
        generate_epic_status(epic_dir, plan, events, "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert content.count("01-create-tables") == 1

    def test_migration_head_included(self, epic_dir, plan):
        """Migration head line is present in output."""
        generate_epic_status(epic_dir, plan, [], "run-1")
        content = (epic_dir / "EPIC_STATUS.md").read_text()
        assert "**Migration head:**" in content


class TestPromptBuilderEpicStatus:
    """Tests for epic_dir integration in build_story_prompt."""

    def test_no_reference_without_epic_dir(self, tmp_path):
        """No EPIC_STATUS.md reference when epic_dir is not provided."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        story = {"story_id": "test", "name": "Test", "purpose": "test", "scope": {}}
        prompt = build_story_prompt(story, rules_dir, wiki_dir)
        assert "EPIC_STATUS.md" not in prompt

    def test_no_reference_without_status_file(self, tmp_path):
        """No reference when epic_dir exists but EPIC_STATUS.md does not."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        epic_dir = tmp_path / "E999"
        epic_dir.mkdir()
        story = {"story_id": "test", "name": "Test", "purpose": "test", "scope": {}}
        prompt = build_story_prompt(story, rules_dir, wiki_dir, epic_dir=epic_dir)
        assert "EPIC_STATUS.md" not in prompt

    def test_reference_when_status_exists(self, tmp_path):
        """Prompt references EPIC_STATUS.md when the file exists."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        epic_dir = tmp_path / "E999"
        epic_dir.mkdir()
        (epic_dir / "EPIC_STATUS.md").write_text("# Epic Status\n")
        story = {"story_id": "test", "name": "Test", "purpose": "test", "scope": {}}
        prompt = build_story_prompt(story, rules_dir, wiki_dir, epic_dir=epic_dir)
        assert "EPIC_STATUS.md" in prompt
        assert "epic context" in prompt
