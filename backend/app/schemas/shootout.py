"""Shootout configuration schemas for API request/response validation.

These schemas define the structure for shootout configurations
sent from the frontend and stored in the job config.
"""

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
