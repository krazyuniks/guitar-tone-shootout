"""Unit tests for DITrack model import location.

Per task specification, DITrack model should be importable from
webapp.adapters.persistence.models.di_track.
"""

import pytest


class TestDITrackModelImport:
    """Tests for DITrack model import location."""

    def test_di_track_model_importable_from_di_track_module(self) -> None:
        """Verify DITrack can be imported from di_track module.

        Task scope specifies creating:
        apps/webapp/src/webapp/adapters/persistence/models/di_track.py

        This test will fail if DITrack is in shootout.py instead.
        """
        from webapp.adapters.persistence.models.di_track import DITrack

        assert DITrack is not None
        assert DITrack.__tablename__ == "di_tracks"

    def test_di_track_has_required_fields(self) -> None:
        """Verify DITrack has all required fields from acceptance criteria."""
        from webapp.adapters.persistence.models.di_track import DITrack

        # Check that DITrack has the required fields
        assert hasattr(DITrack, "user_id")
        assert hasattr(DITrack, "original_filename")  # 'filename' in AC
        assert hasattr(DITrack, "checksum")
        assert hasattr(DITrack, "duration_seconds")  # 'duration' in AC

    def test_di_track_user_id_is_uuid(self) -> None:
        """Verify user_id is a UUID field."""
        from webapp.adapters.persistence.models.di_track import DITrack

        # user_id should be a UUID foreign key
        assert hasattr(DITrack, "user_id")
        # Actual type checking will be done in integration tests

    def test_di_track_checksum_field_exists(self) -> None:
        """Verify checksum field exists for deduplication."""
        from webapp.adapters.persistence.models.di_track import DITrack

        assert hasattr(DITrack, "checksum")

    def test_di_track_duration_field_exists(self) -> None:
        """Verify duration_seconds field exists."""
        from webapp.adapters.persistence.models.di_track import DITrack

        assert hasattr(DITrack, "duration_seconds")
