"""Domain value objects - immutable, identity-less types."""

from gts.domain.value_objects.audio_checksum import AudioChecksum
from gts.domain.value_objects.audio_result import AudioResult
from gts.domain.value_objects.block_category import BlockCategory
from gts.domain.value_objects.chapter_marker import ChapterMarker
from gts.domain.value_objects.composition_spec import CompositionSpec
from gts.domain.value_objects.download_status import DownloadStatus
from gts.domain.value_objects.job_status import JobStatus, JobType
from gts.domain.value_objects.processing_metadata import ProcessingMetadata
from gts.domain.value_objects.render_status import RenderStatus, RenderStatusEnum
from gts.domain.value_objects.shootout_visibility import ShootoutVisibility
from gts.domain.value_objects.signal_chain_enums import (
    BlockPosition,
    EffectCategory,
    GearType,
    ModelSize,
    Platform,
)
from gts.domain.value_objects.tone_config import ToneConfig
from gts.domain.value_objects.video_result import VideoResult
from gts.domain.value_objects.waveform_data import WaveformData

__all__ = [
    "AudioChecksum",
    "AudioResult",
    "BlockCategory",
    "BlockPosition",
    "ChapterMarker",
    "CompositionSpec",
    "DownloadStatus",
    "EffectCategory",
    "GearType",
    "JobStatus",
    "JobType",
    "ModelSize",
    "Platform",
    "ProcessingMetadata",
    "RenderStatus",
    "RenderStatusEnum",
    "ShootoutVisibility",
    "ToneConfig",
    "VideoResult",
    "WaveformData",
]
