"""Tests for the pipeline service."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.pipeline_service import (
    EffectConfig,
    PipelineError,
    PipelineService,
    ShootoutConfig,
    ToneConfig,
)
from app.tasks.shootout import _parse_config


def _has_pipeline_module() -> bool:
    """Check if the guitar_tone_shootout module is available."""
    try:
        import guitar_tone_shootout.config  # noqa: F401

        return True
    except ImportError:
        return False


class TestShootoutConfig:
    """Tests for ShootoutConfig and related classes."""

    def test_shootout_config_creation(self):
        """Test basic ShootoutConfig creation."""
        tones = [
            ToneConfig(
                name="Plexi",
                model_path="tone3000/jcm800/model.nam",
                ir_path="greenback.wav",
            ),
            ToneConfig(
                name="High Gain",
                model_path="tone3000/mesa/model.nam",
                highpass=False,
            ),
        ]

        config = ShootoutConfig(
            name="Test Shootout",
            tones=tones,
            author="Test User",
            guitar="Stratocaster",
            pickup="Bridge",
        )

        assert config.name == "Test Shootout"
        assert len(config.tones) == 2
        assert config.author == "Test User"
        assert config.guitar == "Stratocaster"
        assert config.tones[0].highpass is True
        assert config.tones[1].highpass is False

    def test_tone_config_with_effects(self):
        """Test ToneConfig with additional effects."""
        effects = [
            EffectConfig(effect_type="eq", value="lowpass_12k"),
            EffectConfig(effect_type="reverb", value="room"),
        ]

        tone = ToneConfig(
            name="Ambient Lead",
            model_path="model.nam",
            effects=effects,
        )

        assert len(tone.effects) == 2
        assert tone.effects[0].effect_type == "eq"
        assert tone.effects[1].value == "room"


class TestParseConfig:
    """Tests for JSON configuration parsing."""

    def test_parse_basic_config(self):
        """Test parsing a basic configuration."""
        config_data = {
            "name": "Test Comparison",
            "author": "Test User",
            "guitar": "Les Paul",
            "pickup": "Neck Humbucker",
            "tones": [
                {
                    "name": "Clean Tone",
                    "model_path": "clean.nam",
                    "ir_path": "cabinet.wav",
                    "highpass": True,
                }
            ],
        }

        config = _parse_config(json.dumps(config_data))

        assert config.name == "Test Comparison"
        assert config.author == "Test User"
        assert config.guitar == "Les Paul"
        assert len(config.tones) == 1
        assert config.tones[0].name == "Clean Tone"
        assert config.tones[0].model_path == "clean.nam"

    def test_parse_config_with_effects(self):
        """Test parsing configuration with effects."""
        config_data = {
            "name": "Effects Test",
            "tones": [
                {
                    "name": "Lead Tone",
                    "model_path": "lead.nam",
                    "effects": [
                        {"effect_type": "eq", "value": "highshelf_presence"},
                        {"effect_type": "delay", "value": "slapback"},
                    ],
                }
            ],
        }

        config = _parse_config(json.dumps(config_data))

        assert len(config.tones[0].effects) == 2
        assert config.tones[0].effects[0].effect_type == "eq"
        assert config.tones[0].effects[1].value == "slapback"

    def test_parse_config_multiple_tones(self):
        """Test parsing configuration with multiple tones."""
        config_data = {
            "name": "Multi-tone Test",
            "tones": [
                {"name": "Tone 1", "model_path": "model1.nam"},
                {"name": "Tone 2", "model_path": "model2.nam"},
                {"name": "Tone 3", "model_path": "model3.nam"},
            ],
        }

        config = _parse_config(json.dumps(config_data))

        assert len(config.tones) == 3
        assert config.tones[0].name == "Tone 1"
        assert config.tones[2].name == "Tone 3"


class TestPipelineService:
    """Tests for PipelineService."""

    @pytest.fixture
    def mock_progress_callback(self):
        """Create a mock async progress callback."""
        return AsyncMock()

    @pytest.fixture
    def pipeline_service(self, mock_progress_callback, tmp_path):
        """Create a PipelineService instance for testing."""
        return PipelineService(
            progress_callback=mock_progress_callback,
            data_dir=tmp_path,
        )

    def test_service_initialization(self, pipeline_service, tmp_path):
        """Test PipelineService initialization."""
        assert pipeline_service.data_dir == tmp_path
        assert pipeline_service.uploads_dir == tmp_path / "uploads"
        assert pipeline_service.models_dir == tmp_path / "models"
        assert pipeline_service.outputs_dir == tmp_path / "outputs"

    async def test_progress_callback_invocation(
        self, pipeline_service, mock_progress_callback
    ):
        """Test that progress callback is properly invoked."""
        await pipeline_service._progress(50, "Test message")

        mock_progress_callback.assert_called_once_with(50, "Test message")

    async def test_run_shootout_creates_output_dir(
        self, pipeline_service, tmp_path, mock_progress_callback
    ):
        """Test that run_shootout creates the output directory."""
        # Mock the pipeline library to avoid actual processing
        with patch(
            "app.services.pipeline_service.PipelineService._process_comparison"
        ) as mock_process:
            mock_process.return_value = tmp_path / "outputs" / "test-job" / "video.mp4"

            config = ShootoutConfig(
                name="Test",
                tones=[ToneConfig(name="Tone 1", model_path="test.nam")],
            )

            try:
                await pipeline_service.run_shootout(
                    job_id="test-job",
                    config=config,
                    di_track_path=tmp_path / "test.wav",
                )
            except (PipelineError, FileNotFoundError):
                # Expected since we don't have actual files
                pass

            # Output directory should be created
            assert (tmp_path / "outputs" / "test-job").exists()

    @pytest.mark.skipif(
        not _has_pipeline_module(),
        reason="guitar_tone_shootout module not installed",
    )
    async def test_build_comparison_creates_valid_object(
        self, pipeline_service, tmp_path
    ):
        """Test that _build_comparison creates a valid Comparison object."""
        config = ShootoutConfig(
            name="Test Shootout",
            tones=[
                ToneConfig(
                    name="Plexi",
                    model_path="plexi.nam",
                    ir_path="greenback.wav",
                    highpass=True,
                ),
                ToneConfig(
                    name="Mesa",
                    model_path="mesa.nam",
                    highpass=False,
                ),
            ],
            author="Test Author",
            guitar="Strat",
            pickup="Bridge",
        )

        output_dir = tmp_path / "outputs" / "test-job"
        output_dir.mkdir(parents=True)

        di_track_path = tmp_path / "test.wav"
        di_track_path.touch()

        comparison = await pipeline_service._build_comparison(
            config=config,
            di_track_path=di_track_path,
            output_dir=output_dir,
        )

        assert comparison.meta.name == "Test Shootout"
        assert comparison.meta.author == "Test Author"
        assert len(comparison.di_tracks) == 1
        assert comparison.di_tracks[0].guitar == "Strat"
        assert len(comparison.signal_chains) == 2
        assert comparison.signal_chains[0].name == "Plexi"

        # Check highpass filter is in first chain, not in second
        first_chain_types = [e.effect_type for e in comparison.signal_chains[0].chain]
        second_chain_types = [e.effect_type for e in comparison.signal_chains[1].chain]
        assert "eq" in first_chain_types
        assert "eq" not in second_chain_types


class TestShootoutSchemas:
    """Tests for Pydantic schemas."""

    def test_shootout_config_schema_validation(self):
        """Test ShootoutConfigSchema validation."""
        from app.schemas.shootout import ShootoutConfigSchema, ToneSchema

        # Valid configuration
        config = ShootoutConfigSchema(
            name="Test Shootout",
            tones=[
                ToneSchema(name="Tone 1", model_path="model.nam"),
            ],
        )
        assert config.name == "Test Shootout"

    def test_shootout_config_schema_requires_tones(self):
        """Test that ShootoutConfigSchema requires at least one tone."""
        from pydantic import ValidationError

        from app.schemas.shootout import ShootoutConfigSchema

        with pytest.raises(ValidationError):
            ShootoutConfigSchema(name="Test", tones=[])

    def test_shootout_config_schema_max_tones(self):
        """Test that ShootoutConfigSchema limits tones to 10."""
        from pydantic import ValidationError

        from app.schemas.shootout import ShootoutConfigSchema, ToneSchema

        with pytest.raises(ValidationError):
            ShootoutConfigSchema(
                name="Test",
                tones=[ToneSchema(name=f"Tone {i}") for i in range(11)],
            )
