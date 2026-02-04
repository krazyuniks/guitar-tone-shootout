"""Tests for worktree lifecycle operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from worktree.lifecycle import update_main_branch


class TestUpdateMainBranch:
    """Tests for update_main_branch function."""

    def test_succeeds_without_merge_sha(self):
        """Should succeed when pull works and no merge SHA provided."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = update_main_branch(Path("/fake/main"))

        assert result is True
        # Should call fetch and pull
        assert mock_run.call_count == 2

    def test_succeeds_when_merge_commit_present(self):
        """Should succeed when merge commit is in history."""
        with patch("subprocess.run") as mock_run:
            # fetch, pull, and merge-base all succeed
            mock_run.return_value = MagicMock(returncode=0)
            result = update_main_branch(
                Path("/fake/main"),
                expected_merge_sha="abc123def456",
            )

        assert result is True
        # Should call fetch, pull, and merge-base
        assert mock_run.call_count == 3

    def test_retries_when_merge_commit_not_present(self):
        """Should retry when merge commit not in history yet."""
        call_count = [0]

        def mock_subprocess(*args, **kwargs):
            call_count[0] += 1
            cmd = args[0]
            mock = MagicMock()

            if "fetch" in cmd or "pull" in cmd:
                mock.returncode = 0
            elif "merge-base" in cmd:
                # Fail first 2 times, succeed on 3rd
                # Each retry does fetch + pull + merge-base = 3 calls
                # So merge-base is called on calls 3, 6, 9...
                merge_base_call_num = call_count[0] // 3
                mock.returncode = 0 if merge_base_call_num >= 2 else 1
            else:
                mock.returncode = 0

            return mock

        with patch("subprocess.run", side_effect=mock_subprocess), patch("time.sleep"):
            result = update_main_branch(
                Path("/fake/main"),
                expected_merge_sha="abc123",
                retries=3,
            )

        assert result is True

    def test_fails_after_max_retries(self):
        """Should fail after exhausting retries."""
        with patch("subprocess.run") as mock_run:

            def mock_subprocess(*args, **kwargs):
                cmd = args[0]
                mock = MagicMock()
                if "merge-base" in cmd:
                    mock.returncode = 1  # Always fail verification
                else:
                    mock.returncode = 0
                return mock

            mock_run.side_effect = mock_subprocess

            with patch("time.sleep"):  # Don't actually wait
                result = update_main_branch(
                    Path("/fake/main"),
                    expected_merge_sha="abc123",
                    retries=2,
                )

        assert result is False

    def test_retries_on_pull_failure(self):
        """Should retry when pull fails."""
        call_count = [0]

        def mock_subprocess(*args, **kwargs):
            call_count[0] += 1
            cmd = args[0]
            mock = MagicMock()

            if "pull" in cmd:
                # Fail first time, succeed second
                mock.returncode = 1 if call_count[0] <= 2 else 0
            else:
                mock.returncode = 0

            return mock

        with patch("subprocess.run", side_effect=mock_subprocess), patch("time.sleep"):
            result = update_main_branch(Path("/fake/main"), retries=3)

        assert result is True
