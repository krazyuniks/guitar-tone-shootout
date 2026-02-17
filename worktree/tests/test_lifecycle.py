"""Tests for worktree lifecycle operations.

Uses monkeypatch instead of unittest.mock.
"""

import types
from pathlib import Path

import pytest

from worktree.lifecycle import update_main_branch


class TestUpdateMainBranch:
    """Tests for update_main_branch function."""

    def test_succeeds_without_merge_sha(self, monkeypatch: pytest.MonkeyPatch):
        """Should succeed when pull works and no merge SHA provided."""
        call_count = 0

        def fake_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return types.SimpleNamespace(returncode=0)

        monkeypatch.setattr("subprocess.run", fake_run)

        result = update_main_branch(Path("/fake/main"))

        assert result is True
        assert call_count == 2  # fetch + pull

    def test_succeeds_when_merge_commit_present(self, monkeypatch: pytest.MonkeyPatch):
        """Should succeed when merge commit is in history."""

        def fake_run(*args, **kwargs):
            return types.SimpleNamespace(returncode=0)

        monkeypatch.setattr("subprocess.run", fake_run)

        result = update_main_branch(
            Path("/fake/main"),
            expected_merge_sha="abc123def456",
        )

        assert result is True

    def test_retries_when_merge_commit_not_present(self, monkeypatch: pytest.MonkeyPatch):
        """Should retry when merge commit not in history yet."""
        call_count = 0

        def fake_run(cmd, *args, **kwargs):
            nonlocal call_count
            call_count += 1

            if "merge-base" in cmd:
                # Fail first 2 times, succeed on 3rd
                merge_base_call_num = call_count // 3
                return types.SimpleNamespace(returncode=0 if merge_base_call_num >= 2 else 1)
            return types.SimpleNamespace(returncode=0)

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = update_main_branch(
            Path("/fake/main"),
            expected_merge_sha="abc123",
            retries=3,
        )

        assert result is True

    def test_fails_after_max_retries(self, monkeypatch: pytest.MonkeyPatch):
        """Should fail after exhausting retries."""

        def fake_run(cmd, *args, **kwargs):
            if "merge-base" in cmd:
                return types.SimpleNamespace(returncode=1)  # Always fail verification
            return types.SimpleNamespace(returncode=0)

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = update_main_branch(
            Path("/fake/main"),
            expected_merge_sha="abc123",
            retries=2,
        )

        assert result is False

    def test_retries_on_pull_failure(self, monkeypatch: pytest.MonkeyPatch):
        """Should retry when pull fails."""
        call_count = 0

        def fake_run(cmd, *args, **kwargs):
            nonlocal call_count
            call_count += 1

            if "pull" in cmd:
                # Fail first time, succeed second
                return types.SimpleNamespace(returncode=1 if call_count <= 2 else 0)
            return types.SimpleNamespace(returncode=0)

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = update_main_branch(Path("/fake/main"), retries=3)

        assert result is True
