#!/usr/bin/env zsh
# scripts/cron-backup.sh — scheduled GTS database backup.
#
# Runs `./worktree.py backup` (pg_dump -Fc of every live database into
# ../backups/) and prunes old auto-dumps to a retention window. Wire into cron:
#
#   30 3 * * * /home/ryan/Work/guitar-tone-worktrees/main/scripts/cron-backup.sh >> /tmp/gts-db-backup.log 2>&1
#
# Dumps are the durability guarantee for the named postgres volume: the volume
# is correct practice, but a dump is what survives an accidental volume loss.
# This was the cron that stopped on 8 Apr 2026; the catalogue loss that followed
# is why it is back.

set -euo pipefail

# Cron runs with a minimal PATH; worktree.py is a `uv run --script` shebang and
# the backup shells out to docker, so make both reachable.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

MAIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${MAIN_DIR}/backups"
MAX_BACKUPS="${GTS_MAX_BACKUPS:-14}"

cd "$MAIN_DIR"

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting GTS backup"
./worktree.py backup

# Prune only strict-timestamp auto-dumps ({db}.YYYYMMDD_HHMM.dump), keeping the
# newest MAX_BACKUPS per database. Labelled snapshots (e.g. *.pre-restore.dump)
# and one-off historical baselines never match this pattern, so they are kept.
for db in $(find "$BACKUP_DIR" -maxdepth 1 -type f -regextype posix-extended \
              -regex '.*/[a-z0-9_]+\.[0-9]{8}_[0-9]{4}\.dump' -printf '%f\n' \
            | sed -E 's/\.[0-9]{8}_[0-9]{4}\.dump$//' | sort -u); do
  count="$(find "$BACKUP_DIR" -maxdepth 1 -type f -regextype posix-extended \
             -regex ".*/${db}\.[0-9]{8}_[0-9]{4}\.dump" | wc -l)"
  if (( count > MAX_BACKUPS )); then
    find "$BACKUP_DIR" -maxdepth 1 -type f -regextype posix-extended \
        -regex ".*/${db}\.[0-9]{8}_[0-9]{4}\.dump" -printf '%T@ %p\n' \
      | sort -rn | tail -n +"$((MAX_BACKUPS + 1))" | cut -d' ' -f2- \
      | while read -r old; do
          echo "$(date '+%Y-%m-%d %H:%M:%S') Pruning old backup: $old"
          rm -f "$old"
        done
  fi
done

echo "$(date '+%Y-%m-%d %H:%M:%S') GTS backup complete"
