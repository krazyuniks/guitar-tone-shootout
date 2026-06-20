# Audio Bounded Context

Audio processing pipeline: NAM model loading, IR loading, pedalboard chain execution, loudness normalisation.

## Dependencies

Can import: gts
Cannot import: video, sources, apps

## Key Patterns

- `processing/processor.py` orchestrates the full audio pipeline
- Chain executor runs signal chains through pedalboard
- NAM/IR loaders handle model file I/O
- All audio processing is synchronous CPU-bound work (runs in worker, not webapp)

## Key Files

- `src/audio/processing/processor.py` — Main audio processing orchestrator
- `src/audio/processing/chain_executor.py` — Signal chain execution
- `src/audio/processing/nam_loader.py` — NAM model loading
- `src/audio/processing/ir_loader.py` — Impulse response loading
- `src/audio/analysis/waveform.py` — Waveform analysis
