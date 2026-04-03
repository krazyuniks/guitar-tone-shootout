"""Tests for workflow git helper utilities."""

from __future__ import annotations

import subprocess

import pytest
import typer

from workflow import cli, git_helpers, orchestrator


def test_check_working_tree_clean_allows_clean_repo(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(git_helpers.subprocess, "run", fake_run)

    git_helpers.check_working_tree_clean()


def test_check_working_tree_clean_raises_for_dirty_repo(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=" M workflow/story_executor.py\n?? scratch.txt\n",
            stderr="",
        )

    monkeypatch.setattr(git_helpers.subprocess, "run", fake_run)

    with pytest.raises(git_helpers.GitDirtyWorktreeError) as exc_info:
        git_helpers.check_working_tree_clean()

    assert "Working tree is dirty" in str(exc_info.value)
    assert exc_info.value.dirty_entries == [
        " M workflow/story_executor.py",
        "?? scratch.txt",
    ]


def test_epic_run_exits_before_pipeline_when_tree_is_dirty(monkeypatch) -> None:
    calls: list[int] = []

    def fake_check() -> None:
        raise git_helpers.GitDirtyWorktreeError([" M workflow/story_executor.py"])

    monkeypatch.setattr(git_helpers, "check_working_tree_clean", fake_check)
    monkeypatch.setattr(orchestrator, "run_pipeline", lambda epic_number: calls.append(epic_number))

    with pytest.raises(typer.Exit) as exc_info:
        cli.epic_run(163)

    assert exc_info.value.exit_code == 1
    assert calls == []
