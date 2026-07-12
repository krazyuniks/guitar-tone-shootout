"""Pydantic schemas for Shootout API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from gts.domain.value_objects.shootout_visibility import ShootoutVisibility


class ShootoutCreateRequest(BaseModel):
    """Request schema for creating a shootout."""

    name: str
    di_track_id: UUID
    description: str | None = None
    visibility: ShootoutVisibility = ShootoutVisibility.PUBLIC


class ShootoutUpdateRequest(BaseModel):
    """Request schema for updating a shootout."""

    name: str | None = None
    description: str | None = None
    visibility: ShootoutVisibility | None = None


class ShootoutResponse(BaseModel):
    """Response schema for a shootout."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    di_track_id: UUID
    description: str | None = None
    visibility: ShootoutVisibility = ShootoutVisibility.PUBLIC
    is_processed: bool
    output_path: str | None = None
    created_at: datetime
    updated_at: datetime


class ShootoutArtefactCreator(BaseModel):
    """Public creator attribution captured in the manifest."""

    username: str
    avatar_url: str | None


class ShootoutArtefactDI(BaseModel):
    """Public DI descriptors captured in the manifest."""

    name: str
    guitar: str | None
    pickup: str | None
    tuning: str | None
    duration_seconds: float


class ShootoutArtefactTimeline(BaseModel):
    """Shared, start-aligned comparison timeline."""

    aligned: str
    duration_seconds: float


class ShootoutArtefactWaveform(BaseModel):
    """Display waveform envelope for one rendered chain."""

    peaks: list[float]
    sample_rate: int
    duration_seconds: float | None = None
    samples_per_peak: int | None = None


class ShootoutArtefactProvenanceBlock(BaseModel):
    """Public gear attribution for one block in a rendered chain."""

    position: int
    gear_type: str
    display_name: str
    platform: str
    icon_asset_id: UUID


class ShootoutArtefactChain(BaseModel):
    """Allow-listed player data for one rendered chain."""

    label: str
    media_url: str
    duration_seconds: float
    waveform: ShootoutArtefactWaveform
    integrated_lufs: float
    peak_dbfs: float
    provenance: list[ShootoutArtefactProvenanceBlock]


class ShootoutArtefactResponse(BaseModel):
    """Allow-list projection of an immutable shootout manifest."""

    id: UUID
    title: str
    description: str | None
    creator: ShootoutArtefactCreator
    created_at: datetime
    di: ShootoutArtefactDI
    timeline: ShootoutArtefactTimeline
    chains: list[ShootoutArtefactChain]
