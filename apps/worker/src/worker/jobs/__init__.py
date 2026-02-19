"""Background jobs - TaskIQ job definitions."""

from worker.jobs.audio import handle_shootout_audio_job
from worker.jobs.audio_processing import handle_audio_processing
from worker.jobs.master_audio import handle_shootout_master_job
from worker.jobs.shootout import handle_shootout_job

__all__ = [
    "handle_audio_processing",
    "handle_shootout_audio_job",
    "handle_shootout_job",
    "handle_shootout_master_job",
]
