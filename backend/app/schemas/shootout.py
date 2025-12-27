"""Shootout configuration schemas for API request/response validation.

These schemas define the structure for shootout configurations
sent from the frontend and stored in the job config.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
