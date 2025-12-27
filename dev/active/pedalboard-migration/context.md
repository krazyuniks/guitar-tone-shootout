# Pedalboard NAM Migration Context

**Issue:** #56
**Branch:** 56-pedalboard-nam-migration
**Started:** 2025-12-26

## Summary

Migrate audio processing from PyTorch-based `neural-amp-modeler` to Spotify's Pedalboard with the NAM VST3 plugin.

## Key Discovery

The NAM VST3 plugin doesn't expose model path as a parameter, but we CAN programmatically generate VST3 presets with embedded model paths. The PoC at `~/Work/pedalboard_nam_poc/` proves this works.

## VST3 Preset Format

```
Header (48 bytes): magic + version + class_id + chunk_offset
NAM State (iPlug2):
  - "###NeuralAmpModeler###" (marker)
  - "0.7.13" (version)
  - "/path/to/model.nam" (model path!)
  - "/path/to/ir.wav" (optional)
  - 12 double parameters
```

## New Modules

1. **preset.py** - VST3 preset generation for NAM
2. **normalize.py** - RMS/LUFS volume normalization

## Files Modified

- `pipeline/src/guitar_tone_shootout/preset.py` (NEW)
- `pipeline/src/guitar_tone_shootout/normalize.py` (NEW)
- `pipeline/src/guitar_tone_shootout/audio.py` (REFACTOR)
- `pipeline/pyproject.toml` (UPDATE deps)
- `backend/Dockerfile.dev` (ADD NAM VST3)
- `backend/Dockerfile` (ADD NAM VST3)

## PoC Reference

Key functions from `~/Work/pedalboard_nam_poc/poc.py`:
- `create_nam_state()` - Creates iPlug2 state bytes
- `create_vst3_preset()` - Creates full VST3 preset
- `generate_nam_preset()` - Main entry point

## Architecture Change

```
Before:
  DI → [PyTorch NAM] → [Pedalboard Effects] → Output

After:
  DI → [Pedalboard: NAM VST3 + Effects] → Output
```

## Benefits

- Parallel A/B with `pedalboard.Mix()`
- C++ performance vs Python/PyTorch
- Remove ~2GB PyTorch dependency
- Unified processing graph
