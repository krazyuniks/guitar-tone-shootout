"""Metrics API endpoints for audio analysis and AI evaluation.

Provides endpoints to retrieve:
- Full reproducibility metadata for a shootout
- Detailed metrics for individual segments
- Comparison of all segments with averages

Endpoints:
- GET /api/v1/shootouts/{id}/metadata - Full reproducibility metadata
- GET /api/v1/shootouts/{id}/segments/{position}/metrics - Segment details
- GET /api/v1/shootouts/{id}/comparison - Compare all segments
"""

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.shootout import (
    AIEvaluationSchema,
    AudioMetricsSchema,
    AudioSettingsFullSchema,
    EffectSchema,
    FileHashesSchema,
    MetricsAverages,
    NormalizationSettingsSchema,
    ProcessingVersionsSchema,
    SegmentComparisonItem,
    SegmentMetricsResponse,
    SegmentTimestampsSchema,
    ShootoutComparisonResponse,
    ShootoutMetadataResponse,
    SignalChainSchema,
)
from app.services.shootout_service import ShootoutService

router = APIRouter(prefix="/shootouts", tags=["metrics"])


@router.get("/{shootout_id}/metadata", response_model=ShootoutMetadataResponse)
async def get_shootout_metadata(
    shootout_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> ShootoutMetadataResponse:
    """Get full reproducibility metadata for a shootout.

    Returns all processing information needed to reproduce the shootout,
    including software versions, audio settings, normalization parameters,
    and file hashes.

    Args:
        shootout_id: The shootout ID.
        user: Current authenticated user.
        db: Database session.

    Returns:
        Complete reproducibility metadata.

    Raises:
        HTTPException: If shootout not found or not processed.
    """
    service = ShootoutService(db)
    shootout = await service.get_shootout(user, shootout_id)

    if not shootout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    # Extract metadata from processing_metadata JSONB field
    metadata = shootout.processing_metadata or {}

    # Parse versions if present
    processing_versions = None
    if "versions" in metadata:
        v = metadata["versions"]
        processing_versions = ProcessingVersionsSchema(
            pedalboard=v.get("pedalboard", "unknown"),
            nam_vst=v.get("nam_vst", "unknown"),
            ffmpeg=v.get("ffmpeg", "unknown"),
            pipeline=v.get("pipeline", "unknown"),
            python=v.get("python", "unknown"),
        )

    # Parse audio settings if present
    audio_settings = None
    if "audio_settings" in metadata:
        a = metadata["audio_settings"]
        audio_settings = AudioSettingsFullSchema(
            sample_rate=a.get("sample_rate", shootout.sample_rate),
            bit_depth=a.get("bit_depth", 32),
            channels=a.get("channels", 2),
            format=a.get("format", "float32"),
        )

    # Parse normalization settings if present
    normalization = None
    if "normalization" in metadata:
        n = metadata["normalization"]
        normalization = NormalizationSettingsSchema(
            input_target_rms_db=n.get("input_target_rms_db", -18.0),
            output_target_rms_db=n.get("output_target_rms_db", -14.0),
            method=n.get("method", "rms"),
            headroom_db=n.get("headroom_db", -1.0),
        )

    # Parse file hashes if present
    file_hashes = None
    if "file_hashes" in metadata:
        h = metadata["file_hashes"]
        file_hashes = FileHashesSchema(
            di_track_sha256=h.get("di_track_sha256", ""),
            nam_model_sha256=h.get("nam_model_sha256"),
            ir_sha256=h.get("ir_sha256"),
        )

    # Calculate total duration from segments
    total_duration_ms = 0
    for ts in shootout.tone_selections:
        if ts.start_ms is not None and ts.end_ms is not None:
            total_duration_ms = max(total_duration_ms, ts.end_ms)

    return ShootoutMetadataResponse(
        shootout_id=shootout.id,
        processing_versions=processing_versions,
        normalization=normalization,
        audio_settings=audio_settings,
        file_hashes=file_hashes,
        total_duration_ms=metadata.get("total_duration_ms", total_duration_ms),
        segment_count=len(shootout.tone_selections),
        processed_at=metadata.get("processed_at"),
        platform_info=metadata.get("platform_info"),
    )


@router.get(
    "/{shootout_id}/segments/{position}/metrics",
    response_model=SegmentMetricsResponse,
)
async def get_segment_metrics(
    shootout_id: UUID,
    position: int,
    user: CurrentUser,
    db: DbSession,
) -> SegmentMetricsResponse:
    """Get detailed metrics for a specific segment.

    Returns audio metrics, AI evaluation, signal chain configuration,
    and precise timestamps for the segment at the given position.

    Args:
        shootout_id: The shootout ID.
        position: Segment position (0-indexed).
        user: Current authenticated user.
        db: Database session.

    Returns:
        Detailed segment metrics.

    Raises:
        HTTPException: If shootout or segment not found.
    """
    service = ShootoutService(db)
    shootout = await service.get_shootout(user, shootout_id)

    if not shootout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    # Find segment by position
    segment = None
    for ts in shootout.tone_selections:
        if ts.position == position:
            segment = ts
            break

    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment at position {position} not found",
        )

    # Build timestamps if available
    timestamps = None
    if segment.start_ms is not None and segment.end_ms is not None:
        timestamps = SegmentTimestampsSchema(
            position=position,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            duration_ms=segment.end_ms - segment.start_ms,
            source_start_sample=0,
            source_end_sample=0,
            sample_rate=shootout.sample_rate,
        )

    # Parse audio metrics from JSONB
    audio_metrics = None
    if segment.audio_metrics:
        audio_metrics = AudioMetricsSchema.model_validate(segment.audio_metrics)

    # Parse AI evaluation from JSONB
    ai_evaluation = None
    if segment.ai_evaluation:
        ai_evaluation = AIEvaluationSchema.model_validate(segment.ai_evaluation)

    # Parse effects from JSON string
    effects: list[EffectSchema] = []
    if segment.effects_json:
        try:
            effects_data = json.loads(segment.effects_json)
            effects = [EffectSchema.model_validate(e) for e in effects_data]
        except (json.JSONDecodeError, ValueError):
            pass

    # Build signal chain
    signal_chain = SignalChainSchema(
        tone_title=segment.tone_title,
        model_name=segment.model_name,
        model_size=segment.model_size,
        gear_type=segment.gear_type,
        ir_path=segment.ir_path,
        highpass=segment.highpass,
        effects=effects,
    )

    return SegmentMetricsResponse(
        segment_id=segment.id,
        position=position,
        timestamps=timestamps,
        audio_metrics=audio_metrics,
        ai_evaluation=ai_evaluation,
        signal_chain=signal_chain,
    )


