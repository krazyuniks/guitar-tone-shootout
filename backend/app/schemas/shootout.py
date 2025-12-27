"""Shootout configuration schemas for API request/response validation.

These schemas define the structure for shootout configurations
sent from the frontend and stored in the job config.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Audio Metrics Schemas (matching pipeline/src/guitar_tone_shootout/metrics.py)
# =============================================================================


class CoreMetricsSchema(BaseModel):
    """Core loudness and dynamic metrics.

    Attributes:
        rms_dbfs: RMS level in dB relative to full scale
        peak_dbfs: Peak level in dB relative to full scale
        crest_factor_db: Peak-to-RMS ratio in dB (indicates dynamic range)
        dynamic_range_db: Difference between loudest and quietest parts
    """

    rms_dbfs: float = Field(..., description="RMS level in dBFS")
    peak_dbfs: float = Field(..., description="Peak level in dBFS")
    crest_factor_db: float = Field(..., description="Peak/RMS ratio in dB")
    dynamic_range_db: float = Field(..., description="Dynamic range in dB")


class SpectralMetricsSchema(BaseModel):
    """Spectral distribution metrics.

    Attributes:
        spectral_centroid_hz: Center of mass of the spectrum (brightness indicator)
        bass_energy_ratio: Proportion of energy in bass range (20-250 Hz)
        mid_energy_ratio: Proportion of energy in mid range (250-2000 Hz)
        treble_energy_ratio: Proportion of energy in treble range (2000-20000 Hz)
    """

    spectral_centroid_hz: float = Field(
        ..., description="Spectral centroid in Hz (brightness)"
    )
    bass_energy_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Bass energy (20-250 Hz) ratio"
    )
    mid_energy_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Mid energy (250-2000 Hz) ratio"
    )
    treble_energy_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Treble energy (2000-20000 Hz) ratio"
    )


class AdvancedMetricsSchema(BaseModel):
    """Advanced dynamics and envelope metrics.

    Attributes:
        lufs_integrated: Integrated loudness in LUFS (EBU R128)
        transient_density: Number of transients per second
        attack_time_ms: Time to reach peak amplitude in milliseconds
        sustain_decay_rate_db_s: Rate of amplitude decay in dB/second
    """

    lufs_integrated: float = Field(..., description="Integrated loudness in LUFS")
    transient_density: float = Field(
        ..., ge=0.0, description="Transients per second"
    )
    attack_time_ms: float = Field(
        ..., ge=0.0, description="Attack time in milliseconds"
    )
    sustain_decay_rate_db_s: float = Field(
        ..., description="Sustain decay rate in dB/second"
    )


class AudioMetricsSchema(BaseModel):
    """Complete audio metrics for a guitar tone sample.

    This schema mirrors the AudioMetrics model from the pipeline library
    for consistent serialization between the pipeline and API.

    Attributes:
        duration_seconds: Length of the audio in seconds
        sample_rate: Sample rate in Hz
        core: Core loudness metrics
        spectral: Spectral distribution metrics
        advanced: Advanced dynamics metrics
    """

    duration_seconds: float = Field(
        ..., ge=0.0, description="Audio duration in seconds"
    )
    sample_rate: int = Field(..., gt=0, description="Sample rate in Hz")
    core: CoreMetricsSchema = Field(..., description="Core loudness metrics")
    spectral: SpectralMetricsSchema = Field(
        ..., description="Spectral distribution metrics"
    )
    advanced: AdvancedMetricsSchema = Field(
        ..., description="Advanced dynamics metrics"
    )


# =============================================================================
# AI Evaluation Schema
# =============================================================================


class AIEvaluationSchema(BaseModel):
    """AI-generated evaluation of a tone.

    Stores subjective analysis from AI models (e.g., tone description,
    comparison insights, recommended use cases).

    Attributes:
        model_name: The AI model used for evaluation (e.g., "gpt-4", "claude-3")
        model_version: Version identifier for the model
        tone_description: Natural language description of the tone character
        strengths: List of tone strengths/positive characteristics
        weaknesses: List of tone weaknesses/negative characteristics
        recommended_genres: Suggested musical genres for this tone
        comparison_notes: Notes from comparison with other tones (if applicable)
        overall_rating: Subjective quality rating (1-10 scale)
        raw_response: The complete raw response from the AI model
    """

    model_name: str = Field(
        ..., description="AI model used for evaluation", examples=["gpt-4", "claude-3"]
    )
    model_version: str | None = Field(
        default=None, description="Version identifier for the AI model"
    )
    tone_description: str = Field(
        ..., description="Natural language description of the tone character"
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="List of tone strengths/positive characteristics",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="List of tone weaknesses/negative characteristics",
    )
    recommended_genres: list[str] = Field(
        default_factory=list,
        description="Suggested musical genres for this tone",
        examples=[["rock", "blues", "metal"]],
    )
    comparison_notes: str | None = Field(
        default=None,
        description="Notes from comparison with other tones in the shootout",
    )
    overall_rating: float | None = Field(
        default=None, ge=1.0, le=10.0, description="Subjective quality rating (1-10)"
    )
    raw_response: dict[str, Any] | None = Field(
        default=None, description="Complete raw response from the AI model"
    )


# =============================================================================
# Processing Metadata Schema
# =============================================================================


class ProcessingMetadataSchema(BaseModel):
    """Metadata about the processing pipeline for reproducibility.

    Stores all configuration and version information needed to reproduce
    the exact processing of a shootout.

    Attributes:
        pipeline_version: Version of the guitar-tone-shootout pipeline
        nam_version: Version of NAM (Neural Amp Modeler) used
        ffmpeg_version: Version of ffmpeg used for audio/video processing
        python_version: Python version used for processing
        processed_at: ISO timestamp when processing completed
        processing_duration_seconds: Total processing time
        worker_id: Identifier of the worker that processed the job
        config_hash: Hash of the processing configuration for cache validation
        audio_settings: Audio processing settings (sample rate, bit depth, etc.)
        video_settings: Video encoding settings (if applicable)
    """

    pipeline_version: str = Field(
        ..., description="Version of the guitar-tone-shootout pipeline"
    )
    nam_version: str | None = Field(
        default=None, description="Version of NAM (Neural Amp Modeler) used"
    )
    ffmpeg_version: str | None = Field(
        default=None, description="Version of ffmpeg used"
    )
    python_version: str | None = Field(
        default=None, description="Python version used for processing"
    )
    processed_at: str = Field(
        ..., description="ISO timestamp when processing completed"
    )
    processing_duration_seconds: float | None = Field(
        default=None, ge=0.0, description="Total processing time in seconds"
    )
    worker_id: str | None = Field(
        default=None, description="Identifier of the worker that processed the job"
    )
    config_hash: str | None = Field(
        default=None,
        description="Hash of the processing configuration for cache validation",
    )
    audio_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Audio processing settings (sample rate, bit depth, etc.)",
    )
    video_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Video encoding settings (codec, resolution, etc.)",
    )


# =============================================================================
# Segment Timestamp Schema
# =============================================================================


class SegmentTimestampsSchema(BaseModel):
    """Precise timing information for a processed audio segment.

    Tracks both the position in the final output (milliseconds) and the
    source sample positions for exact reproducibility.

    Attributes:
        position: Segment index (0-based) in the shootout
        start_ms: Start position in final output (milliseconds)
        end_ms: End position in final output (milliseconds)
        duration_ms: Segment duration (milliseconds)
        source_start_sample: Start sample index in source audio
        source_end_sample: End sample index in source audio
        sample_rate: Sample rate used for processing (Hz)
    """

    position: int = Field(
        ...,
        ge=0,
        description="Segment index (0-based) in the shootout",
    )
    start_ms: int = Field(
        ...,
        ge=0,
        description="Start position in final output (milliseconds)",
    )
    end_ms: int = Field(
        ...,
        ge=0,
        description="End position in final output (milliseconds)",
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Segment duration (milliseconds)",
    )
    source_start_sample: int = Field(
        default=0,
        ge=0,
        description="Start sample index in source audio",
    )
    source_end_sample: int = Field(
        default=0,
        ge=0,
        description="End sample index in source audio",
    )
    sample_rate: int = Field(
        ...,
        gt=0,
        description="Sample rate used for processing (Hz)",
    )


class EffectSchema(BaseModel):
    """Schema for an audio effect in the signal chain."""

    effect_type: str = Field(
        description="Type of effect (eq, reverb, delay, gain)",
        examples=["eq", "reverb", "delay", "gain"],
    )
    value: str = Field(
        description="Effect parameters or preset name",
        examples=["highpass_80hz", "room", "slapback", "+3.0"],
    )


class ToneSchema(BaseModel):
    """Schema for a single tone configuration."""

    name: str = Field(
        description="Display name for this tone",
        examples=["Plexi Crunch", "High Gain Lead"],
    )
    model_path: str | None = Field(
        default=None,
        description="Path to NAM model file (relative to models dir)",
        examples=["tone3000/jcm800-44269/JCM800 capture 3.nam"],
    )
    ir_path: str | None = Field(
        default=None,
        description="Path to IR file (relative to IRs dir)",
        examples=["greenback_1.wav"],
    )
    tone3000_model_id: int | None = Field(
        default=None,
        description="Tone 3000 model ID for downloading",
        examples=[44269],
    )
    description: str | None = Field(
        default=None,
        description="Description of the tone",
        examples=["Classic Marshall crunch"],
    )
    highpass: bool = Field(
        default=True,
        description="Apply 80Hz highpass filter before processing",
    )
    effects: list[EffectSchema] = Field(
        default_factory=list,
        description="Additional effects to apply after the amp model",
    )


class ShootoutConfigSchema(BaseModel):
    """Schema for a complete shootout configuration.

    This is the structure sent from the frontend when creating a shootout job.
    """

    name: str = Field(
        description="Name of the shootout comparison",
        examples=["Marshall vs Mesa Comparison"],
    )
    tones: list[ToneSchema] = Field(
        min_length=1,
        max_length=10,
        description="List of tone configurations to compare (1-10 tones)",
    )
    author: str | None = Field(
        default=None,
        description="Author name",
        examples=["John Doe"],
    )
    description: str | None = Field(
        default=None,
        description="Description of the comparison",
        examples=["Comparing classic British vs American high gain tones"],
    )
    guitar: str | None = Field(
        default=None,
        description="Guitar used for DI recording",
        examples=["Fender Stratocaster", "Gibson Les Paul"],
    )
    pickup: str | None = Field(
        default=None,
        description="Pickup configuration used",
        examples=["Bridge Humbucker", "Neck Single Coil"],
    )


class ShootoutSubmitRequest(BaseModel):
    """Request schema for submitting a shootout job.

    Note: The DI track file is uploaded separately via multipart form.
    This schema is for the JSON configuration payload.
    """

    config: ShootoutConfigSchema = Field(
        description="Shootout configuration",
    )


class ShootoutSubmitResponse(BaseModel):
    """Response schema after submitting a shootout job."""

    job_id: str = Field(
        description="The created job ID for tracking progress",
    )
    message: str = Field(
        default="Job submitted successfully",
        description="Success message",
    )


# =============================================================================
# Shootout Database Model Schemas
# =============================================================================


class ToneSelectionCreate(BaseModel):
    """Schema for creating a tone selection."""

    tone3000_tone_id: int = Field(
        description="Tone 3000 tone ID",
    )
    tone3000_model_id: int = Field(
        description="Tone 3000 model ID",
    )
    tone_title: str = Field(
        max_length=255,
        description="Title of the tone from Tone 3000",
    )
    model_name: str = Field(
        max_length=255,
        description="Name of the model from Tone 3000",
    )
    model_size: str = Field(
        max_length=20,
        description="Model size (standard, lite, feather, nano)",
        examples=["standard", "lite", "feather", "nano"],
    )
    gear_type: str = Field(
        max_length=20,
        description="Type of gear (amp, pedal, full-rig)",
        examples=["amp", "pedal", "full-rig"],
    )
    display_name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional display name override",
    )
    description: str | None = Field(
        default=None,
        description="Description of the tone (e.g., 'Classic British crunch tone')",
    )
    ir_path: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional IR file path override",
    )
    highpass: bool = Field(
        default=True,
        description="Apply 80Hz highpass filter before processing",
    )
    effects: list[EffectSchema] = Field(
        default_factory=list,
        description="Additional effects to apply after the amp model",
    )
    position: int = Field(
        default=0,
        ge=0,
        description="Position in the shootout comparison order",
    )


class ToneSelectionResponse(BaseModel):
    """Schema for tone selection in API responses."""

    id: UUID
    tone3000_tone_id: int
    tone3000_model_id: int
    tone_title: str
    model_name: str
    model_size: str
    gear_type: str
    display_name: str | None
    description: str | None
    ir_path: str | None
    highpass: bool
    effects_json: str | None
    position: int
    start_ms: int | None
    end_ms: int | None
    audio_metrics: AudioMetricsSchema | None
    ai_evaluation: AIEvaluationSchema | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShootoutCreate(BaseModel):
    """Schema for creating a new shootout."""

    name: str = Field(
        max_length=255,
        description="Name of the shootout comparison",
    )
    description: str | None = Field(
        default=None,
        description="Description of the comparison",
    )
    di_track_path: str = Field(
        max_length=1000,
        description="Path to the uploaded DI track file",
    )
    di_track_original_name: str = Field(
        max_length=255,
        description="Original filename of the uploaded DI track",
    )
    output_format: str = Field(
        default="mp4",
        max_length=10,
        description="Output video format",
        examples=["mp4", "webm"],
    )
    sample_rate: int = Field(
        default=44100,
        ge=22050,
        le=96000,
        description="Audio sample rate in Hz",
    )
    guitar: str | None = Field(
        default=None,
        max_length=255,
        description="Guitar used for DI recording",
    )
    pickup: str | None = Field(
        default=None,
        max_length=255,
        description="Pickup configuration used",
    )
    di_track_description: str | None = Field(
        default=None,
        description="Description of the DI recording",
    )
    tone_selections: list[ToneSelectionCreate] = Field(
        min_length=1,
        max_length=10,
        description="List of tones to include in the shootout (1-10)",
    )


class ShootoutUpdate(BaseModel):
    """Schema for updating a shootout."""

    name: str | None = Field(
        default=None,
        max_length=255,
        description="Name of the shootout comparison",
    )
    description: str | None = Field(
        default=None,
        description="Description of the comparison",
    )
    guitar: str | None = Field(
        default=None,
        max_length=255,
        description="Guitar used for DI recording",
    )
    pickup: str | None = Field(
        default=None,
        max_length=255,
        description="Pickup configuration used",
    )
    di_track_description: str | None = Field(
        default=None,
        description="Description of the DI recording",
    )


class ShootoutResponse(BaseModel):
    """Schema for shootout in API responses."""

    id: UUID
    name: str
    description: str | None
    di_track_path: str
    di_track_original_name: str
    output_format: str
    sample_rate: int
    guitar: str | None
    pickup: str | None
    di_track_description: str | None
    is_processed: bool
    output_path: str | None
    processing_metadata: ProcessingMetadataSchema | None
    tone_selections: list[ToneSelectionResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShootoutListItem(BaseModel):
    """Schema for a single shootout in list responses."""

    id: UUID
    name: str
    description: str | None
    is_processed: bool
    output_path: str | None
    tone_count: int = Field(
        description="Number of tones in this shootout",
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShootoutListResponse(BaseModel):
    """Paginated list of shootouts."""

    shootouts: list[ShootoutListItem] = Field(
        description="List of shootouts",
    )
    total: int = Field(
        description="Total number of shootouts matching the query",
    )
    page: int = Field(
        description="Current page number (1-indexed)",
    )
    page_size: int = Field(
        description="Number of items per page",
    )


# =============================================================================
# Metrics API Response Schemas
# =============================================================================


class ProcessingVersionsSchema(BaseModel):
    """Software versions used during processing."""

    pedalboard: str = Field(..., description="Pedalboard library version")
    nam_vst: str = Field(..., description="NAM VST/library version")
    ffmpeg: str = Field(..., description="FFmpeg version")
    pipeline: str = Field(..., description="Pipeline version")
    python: str = Field(..., description="Python version")


class AudioSettingsFullSchema(BaseModel):
    """Audio processing settings for reproducibility."""

    sample_rate: int = Field(..., gt=0, description="Sample rate in Hz")
    bit_depth: int = Field(..., gt=0, description="Bit depth")
    channels: int = Field(..., ge=1, le=2, description="Number of channels")
    format: str = Field(default="float32", description="Audio format")


class NormalizationSettingsSchema(BaseModel):
    """Audio normalization settings."""

    input_target_rms_db: float = Field(
        default=-18.0, description="Input normalization target RMS in dB"
    )
    output_target_rms_db: float = Field(
        default=-14.0, description="Output normalization target RMS in dB"
    )
    method: str = Field(default="rms", description="Normalization method")
    headroom_db: float = Field(default=-1.0, description="Peak headroom in dB")


class FileHashesSchema(BaseModel):
    """SHA-256 hashes of input files."""

    di_track_sha256: str = Field(..., description="SHA-256 hash of DI track")
    nam_model_sha256: str | None = Field(
        default=None, description="SHA-256 hash of NAM model"
    )
    ir_sha256: str | None = Field(default=None, description="SHA-256 hash of IR file")


class ShootoutMetadataResponse(BaseModel):
    """Full reproducibility metadata for a shootout.

    Response schema for GET /api/v1/shootouts/{id}/metadata
    """

    shootout_id: UUID = Field(..., description="Shootout ID")
    processing_versions: ProcessingVersionsSchema | None = Field(
        default=None, description="Software versions used"
    )
    normalization: NormalizationSettingsSchema | None = Field(
        default=None, description="Normalization settings"
    )
    audio_settings: AudioSettingsFullSchema | None = Field(
        default=None, description="Audio processing settings"
    )
    file_hashes: FileHashesSchema | None = Field(
        default=None, description="Input file hashes"
    )
    total_duration_ms: int = Field(default=0, ge=0, description="Total output duration")
    segment_count: int = Field(default=0, ge=0, description="Number of segments")
    processed_at: str | None = Field(
        default=None, description="ISO timestamp of processing"
    )
    platform_info: str | None = Field(
        default=None, description="Platform/OS information"
    )


class SignalChainSchema(BaseModel):
    """Signal chain information for a segment."""

    tone_title: str = Field(..., description="Title of the tone")
    model_name: str = Field(..., description="NAM model name")
    model_size: str = Field(..., description="Model size (standard, lite, etc.)")
    gear_type: str = Field(..., description="Gear type (amp, pedal, full-rig)")
    ir_path: str | None = Field(default=None, description="IR file path if used")
    highpass: bool = Field(default=True, description="Highpass filter applied")
    effects: list[EffectSchema] = Field(
        default_factory=list, description="Additional effects"
    )


class SegmentMetricsResponse(BaseModel):
    """Detailed metrics for a single segment.

    Response schema for GET /api/v1/shootouts/{id}/segments/{position}/metrics
    """

    segment_id: UUID = Field(..., description="Segment (tone selection) ID")
    position: int = Field(..., ge=0, description="Position in shootout")
    timestamps: SegmentTimestampsSchema | None = Field(
        default=None, description="Precise timing information"
    )
    audio_metrics: AudioMetricsSchema | None = Field(
        default=None, description="Audio analysis metrics"
    )
    ai_evaluation: AIEvaluationSchema | None = Field(
        default=None, description="AI-generated evaluation"
    )
    signal_chain: SignalChainSchema = Field(
        ..., description="Signal chain configuration"
    )


class SegmentComparisonItem(BaseModel):
    """Single segment for comparison view."""

    segment_id: UUID = Field(..., description="Segment ID")
    position: int = Field(..., ge=0, description="Position in shootout")
    tone_title: str = Field(..., description="Tone title")
    timestamps: SegmentTimestampsSchema | None = Field(
        default=None, description="Timing information"
    )
    audio_metrics: AudioMetricsSchema | None = Field(
        default=None, description="Audio metrics"
    )
    ai_evaluation: AIEvaluationSchema | None = Field(
        default=None, description="AI evaluation"
    )


class MetricsAverages(BaseModel):
    """Average metrics across all segments."""

    rms_dbfs: float = Field(..., description="Average RMS level")
    peak_dbfs: float = Field(..., description="Average peak level")
    spectral_centroid_hz: float = Field(..., description="Average spectral centroid")
    bass_energy_ratio: float = Field(..., description="Average bass energy ratio")
    mid_energy_ratio: float = Field(..., description="Average mid energy ratio")
    treble_energy_ratio: float = Field(..., description="Average treble energy ratio")
    lufs_integrated: float = Field(..., description="Average LUFS")


class ShootoutComparisonResponse(BaseModel):
    """Comparison of all segments with averages.

    Response schema for GET /api/v1/shootouts/{id}/comparison
    """

    shootout_id: UUID = Field(..., description="Shootout ID")
    shootout_name: str = Field(..., description="Shootout name")
    segment_count: int = Field(..., ge=0, description="Number of segments")
    total_duration_ms: int = Field(default=0, ge=0, description="Total duration")
    segments: list[SegmentComparisonItem] = Field(
        ..., description="All segments with metrics"
    )
    averages: MetricsAverages | None = Field(
        default=None, description="Average metrics across segments"
    )
