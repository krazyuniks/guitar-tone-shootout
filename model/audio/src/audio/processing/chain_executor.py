"""Signal chain execution with block-by-block sequential processing.

This module provides functionality to execute a complete signal chain by
processing audio through each block in position order, enforcing grammar
constraints for FULL_RIG vs HEAD configurations.

Execution is synchronous CPU-bound DSP (NAM inference, IR convolution) and
holds no async work; async callers must run it off the event loop
(asyncio.to_thread) so health endpoints and lease heartbeats stay responsive.
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from pedalboard import Pedalboard  # type: ignore[attr-defined]

from audio.processing.ir_loader import IRLoadError, load_ir
from audio.processing.nam_loader import NAMLoadError, get_cached_model

if TYPE_CHECKING:
    from gts.domain.entities.signal_chain import SignalChain, SignalChainBlock
    from gts.domain.value_objects.signal_chain_enums import GearType
else:
    from gts.domain.entities.signal_chain import SignalChain, SignalChainBlock
    from gts.domain.value_objects.signal_chain_enums import (
        GearType,  # type: ignore[import-untyped]
    )


class ChainExecutionError(Exception):
    """Exception raised when signal chain execution fails."""

    pass


def execute_signal_chain(
    chain: SignalChain,
    di_audio: np.ndarray,
    sample_rate: int,
    gear_path_resolver: Callable[[str, GearType], Path],
) -> np.ndarray:
    """Execute a signal chain by processing audio through each block.

    Processes audio sequentially through each block in position order:
    1. Sort blocks by position (PRE -> AMP -> LOOP -> IR -> POST)
    2. Validate chain constraints (FULL_RIG vs HEAD)
    3. Process audio through each block sequentially

    Args:
        chain: The signal chain to execute
        di_audio: Input DI audio as numpy array
        sample_rate: Sample rate of the audio in Hz
        gear_path_resolver: Function mapping (user_gear_id, gear_type) -> file Path

    Returns:
        Processed audio as numpy array

    Raises:
        ChainExecutionError: If chain is invalid or execution fails

    Examples:
        >>> def resolver(user_gear_id, gear_type):
        ...     return Path(f"/gear/{user_gear_id}.nam")
        >>> result = execute_signal_chain(
        ...     chain=my_chain,
        ...     di_audio=audio,
        ...     sample_rate=48000,
        ...     gear_path_resolver=resolver,
        ... )
    """
    # Validate chain is not empty
    if not chain.blocks:
        raise ChainExecutionError("Cannot execute empty signal chain (no blocks)")

    # Sort blocks by position for sequential processing
    sorted_blocks = sorted(chain.blocks, key=lambda b: b.position)

    # Validate chain constraints
    _validate_chain_constraints(sorted_blocks)

    # Process audio through each block
    current_audio = di_audio.copy()

    for block in sorted_blocks:
        # Resolve gear file path
        gear_path = gear_path_resolver(str(block.user_gear_id), block.gear_type)

        # Process based on gear type
        if block.gear_type in (
            GearType.AMP,
            GearType.FULL_RIG,
            GearType.PEDAL,
            GearType.POST_EFFECT,
        ):
            # NAM model processing
            current_audio = _process_nam_block(
                audio=current_audio,
                sample_rate=sample_rate,
                model_path=gear_path,
            )
        elif block.gear_type == GearType.IR:
            # IR convolution processing
            current_audio = _process_ir_block(
                audio=current_audio,
                sample_rate=sample_rate,
                ir_path=gear_path,
            )
        else:
            raise ChainExecutionError(f"Unsupported gear type for execution: {block.gear_type}")

    return current_audio


def _validate_chain_constraints(blocks: list["SignalChainBlock"]) -> None:
    """Validate signal chain grammar constraints.

    Rules:
    - FULL_RIG cannot be used with IR (IR is baked in)
    - AMP (HEAD) requires IR after it

    Args:
        blocks: List of blocks sorted by position

    Raises:
        ChainExecutionError: If constraints are violated
    """
    has_amp = any(b.gear_type == GearType.AMP for b in blocks)
    has_full_rig = any(b.gear_type == GearType.FULL_RIG for b in blocks)
    has_ir = any(b.gear_type == GearType.IR for b in blocks)

    # FULL_RIG constraint: Cannot have IR with FULL_RIG
    if has_full_rig and has_ir:
        raise ChainExecutionError(
            "Invalid chain: FULL_RIG configuration cannot include IR block "
            "(IR is already baked into the full rig capture)"
        )

    # HEAD constraint: AMP requires IR
    if has_amp and not has_ir:
        raise ChainExecutionError(
            "Invalid chain: AMP (head) configuration requires an IR block (cabinet simulation)"
        )


def _process_nam_block(
    audio: np.ndarray,
    sample_rate: int,
    model_path: Path,
) -> np.ndarray:
    """Process audio through a NAM model block.

    Args:
        audio: Input audio array
        sample_rate: Sample rate in Hz
        model_path: Path to .nam model file

    Returns:
        Processed audio array

    Raises:
        ChainExecutionError: If NAM processing fails
    """
    try:
        model = get_cached_model(str(model_path))
        return model.process(audio.astype(np.float32))
    except NAMLoadError as e:
        raise ChainExecutionError(f"Failed to load NAM model: {e}") from e
    except Exception as e:
        raise ChainExecutionError(f"NAM processing failed: {e}") from e


def _process_ir_block(
    audio: np.ndarray,
    sample_rate: int,
    ir_path: Path,
) -> np.ndarray:
    """Process audio through an IR convolution block.

    Args:
        audio: Input audio array
        sample_rate: Sample rate in Hz
        ir_path: Path to IR file (.wav or .flac)

    Returns:
        Processed audio array

    Raises:
        ChainExecutionError: If IR processing fails
    """
    try:
        # Load IR as Pedalboard Convolution effect
        convolution = load_ir(ir_path)

        # Apply convolution using Pedalboard
        board = Pedalboard([convolution])
        result = board(audio, sample_rate)

        return result

    except IRLoadError as e:
        raise ChainExecutionError(f"Failed to load IR: {e}") from e
    except Exception as e:
        raise ChainExecutionError(f"IR processing failed: {e}") from e
