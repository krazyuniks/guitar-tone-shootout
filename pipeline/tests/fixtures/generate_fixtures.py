#!/usr/bin/env python3
"""
Generate test fixture files.

Run this script to create/regenerate test audio files:
    cd pipeline && uv run python tests/fixtures/generate_fixtures.py
"""

from pathlib import Path

import numpy as np
from pedalboard.io import AudioFile


def generate_test_di(output_path: Path, duration: float = 2.0) -> None:
    """Generate a test DI track (guitar-like harmonics)."""
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    # Simulate guitar-like sound with fundamental + harmonics
    fundamental = 82.41  # E2 note
    audio = np.zeros_like(t, dtype=np.float32)

    # Add harmonics with decreasing amplitude
    for harmonic in range(1, 8):
        amplitude = 0.3 / harmonic
        audio += amplitude * np.sin(2 * np.pi * fundamental * harmonic * t)

    # Add slight decay envelope
    envelope = np.exp(-t * 0.5)
    audio = (audio * envelope).astype(np.float32)

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.8

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with AudioFile(str(output_path), "w", samplerate=sample_rate, num_channels=1) as f:
        f.write(audio.reshape(1, -1))

    print(f"Generated: {output_path} ({duration}s)")


def generate_test_ir(output_path: Path) -> None:
    """Generate a test impulse response (simple room simulation)."""
    sample_rate = 48000
    length = 4096

    # Create simple IR with initial impulse + early reflections
    ir = np.zeros(length, dtype=np.float32)

    # Main impulse
    ir[0] = 1.0

    # Early reflections (simulated)
    ir[int(0.002 * sample_rate)] = 0.3  # 2ms
    ir[int(0.005 * sample_rate)] = 0.2  # 5ms
    ir[int(0.010 * sample_rate)] = 0.1  # 10ms

    # Exponential decay tail
    decay = np.exp(-np.arange(length) / (sample_rate * 0.05))
    noise = np.random.randn(length).astype(np.float32) * 0.02
    ir += noise * decay

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with AudioFile(str(output_path), "w", samplerate=sample_rate, num_channels=1) as f:
        f.write(ir.reshape(1, -1))

    print(f"Generated: {output_path} ({length} samples)")


def generate_test_comparison_ini(output_path: Path) -> None:
    """Generate a test comparison INI file."""
    content = """# Test Comparison for Integration Tests
[meta]
name = Test Comparison
author = test_suite
description = Integration test comparison

[di_tracks]
1.file = test_di.wav
1.guitar = Test Guitar
1.pickup = test pickup
1.notes = Generated test audio

[signal_chains]
1.name = Test Chain
1.description = Simple test chain with IR only
1.chain = ir:test/test_ir.wav

2.name = Test Chain with EQ
2.description = Test chain with EQ and IR
2.chain = eq:highpass_80hz, ir:test/test_ir.wav
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    print(f"Generated: {output_path}")


def main() -> None:
    """Generate all test fixtures."""
    fixtures_dir = Path(__file__).parent

    print("Generating test fixtures...")

    generate_test_di(fixtures_dir / "di_tracks" / "test_di.wav")
    generate_test_ir(fixtures_dir / "irs" / "test_ir.wav")
    generate_test_comparison_ini(fixtures_dir / "comparisons" / "test_comparison.ini")

    print("\nDone! Fixtures generated in:", fixtures_dir)


if __name__ == "__main__":
    main()
