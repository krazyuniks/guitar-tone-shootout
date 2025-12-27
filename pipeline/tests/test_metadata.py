"""Tests for shootout metadata capture."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from guitar_tone_shootout.metadata import (
    AudioSettings,
    AudioSettingsSchema,
    FileHashes,
    FileHashesSchema,
    NormalizationSettings,
    NormalizationSettingsSchema,
    ProcessingMetadata,
    ProcessingMetadataFullSchema,
    ProcessingVersions,
    ProcessingVersionsSchema,
    collect_processing_versions,
    compute_file_hash,
    compute_file_hashes,
    create_processing_metadata,
    get_ffmpeg_version,
    get_pedalboard_version,
    get_pipeline_version,
    get_python_version,
)


class TestProcessingVersions:
    """Tests for ProcessingVersions dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        versions = ProcessingVersions(
            pedalboard="0.9.19",
            nam_vst="0.7.13",
            ffmpeg="6.1.1",
            pipeline="0.1.0",
            python="3.12.0",
        )

        data = versions.to_dict()

        assert data == {
            "pedalboard": "0.9.19",
            "nam_vst": "0.7.13",
            "ffmpeg": "6.1.1",
            "pipeline": "0.1.0",
            "python": "3.12.0",
        }


class TestVersionGetters:
    """Tests for individual version getter functions."""

    def test_get_python_version(self) -> None:
        """Test Python version getter returns valid format."""
        version = get_python_version()
        # Should be in format "3.x.y"
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_get_pipeline_version(self) -> None:
        """Test pipeline version getter."""
        version = get_pipeline_version()
        # Should return the __version__ or "unknown"
        assert version != ""

    def test_get_pedalboard_version(self) -> None:
        """Test pedalboard version getter handles import error."""
        version = get_pedalboard_version()
        # Should return a version string or "not installed"
        assert version != ""

    def test_get_ffmpeg_version(self) -> None:
        """Test FFmpeg version getter."""
        version = get_ffmpeg_version()
        # Should return a version or "not installed"
        assert version != ""

    def test_collect_processing_versions(self) -> None:
        """Test collecting all versions."""
        versions = collect_processing_versions()

        assert isinstance(versions, ProcessingVersions)
        assert versions.python != ""
        assert versions.pipeline != ""


class TestAudioSettings:
    """Tests for AudioSettings dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        settings = AudioSettings(
            sample_rate=48000,
            bit_depth=32,
            channels=2,
            format="float32",
        )

        data = settings.to_dict()

        assert data == {
            "sample_rate": 48000,
            "bit_depth": 32,
            "channels": 2,
            "format": "float32",
        }

    def test_default_format(self) -> None:
        """Test default format is float32."""
        settings = AudioSettings(
            sample_rate=44100,
            bit_depth=24,
            channels=1,
        )

        assert settings.format == "float32"


class TestNormalizationSettings:
    """Tests for NormalizationSettings dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        settings = NormalizationSettings()

        assert settings.input_target_rms_db == -18.0
        assert settings.output_target_rms_db == -14.0
        assert settings.method == "rms"
        assert settings.headroom_db == -1.0

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        settings = NormalizationSettings(
            input_target_rms_db=-20.0,
            output_target_rms_db=-16.0,
            method="lufs",
            headroom_db=-0.5,
        )

        data = settings.to_dict()

        assert data == {
            "input_target_rms_db": -20.0,
            "output_target_rms_db": -16.0,
            "method": "lufs",
            "headroom_db": -0.5,
        }


