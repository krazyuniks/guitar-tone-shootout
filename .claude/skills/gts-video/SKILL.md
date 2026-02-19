---
name: gts-video
description: Video BC (Bounded Context) development patterns for GTS. Use when working with video composition, Remotion, rendering workflows, image preparation, or video service infrastructure.
user-invocable: false
---

# GTS Video Development Guide

Video composition layer for GTS, built on Remotion (React-based video framework). Located in `libs/video/`.

## Quick Reference

| Task | Command | Location |
|------|---------|----------|
| Open Remotion Studio | `just video-studio` | Interactive composition preview |
| Run video tests | `just video-test` | All video tests (Python + TypeScript) |
| Check TypeScript types | `just video-types` | TypeScript type checking |
| Run Python unit tests | `just tdd tests/unit/video/` | Video Python tests only |

## Project Structure

```
libs/video/
├── pyproject.toml              # Python package config
├── package.json                # Node.js dependencies (Remotion)
├── tsconfig.json               # TypeScript config
├── remotion-wrapper.js         # Remotion CLI wrapper
├── tsc-wrapper.js              # TypeScript compiler wrapper
└── src/video/
    ├── __init__.py             # Package init
    ├── api.py                  # FastAPI endpoints (POST /render, GET /health)
    ├── schemas.py              # Pydantic models for API
    ├── props.py                # Domain → Remotion props serialisation
    ├── image_prep.py           # Image preprocessing (Pillow)
    └── remotion/               # Remotion compositions
        ├── index.ts            # Remotion entry point
        ├── Root.tsx            # Root component
        └── compositions/       # React components
            ├── ShootoutVideo.tsx       # Main shootout video composition
            ├── SignalChainSegment.tsx  # Individual tone segment
            ├── GearBlock.tsx           # Gear visualization
            ├── MetadataOverlay.tsx     # Labels and text
            └── SlideTransition.tsx     # Transitions between segments
```

## Architecture

### Dependency Rules

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `video` | core, audio | sources, apps |

Enforced via `import-linter` in root `pyproject.toml`.

**Rationale:** Video layer sits above core and audio, composing domain models and audio segments into videos. It must NOT depend on application-specific concerns (webapp, worker) or data sources (T3K).

### Layer Responsibilities

- **Video API** (`api.py`): FastAPI endpoints for job submission and status polling
- **Props serialisation** (`props.py`): Convert domain entities → Remotion JSON props
- **Image preparation** (`image_prep.py`): Resize, normalise, and prepare gear images
- **Remotion compositions**: React components rendering video frames

## Video API Patterns

### FastAPI Endpoints

```python
# libs/video/src/video/api.py

from fastapi import FastAPI
from video.schemas import RenderRequest, RenderResponse, StatusResponse

@app.post("/render", response_model=RenderResponse, status_code=202)
async def render(request: RenderRequest) -> RenderResponse:
    """Submit a video render job."""
    # Returns job_id immediately (async processing)
    ...

@app.get("/render/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str) -> StatusResponse:
    """Poll render job status."""
    # Returns: pending | processing | complete | failed
    ...

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint (no auth required)."""
    ...
```

### Request/Response Schemas

```python
# libs/video/src/video/schemas.py

from pydantic import BaseModel

class RenderRequest(BaseModel):
    composition_type: str  # e.g., "ShootoutVideo"
    data: dict[str, Any]   # Composition-specific props

class RenderResponse(BaseModel):
    job_id: str

class StatusResponse(BaseModel):
    job_id: str
    status: str  # pending | processing | complete | failed
    output_path: str | None
    error_message: str | None
```

## Remotion Composition Patterns

### Composition Registration

```tsx
// libs/video/src/video/remotion/index.ts

import { Composition } from "remotion";
import { ShootoutVideo } from "./compositions/ShootoutVideo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ShootoutVideo"
        component={ShootoutVideo}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
```

### Main Composition

