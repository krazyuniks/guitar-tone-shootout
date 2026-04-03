"""Tests for validated story checkpoint commits."""

from __future__ import annotations

from workflow import git_helpers, story_executor


class _FakeEventLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def log_event(self, event_name: str, **payload) -> None:
        self.events.append((event_name, payload))


def test_commit_story_checkpoint_returns_commit_hash(monkeypatch, tmp_path) -> None:
    epic_dir = tmp_path / "E163"
    story_log = epic_dir / "stories" / "01-sample" / "story.jsonl"
    story_log.parent.mkdir(parents=True)
    story_log.write_text('{"event":"story_complete"}\n', encoding="utf-8")
    logger = _FakeEventLogger()

    monkeypatch.setattr(story_executor, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(git_helpers, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(git_helpers, "robust_commit", lambda _message, _paths: "abc1234")

    commit_hash = story_executor._commit_story_checkpoint(
        story_id="01-sample",
        attempt=1,
        epic_dir=epic_dir,
        plan_scope_paths=["workflow/story_executor.py"],
        event_logger=logger,
    )

    assert commit_hash == "abc1234"
    assert logger.events == []


def test_commit_story_checkpoint_stops_on_commit_failure(monkeypatch, tmp_path) -> None:
    epic_dir = tmp_path / "E163"
    story_log = epic_dir / "stories" / "01-sample" / "story.jsonl"
    story_log.parent.mkdir(parents=True)
    story_log.write_text('{"event":"story_complete"}\n', encoding="utf-8")
    logger = _FakeEventLogger()

    monkeypatch.setattr(story_executor, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(git_helpers, "PROJECT_ROOT", tmp_path)

    def fail_commit(message, paths):
        raise git_helpers.GitCommitError("boom", "stderr boom")

    monkeypatch.setattr(git_helpers, "robust_commit", fail_commit)

    commit_hash = story_executor._commit_story_checkpoint(
        story_id="01-sample",
        attempt=1,
        epic_dir=epic_dir,
        plan_scope_paths=["workflow/story_executor.py"],
        event_logger=logger,
    )

    assert commit_hash is None
    assert logger.events[0][0] == "story_failed"
    assert logger.events[1][0] == "exit_to_human"
