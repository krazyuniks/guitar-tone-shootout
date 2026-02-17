"""Tests for NAM model loader."""

import json
from pathlib import Path

import numpy as np
import pytest

from audio.processing.nam_loader import (
    NAMLoadError,
    NAMModel,
    clear_model_cache,
    get_cached_model,
    load_nam_model,
)


def _create_minimal_nam_file(path: Path) -> None:
    """Create a minimal valid .nam file (WaveNet architecture).

    Instantiates a tiny WaveNet directly to extract valid weights,
    then writes the JSON config that init_from_nam expects.
    """
    import sys
    import types

    for mod_name in ("nam.train", "nam.train.colab"):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    from nam.models.wavenet import WaveNet

    layer_config = {
        "input_size": 1,
        "condition_size": 1,
        "head_size": 1,
        "channels": 1,
        "kernel_size": 2,
        "dilations": [1],
        "activation": "Tanh",
        "gated": False,
        "head_bias": False,
    }
    wavenet_config = {
        "layers": [layer_config],
        "head": None,
        "head_scale": 0.02,
    }

    # Create model to get valid weights
    model = WaveNet(
        layers_configs=wavenet_config["layers"],
        head_config=wavenet_config["head"],
        head_scale=wavenet_config["head_scale"],
        sample_rate=48000,
    )
    weights = []
    for p in model.parameters():
        weights.extend(p.detach().cpu().numpy().flatten().tolist())

    config = {
        "version": "0.5.4",
        "architecture": "WaveNet",
        "config": wavenet_config,
        "weights": weights,
        "sample_rate": 48000,
        "metadata": {},
    }

    with open(path, "w") as f:
        json.dump(config, f)


class TestLoadNAMModel:
    """Tests for load_nam_model function."""

    def setup_method(self) -> None:
        clear_model_cache()

    def test_load_nam_model_success(self, tmp_path: Path) -> None:
        """Test successful NAM model loading from .nam JSON file."""
        model_path = tmp_path / "test.nam"
        _create_minimal_nam_file(model_path)

        result = load_nam_model(model_path)

        assert isinstance(result, NAMModel)
        assert result.path == model_path
        assert result.sample_rate == 48000

    def test_load_nam_model_process(self, tmp_path: Path) -> None:
        """Test that loaded model can process audio."""
        model_path = tmp_path / "test.nam"
        _create_minimal_nam_file(model_path)

        model = load_nam_model(model_path)
        audio = np.random.randn(1000).astype(np.float32)
        result = model.process(audio)

        assert isinstance(result, np.ndarray)
        assert result.shape == audio.shape
        assert result.dtype == np.float32

    def test_load_nam_model_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading nonexistent file raises FileNotFoundError."""
        model_path = tmp_path / "nonexistent.nam"

        with pytest.raises(FileNotFoundError, match="NAM model not found"):
            load_nam_model(model_path)

    def test_load_nam_model_invalid_format(self, tmp_path: Path) -> None:
        """Test loading invalid file raises NAMLoadError."""
        model_path = tmp_path / "invalid.nam"
        model_path.write_text("not a valid model file")

        with pytest.raises(NAMLoadError, match="Failed to load NAM model"):
            load_nam_model(model_path)

    def test_get_cached_model(self, tmp_path: Path) -> None:
        """Test that get_cached_model returns same instance."""
        model_path = tmp_path / "test.nam"
        _create_minimal_nam_file(model_path)

        model1 = get_cached_model(str(model_path))
        model2 = get_cached_model(str(model_path))

        assert model1 is model2

    def test_clear_model_cache(self, tmp_path: Path) -> None:
        """Test that clear_model_cache resets the cache."""
        model_path = tmp_path / "test.nam"
        _create_minimal_nam_file(model_path)

        model1 = get_cached_model(str(model_path))
        clear_model_cache()
        model2 = get_cached_model(str(model_path))

        assert model1 is not model2