```tsx
// libs/video/src/video/remotion/compositions/ShootoutVideo.tsx

import { AbsoluteFill, Audio, Sequence } from "remotion";
import { SignalChainSegment } from "./SignalChainSegment";

export const ShootoutVideo: React.FC<ShootoutVideoProps> = ({ segments }) => {
  return (
    <AbsoluteFill>
      {segments.map((segment, index) => (
        <Sequence
          key={segment.id}
          from={segment.startFrame}
          durationInFrames={segment.durationInFrames}
        >
          <SignalChainSegment {...segment} />
          <Audio src={segment.audioPath} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
```

## Props Serialisation

Domain entities (core models) cannot be passed directly to Remotion (React). Convert via `props.py`:

```python
# libs/video/src/video/props.py

from core.domain.value_objects.composition_spec import CompositionSpec

def serialize_composition_props(spec: CompositionSpec) -> dict[str, Any]:
    """Convert domain model → Remotion JSON props."""
    return {
        "compositionType": spec.composition_type,
        "data": spec.data,
    }

def deserialize_composition_props(props: dict[str, Any]) -> CompositionSpec:
    """Convert Remotion props → domain model."""
    # Used for validation and reverse mapping
    ...
```

**Why separate serialisation:**
- Domain models use Python conventions (snake_case, UUIDs)
- Remotion expects JSON-serialisable props (camelCase, strings)
- Decouples domain logic from React component structure

## Image Preparation

Gear images must be preprocessed before use in Remotion compositions:

```python
# libs/video/src/video/image_prep.py

from PIL import Image

def prepare_gear_image(
    input_path: Path,
    output_path: Path,
    target_width: int = 800,
    target_height: int = 600,
) -> None:
    """Resize and normalise gear image for video composition.

    - Maintains aspect ratio
    - Adds padding if needed
    - Converts to RGB (removes alpha)
    - Saves as optimised JPEG
    """
    ...
```

