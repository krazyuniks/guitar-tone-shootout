"""Unit tests for auth file persistence (T19).

Tests for .gts-auth.json file save/restore functionality:
- Saving auth data to .gts-auth.json
- Loading auth data from .gts-auth.json
- File format validation
- Multi-worktree sharing
"""

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest


class TestAuthFilePersistence:
    """Test suite for .gts-auth.json file operations."""

    def test_save_auth_data_to_file(self) -> None:
        """Test saving auth data to .gts-auth.json file."""
        from webapp.auth.persistence import AuthFilePersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file_path = Path(tmpdir) / ".gts-auth.json"

            persistence = AuthFilePersistence(str(auth_file_path))

            user_id = uuid4()
            auth_data = {
                "user_id": str(user_id),
                "username": "test_user",
                "access_token": "encrypted_access_token",
                "refresh_token": "encrypted_refresh_token",
                "expires_at": "2026-02-06T12:00:00Z",
            }

            # Save auth data
            persistence.save(auth_data)

            # Verify file was created
            assert auth_file_path.exists()

            # Verify file contains correct data
            with open(auth_file_path) as f:
                saved_data = json.load(f)
                assert saved_data["user_id"] == str(user_id)
                assert saved_data["username"] == "test_user"

    def test_load_auth_data_from_file(self) -> None:
        """Test loading auth data from .gts-auth.json file."""
        from webapp.auth.persistence import AuthFilePersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file_path = Path(tmpdir) / ".gts-auth.json"

            # Create auth file
            user_id = uuid4()
            auth_data = {
                "user_id": str(user_id),
                "username": "loaded_user",
                "access_token": "encrypted_token",
                "refresh_token": "encrypted_refresh",
                "expires_at": "2026-02-06T12:00:00Z",
            }
            with open(auth_file_path, "w") as f:
                json.dump(auth_data, f)

            persistence = AuthFilePersistence(str(auth_file_path))

            # Load auth data
            loaded_data = persistence.load()

            # Verify loaded data matches
            assert loaded_data["user_id"] == str(user_id)
            assert loaded_data["username"] == "loaded_user"
            assert loaded_data["access_token"] == "encrypted_token"

    def test_load_returns_none_when_file_missing(self) -> None:
        """Test load returns None when .gts-auth.json doesn't exist."""
        from webapp.auth.persistence import AuthFilePersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file_path = Path(tmpdir) / ".gts-auth.json"

            persistence = AuthFilePersistence(str(auth_file_path))

            # Load from non-existent file
            loaded_data = persistence.load()

            # Should return None
            assert loaded_data is None

    def test_save_overwrites_existing_file(self) -> None:
        """Test saving overwrites existing .gts-auth.json file."""
        from webapp.auth.persistence import AuthFilePersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file_path = Path(tmpdir) / ".gts-auth.json"

            persistence = AuthFilePersistence(str(auth_file_path))

            # Save initial data
            initial_data = {
                "user_id": str(uuid4()),
                "username": "initial_user",
                "access_token": "initial_token",
            }
            persistence.save(initial_data)

            # Save new data (should overwrite)
            new_user_id = uuid4()
            new_data = {
                "user_id": str(new_user_id),
                "username": "new_user",
                "access_token": "new_token",
            }
            persistence.save(new_data)

            # Load and verify new data
            loaded_data = persistence.load()
            assert loaded_data["user_id"] == str(new_user_id)
            assert loaded_data["username"] == "new_user"

    def test_auth_file_has_correct_permissions(self) -> None:
        """Test .gts-auth.json file has secure permissions (0600)."""
        from webapp.auth.persistence import AuthFilePersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file_path = Path(tmpdir) / ".gts-auth.json"

            persistence = AuthFilePersistence(str(auth_file_path))

            auth_data = {
                "user_id": str(uuid4()),
                "username": "test_user",
                "access_token": "token",
            }
            persistence.save(auth_data)

            # Check file permissions (should be 0600 - owner read/write only)
            file_stat = os.stat(auth_file_path)
            file_mode = file_stat.st_mode & 0o777

            # Should be readable and writable by owner only
            assert file_mode == 0o600

    def test_delete_auth_file(self) -> None:
        """Test deleting .gts-auth.json file."""
        from webapp.auth.persistence import AuthFilePersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file_path = Path(tmpdir) / ".gts-auth.json"

            persistence = AuthFilePersistence(str(auth_file_path))

            # Save data
            persistence.save({"user_id": str(uuid4()), "username": "test"})
            assert auth_file_path.exists()

            # Delete file
            persistence.delete()

            # File should be gone
            assert not auth_file_path.exists()

    def test_load_handles_corrupted_json(self) -> None:
        """Test load handles corrupted .gts-auth.json gracefully."""
        from webapp.auth.persistence import AuthFilePersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file_path = Path(tmpdir) / ".gts-auth.json"

            # Write corrupted JSON
            with open(auth_file_path, "w") as f:
                f.write("{invalid json")

            persistence = AuthFilePersistence(str(auth_file_path))

            # Should handle corrupted file gracefully
            with pytest.raises(json.JSONDecodeError):
                persistence.load()

    def test_auth_file_path_defaults_to_worktree_root(self) -> None:
        """Test auth file path defaults to worktree root .gts-auth.json."""
        from webapp.auth.persistence import AuthFilePersistence

        # Create persistence without explicit path
        persistence = AuthFilePersistence()

        # Should use .gts-auth.json in current directory or worktree root
        assert persistence.auth_file_path.endswith(".gts-auth.json")

    def test_auth_file_shared_across_worktrees(self) -> None:
        """Test .gts-auth.json can be shared across multiple worktrees."""
        from webapp.auth.persistence import AuthFilePersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            # Shared auth file location (outside worktrees)
            shared_auth_file = Path(tmpdir) / ".gts-auth.json"

            # Simulate two worktrees using same auth file
            worktree1 = AuthFilePersistence(str(shared_auth_file))
            worktree2 = AuthFilePersistence(str(shared_auth_file))

            # Save from worktree1
            user_id = uuid4()
            auth_data = {
                "user_id": str(user_id),
                "username": "shared_user",
                "access_token": "shared_token",
            }
            worktree1.save(auth_data)

            # Load from worktree2
            loaded_data = worktree2.load()

            # Should see same data
            assert loaded_data["user_id"] == str(user_id)
            assert loaded_data["username"] == "shared_user"
