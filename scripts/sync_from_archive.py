#!/usr/bin/env -S python3 -u
"""Sync T3K tones and models from archive database into current staging.

Reads from the archive_temp database (restored from pre-migration dump)
and inserts missing tones and models into gts_t3k_source staging tables.
Then copies NAM files from the archive storage directory into the current
source_downloads layout.

Usage:
    scripts/sync_from_archive.py

Prerequisites:
    - archive_temp database exists (restored from pre-migration dump)
    - Archive storage accessible at ARCHIVE_STORAGE_DIR
    - DB accessible via docker compose exec
"""

import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath

ARCHIVE_STORAGE_DIR = Path(
    os.getenv(
        "ARCHIVE_STORAGE_DIR",
        os.path.expanduser("~/Work/guitar-tone-worktrees-archive-20260202/gts-storage/models/t3k"),
    )
)


def psql(db: str, query: str) -> str:
    """Run a query via docker compose exec db psql, return raw output."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "gts",
            "-d",
            db,
            "-t",
            "-A",
            "-c",
            query,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def psql_exec(db: str, query: str) -> str:
    """Run a mutating query, return output."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "gts",
            "-d",
            db,
            "-c",
            query,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def pipe_to_container(data: str, container_path: str) -> None:
    """Write data into a file inside a container via stdin."""
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "bash",
            "-c",
            f"cat > {container_path}",
        ],
        input=data,
        capture_output=True,
        text=True,
        check=True,
    )


def sync_tones() -> int:
    """Insert archive tones missing from staging."""
    print("  Extracting tones from archive...")
    rows = psql(
        "archive_temp",
        """
        COPY (
            SELECT
                p.t3k_pack_id,
                p.title,
                COALESCE(p.description, ''),
                p.gear_type::text,
                p.platform::text,
                p.models_count,
                p.favorites_count,
                p.downloads_count,
                COALESCE(p.t3k_url, ''),
                COALESCE(c.t3k_creator_id, ''),
                COALESCE(
                    (SELECT array_agg(DISTINCT t.name)
                     FROM t3k_pack_tags pt
                     JOIN t3k_tags t ON t.id = pt.tag_id
                     WHERE pt.pack_id = p.id),
                    '{}'
                ),
                COALESCE(
                    (SELECT array_agg(DISTINCT mk.name)
                     FROM t3k_pack_makes pm
                     JOIN t3k_makes mk ON mk.id = pm.make_id
                     WHERE pm.pack_id = p.id),
                    '{}'
                ),
                COALESCE(
                    (SELECT array_agg(DISTINCT i.url)
                     FROM t3k_pack_images i
                     WHERE i.pack_id = p.id),
                    '{}'
                ),
                COALESCE(p.t3k_created_at, p.t3k_updated_at),
                p.t3k_updated_at
            FROM t3k_packs p
            LEFT JOIN t3k_creators c ON c.id = p.creator_uuid
            WHERE p.is_deleted = false
            ORDER BY p.t3k_pack_id
        ) TO STDOUT
    """,
    )

    if not rows:
        print("  No tones found in archive")
        return 0

    print(f"  Extracted {rows.count(chr(10)) + 1} rows")
    print("  Loading into staging...")
    pipe_to_container(rows, "/tmp/archive_tones.tsv")

    insert_sql = """
        CREATE TEMP TABLE _archive_tones (
            id int, title text, description text, gear text, platform text,
            models_count int, favorites_count int, downloads_count int,
            url text, user_id text, tags text[], makes text[], images text[],
            created_at timestamptz, updated_at timestamptz
        );
        COPY _archive_tones FROM '/tmp/archive_tones.tsv';
        INSERT INTO t3k_tones_staging
            (id, title, description, gear, platform, models_count,
             favorites_count, downloads_count, url, user_id,
             tags, makes, images, created_at, updated_at)
        SELECT id, title, description, gear, platform, models_count,
               favorites_count, downloads_count, url, user_id,
               tags, makes, images, created_at, updated_at
        FROM _archive_tones
        ON CONFLICT (id) DO NOTHING;
    """
    output = psql_exec("gts_t3k_source", insert_sql)
    for line in output.splitlines():
        if line.startswith("INSERT"):
            parts = line.split()
            return int(parts[-1]) if parts else 0
    return 0


