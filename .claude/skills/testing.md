# Testing Skill

Use this skill when writing or debugging tests.

## Test Framework

- **pytest**: Test runner
- **pytest-cov**: Coverage reporting
- **tmp_path**: Built-in fixture for temporary directories

## Project Test Structure

```
pipeline/
└── tests/
    ├── __init__.py
    ├── conftest.py          # Shared fixtures
    ├── test_config.py       # Config parsing tests
    ├── test_audio.py        # Audio processing tests
    └── test_pipeline.py     # Pipeline tests
```

## Test Patterns

### Basic Test
```python
import pytest
from pathlib import Path
from guitar_tone_shootout.config import parse_comparison

def test_parse_valid_config(tmp_path: Path) -> None:
    """Should parse valid INI configuration."""
    config_path = tmp_path / "test.ini"
    config_path.write_text("""
[meta]
name = Test Comparison

[di_tracks]
1 = test.wav
""")

    result = parse_comparison(config_path)

    assert result.meta.name == "Test Comparison"
    assert len(result.di_tracks) == 1
```

### Testing Exceptions
```python
def test_missing_section_raises(tmp_path: Path) -> None:
    """Should raise ConfigError for missing section."""
    config_path = tmp_path / "test.ini"
    config_path.write_text("[meta]\nname = Test\n")

    with pytest.raises(ConfigError, match="Missing required section"):
        parse_comparison(config_path)
```

### Fixtures in conftest.py
```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    """Create a sample valid config file."""
    config = tmp_path / "sample.ini"
    config.write_text("""
[meta]
name = Sample Comparison
guitar = Test Guitar

[di_tracks]
1 = test.wav

[signal_chains]
chain1 = amp1 > cab1
""")
    return config

@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    """Create a sample audio file (silent)."""
    import numpy as np
    import soundfile as sf

    audio = np.zeros((44100,), dtype=np.float32)  # 1 second of silence
    path = tmp_path / "test.wav"
    sf.write(path, audio, 44100)
    return path
```

### Parametrized Tests
```python
@pytest.mark.parametrize("effect,expected_type", [
    ("eq_bright", EQEffect),
    ("reverb_room", ReverbEffect),
    ("delay_short", DelayEffect),
])
def test_effect_presets(effect: str, expected_type: type) -> None:
    """Should create correct effect type from preset."""
    result = create_effect(effect)
    assert isinstance(result, expected_type)
```

### Mocking Heavy Dependencies
```python
from unittest.mock import Mock, patch

def test_process_with_mock_nam(tmp_path: Path) -> None:
    """Should process audio with mocked NAM model."""
    mock_model = Mock()
    mock_model.return_value = torch.zeros((1, 44100))

    with patch("guitar_tone_shootout.audio.load_nam_model", return_value=mock_model):
        result = process_audio(input_path, output_path, "model.nam")

    mock_model.assert_called_once()
    assert output_path.exists()
```

## Running Tests

```bash
# All tests
cd pipeline && just test

# With coverage
cd pipeline && just test-cov

# Specific file
uv run pytest tests/test_config.py

# Specific test
uv run pytest tests/test_config.py::test_parse_valid_config

# With output
uv run pytest -v -s

# Stop on first failure
uv run pytest -x
```

## Coverage

Target: 80%+ coverage on new code.

```bash
cd pipeline
uv run pytest --cov=src/guitar_tone_shootout --cov-report=term-missing
```
