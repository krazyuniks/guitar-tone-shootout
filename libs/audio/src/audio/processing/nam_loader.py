"""NAM (Neural Amp Modeler) model loader with LRU caching.

This module provides functionality to load NAM models using PyTorch directly,
without requiring the neural-amp-modeler library (which has Python 3.12 compatibility issues).
"""

from functools import lru_cache
from pathlib import Path

import torch


class NAMLoadError(Exception):
    """Exception raised when NAM model loading fails."""

    pass


@lru_cache(maxsize=10)
def load_nam_model(
    model_path: Path,
) -> tuple[torch.nn.Module, int]:
    """Load a NAM model from file with LRU caching.

    Args:
        model_path: Path to the .nam model file

    Returns:
        Tuple of (model, sample_rate) where model is the loaded PyTorch model
        and sample_rate is the expected audio sample rate (default 48000 Hz)

    Raises:
        NAMLoadError: If the model file doesn't exist or cannot be loaded

    Note:
        Models are cached using LRU (Least Recently Used) cache with a default
        size of 10 models. The cache key is based on the file path.
    """
    # Validate file exists
    if not model_path.exists():
        raise NAMLoadError(f"Model file not found: {model_path}")

    if not model_path.is_file():
        raise NAMLoadError(f"Path is not a file: {model_path}")

    try:
        # Load the model checkpoint
        # NAM models are PyTorch checkpoints with 'model' and optionally 'sample_rate' keys
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)

        # Extract model state dict
        if isinstance(checkpoint, dict):
            if "model" in checkpoint:
                model_state = checkpoint["model"]
                sample_rate = checkpoint.get("sample_rate", 48000)
            else:
                # Checkpoint is already the state dict
                model_state = checkpoint
                sample_rate = 48000
        else:
            raise NAMLoadError(
                f"Unexpected checkpoint format: expected dict, got {type(checkpoint)}"
            )

        # Create a simple model wrapper
        # NAM models are typically feed-forward networks with specific architectures
        # For now, we'll load the state dict into a generic Sequential model
        # This is a simplified approach - production code would need to reconstruct
        # the exact NAM architecture
        model = _create_nam_model(model_state)

        return model, sample_rate

    except Exception as e:
        if isinstance(e, NAMLoadError):
            raise
        raise NAMLoadError(f"Failed to load NAM model from {model_path}: {e}") from e


def _create_nam_model(state_dict: dict[str, torch.Tensor]) -> torch.nn.Module:
    """Create a NAM model from state dictionary.

    This is a simplified implementation that creates a model compatible with
    the loaded state dict. In a production system, this would need to
    reconstruct the exact NAM architecture based on metadata.

    Args:
        state_dict: Model state dictionary

    Returns:
        Loaded PyTorch model

    Raises:
        NAMLoadError: If model cannot be created
    """
    try:
        # Create a simple sequential model
        # NAM models typically have input layer -> hidden layers -> output layer
        # This is a placeholder implementation
        model = torch.nn.Sequential(
            torch.nn.Linear(1, 1)  # Placeholder - real NAM models have more complex architecture
        )

        # Load the state dict
        model.load_state_dict(state_dict, strict=False)

        # Set to evaluation mode
        model.eval()

        return model

    except Exception as e:
        raise NAMLoadError(f"Failed to create NAM model: {e}") from e