def sync_models() -> int:
    """Insert archive models missing from staging."""
    print("  Extracting models from archive...")
    rows = psql(
        "archive_temp",
        """
        COPY (
            SELECT
                m.t3k_model_id,
                p.t3k_pack_id,
                m.name,
                m.download_url,
                m.model_size::text,
                COALESCE(c.t3k_creator_id, ''),
                m.created_at,
                m.updated_at
            FROM t3k_models m
            JOIN t3k_packs p ON p.id = m.pack_id
            LEFT JOIN t3k_creators c ON c.id = p.creator_uuid
            WHERE p.is_deleted = false
            ORDER BY m.t3k_model_id
        ) TO STDOUT
    """,
    )

    if not rows:
        print("  No models found in archive")
        return 0

    print(f"  Extracted {rows.count(chr(10)) + 1} rows")
    print("  Loading into staging...")
    pipe_to_container(rows, "/tmp/archive_models.tsv")

    insert_sql = """
        CREATE TEMP TABLE _archive_models (
            id int, tone_id int, name text, model_url text, size text,
            user_id text, created_at timestamptz, updated_at timestamptz
        );
        COPY _archive_models FROM '/tmp/archive_models.tsv';
        INSERT INTO t3k_models_staging
            (id, tone_id, name, model_url, size, user_id, created_at, updated_at)
        SELECT id, tone_id, name, model_url, size, user_id, created_at, updated_at
        FROM _archive_models
        ON CONFLICT (id) DO NOTHING;
    """
    output = psql_exec("gts_t3k_source", insert_sql)
    for line in output.splitlines():
        if line.startswith("INSERT"):
            parts = line.split()
            return int(parts[-1]) if parts else 0
    return 0


def copy_nam_files() -> tuple[int, int]:
    """Copy NAM files from archive storage into source_downloads layout.

    Archive layout: {tone_id}/{model_id}_{size}.nam
    Current layout: {model_id}/{url_filename}.nam
    """
    if not ARCHIVE_STORAGE_DIR.exists():
        print(f"  Archive storage not found at {ARCHIVE_STORAGE_DIR}")
        return 0, 0

    # Build model_id -> url_filename mapping from archive DB
    print("  Building model URL mapping...")
    raw = psql(
        "archive_temp",
        "SELECT t3k_model_id || '|' || download_url FROM t3k_models",
    )
    url_map: dict[int, str] = {}
    for line in raw.splitlines():
        if "|" not in line:
            continue
        mid_str, url = line.split("|", 1)
        url_map[int(mid_str)] = PurePosixPath(url).name

    # Stage files into a temp directory with correct layout
    staging_dir = Path("/tmp/archive_nam_staging")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir()

    copied = 0
    skipped = 0

    print("  Scanning archive files...")
    for nam_file in ARCHIVE_STORAGE_DIR.rglob("*.nam"):
        stem = nam_file.stem  # e.g. "294932_standard"
        parts = stem.rsplit("_", 1)
        if len(parts) != 2:
            skipped += 1
            continue

        try:
            model_id = int(parts[0])
        except ValueError:
            skipped += 1
            continue

        url_filename = url_map.get(model_id)
        if not url_filename:
            print(f"    No URL mapping for model {model_id}")
            skipped += 1
            continue

        dest_dir = staging_dir / str(model_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nam_file, dest_dir / url_filename)
        copied += 1

    if copied == 0:
        print("  No new files to copy")
        return 0, skipped

    # Tar and copy into the worker container
    print(f"  Packaging {copied} files...")
    tar_path = Path("/tmp/archive_nam.tar")
    subprocess.run(
        ["tar", "cf", str(tar_path), "-C", str(staging_dir), "."],
        check=True,
    )

    print("  Copying into worker container...")
    subprocess.run(
        ["docker", "compose", "cp", str(tar_path), "worker:/tmp/archive_nam.tar"],
        check=True,
    )

    print("  Extracting into source_downloads...")
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "worker",
            "bash",
            "-c",
            "cd /app/storage/source_downloads/t3k"
            " && tar xf /tmp/archive_nam.tar"
            " && rm /tmp/archive_nam.tar",
        ],
        check=True,
    )

    # Fix ownership
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "--user",
            "root",
            "worker",
            "chown",
            "-R",
            "appuser:appgroup",
            "/app/storage/source_downloads/t3k/",
        ],
        check=True,
    )

    # Cleanup
    shutil.rmtree(staging_dir, ignore_errors=True)
    tar_path.unlink(missing_ok=True)

    return copied, skipped


def print_summary() -> None:
    """Print current staging totals."""
    tones = psql("gts_t3k_source", "SELECT count(*) FROM t3k_tones_staging")
    models = psql("gts_t3k_source", "SELECT count(*) FROM t3k_models_staging")
    gear_models = psql("gts_core", "SELECT count(*) FROM gear_models")

    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "worker",
            "find",
            "/app/storage/source_downloads/t3k/",
            "-name",
            "*.nam",
        ],
        capture_output=True,
        text=True,
    )
    nam_count = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0

    print(f"  Staging tones:    {tones}")
    print(f"  Staging models:   {models}")
    print(f"  Core gear_models: {gear_models}")
    print(f"  NAM files on disk: {nam_count}")


def main() -> None:
    print("=== T3K Archive Sync ===\n")

    print("[1/4] Syncing tones...")
    tones_inserted = sync_tones()
    print(f"  Inserted: {tones_inserted}\n")

    print("[2/4] Syncing models...")
    models_inserted = sync_models()
    print(f"  Inserted: {models_inserted}\n")

    print("[3/4] Copying NAM files...")
    copied, skipped = copy_nam_files()
    print(f"  Copied: {copied}, skipped: {skipped}\n")

    print("[4/4] Summary")
    print_summary()


if __name__ == "__main__":
    main()