@router.get("/{shootout_id}/comparison", response_model=ShootoutComparisonResponse)
async def get_shootout_comparison(
    shootout_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> ShootoutComparisonResponse:
    """Compare all segments in a shootout with averages.

    Returns all segments with their metrics and calculates average
    values across all segments for easy comparison.

    Args:
        shootout_id: The shootout ID.
        user: Current authenticated user.
        db: Database session.

    Returns:
        Comparison data with all segments and averages.

    Raises:
        HTTPException: If shootout not found.
    """
    service = ShootoutService(db)
    shootout = await service.get_shootout(user, shootout_id)

    if not shootout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    # Build segment list and collect metrics for averaging
    segments: list[SegmentComparisonItem] = []
    metrics_for_avg: list[dict[str, Any]] = []
    total_duration_ms = 0

    for ts in sorted(shootout.tone_selections, key=lambda x: x.position):
        # Build timestamps if available
        timestamps = None
        if ts.start_ms is not None and ts.end_ms is not None:
            timestamps = SegmentTimestampsSchema(
                position=ts.position,
                start_ms=ts.start_ms,
                end_ms=ts.end_ms,
                duration_ms=ts.end_ms - ts.start_ms,
                source_start_sample=0,
                source_end_sample=0,
                sample_rate=shootout.sample_rate,
            )
            total_duration_ms = max(total_duration_ms, ts.end_ms)

        # Parse audio metrics
        audio_metrics = None
        if ts.audio_metrics:
            audio_metrics = AudioMetricsSchema.model_validate(ts.audio_metrics)
            # Collect for averaging
            metrics_for_avg.append(ts.audio_metrics)

        # Parse AI evaluation
        ai_evaluation = None
        if ts.ai_evaluation:
            ai_evaluation = AIEvaluationSchema.model_validate(ts.ai_evaluation)

        segments.append(
            SegmentComparisonItem(
                segment_id=ts.id,
                position=ts.position,
                tone_title=ts.tone_title,
                timestamps=timestamps,
                audio_metrics=audio_metrics,
                ai_evaluation=ai_evaluation,
            )
        )

    # Calculate averages if we have metrics
    averages = None
    if metrics_for_avg:
        averages = _compute_averages(metrics_for_avg)

    return ShootoutComparisonResponse(
        shootout_id=shootout.id,
        shootout_name=shootout.name,
        segment_count=len(segments),
        total_duration_ms=total_duration_ms,
        segments=segments,
        averages=averages,
    )


def _compute_averages(metrics_list: list[dict[str, Any]]) -> MetricsAverages:
    """Compute average metrics from a list of metric dictionaries.

    Args:
        metrics_list: List of audio metrics dictionaries.

    Returns:
        MetricsAverages with computed averages.
    """
    count = len(metrics_list)
    if count == 0:
        # Return zeros for empty list
        return MetricsAverages(
            rms_dbfs=0.0,
            peak_dbfs=0.0,
            spectral_centroid_hz=0.0,
            bass_energy_ratio=0.0,
            mid_energy_ratio=0.0,
            treble_energy_ratio=0.0,
            lufs_integrated=0.0,
        )

    # Sum up all metrics
    sum_rms = 0.0
    sum_peak = 0.0
    sum_centroid = 0.0
    sum_bass = 0.0
    sum_mid = 0.0
    sum_treble = 0.0
    sum_lufs = 0.0

    for m in metrics_list:
        core = m.get("core", {})
        spectral = m.get("spectral", {})
        advanced = m.get("advanced", {})

        sum_rms += core.get("rms_dbfs", 0.0)
        sum_peak += core.get("peak_dbfs", 0.0)
        sum_centroid += spectral.get("spectral_centroid_hz", 0.0)
        sum_bass += spectral.get("bass_energy_ratio", 0.0)
        sum_mid += spectral.get("mid_energy_ratio", 0.0)
        sum_treble += spectral.get("treble_energy_ratio", 0.0)
        sum_lufs += advanced.get("lufs_integrated", 0.0)

    return MetricsAverages(
        rms_dbfs=sum_rms / count,
        peak_dbfs=sum_peak / count,
        spectral_centroid_hz=sum_centroid / count,
        bass_energy_ratio=sum_bass / count,
        mid_energy_ratio=sum_mid / count,
        treble_energy_ratio=sum_treble / count,
        lufs_integrated=sum_lufs / count,
    )