class TestFileHashes:
    """Tests for file hash functions."""

    def test_compute_file_hash(self, tmp_path: Path) -> None:
        """Test computing hash of a file."""
        test_file = tmp_path / "test.wav"
        content = b"test audio content"
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        actual_hash = compute_file_hash(test_file)

        assert actual_hash == expected_hash

    def test_compute_file_hash_large_file(self, tmp_path: Path) -> None:
        """Test computing hash of a larger file (uses chunked reading)."""
        test_file = tmp_path / "large.wav"
        # Create a file larger than 8192 bytes (our chunk size)
        content = b"x" * 20000
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        actual_hash = compute_file_hash(test_file)

        assert actual_hash == expected_hash

    def test_compute_file_hash_file_not_found(self, tmp_path: Path) -> None:
        """Test computing hash of non-existent file raises error."""
        non_existent = tmp_path / "nonexistent.wav"

        with pytest.raises(FileNotFoundError):
            compute_file_hash(non_existent)

    def test_compute_file_hashes_all_files(self, tmp_path: Path) -> None:
        """Test computing hashes for all input files."""
        di_track = tmp_path / "di.wav"
        nam_model = tmp_path / "model.nam"
        ir_file = tmp_path / "ir.wav"

        di_track.write_bytes(b"di content")
        nam_model.write_bytes(b"nam content")
        ir_file.write_bytes(b"ir content")

        hashes = compute_file_hashes(di_track, nam_model, ir_file)

        assert hashes.di_track_sha256 == hashlib.sha256(b"di content").hexdigest()
        assert hashes.nam_model_sha256 == hashlib.sha256(b"nam content").hexdigest()
        assert hashes.ir_sha256 == hashlib.sha256(b"ir content").hexdigest()

    def test_compute_file_hashes_di_only(self, tmp_path: Path) -> None:
        """Test computing hashes with only DI track."""
        di_track = tmp_path / "di.wav"
        di_track.write_bytes(b"di content")

        hashes = compute_file_hashes(di_track)

        assert hashes.di_track_sha256 == hashlib.sha256(b"di content").hexdigest()
        assert hashes.nam_model_sha256 is None
        assert hashes.ir_sha256 is None

    def test_file_hashes_to_dict(self) -> None:
        """Test FileHashes to_dict conversion."""
        hashes = FileHashes(
            di_track_sha256="abc123",
            nam_model_sha256="def456",
            ir_sha256=None,
        )

        data = hashes.to_dict()

        assert data == {
            "di_track_sha256": "abc123",
            "nam_model_sha256": "def456",
            "ir_sha256": None,
        }


