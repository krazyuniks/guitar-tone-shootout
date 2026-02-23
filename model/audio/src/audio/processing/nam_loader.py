"""NAM (Neural Amp Modeler) model loader with LRU caching.

Loads .nam files (JSON format) using nam.models.init_from_nam() to
reconstruct WaveNet models for PyTorch inference.
"""

from __future__ import annotations

import json
import logging
import sys
import types
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import torch
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class NAMLoadError(Exception):
    """Exception raised when NAM model loading fails."""


class NAMModel:
    """Wrapper for a loaded NAM PyTorch model."""

    def __init__(self, model: torch.nn.Module, path: Path) -> None:
        self._model = model
        self.path = path
        self.sample_rate: float | None = getattr(model, "sample_rate", None)

    def process(self, audio: NDArray[np.float32]) -> NDArray[np.float32]:
        """Process audio through the NAM model (batch inference)."""
        import numpy as np
        import torch as th

        x = th.tensor(audio, dtype=th.float32)
        with th.no_grad():
            y = self._model(x, pad_start=True)
        result: NDArray[np.float32] = y.cpu().numpy().astype(np.float32)
        return result


def load_nam_model(model_path: Path) -> NAMModel:
    """Load a NAM model from a .nam JSON file.

    Raises:
        FileNotFoundError: If file doesn't exist.
        NAMLoadError: If loading/parsing fails.
    """
    if not model_path.exists():
        raise FileNotFoundError(f"NAM model not found: {model_path}")

    try:
        # nam.__init__ imports nam.train which requires tkinter (not available
        # in headless Docker). Pre-register dummy modules to skip that import
        # path — we only need nam.models for inference.
        for mod_name in ("nam.train", "nam.train.colab"):
            if mod_name not in sys.modules:
                sys.modules[mod_name] = types.ModuleType(mod_name)

        from nam.models import init_from_nam

        with model_path.open() as fp:
            config = json.load(fp)
        model = init_from_nam(config)
        # Set to inference mode (no gradient computation)
        model.train(False)
        return NAMModel(model, model_path)
    except FileNotFoundError:
        raise
    except Exception as e:
        raise NAMLoadError(f"Failed to load NAM model: {model_path}") from e


@lru_cache(maxsize=32)
def get_cached_model(model_path: str) -> NAMModel:
    """Load a NAM model with LRU caching (keyed by path string)."""
    return load_nam_model(Path(model_path))


def clear_model_cache() -> None:
    """Clear the model cache."""
    get_cached_model.cache_clear()
