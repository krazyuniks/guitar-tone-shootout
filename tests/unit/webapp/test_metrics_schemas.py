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
