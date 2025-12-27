# Pipeline Development Skill

Use this skill when working on the `pipeline/` subproject.

## Context

The pipeline processes DI guitar tracks through NAM models and IRs to create comparison videos.

## Key Technologies

- **NAM (Neural Amp Modeler)**: Load models with `nam.models.init_from_nam(json.load(fp))`
- **Pedalboard**: Spotify's audio effects library for IR convolution and effects
- **FFmpeg**: Video/audio encoding and manipulation
- **Playwright**: HTML to PNG rendering for comparison images

## Architecture

```
DI Track → Silence Trim → NAM Model → IR Convolution → Effects → FLAC
                                                                    ↓
                              HTML Template → Playwright → PNG Image
                                                                    ↓
                              Image + Audio → FFmpeg → Video Clip → Master MP4
```

## Key Patterns

### NAM Model Loading (Lazy Import)
```python
def load_nam_model(path: Path) -> Any:
    """Load NAM model from .nam file."""
    import torch
    from nam.models import init_from_nam

    with open(path) as f:
        model_data = json.load(f)
    model = init_from_nam(model_data)
    model.eval()
    return model
```

### Pedalboard Processing
```python
from pedalboard import Pedalboard, Convolution, Reverb, Delay

board = Pedalboard([
    Convolution(ir_path, mix=1.0),
    Reverb(room_size=0.3),
])
processed = board(audio, sample_rate)
```

### FFmpeg Commands
```python
# Silence trimming
ffmpeg -i input.wav -af silenceremove=1:0:-50dB output.wav

# Create video clip from image + audio
ffmpeg -loop 1 -i image.png -i audio.flac -c:v libx264 -tune stillimage \
    -c:a aac -b:a 384k -ar 48000 -shortest output.mp4

# Concatenate clips
ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4
```

## Testing

```bash
cd pipeline
just test                    # Run all tests
just test-cov               # With coverage
uv run pytest -k "audio"    # Run specific tests
```

## Common Issues

1. **NAM model fails**: Check JSON validity, PyTorch version
2. **Pedalboard IR fails**: Ensure WAV is mono, correct sample rate
3. **FFmpeg errors**: Check codec availability, file permissions
