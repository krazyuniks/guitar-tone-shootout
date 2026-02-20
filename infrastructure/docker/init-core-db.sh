#!/usr/bin/env bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
-- Core database initialization for single-database architecture.
-- Installs pgmq and creates all required queues in gts_core.

CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pgmq;

-- Source sync queues
SELECT pgmq.create('gear_sync');
SELECT pgmq.create('gear_sync_dlq');
SELECT pgmq.create('gear_pack_sync');
SELECT pgmq.create('gear_model_sync');
SELECT pgmq.create('preset_sync');
SELECT pgmq.create('sync_dead_letter');

-- Core processing queues
SELECT pgmq.create('audio_processing');
SELECT pgmq.create('video_composition');
SELECT pgmq.create('notifications');
SELECT pgmq.create('jobs_dead_letter');

-- BC command/event queues
SELECT pgmq.create('process_audio');
SELECT pgmq.create('process_audio_dlq');
SELECT pgmq.create('render_video');
SELECT pgmq.create('render_video_dlq');

GRANT ALL ON ALL TABLES IN SCHEMA pgmq TO gts;
GRANT ALL ON ALL SEQUENCES IN SCHEMA pgmq TO gts;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pgmq TO gts;
SQL
