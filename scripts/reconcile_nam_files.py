#!/usr/bin/env python3
"""Reconcile .nam files from archive into source_downloads/t3k/.

Maps UUID-named files in models/ back to T3K model IDs using a pre-dumped
mapping CSV, then copies them to source_downloads/t3k/{model_id}/.

Also copies .archive-backup/models/t3k/{tone_id}/{model_id}_size.nam files.

Preparation (run on host):
    docker compose exec -T db psql -U gts -d gts_archive -t -A -F'|' -c \
      "SELECT id, source_external_id, download_url FROM gear_model \
       WHERE download_url LIKE '%tone3000.com%'" > /tmp/uuid_mapping.csv
    docker cp /tmp/uuid_mapping.csv $(docker compose ps -q webapp):/tmp/uuid_mapping.csv

Then run inside webapp container:
    docker compose exec webapp python /app/scripts/reconcile_nam_files.py
"""

import re
import shutil
from pathlib import Path

STORAGE_ROOT = Path("/app/storage")
SOURCE_DOWNLOADS = STORAGE_ROOT / "source_downloads" / "t3k"
MODELS_DIR = STORAGE_ROOT / "models"
ARCHIVE_BACKUP = STORAGE_ROOT / ".archive-backup" / "models"
MAPPING_FILE = Path("/tmp/uuid_mapping.csv")


def extract_model_id_from_url(url: str) -> str | None:
    """Extract T3K model ID from download URL.

    URL pattern: .../models/{model_id}/download/{filename}.nam
    """
    match = re.search(r"/models/(\d+)/download/", url)
    return match.group(1) if match else None


def load_uuid_mapping() -> dict[str, tuple[str, str]]:
    """Load UUID → (t3k_model_id, download_url) mapping from CSV file.

    CSV format: uuid|download_url (from gts_core.gear_models)
    """
    mapping: dict[str, tuple[str, str]] = {}
    with MAPPING_FILE.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                uuid_str, download_url = parts[0], parts[1]
                t3k_model_id = extract_model_id_from_url(download_url)
                if t3k_model_id:
                    mapping[uuid_str] = (t3k_model_id, download_url)
    return mapping


def filename_from_download_url(download_url: str) -> str:
    """Extract filename from T3K download URL."""
    # URL pattern: .../models/{model_id}/download/{filename}.nam
    parts = download_url.rstrip("/").split("/")
    return parts[-1] if parts else "unknown.nam"


def copy_uuid_files(mapping: dict[str, tuple[str, str]]) -> int:
    """Copy UUID-named files from models/ to source_downloads/t3k/{model_id}/."""
    copied = 0
    skipped = 0

    if not MODELS_DIR.exists():
        print(f"Models directory {MODELS_DIR} does not exist")
        return 0

    for nam_file in MODELS_DIR.glob("*.nam"):
        uuid_str = nam_file.stem
        if uuid_str not in mapping:
            continue

        t3k_model_id, download_url = mapping[uuid_str]
        filename = filename_from_download_url(download_url)
        dest_dir = SOURCE_DOWNLOADS / t3k_model_id
        dest_path = dest_dir / filename

        if dest_path.exists():
            skipped += 1
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nam_file, dest_path)
        copied += 1

        if copied % 500 == 0:
            print(f"  Copied {copied} files...")

    print(f"UUID files: copied={copied}, skipped={skipped} (already existed)")
    return copied


def copy_archive_backup_files() -> int:
    """Copy .archive-backup/models/t3k/{tone_id}/{model_id}_size.nam files."""
    copied = 0
    skipped = 0
    t3k_dir = ARCHIVE_BACKUP / "t3k"

    if not t3k_dir.exists():
        print(f"Archive backup t3k dir {t3k_dir} does not exist")
        return 0

    for tone_dir in t3k_dir.iterdir():
        if not tone_dir.is_dir():
            continue
        for nam_file in tone_dir.glob("*.nam"):
            # Filename pattern: {model_id}_size.nam
            match = re.match(r"^(\d+)_\w+\.nam$", nam_file.name)
            if not match:
                continue
            model_id = match.group(1)
            dest_dir = SOURCE_DOWNLOADS / model_id
            dest_path = dest_dir / nam_file.name

            if dest_path.exists():
                skipped += 1
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(nam_file, dest_path)
            copied += 1

    # Also handle root-level files: {tone_id}_{model_id}_size.nam
    for nam_file in ARCHIVE_BACKUP.glob("*.nam"):
        match = re.match(r"^(\d+)_(\d+)_(\w+)\.nam$", nam_file.name)
        if not match:
            continue
        model_id = match.group(2)
        dest_dir = SOURCE_DOWNLOADS / model_id
        dest_name = f"{model_id}_{match.group(3)}.nam"
        dest_path = dest_dir / dest_name

        if dest_path.exists():
            skipped += 1
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nam_file, dest_path)
        copied += 1

    print(f"Archive backup files: copied={copied}, skipped={skipped}")
    return copied


def main() -> None:
    print("=== NAM File Reconciliation ===")
    print()

    # Phase 1: Load mapping from CSV
    print("Phase 1: Loading UUID → T3K model ID mapping from CSV...")
    if not MAPPING_FILE.exists():
        print(f"ERROR: {MAPPING_FILE} not found. Run preparation steps first.")
        raise SystemExit(1)
    mapping = load_uuid_mapping()
    print(f"  Found {len(mapping)} mappable gear models")

    # Phase 2: Copy UUID files
    print()
    print("Phase 2: Copying UUID-named files to source_downloads/t3k/...")
    uuid_copied = copy_uuid_files(mapping)

    # Phase 3: Copy archive backup files
    print()
    print("Phase 3: Copying archive backup files...")
    archive_copied = copy_archive_backup_files()

    # Phase 4: Count final state
    print()
    print("Phase 4: Final state...")
    total_dirs = sum(1 for d in SOURCE_DOWNLOADS.iterdir() if d.is_dir())
    total_files = sum(1 for _ in SOURCE_DOWNLOADS.rglob("*.nam"))
    print(f"  source_downloads/t3k/: {total_dirs} model dirs, {total_files} .nam files")
    print()
    print(f"Total copied: {uuid_copied + archive_copied}")


if __name__ == "__main__":
    main()
