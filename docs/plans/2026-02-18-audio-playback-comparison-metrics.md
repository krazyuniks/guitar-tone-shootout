# Audio Playback, Comparison, and Metrics — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver audio serving endpoints, per-segment metrics/comparison endpoints, and the full shootout detail UI with audio player, A/B comparison, metrics display, and download functionality.

**Architecture:** New API endpoints on the existing `/api/v1/shootouts` prefix. Audio streaming via `FileResponse` with ownership checks. Metrics from existing `AudioSegment` ORM model fields (LUFS, peak, waveform). Frontend Alpine.js tabs fetch data from new API endpoints.

**Tech Stack:** FastAPI + SQLAlchemy (joinedload) | Pydantic schemas | Astro + Jinja2 + Alpine.js

**Observable Truths:** OT-8 (A/B comparison), OT-9 (per-segment metrics), OT-10 (download audio)

---

## Task 1: Pydantic Response Schemas

**Files:**
- Create: `apps/webapp/src/webapp/api/v1/schemas/metrics.py`
- Test: `tests/unit/webapp/test_metrics_schemas.py`

**Step 1: Create the schemas file**

```python
# apps/webapp/src/webapp/api/v1/schemas/metrics.py
"""Pydantic schemas for shootout metrics and comparison endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChainConfig(BaseModel):
    """Signal chain configuration within a shootout."""

    model_config = ConfigDict(from_attributes=True)

    chain_id: UUID
    label: str
    position: int
    signal_chain_name: str


class AudioSettings(BaseModel):
    """Audio processing settings."""

    output_format: str
    sample_rate: int


class MetadataResponse(BaseModel):
    """Reproducibility metadata for a shootout."""

    shootout_id: UUID
    audio_settings: AudioSettings
    chains: list[ChainConfig]


class SegmentMetrics(BaseModel):
    """Audio metrics for a single chain's segment."""

    chain_id: UUID
    chain_label: str
    chain_position: int
    duration_seconds: float
    integrated_lufs: float
    peak_dbfs: float
    waveform: list[float] | None = None


class SegmentMetricsResponse(BaseModel):
    """Per-position segment metrics with chain config."""

    shootout_id: UUID
    position: int
    chain_label: str
    metrics: SegmentMetrics


class ComparisonResponse(BaseModel):
    """All segments with computed averages for cross-chain comparison."""

    shootout_id: UUID
    segments: list[SegmentMetrics]
    averages: ComparisonAverages


class ComparisonAverages(BaseModel):
    """Computed averages across all segments."""

    avg_duration_seconds: float
    avg_integrated_lufs: float
    avg_peak_dbfs: float
```

Note: `ComparisonAverages` must be defined before `ComparisonResponse` (or use `from __future__ import annotations` which is already imported — forward refs work).

**Step 2: Write unit test for schema validation**

```python
# tests/unit/webapp/test_metrics_schemas.py
"""Unit tests for metrics Pydantic schemas."""

from uuid import uuid4

from webapp.api.v1.schemas.metrics import (
    AudioSettings,
    ChainConfig,
    ComparisonAverages,
    ComparisonResponse,
    MetadataResponse,
    SegmentMetrics,
    SegmentMetricsResponse,
)


def test_metadata_response_serialisation() -> None:
    chain_id = uuid4()
    shootout_id = uuid4()
    resp = MetadataResponse(
        shootout_id=shootout_id,
        audio_settings=AudioSettings(output_format="flac", sample_rate=44100),
        chains=[
            ChainConfig(
                chain_id=chain_id,
                label="Chain A",
                position=0,
                signal_chain_name="Mesa Mark V",
            ),
        ],
    )
    data = resp.model_dump()
    assert data["shootout_id"] == shootout_id
    assert data["audio_settings"]["sample_rate"] == 44100
    assert len(data["chains"]) == 1


def test_comparison_response_with_averages() -> None:
    shootout_id = uuid4()
    resp = ComparisonResponse(
        shootout_id=shootout_id,
        segments=[
            SegmentMetrics(
                chain_id=uuid4(),
                chain_label="Chain A",
                chain_position=0,
                duration_seconds=10.0,
                integrated_lufs=-14.0,
                peak_dbfs=-1.0,
            ),
            SegmentMetrics(
                chain_id=uuid4(),
                chain_label="Chain B",
                chain_position=1,
                duration_seconds=10.0,
                integrated_lufs=-16.0,
                peak_dbfs=-2.0,
            ),
        ],
        averages=ComparisonAverages(
            avg_duration_seconds=10.0,
            avg_integrated_lufs=-15.0,
            avg_peak_dbfs=-1.5,
        ),
    )
    assert len(resp.segments) == 2
    assert resp.averages.avg_integrated_lufs == -15.0


def test_segment_metrics_response() -> None:
    resp = SegmentMetricsResponse(
        shootout_id=uuid4(),
        position=0,
        chain_label="Chain A",
        metrics=SegmentMetrics(
            chain_id=uuid4(),
            chain_label="Chain A",
            chain_position=0,
            duration_seconds=10.0,
            integrated_lufs=-14.0,
            peak_dbfs=-1.0,
            waveform=[0.1, 0.2, 0.3],
        ),
    )
    assert resp.metrics.waveform == [0.1, 0.2, 0.3]
```