**Why preprocessing:**
- Consistent sizing for composition layout
- Removes alpha channels (video doesn't support transparency)
- Optimises file size (faster rendering)

## Video Service (Docker)

### Service Definition

```yaml
# docker-compose.yml
services:
  video:
    profiles:
      - jobs  # Only runs when explicitly started
    build:
      dockerfile: infrastructure/docker/Dockerfile.video
    volumes:
      - ./libs/core:/app/libs/core:ro
      - ./libs/video:/app/libs/video
      - ../gts-storage:/app/storage
```

**Profile:** `jobs` — video service does NOT run by default. Start with:
```bash
docker compose --profile jobs up video
```

### Dockerfile

```dockerfile
# infrastructure/docker/Dockerfile.video

FROM node:24-alpine

# Install Remotion dependencies
RUN apk add --no-cache \
    python3 py3-pip \
    ffmpeg chromium

# Install Python + Node packages
COPY libs/video/package.json ./
RUN npm install

# Remotion render command
CMD ["node", "remotion-wrapper.js", "render"]
```

**Key dependencies:**
- Node.js 24 (Remotion runtime)
- FFmpeg (video encoding)
- Chromium (headless rendering)
- Python 3 (for API server)

## Rendering Workflow

### Job Lifecycle

```
1. POST /render → job_id (202 Accepted)
2. Job status: pending
3. Background worker picks up job → processing
4. Remotion renders frames → video file
5. Job status: complete (with output_path)
```

### Status Polling

```python
# Client polls until complete or failed
while True:
    response = requests.get(f"/render/{job_id}")
    if response.status in ["complete", "failed"]:
        break
    time.sleep(1)
```

**Alternative:** Use webhooks or WebSockets (future enhancement).

## Testing Patterns

### Test Locations

```
tests/
├── unit/video/
│   ├── test_props.py                          # Props serialisation
│   ├── test_schemas.py                        # Pydantic models
│   ├── test_image_prep.py                     # Image preprocessing
│   ├── test_remotion_compositions.py          # Composition structure
│   └── test_video_package_structure.py        # Package integrity
│
└── integration/video/
    ├── test_video_api.py                      # FastAPI endpoints
    └── test_remotion_typescript_compilation.py # TypeScript builds
```

### Unit Test Example

```python
# tests/unit/video/test_props.py

from video.props import serialize_composition_props
from core.domain.value_objects.composition_spec import CompositionSpec

def test_serialize_composition_props():
    spec = CompositionSpec(
        composition_type="ShootoutVideo",
        data={"segments": [...]},
    )

    props = serialize_composition_props(spec)

    assert props["compositionType"] == "ShootoutVideo"
    assert "segments" in props["data"]
```

### Integration Test Example

```python
# tests/integration/video/test_video_api.py

import pytest
from fastapi.testclient import TestClient
from video.api import create_app

@pytest.fixture
def client():
    return TestClient(create_app())

def test_render_endpoint_returns_job_id(client):
    response = client.post("/render", json={
        "composition_type": "ShootoutVideo",
        "data": {"segments": []},
    })

    assert response.status_code == 202
    assert "job_id" in response.json()
```

## Remotion Commands

### Development

```bash
# Open Remotion Studio (interactive preview)
just video-studio

# Equivalent to:
cd libs/video && npx remotion studio src/video/remotion/index.ts
```

**Studio features:**
- Live preview of compositions
- Scrub through timeline
- Edit props interactively
- Hot reload on code changes

### Production Rendering

```bash
# Render a composition to video file
just remotion render ShootoutVideo output.mp4 --props='{"segments": [...]}'

# With custom resolution/fps
just remotion render ShootoutVideo output.mp4 --width=1920 --height=1080 --fps=30
```

**Render options:**
- `--codec`: h264 (default), h265, vp8, vp9
- `--quality`: 0-100 (default 80)
- `--concurrency`: Parallel rendering threads

## Common Patterns

### Adding a New Composition

1. Create React component in `libs/video/src/video/remotion/compositions/`
2. Register in `libs/video/src/video/remotion/index.ts`
3. Add TypeScript types for props
4. Create unit test in `tests/unit/video/`
5. Test in Remotion Studio: `just video-studio`

### Updating Props Schema

1. Modify domain model in `libs/core/src/core/domain/`
2. Update serialisation in `libs/video/src/video/props.py`
3. Update Pydantic schema in `libs/video/src/video/schemas.py`
4. Update React component props in `.tsx` file
5. Run tests: `just video-test`

### Debugging Render Failures

1. Check job status: `GET /render/{job_id}`
2. View container logs: `docker compose logs video`
3. Reproduce in Studio: `just video-studio`
4. Check FFmpeg logs: `/app/storage/audio/{job_id}/ffmpeg.log`

## Dependencies

### Python

```toml
# libs/video/pyproject.toml

[project]
dependencies = [
    "fastapi",
    "pydantic",
    "pillow",         # Image preprocessing
    "core @ file:///app/libs/core",  # Domain models
]
```

### Node.js

```json
// libs/video/package.json

{
  "dependencies": {
    "remotion": "^4.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "typescript": "^5.0.0"
  }
}
```

## Gotchas

1. **Remotion requires Node 24+** — older versions fail with module errors
2. **FFmpeg must be in PATH** — rendering silently fails without it
3. **Chromium for headless rendering** — Alpine requires `chromium` package
4. **Props must be JSON-serialisable** — no Python objects, use dicts/lists/primitives
5. **Alpha channels not supported** — convert PNG to JPEG in `image_prep.py`
6. **Large videos = slow renders** — use `--concurrency` to parallelise

## Related Skills

- **gts-architecture**: Dependency rules, layer responsibilities
- **gts-security**: Container hardening, secret handling, and security checks for video services
- **gts-testing**: Video test patterns, test locations
- **expertise/python**: Python service patterns used by FastAPI video endpoints

## References

- Remotion docs: https://www.remotion.dev/docs
- Video architecture: `.claude/skills/gts-architecture/references/audio-video.md`
- Composition examples: `libs/video/src/video/remotion/compositions/`
