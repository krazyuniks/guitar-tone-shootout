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


class ComparisonAverages(BaseModel):
    """Computed averages across all segments."""

    avg_duration_seconds: float
    avg_integrated_lufs: float
    avg_peak_dbfs: float


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