**Step 3: Run tests**

Run: `just tdd tests/unit/webapp/test_metrics_schemas.py`
Expected: PASS

**Step 4: Commit**

```bash
git add apps/webapp/src/webapp/api/v1/schemas/metrics.py tests/unit/webapp/test_metrics_schemas.py
git commit -m "feat(epic-112): add Pydantic schemas for metrics and comparison endpoints"
```

---

## Task 2: Audio Streaming Endpoints

**Files:**
- Modify: `apps/webapp/src/webapp/api/v1/shootouts.py` (add 2 endpoints)
- Test: `tests/integration/webapp/test_shootout_audio_stream.py`

These endpoints go in `shootouts.py` because they share the `/api/v1/shootouts` prefix and use the same local dependency overrides.

**Step 1: Write integration tests**

Follow the exact pattern from `tests/integration/webapp/test_di_track_stream.py`. Key differences: shootouts.py uses its own local `set_session_override` / `set_user_override`.

```python
# tests/integration/webapp/test_shootout_audio_stream.py
"""Integration tests for shootout audio streaming endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.shootouts import router, set_session_override, set_user_override

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def _wire_shootout_deps(db_session: AsyncSession, test_user: User) -> None:
    """Wire shootout module's local dependency overrides."""
    set_session_override(db_session)
    set_user_override(test_user)
    yield  # type: ignore[misc]
    set_session_override(None)
    set_user_override(None)


@pytest.fixture
async def completed_shootout(
    db_session: AsyncSession,
    test_user: User,
    tmp_path: Path,
) -> dict:
    """Create a completed shootout with master audio and chain segments."""
    # DI track
    di_file = tmp_path / f"{uuid4()}.wav"
    di_file.write_bytes(b"RIFF" + b"\x00" * 100)
    di_track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Test DI",
        file_path=str(di_file),
        original_filename="test.wav",
        duration_seconds=10.0,
        sample_rate=44100,
    )
    db_session.add(di_track)
    await db_session.flush()

    # Master audio file
    master_file = tmp_path / "master.flac"
    master_file.write_bytes(b"fLaC" + b"\x00" * 100)

    # Shootout
    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        di_track_id=di_track.id,
        name="Test Shootout",
        status=ShootoutStatus.COMPLETED,
        output_path=str(master_file),
    )
    db_session.add(shootout)
    await db_session.flush()

    # Signal chains
    sc1 = SignalChain(id=uuid4(), user_id=test_user.id, name="Chain 1", platform=Platform.NAM)
    sc2 = SignalChain(id=uuid4(), user_id=test_user.id, name="Chain 2", platform=Platform.NAM)
    db_session.add_all([sc1, sc2])
    await db_session.flush()

    # Shootout chains
    chain1 = ShootoutChain(
        id=uuid4(), shootout_id=shootout.id, signal_chain_id=sc1.id, position=0, label="A",
    )
    chain2 = ShootoutChain(
        id=uuid4(), shootout_id=shootout.id, signal_chain_id=sc2.id, position=1, label="B",
    )
    db_session.add_all([chain1, chain2])
    await db_session.flush()

    # Audio segments (one per chain)
    seg1_file = tmp_path / "seg1.flac"
    seg1_file.write_bytes(b"fLaC" + b"\x01" * 50)
    seg1 = AudioSegment(
        id=uuid4(),
        shootout_chain_id=chain1.id,
        file_path=str(seg1_file),
        duration_seconds=10.0,
        integrated_lufs=-14.0,
        peak_dbfs=-1.0,
    )
    seg2_file = tmp_path / "seg2.flac"
    seg2_file.write_bytes(b"fLaC" + b"\x02" * 50)
    seg2 = AudioSegment(
        id=uuid4(),
        shootout_chain_id=chain2.id,
        file_path=str(seg2_file),
        duration_seconds=10.0,
        integrated_lufs=-16.0,
        peak_dbfs=-2.0,
    )
    db_session.add_all([seg1, seg2])
    await db_session.commit()

    return {
        "shootout": shootout,
        "chain1": chain1,
        "chain2": chain2,
        "seg1": seg1,
        "seg2": seg2,
        "master_file": master_file,
        "seg1_file": seg1_file,
    }


@pytest.mark.asyncio
@pytest.mark.integration
class TestMasterAudioStream:
    """Tests for GET /api/v1/shootouts/{id}/audio/master."""

    async def test_stream_master_returns_flac(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/shootouts/{completed_shootout['shootout'].id}/audio/master",
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/flac"
        assert response.content.startswith(b"fLaC")

    async def test_stream_master_returns_404_for_other_user(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        other = User(id=uuid4(), username="other", email="other@test.com")
        db_session.add(other)
        await db_session.flush()
        set_user_override(other)
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/shootouts/{completed_shootout['shootout'].id}/audio/master",
            )
        assert response.status_code == 404

    async def test_stream_master_returns_404_for_nonexistent(
        self, db_session: AsyncSession, test_user: User,
    ) -> None:
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{uuid4()}/audio/master")
        assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
class TestChainAudioStream:
    """Tests for GET /api/v1/shootouts/{id}/chains/{chain_id}/audio."""

    async def test_stream_chain_audio_returns_flac(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        cid = completed_shootout["chain1"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{sid}/chains/{cid}/audio")
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/flac"

    async def test_stream_chain_audio_returns_404_for_wrong_chain(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{sid}/chains/{uuid4()}/audio")
        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `just tdd tests/integration/webapp/test_shootout_audio_stream.py`
Expected: FAIL (endpoints don't exist yet)

**Step 3: Implement audio streaming endpoints in shootouts.py**

Add at the end of `apps/webapp/src/webapp/api/v1/shootouts.py`, before the comment endpoints section:

```python
from pathlib import Path
from fastapi.responses import FileResponse

