"""Tests for NAM model loader."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

from audio.processing.nam_loader import NAMLoadError, load_nam_model


class TestLoadNAMModel:
    """Tests for load_nam_model function."""

    def test_load_nam_model_success(self, tmp_path: Path) -> None:
        """Test successful NAM model loading."""
        # Create a mock NAM model file
        model_path = tmp_path / "test.nam"

        # Create a simple PyTorch model and save it
        mock_model = torch.nn.Linear(1, 1)
        torch.save({"model": mock_model.state_dict(), "sample_rate": 48000}, model_path)

        # Load the model
        model, sample_rate = load_nam_model(model_path)

        assert model is not None
        assert sample_rate == 48000
        assert isinstance(model, torch.nn.Module)

    def test_load_nam_model_caches_result(self, tmp_path: Path) -> None:
        """Test that loaded models are cached."""
        model_path = tmp_path / "test.nam"

        # Create and save model
        mock_model = torch.nn.Linear(1, 1)
        torch.save({"model": mock_model.state_dict(), "sample_rate": 48000}, model_path)

        # Load twice
        model1, _ = load_nam_model(model_path)
        model2, _ = load_nam_model(model_path)

        # Should return the same cached instance
        assert model1 is model2

    def test_load_nam_model_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading nonexistent file raises NAMLoadError."""
        model_path = tmp_path / "nonexistent.nam"

        with pytest.raises(NAMLoadError, match="Model file not found"):
            load_nam_model(model_path)

    def test_load_nam_model_invalid_format(self, tmp_path: Path) -> None:
        """Test loading invalid file raises NAMLoadError."""
        model_path = tmp_path / "invalid.nam"
        model_path.write_text("not a valid model file")

        with pytest.raises(NAMLoadError, match="Failed to load NAM model"):
            load_nam_model(model_path)

    def test_load_nam_model_missing_sample_rate(self, tmp_path: Path) -> None:
        """Test loading model without sample_rate metadata."""
        model_path = tmp_path / "no_sr.nam"

        # Save model without sample_rate
        mock_model = torch.nn.Linear(1, 1)
        torch.save({"model": mock_model.state_dict()}, model_path)

        # Should use default sample rate
        model, sample_rate = load_nam_model(model_path)

        assert model is not None
        assert sample_rate == 48000  # Default

    def test_lru_cache_size_limit(self, tmp_path: Path) -> None:
        """Test that cache respects size limit."""
        # Create 11 different model files (default cache size is 10)
        models = []
        for i in range(11):
            model_path = tmp_path / f"model_{i}.nam"
            mock_model = torch.nn.Linear(1, 1)
            torch.save({"model": mock_model.state_dict(), "sample_rate": 48000}, model_path)
            models.append(model_path)

        # Load all models
        loaded_models = []
        for model_path in models:
            model, _ = load_nam_model(model_path)
            loaded_models.append(model)

        # First model should have been evicted from cache
        # Loading it again should create a new instance
        model_first_again, _ = load_nam_model(models[0])
        assert model_first_again is not loaded_models[0]

        # Most recent model should still be cached
        model_last_again, _ = load_nam_model(models[-1])
        assert model_last_again is loaded_models[-1]
