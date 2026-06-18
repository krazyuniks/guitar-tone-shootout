#!/usr/bin/env python3
"""Idempotent reconcile importer: recover DI tracks from on-disk audio.

Recovery tool for DI tracks whose ``core_di_tracks`` rows were lost (e.g. a
worktree teardown deleting a DB volume) while the audio files survived on disk.

Idempotent: a file already represented by a row for the same owner and content
checksum is skipped, so repeated runs converge to "exactly one row per unique
genuine audio file under <source>". Safe to re-run after partial failures.

It refuses to recover noise. Files are skipped (with a reason) when they are:
  * undecodable / corrupted (soundfile cannot open them),
  * below a byte/duration threshold (test fixtures, header-only stubs),
  * byte-duplicate content already seen this run (one row per unique checksum),
  * already present in the DB for this owner.

Genuine survivors are copied into the storage upload dir under a content-
addressed name (so re-copies are no-ops) and inserted via the canonical
``DITrackService`` (same metadata/waveform/checksum path the app uses).

Runs inside the webapp container (needs the DB, soundfile, and the webapp
package on the path). Source must be a path visible in the container, i.e.
under ``/app/storage``:

    # dry run (default): report what WOULD be recovered, write nothing
    docker compose exec -T webapp python /app/scripts/reconcile_di_tracks.py \
        /app/storage/<source>

    # apply: copy files and write rows
    docker compose exec -T webapp python /app/scripts/reconcile_di_tracks.py \
        /app/storage/<source> --apply

Owner defaults to the sole OAuth-identity user (the single real account in a
single-user install); pass --user-id to override.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import soundfile as sf
from sqlalchemy import text

try:
    from gts.domain.value_objects.audio_checksum import AudioChecksum
    from webapp.adapters.persistence.models.base import get_async_session
    from webapp.services.di_track_service import DITrackService
except ImportError:  # direct execution outside the installed env
    repo_root = Path(__file__).parent.parent
    sys.path.insert(0, str(repo_root / "apps" / "webapp" / "src"))
    from gts.domain.value_objects.audio_checksum import AudioChecksum
    from webapp.adapters.persistence.models.base import get_async_session
    from webapp.services.di_track_service import DITrackService

SUPPORTED_FORMATS = {".wav", ".flac", ".ogg", ".mp3"}
MIN_BYTES = 2048  # below this is a fixture/stub, not a real recording
MIN_SECONDS = 0.5  # below this is a fixture, not a real DI take


@dataclass
class Plan:
    """A file selected for recovery (one per unique genuine checksum)."""

    source: Path
    name: str
    original_filename: str
    checksum: str
    duration_seconds: float
    sample_rate: int
    channels: int


@dataclass
class Report:
    imported: int = 0
    planned: list[Plan] = field(default_factory=list)
    skipped: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)


def find_audio(source: Path) -> list[Path]:
    files: list[Path] = []
    for suffix in SUPPORTED_FORMATS:
        files.extend(source.rglob(f"*{suffix}"))
    return sorted(f for f in files if f.is_file())


async def _existing_checksums(session, user_id: UUID) -> set[str]:
    """Content checksums already recorded for this owner (idempotency set)."""
    rows = await session.execute(
        text("SELECT checksum FROM core_di_tracks WHERE user_id = :uid AND checksum IS NOT NULL"),
        {"uid": str(user_id)},
    )
    return {r[0] for r in rows if r[0]}


async def _resolve_user_id(session, explicit: str | None) -> UUID:
    if explicit:
        return UUID(explicit)
    rows = await session.execute(text("SELECT DISTINCT user_id FROM core_user_identities"))
    ids = [r[0] for r in rows]
    if len(ids) == 1:
        return UUID(str(ids[0]))
    raise SystemExit(
        f"--user-id is required: found {len(ids)} identity-bearing users, cannot auto-resolve owner"
    )


def select_plans(files: list[Path], existing: set[str], report: Report) -> list[Plan]:
    """Decode/validate/dedup files into a recovery plan, recording skip reasons."""
    seen: set[str] = set()
    plans: list[Plan] = []
    for path in files:
        try:
            if path.stat().st_size < MIN_BYTES:
                report.skipped["too-small (fixture/stub)"] += 1
                continue
            try:
                with sf.SoundFile(str(path)) as audio:
                    duration = len(audio) / audio.samplerate
                    sample_rate = audio.samplerate
                    channels = audio.channels
            except Exception:
                report.skipped["undecodable/corrupted"] += 1
                continue
            if duration < MIN_SECONDS:
                report.skipped["too-short (fixture)"] += 1
                continue

            checksum = AudioChecksum.from_file(path).value
            if checksum in seen:
                report.skipped["duplicate-content (this run)"] += 1
                continue
            seen.add(checksum)
            if checksum in existing:
                report.skipped["already-imported"] += 1
                continue

            plans.append(
                Plan(
                    source=path,
                    name=path.stem,
                    original_filename=path.name,
                    checksum=checksum,
                    duration_seconds=round(duration, 3),
                    sample_rate=sample_rate,
                    channels=channels,
                )
            )
        except Exception as e:
            report.errors.append(f"{path.name}: {e}")
    return plans


async def apply_plans(
    session,
    service: DITrackService,
    plans: list[Plan],
    user_id: UUID,
    storage: Path,
    report: Report,
) -> None:
    storage.mkdir(parents=True, exist_ok=True)
    for plan in plans:
        try:
            # Content-addressed destination: deterministic, so a re-run that
            # reaches a file already copied finds it in place and does not re-copy.
            dest = storage / f"{user_id}_{plan.checksum[:12]}{plan.source.suffix.lower()}"
            if not dest.exists():
                shutil.copy2(plan.source, dest)
            await service.upload(
                user_id=user_id,
                file_path=str(dest),
                original_filename=plan.original_filename,
                name=plan.name,
                description=f"Recovered from {plan.source.parent.name}",
            )
            report.imported += 1
            print(f"+ recovered: {plan.original_filename}  ({plan.duration_seconds}s)")
        except ValueError as e:
            if "duplicate checksum" in str(e):
                report.skipped["already-imported (race)"] += 1
            else:
                report.errors.append(f"{plan.original_filename}: {e}")
        except Exception as e:
            report.errors.append(f"{plan.original_filename}: {e}")
    await session.commit()


async def _main(args: argparse.Namespace) -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 1

    source = Path(args.source).expanduser()
    if not source.exists():
        print(f"ERROR: source does not exist: {source}", file=sys.stderr)
        return 1

    storage = (
        Path(args.storage_path)
        if args.storage_path
        else Path(os.environ.get("GTS_STORAGE_ROOT", "/app/storage")) / "uploads" / "di_tracks"
    )

    session_factory = get_async_session(database_url)
    report = Report()

    async with session_factory() as session:
        user_id = await _resolve_user_id(session, args.user_id)
        existing = await _existing_checksums(session, user_id)
        files = find_audio(source)
        plans = select_plans(files, existing, report)
        report.planned = plans

        print(f"source:           {source}")
        print(f"owner (user_id):  {user_id}")
        print(f"audio files found: {len(files)}")
        print(f"existing rows for owner: {len(existing)}")
        print(f"unique genuine tracks to recover: {len(plans)}")
        print("skipped:")
        for reason, n in sorted(report.skipped.items()):
            print(f"  {n:>5}  {reason}")

        if args.apply and plans:
            print(f"\n--apply: writing {len(plans)} rows...\n")
            service = DITrackService(session)
            await apply_plans(session, service, plans, user_id, storage, report)
        elif plans:
            print("\n(dry run - no rows written; pass --apply to recover)")
            for plan in plans[:50]:
                print(f"  would recover: {plan.original_filename}  ({plan.duration_seconds}s)")
            if len(plans) > 50:
                print(f"  ... and {len(plans) - 50} more")

    print("\n" + "=" * 60)
    print(f"  recovered/would-recover: {report.imported if args.apply else len(report.planned)}")
    print(f"  skipped: {sum(report.skipped.values())}")
    print(f"  errors:  {len(report.errors)}")
    for err in report.errors[:20]:
        print(f"    ! {err}")
    print("=" * 60)
    return 1 if report.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile on-disk DI audio into core_di_tracks")
    parser.add_argument("source", help="Directory of audio files (must be visible in-container)")
    parser.add_argument("--user-id", help="Owner UUID (default: the sole OAuth-identity user)")
    parser.add_argument("--apply", action="store_true", help="Write rows (default: dry run)")
    parser.add_argument("--storage-path", help="Override storage dir for recovered copies")
    args = parser.parse_args()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())
