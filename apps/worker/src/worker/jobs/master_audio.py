"""Master Audio Creation Job.

This module creates a master audio file for a shootout by:
1. Loading all audio segments for the shootout
2. Normalising each segment to -14.0 LUFS
3. Updating AudioSegment records with post-normalisation loudness values
4. Concatenating segments in chain position order
5. Creating chapter markers
6. Saving the master audio as FLAC
7. Updating the shootout's output_path field
"""

import os
from pathlib import Path
from uuid import UUID

import numpy as np
import soundfile as sf
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from audio.processing.loudness import normalize_loudness
from worker.db import get_session


async def create_master_audio(shootout_id: UUID, database_url: str | None = None) -> None:
    """Create master audio file for a shootout.

    Args:
        shootout_id: UUID of the shootout to process
        database_url: Database connection string (or None to use DATABASE_URL env var)

    Raises:
        ValueError: If shootout is not found
    """
    if database_url is None:
        database_url = os.environ.get("DATABASE_URL", "")

    async with get_session(database_url) as session:
        from webapp.adapters.persistence.models.shootout import Shootout, ShootoutChain

        stmt = (
            select(Shootout)
            .where(Shootout.id == shootout_id)
            .options(joinedload(Shootout.chains).joinedload(ShootoutChain.segments))
        )
        result = await session.execute(stmt)
        shootout = result.unique().scalar_one_or_none()

        if shootout is None:
            raise ValueError(f"Shootout {shootout_id} not found")

        if not shootout.chains:
            return

        chains = sorted(shootout.chains, key=lambda c: c.position)

        total_segments = sum(len(chain.segments) for chain in chains)
        if total_segments == 0:
            return

        output_dir = Path("processed") / str(shootout_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        normalized_files: list[Path] = []
        for chain in chains:
            for segment in chain.segments:
                input_path = Path(segment.file_path)
                normalized_path = output_dir / f"normalized_{input_path.name}"

                result_lufs, result_peak_dbfs = normalize_loudness(
                    input_path, normalized_path, target_lufs=-14.0
                )

                segment.integrated_lufs = result_lufs
                segment.peak_dbfs = result_peak_dbfs
                normalized_files.append(normalized_path)

        audio_arrays = []
        sample_rate = None
        for norm_file in normalized_files:
            audio_data, sr = sf.read(norm_file)
            audio_arrays.append(audio_data)
            if sample_rate is None:
                sample_rate = sr

        master_audio = np.concatenate(audio_arrays)

        chapters = []
        current_time = 0.0
        for chain in chains:
            for segment in chain.segments:
                duration = segment.duration_seconds or 0.0
                chapters.append(
                    {
                        "label": chain.label,
                        "start_time": current_time,
                        "end_time": current_time + duration,
                    }
                )
                current_time += duration

        master_path = output_dir / "master.flac"
        sf.write(master_path, master_audio, sample_rate)

        shootout.output_path = str(master_path)

        await session.commit()