class TestProcessingMetadata:
    """Tests for ProcessingMetadata dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        metadata = ProcessingMetadata(
            versions=ProcessingVersions(
                pedalboard="0.9.19",
                nam_vst="0.7.13",
                ffmpeg="6.1.1",
                pipeline="0.1.0",
                python="3.12.0",
            ),
            audio_settings=AudioSettings(
                sample_rate=48000,
                bit_depth=32,
                channels=2,
            ),
            normalization=NormalizationSettings(),
            file_hashes=FileHashes(di_track_sha256="abc123"),
            processed_at="2024-01-01T00:00:00Z",
            processing_duration_seconds=10.5,
            total_duration_ms=30000,
            segment_count=3,
        )

        data = metadata.to_dict()

        assert "versions" in data
        assert "audio_settings" in data
        assert "normalization" in data
        assert "file_hashes" in data
        assert data["processed_at"] == "2024-01-01T00:00:00Z"
        assert data["processing_duration_seconds"] == 10.5
        assert data["total_duration_ms"] == 30000
        assert data["segment_count"] == 3

    def test_processed_at_default(self) -> None:
        """Test that processed_at defaults to current time."""
        metadata = ProcessingMetadata(
            versions=ProcessingVersions(
                pedalboard="1.0", nam_vst="1.0", ffmpeg="1.0",
                pipeline="1.0", python="3.12",
            ),
            audio_settings=AudioSettings(
                sample_rate=48000, bit_depth=32, channels=2,
            ),
            normalization=NormalizationSettings(),
            file_hashes=FileHashes(di_track_sha256="abc"),
        )

        # Should have an ISO timestamp
        assert "T" in metadata.processed_at
        assert metadata.processed_at.endswith("+00:00") or "Z" in metadata.processed_at


class TestCreateProcessingMetadata:
    """Tests for create_processing_metadata convenience function."""

    def test_creates_complete_metadata(self, tmp_path: Path) -> None:
        """Test creating complete metadata from paths."""
        di_track = tmp_path / "di.wav"
        di_track.write_bytes(b"di content")

        metadata = create_processing_metadata(
            di_track=di_track,
            sample_rate=48000,
            bit_depth=32,
            channels=2,
        )

        assert isinstance(metadata, ProcessingMetadata)
        assert metadata.audio_settings.sample_rate == 48000
        assert metadata.audio_settings.bit_depth == 32
        assert metadata.audio_settings.channels == 2
        assert metadata.file_hashes.di_track_sha256 != ""

    def test_with_optional_files(self, tmp_path: Path) -> None:
        """Test creating metadata with NAM and IR files."""
        di_track = tmp_path / "di.wav"
        nam_model = tmp_path / "model.nam"
        ir_file = tmp_path / "ir.wav"

        di_track.write_bytes(b"di")
        nam_model.write_bytes(b"nam")
        ir_file.write_bytes(b"ir")

        metadata = create_processing_metadata(
            di_track=di_track,
            nam_model=nam_model,
            ir_file=ir_file,
        )

        assert metadata.file_hashes.di_track_sha256 != ""
        assert metadata.file_hashes.nam_model_sha256 is not None
        assert metadata.file_hashes.ir_sha256 is not None

    def test_with_custom_normalization(self, tmp_path: Path) -> None:
        """Test creating metadata with custom normalization."""
        di_track = tmp_path / "di.wav"
        di_track.write_bytes(b"di content")

        custom_norm = NormalizationSettings(
            input_target_rms_db=-20.0,
            output_target_rms_db=-12.0,
            method="lufs",
        )

        metadata = create_processing_metadata(
            di_track=di_track,
            normalization=custom_norm,
        )

        assert metadata.normalization.input_target_rms_db == -20.0
        assert metadata.normalization.output_target_rms_db == -12.0
        assert metadata.normalization.method == "lufs"


class TestPydanticSchemas:
    """Tests for Pydantic schema classes."""

    def test_processing_versions_schema(self) -> None:
        """Test ProcessingVersionsSchema validation."""
        schema = ProcessingVersionsSchema(
            pedalboard="0.9.19",
            nam_vst="0.7.13",
            ffmpeg="6.1.1",
            pipeline="0.1.0",
            python="3.12.0",
        )

        assert schema.pedalboard == "0.9.19"
        assert schema.python == "3.12.0"

    def test_audio_settings_schema_validation(self) -> None:
        """Test AudioSettingsSchema validation."""
        # Valid schema
        schema = AudioSettingsSchema(
            sample_rate=48000,
            bit_depth=32,
            channels=2,
        )
        assert schema.sample_rate == 48000

        # Invalid: zero sample rate
        with pytest.raises(ValueError):
            AudioSettingsSchema(
                sample_rate=0,
                bit_depth=32,
                channels=2,
            )

        # Invalid: too many channels
        with pytest.raises(ValueError):
            AudioSettingsSchema(
                sample_rate=48000,
                bit_depth=32,
                channels=8,
            )

    def test_normalization_settings_schema_defaults(self) -> None:
        """Test NormalizationSettingsSchema defaults."""
        schema = NormalizationSettingsSchema()

        assert schema.input_target_rms_db == -18.0
        assert schema.output_target_rms_db == -14.0
        assert schema.method == "rms"
        assert schema.headroom_db == -1.0

    def test_file_hashes_schema(self) -> None:
        """Test FileHashesSchema with optional fields."""
        # With all fields
        schema = FileHashesSchema(
            di_track_sha256="abc123",
            nam_model_sha256="def456",
            ir_sha256="ghi789",
        )
        assert schema.di_track_sha256 == "abc123"

        # With only required field
        schema2 = FileHashesSchema(di_track_sha256="abc123")
        assert schema2.nam_model_sha256 is None
        assert schema2.ir_sha256 is None

    def test_processing_metadata_full_schema_from_dataclass(
        self, tmp_path: Path
    ) -> None:
        """Test creating full schema from dataclass."""
        di_track = tmp_path / "di.wav"
        di_track.write_bytes(b"di content")

        metadata = create_processing_metadata(di_track=di_track)
        schema = ProcessingMetadataFullSchema.from_dataclass(metadata)

        assert schema.versions.pipeline != ""
        assert schema.audio_settings.sample_rate == 48000
        assert schema.file_hashes.di_track_sha256 != ""

    def test_processing_metadata_full_schema_json(self) -> None:
        """Test JSON serialization of full schema."""
        schema = ProcessingMetadataFullSchema(
            versions=ProcessingVersionsSchema(
                pedalboard="0.9.19",
                nam_vst="0.7.13",
                ffmpeg="6.1.1",
                pipeline="0.1.0",
                python="3.12.0",
            ),
            audio_settings=AudioSettingsSchema(
                sample_rate=48000,
                bit_depth=32,
                channels=2,
            ),
            normalization=NormalizationSettingsSchema(),
            file_hashes=FileHashesSchema(di_track_sha256="abc123"),
            processed_at="2024-01-01T00:00:00Z",
            total_duration_ms=30000,
            segment_count=3,
        )

        json_str = schema.model_dump_json()

        assert "pedalboard" in json_str
        assert "sample_rate" in json_str
        assert "di_track_sha256" in json_str
