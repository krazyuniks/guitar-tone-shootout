#!/usr/bin/env bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
-- Core database initialization for single-database architecture.
-- Installs pgmq and creates all required queues in gts_core.

CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pgmq;

-- Canonical 6-queue topology
SELECT pgmq.create('audio_commands');
SELECT pgmq.create('audio_events');
SELECT pgmq.create('video_commands');
SELECT pgmq.create('video_events');
SELECT pgmq.create('source_events');
SELECT pgmq.create('dead_letter');

GRANT ALL ON ALL TABLES IN SCHEMA pgmq TO gts;
GRANT ALL ON ALL SEQUENCES IN SCHEMA pgmq TO gts;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pgmq TO gts;
SQL
