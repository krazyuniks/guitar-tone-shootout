"""Metrics and comparison endpoints for shootouts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.shootout import (
    Shootout as ShootoutModel,
)
from webapp.adapters.persistence.models.shootout import (
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
)
from webapp.auth.dependencies import (
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

    stmt = select(ShootoutModel).where(ShootoutModel.id == shootout_id).options(*options)
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
        db,
        shootout_id,
        current_user.id,
        load_signal_chains=True,
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
        db,
        shootout_id,
        current_user.id,
        load_segments=True,
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
        db,
        shootout_id,
        current_user.id,
        load_segments=True,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No audio segments found",
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
