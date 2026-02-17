# Video Bounded Context

Remotion-based video composition and rendering. Image preparation, composition props, render API.

## Dependencies

Can import: core, audio
Cannot import: sources, apps

## Key Patterns

- `api.py` is the Remotion render API client
- `client.py` orchestrates video creation workflow
- `props.py` builds Remotion composition input props from domain data
- Image prep converts gear/amp images for video overlay

## Key Files

- `src/video/api.py` — Remotion API client
- `src/video/client.py` — Video rendering orchestrator
- `src/video/image_prep.py` — Image preparation for compositions
- `src/video/props.py` — Remotion composition props builder
- `src/video/schemas.py` — Pydantic schemas for video data