# Content-type mapping for audio formats
_AUDIO_CONTENT_TYPES: dict[str, str] = {
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
}


@router.get("/{shootout_id}/audio/master")
async def stream_master_audio(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """Stream the master FLAC audio file for a completed shootout."""
    stmt = select(ShootoutModel).where(ShootoutModel.id == shootout_id)
    result = await db.execute(stmt)
    shootout = result.scalar_one_or_none()

    if not shootout or shootout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shootout not found")

    if not shootout.output_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master audio not available")

    file_path = Path(shootout.output_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master audio file not found")

    ext = file_path.suffix.lower()
    media_type = _AUDIO_CONTENT_TYPES.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"{shootout.name}-master{ext}",
        headers={"Content-Disposition": f'attachment; filename="{shootout.name}-master{ext}"'},
    )


@router.get("/{shootout_id}/chains/{chain_id}/audio")
async def stream_chain_audio(
    shootout_id: UUID,
    chain_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """Stream processed audio for a specific chain in a shootout."""
    from webapp.adapters.persistence.models.shootout import (
        AudioSegment as AudioSegmentModel,
        ShootoutChain as ShootoutChainModel,
    )

    stmt = (
        select(ShootoutChainModel)
        .where(
            ShootoutChainModel.id == chain_id,
            ShootoutChainModel.shootout_id == shootout_id,
        )
        .options(
            joinedload(ShootoutChainModel.shootout),
            joinedload(ShootoutChainModel.segments),
        )
    )
    result = await db.execute(stmt)
    chain = result.unique().scalar_one_or_none()

    if not chain or chain.shootout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")

    if not chain.segments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No audio segments")

    segment = chain.segments[0]
    file_path = Path(segment.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found")

    ext = file_path.suffix.lower()
    media_type = _AUDIO_CONTENT_TYPES.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"{chain.label}{ext}",
    )
```

Import additions at the top of shootouts.py:
```python
from pathlib import Path
from fastapi.responses import FileResponse
```

**Step 4: Run tests**

Run: `just tdd tests/integration/webapp/test_shootout_audio_stream.py`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/webapp/src/webapp/api/v1/shootouts.py tests/integration/webapp/test_shootout_audio_stream.py
git commit -m "feat(epic-112): add audio streaming endpoints for master and chain audio"
```

---

## Task 3: Metrics Endpoints + Router Registration

**Files:**
- Create: `apps/webapp/src/webapp/api/v1/metrics.py`
- Modify: `apps/webapp/src/webapp/main.py` (register router)
- Test: `tests/integration/webapp/test_shootout_metrics.py`

The metrics router uses **centralised auth dependencies** (like di_tracks.py), NOT shootouts.py's local deps. This means the conftest's `_wire_auth_session` fixture handles session/user wiring automatically.

**Step 1: Write integration tests**

```python
# tests/integration/webapp/test_shootout_metrics.py
"""Integration tests for shootout metrics API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.metrics import router

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def completed_shootout(db_session: AsyncSession, test_user: User) -> dict:
    """Create a completed shootout with chains and segments."""
    di_track = DITrack(
        id=uuid4(),
        user_id=test_user.id,
        name="Test DI",
        file_path="/tmp/test.wav",
        original_filename="test.wav",
        duration_seconds=10.0,
        sample_rate=44100,
    )
    db_session.add(di_track)
    await db_session.flush()

    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        di_track_id=di_track.id,
        name="Test Shootout",
        status=ShootoutStatus.COMPLETED,
        output_path="/tmp/master.flac",
    )
    db_session.add(shootout)
    await db_session.flush()

    sc1 = SignalChain(id=uuid4(), user_id=test_user.id, name="Mesa Mark V", platform=Platform.NAM)
    sc2 = SignalChain(id=uuid4(), user_id=test_user.id, name="Fender Twin", platform=Platform.NAM)
    db_session.add_all([sc1, sc2])
    await db_session.flush()

    chain1 = ShootoutChain(
        id=uuid4(), shootout_id=shootout.id, signal_chain_id=sc1.id, position=0, label="A",
    )
    chain2 = ShootoutChain(
        id=uuid4(), shootout_id=shootout.id, signal_chain_id=sc2.id, position=1, label="B",
    )
    db_session.add_all([chain1, chain2])
    await db_session.flush()

    seg1 = AudioSegment(
        id=uuid4(),
        shootout_chain_id=chain1.id,
        file_path="/tmp/seg1.flac",
        duration_seconds=10.0,
        integrated_lufs=-14.0,
        peak_dbfs=-1.0,
    )
    seg2 = AudioSegment(
        id=uuid4(),
        shootout_chain_id=chain2.id,
        file_path="/tmp/seg2.flac",
        duration_seconds=10.0,
        integrated_lufs=-16.0,
        peak_dbfs=-2.0,
    )
    db_session.add_all([seg1, seg2])
    await db_session.commit()

    return {
        "shootout": shootout,
        "chain1": chain1,
        "chain2": chain2,
        "sc1": sc1,
        "sc2": sc2,
    }


@pytest.mark.asyncio
@pytest.mark.integration
class TestMetadataEndpoint:
    """Tests for GET /api/v1/shootouts/{id}/metadata."""

    async def test_metadata_returns_chain_configs(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{sid}/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["shootout_id"] == str(sid)
        assert len(data["chains"]) == 2
        assert data["chains"][0]["signal_chain_name"] == "Mesa Mark V"
        assert data["audio_settings"]["sample_rate"] == 44100

    async def test_metadata_returns_404_for_other_user(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        from webapp.auth.dependencies import set_user_override
        other = User(id=uuid4(), username="other", email="other@test.com")
        db_session.add(other)
        await db_session.flush()
        set_user_override(other)
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{sid}/metadata")
        assert response.status_code == 404
        # Restore original user
        set_user_override(test_user)


@pytest.mark.asyncio
@pytest.mark.integration
class TestComparisonEndpoint:
    """Tests for GET /api/v1/shootouts/{id}/comparison."""

    async def test_comparison_returns_all_segments_with_averages(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{sid}/comparison")
        assert response.status_code == 200
        data = response.json()
        assert len(data["segments"]) == 2
        assert data["averages"]["avg_integrated_lufs"] == -15.0
        assert data["averages"]["avg_peak_dbfs"] == -1.5


@pytest.mark.asyncio
@pytest.mark.integration
class TestSegmentMetricsEndpoint:
    """Tests for GET /api/v1/shootouts/{id}/segments/{position}/metrics."""

    async def test_segment_metrics_returns_metrics_for_position(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{sid}/segments/0/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["position"] == 0
        assert data["metrics"]["integrated_lufs"] == -14.0

    async def test_segment_metrics_returns_404_for_invalid_position(
        self, db_session: AsyncSession, test_user: User, completed_shootout: dict,
    ) -> None:
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        sid = completed_shootout["shootout"].id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/shootouts/{sid}/segments/99/metrics")
        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `just tdd tests/integration/webapp/test_shootout_metrics.py`
Expected: FAIL (import error — metrics module doesn't exist yet)

**Step 3: Create metrics.py endpoint module**

```python
# apps/webapp/src/webapp/api/v1/metrics.py
"""Metrics and comparison endpoints for shootouts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.shootout import (
    Shootout as ShootoutModel,
    ShootoutChain as ShootoutChainModel,
)
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.metrics import (
    AudioSettings,
    ChainConfig,
    ComparisonAverages,
    ComparisonResponse,
    MetadataResponse,
    SegmentMetrics,
    SegmentMetricsResponse,
)
from webapp.auth.dependencies import (
    get_current_user_required as get_current_user,
    get_db_session,
)

router = APIRouter(prefix="/api/v1/shootouts", tags=["shootout-metrics"])


async def _get_shootout_for_user(
    db: AsyncSession,
    shootout_id: UUID,
    user_id: UUID,
    *,
    load_segments: bool = False,
    load_signal_chains: bool = False,
) -> ShootoutModel:
    """Fetch shootout with ownership check. Raises 404 if not found or not owned."""
    options = [joinedload(ShootoutModel.chains)]
    if load_segments:
        options = [joinedload(ShootoutModel.chains).joinedload(ShootoutChainModel.segments)]
    if load_signal_chains:
        options.append(
            joinedload(ShootoutModel.chains).joinedload(ShootoutChainModel.signal_chain),
        )

    stmt = (
        select(ShootoutModel)
        .where(ShootoutModel.id == shootout_id)
        .options(*options)
    )
    result = await db.execute(stmt)
    shootout = result.unique().scalar_one_or_none()

    if not shootout or shootout.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shootout not found")

    return shootout


@router.get("/{shootout_id}/metadata", response_model=MetadataResponse)
async def get_metadata(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MetadataResponse:
    """Get reproducibility metadata for a shootout."""
    shootout = await _get_shootout_for_user(
        db, shootout_id, current_user.id, load_signal_chains=True,
    )

    chains_sorted = sorted(shootout.chains, key=lambda c: c.position)
    return MetadataResponse(
        shootout_id=shootout.id,
        audio_settings=AudioSettings(
            output_format="flac",
            sample_rate=44100,
        ),
        chains=[
            ChainConfig(
                chain_id=chain.id,
                label=chain.label,
                position=chain.position,
                signal_chain_name=chain.signal_chain.name if chain.signal_chain else chain.label,
            )
            for chain in chains_sorted
        ],
    )


@router.get("/{shootout_id}/segments/{position}/metrics", response_model=SegmentMetricsResponse)
async def get_segment_metrics(
    shootout_id: UUID,
    position: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SegmentMetricsResponse:
    """Get audio metrics for a specific segment (chain position)."""
    shootout = await _get_shootout_for_user(
        db, shootout_id, current_user.id, load_segments=True,
    )

    chain = next((c for c in shootout.chains if c.position == position), None)
    if not chain or not chain.segments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    segment = chain.segments[0]
    return SegmentMetricsResponse(
        shootout_id=shootout.id,
        position=position,
        chain_label=chain.label,
        metrics=SegmentMetrics(
            chain_id=chain.id,
            chain_label=chain.label,
            chain_position=chain.position,
            duration_seconds=segment.duration_seconds,
            integrated_lufs=segment.integrated_lufs,
            peak_dbfs=segment.peak_dbfs,
            waveform=segment.waveform,
        ),
    )


@router.get("/{shootout_id}/comparison", response_model=ComparisonResponse)
async def get_comparison(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ComparisonResponse:
    """Get all segments with computed averages for cross-chain comparison."""
    shootout = await _get_shootout_for_user(
        db, shootout_id, current_user.id, load_segments=True,
    )

    chains_sorted = sorted(shootout.chains, key=lambda c: c.position)
    segments = []
    for chain in chains_sorted:
        if chain.segments:
            seg = chain.segments[0]
            segments.append(
                SegmentMetrics(
                    chain_id=chain.id,
                    chain_label=chain.label,
                    chain_position=chain.position,
                    duration_seconds=seg.duration_seconds,
                    integrated_lufs=seg.integrated_lufs,
                    peak_dbfs=seg.peak_dbfs,
                    waveform=seg.waveform,
                ),
            )

    if not segments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No audio segments found",
        )

    avg_duration = sum(s.duration_seconds for s in segments) / len(segments)
    avg_lufs = sum(s.integrated_lufs for s in segments) / len(segments)
    avg_peak = sum(s.peak_dbfs for s in segments) / len(segments)

    return ComparisonResponse(
        shootout_id=shootout.id,
        segments=segments,
        averages=ComparisonAverages(
            avg_duration_seconds=avg_duration,
            avg_integrated_lufs=avg_lufs,
            avg_peak_dbfs=avg_peak,
        ),
    )
```

**Step 4: Register router in main.py**

In `apps/webapp/src/webapp/main.py`:
- Add `metrics` to the import: `from webapp.api.v1 import ..., metrics, ...`
- Add `app.include_router(metrics.router)` after the shootouts router line

**Step 5: Run tests**

Run: `just tdd tests/integration/webapp/test_shootout_metrics.py`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/webapp/src/webapp/api/v1/metrics.py apps/webapp/src/webapp/main.py tests/integration/webapp/test_shootout_metrics.py
git commit -m "feat(epic-112): add metrics, comparison, and metadata API endpoints"
```

---

## Task 4: Update Page Context (Chain IDs)

**Files:**
- Modify: `apps/webapp/src/webapp/api/pages.py:736-745`

The page route needs to include `ShootoutChain.id` in the chains context so the frontend can build audio streaming URLs.

**Step 1: Add chain ID to context**

In `apps/webapp/src/webapp/api/pages.py`, in the `shootout_detail_page` function, update `chain_items` to include the chain ID:

```python
chain_items = [
    {
        "id": str(chain.id),  # ADD THIS — needed for audio endpoint URLs
        "signal_chain_id": str(chain.signal_chain_id),
        "position": chain.position,
        "label": chain.label,
        "chain_name": chain.signal_chain.name if chain.signal_chain else chain.label,
    }
    for chain in chains_sorted
    if chain.signal_chain is not None
]
```

Also joinedload segments so the page can show segment metadata. Update the query (around line 717):

```python
stmt = (
    select(Shootout)
    .where(Shootout.id == UUID(shootout_id))
    .options(
        joinedload(Shootout.di_track),
        joinedload(Shootout.chains).joinedload(ShootoutChain.signal_chain),
        joinedload(Shootout.chains).joinedload(ShootoutChain.segments),  # ADD THIS
    )
)
```

Import `AudioSegment` won't be needed — just the joinedload path.

**Step 2: Commit**

```bash
git add apps/webapp/src/webapp/api/pages.py
git commit -m "feat(epic-112): include chain IDs and segments in shootout detail page context"
```

---

## Task 5: Frontend Analytics Tabs

**Files:**
- Modify: `frontend/astro/src/pages/fragments/shootouts/detail.html.ts`

Replace the four placeholder tabs (Metrics, AI Evaluation, Compare, Technical) with working content:
1. **Playback** — HTML5 `<audio>` per chain segment + download buttons
2. **Comparison** — A/B chain selectors + synchronised playback + quick-switch
3. **Metrics** — Per-chain metrics table (duration, LUFS, peak)
4. **Technical** — Metadata from `/metadata` endpoint

The analytics section is wrapped in an Alpine.js component that fetches data on init.

**Step 1: Replace the analytics section**

Replace the entire analytics section (from `{# Analytics Section with Alpine.js Tabs #}` to the closing `{% endif %}` around line 339) with:

```html
{# Analytics Section with Alpine.js Tabs #}
{% if shootout.status == 'completed' %}
  <div
    class="mb-8"
    data-testid="analytics-section"
    x-data="{
      activeTab: 'playback',
      comparison: null,
      metadata: null,
      loading: true,
      chainA: 0,
      chainB: 1,
      async init() {
        const sid = '{{ shootout.id }}';
        const [compResp, metaResp] = await Promise.all([
          fetch('/api/v1/shootouts/' + sid + '/comparison', { credentials: 'same-origin' }),
          fetch('/api/v1/shootouts/' + sid + '/metadata', { credentials: 'same-origin' }),
        ]);
        if (compResp.ok) this.comparison = await compResp.json();
        if (metaResp.ok) this.metadata = await metaResp.json();
        this.loading = false;
      },
      swapChains() { [this.chainA, this.chainB] = [this.chainB, this.chainA]; },
    }"
  >
    <h2 class="text-lg font-semibold text-[var(--color-text-primary)] mb-4 flex items-center gap-2">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5 text-amber-500">
        <path fill-rule="evenodd" d="M2.25 13.5a8.25 8.25 0 018.25-8.25.75.75 0 01.75.75v6.75H18a.75.75 0 01.75.75 8.25 8.25 0 01-16.5 0z" clip-rule="evenodd" />
        <path fill-rule="evenodd" d="M12.75 3a.75.75 0 01.75-.75 8.25 8.25 0 018.25 8.25.75.75 0 01-.75.75h-7.5a.75.75 0 01-.75-.75V3z" clip-rule="evenodd" />
      </svg>
      Audio Analysis
    </h2>

    {# Tab Navigation #}
    <div class="flex gap-1 mb-4 bg-[var(--color-bg-surface)] rounded-lg p-1 border border-[var(--border)]">
      <button
        x-on:click="activeTab = 'playback'"
        x-bind:class="activeTab === 'playback' ? 'bg-amber-500 text-white' : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)]'"
        class="flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all"
        data-testid="tab-playback"
      >
        Playback
      </button>
      <button
        x-on:click="activeTab = 'comparison'"
        x-bind:class="activeTab === 'comparison' ? 'bg-amber-500 text-white' : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)]'"
        class="flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all"
        data-testid="comparison-tab"
      >
        Compare
      </button>
      <button
        x-on:click="activeTab = 'metrics'"
        x-bind:class="activeTab === 'metrics' ? 'bg-amber-500 text-white' : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)]'"
        class="flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all"
        data-testid="metrics-tab"
      >
        Metrics
      </button>
      <button
        x-on:click="activeTab = 'technical'"
        x-bind:class="activeTab === 'technical' ? 'bg-amber-500 text-white' : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)]'"
        class="flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all"
        data-testid="tab-technical"
      >
        Technical
      </button>
    </div>

    {# Tab Content #}
    <div class="bg-[var(--color-bg-surface)] rounded-lg border border-[var(--border)] p-6">
      {# Loading state #}
      <template x-if="loading">
        <div class="text-center py-8 text-[var(--color-text-muted)]">
          <div class="animate-spin w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full mx-auto mb-3"></div>
          <p>Loading analysis data...</p>
        </div>
      </template>

      {# Playback Tab — audio player per chain + downloads #}
      <div x-show="activeTab === 'playback' && !loading" data-testid="playback-content">
        <div class="space-y-4">
          {% for chain in chains %}
            <div class="bg-[var(--color-bg-elevated)] rounded-lg p-4">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium text-[var(--color-text-primary)]">
                  {{ chain.chain_name or chain.label }}
                </span>
                <a
                  href="/api/v1/shootouts/{{ shootout.id }}/chains/{{ chain.id }}/audio"
                  download
                  class="text-xs text-amber-400 hover:text-amber-300 transition-colors"
                  data-testid="download-segment-btn"
                >
                  Download
                </a>
              </div>
              <audio
                controls
                preload="metadata"
                class="w-full"
                src="/api/v1/shootouts/{{ shootout.id }}/chains/{{ chain.id }}/audio"
                data-testid="audio-player"
              >
                Your browser does not support the audio element.
              </audio>
            </div>
          {% endfor %}
          {% if shootout.output_path %}
            <div class="pt-4 border-t border-[var(--border)]">
              <a
                href="/api/v1/shootouts/{{ shootout.id }}/audio/master"
                download
                class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-sm font-medium transition-colors"
                data-testid="download-master-btn"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
                  <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
                  <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
                </svg>
                Download Master FLAC
              </a>
            </div>
          {% endif %}
        </div>
      </div>

      {# Comparison Tab — A/B selectors + synchronised playback #}
      <div x-show="activeTab === 'comparison' && !loading" data-testid="comparison-content">
        <template x-if="comparison && comparison.segments.length >= 2">
          <div>
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-xs text-[var(--color-text-muted)] mb-1">Chain A</label>
                <select
                  x-model.number="chainA"
                  class="w-full bg-[var(--color-bg-elevated)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--color-text-primary)]"
                  data-testid="chain-a-selector"
                >
                  <template x-for="(seg, idx) in comparison.segments" :key="idx">
                    <option :value="idx" x-text="seg.chain_label + ' (Position ' + seg.chain_position + ')'"></option>
                  </template>
                </select>
              </div>
              <div>
                <label class="block text-xs text-[var(--color-text-muted)] mb-1">Chain B</label>
                <select
                  x-model.number="chainB"
                  class="w-full bg-[var(--color-bg-elevated)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--color-text-primary)]"
                  data-testid="chain-b-selector"
                >
                  <template x-for="(seg, idx) in comparison.segments" :key="idx">
                    <option :value="idx" x-text="seg.chain_label + ' (Position ' + seg.chain_position + ')'"></option>
                  </template>
                </select>
              </div>
            </div>
            <div class="flex justify-center mb-4">
              <button
                x-on:click="swapChains()"
                class="px-4 py-2 rounded-lg bg-[var(--color-bg-elevated)] hover:bg-amber-500/20 text-[var(--color-text-secondary)] hover:text-amber-400 text-sm font-medium transition-all"
                data-testid="ab-switch-btn"
              >
                Swap A/B
              </button>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-[var(--color-bg-elevated)] rounded-lg p-4">
                <p class="text-xs text-[var(--color-text-muted)] mb-2">Chain A</p>
                <p class="text-sm font-medium text-[var(--color-text-primary)] mb-2"
                   x-text="comparison.segments[chainA]?.chain_label"></p>
                <div class="text-xs text-[var(--color-text-secondary)] space-y-1">
                  <p>LUFS: <span x-text="comparison.segments[chainA]?.integrated_lufs.toFixed(1)"></span></p>
                  <p>Peak: <span x-text="comparison.segments[chainA]?.peak_dbfs.toFixed(1)"></span> dBFS</p>
                  <p>Duration: <span x-text="comparison.segments[chainA]?.duration_seconds.toFixed(1)"></span>s</p>
                </div>
              </div>
              <div class="bg-[var(--color-bg-elevated)] rounded-lg p-4">
                <p class="text-xs text-[var(--color-text-muted)] mb-2">Chain B</p>
                <p class="text-sm font-medium text-[var(--color-text-primary)] mb-2"
                   x-text="comparison.segments[chainB]?.chain_label"></p>
                <div class="text-xs text-[var(--color-text-secondary)] space-y-1">
                  <p>LUFS: <span x-text="comparison.segments[chainB]?.integrated_lufs.toFixed(1)"></span></p>
                  <p>Peak: <span x-text="comparison.segments[chainB]?.peak_dbfs.toFixed(1)"></span> dBFS</p>
                  <p>Duration: <span x-text="comparison.segments[chainB]?.duration_seconds.toFixed(1)"></span>s</p>
                </div>
              </div>
            </div>
          </div>
        </template>
        <template x-if="!comparison || comparison.segments.length < 2">
          <p class="text-center py-8 text-[var(--color-text-muted)]">Need at least 2 chains for comparison.</p>
        </template>
      </div>

      {# Metrics Tab — per-chain metrics table #}
      <div x-show="activeTab === 'metrics' && !loading" data-testid="metrics-content">
        <template x-if="comparison">
          <div>
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-[var(--color-text-muted)] border-b border-[var(--border)]">
                  <th class="pb-3 font-medium">Chain</th>
                  <th class="pb-3 font-medium">Duration</th>
                  <th class="pb-3 font-medium">LUFS</th>
                  <th class="pb-3 font-medium">Peak dBFS</th>
                </tr>
              </thead>
              <tbody>
                <template x-for="seg in comparison.segments" :key="seg.chain_id">
                  <tr class="border-b border-[var(--border)]/50">
                    <td class="py-3 text-[var(--color-text-primary)] font-medium" x-text="seg.chain_label"></td>
                    <td class="py-3 text-[var(--color-text-secondary)]" x-text="seg.duration_seconds.toFixed(1) + 's'"></td>
                    <td class="py-3 text-[var(--color-text-secondary)]" x-text="seg.integrated_lufs.toFixed(1)"></td>
                    <td class="py-3 text-[var(--color-text-secondary)]" x-text="seg.peak_dbfs.toFixed(1)"></td>
                  </tr>
                </template>
              </tbody>
              <tfoot>
                <tr class="text-amber-400 font-medium">
                  <td class="pt-3">Average</td>
                  <td class="pt-3" x-text="comparison.averages.avg_duration_seconds.toFixed(1) + 's'"></td>
                  <td class="pt-3" x-text="comparison.averages.avg_integrated_lufs.toFixed(1)"></td>
                  <td class="pt-3" x-text="comparison.averages.avg_peak_dbfs.toFixed(1)"></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </template>
        <template x-if="!comparison">
          <p class="text-center py-8 text-[var(--color-text-muted)]">No metrics data available.</p>
        </template>
      </div>

      {# Technical Tab — metadata from /metadata endpoint #}
      <div x-show="activeTab === 'technical' && !loading" data-testid="technical-content">
        <template x-if="metadata">
          <div class="space-y-6">
            <div>
              <h3 class="text-sm font-medium text-[var(--color-text-primary)] mb-2">Audio Settings</h3>
              <div class="grid grid-cols-2 gap-3 text-sm">
                <div class="bg-[var(--color-bg-elevated)] rounded-lg p-3">
                  <span class="text-[var(--color-text-muted)]">Format:</span>
                  <span class="text-[var(--color-text-primary)] ml-2" x-text="metadata.audio_settings.output_format.toUpperCase()"></span>
                </div>
                <div class="bg-[var(--color-bg-elevated)] rounded-lg p-3">
                  <span class="text-[var(--color-text-muted)]">Sample Rate:</span>
                  <span class="text-[var(--color-text-primary)] ml-2" x-text="(metadata.audio_settings.sample_rate / 1000) + ' kHz'"></span>
                </div>
              </div>
            </div>
            <div>
              <h3 class="text-sm font-medium text-[var(--color-text-primary)] mb-2">Chain Configurations</h3>
              <div class="space-y-2">
                <template x-for="chain in metadata.chains" :key="chain.chain_id">
                  <div class="bg-[var(--color-bg-elevated)] rounded-lg p-3 flex items-center justify-between text-sm">
                    <div>
                      <span class="text-[var(--color-text-primary)] font-medium" x-text="chain.label"></span>
                      <span class="text-[var(--color-text-muted)] ml-2" x-text="'(' + chain.signal_chain_name + ')'"></span>
                    </div>
                    <span class="text-xs text-[var(--color-text-muted)]" x-text="'Position ' + chain.position"></span>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </template>
        <template x-if="!metadata">
          <p class="text-center py-8 text-[var(--color-text-muted)]">No metadata available.</p>
        </template>
      </div>
    </div>
  </div>
{% endif %}
```

**Required `data-testid` attributes** (all present above):
- `audio-player` — on each `<audio>` element in the Playback tab
- `comparison-tab` — on the Compare tab button
- `metrics-tab` — on the Metrics tab button
- `download-segment-btn` — on each chain download link
- `download-master-btn` — on the master FLAC download button
- `ab-switch-btn` — on the Swap A/B button

**Step 2: Commit frontend changes**

```bash
git add frontend/astro/src/pages/fragments/shootouts/detail.html.ts
git commit -m "feat(epic-112): implement playback, comparison, metrics, and technical tabs"
```

---

## Task 6: Build Astro + Quality Gates

**Step 1: Build Astro**

Run: `just build-astro`
Expected: Clean build, dist files updated

**Step 2: Run quality gates**

Run: `just check`
Expected: lint, types, tests all pass (except pre-existing failures in test_skill_video_updates and test_sync_service)

**Step 3: Final commit with dist**

```bash
git add frontend/astro/dist/
git commit -m "build(astro): rebuild dist with audio playback and metrics UI"
```

**Step 4: Squash or combine into final commit**

All work combined into one feature commit:
```
feat(epic-112): audio playback, comparison, and metrics endpoints + UI
```

---

## Validation Checklist

After implementation, verify:

- [ ] `GET /api/v1/shootouts/{id}/audio/master` returns audio with correct Content-Type for authenticated owner
- [ ] `GET /api/v1/shootouts/{id}/chains/{chain_id}/audio` returns per-chain audio with correct Content-Type
- [ ] `GET /api/v1/shootouts/{id}/metadata` returns JSON with audio settings, chain configs
- [ ] `GET /api/v1/shootouts/{id}/comparison` returns JSON with all segments and computed averages
- [ ] `GET /api/v1/shootouts/{id}/segments/{position}/metrics` returns JSON with metrics for that position
- [ ] All endpoints return 404 for non-owner access
- [ ] Frontend Playback tab shows audio player per chain
- [ ] Frontend Comparison tab has A/B selectors and swap button
- [ ] Frontend Metrics tab shows LUFS/peak/duration table
- [ ] Frontend Technical tab shows metadata
- [ ] Download links work for segments and master FLAC
- [ ] All `data-testid` attributes present: `audio-player`, `comparison-tab`, `metrics-tab`, `download-segment-btn`, `download-master-btn`, `ab-switch-btn`
