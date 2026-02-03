"""Domain value objects - immutable, identity-less types."""

from core.domain.value_objects.audio_checksum import AudioChecksum
from core.domain.value_objects.audio_result import AudioResult
from core.domain.value_objects.block_category import BlockCategory
from core.domain.value_objects.chapter_marker import ChapterMarker
from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.job_status import JobStatus, JobType
from core.domain.value_objects.processing_metadata import ProcessingMetadata
from core.domain.value_objects.signal_chain_enums import (
    BlockPosition,
    EffectCategory,
    GearType,
    ModelSize,
    Platform,
)
from core.domain.value_objects.tone_config import ToneConfig
from core.domain.value_objects.video_result import VideoResult
from core.domain.value_objects.waveform_data import WaveformData

__all__ = [
    "AudioChecksum",
    "AudioResult",
    "BlockCategory",
    "BlockPosition",
    "ChapterMarker",
    "DownloadStatus",
    "EffectCategory",
    "GearType",
    "JobStatus",
    "JobType",
    "ModelSize",
    "Platform",
    "ProcessingMetadata",
    "ToneConfig",
    "VideoResult",
    "WaveformData",
]
