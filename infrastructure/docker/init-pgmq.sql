-- pgmq Extension Initialization
-- Enables pgmq on T3K source database and creates message queues

-- Connect to T3K source database and enable pgmq
\c gts_t3k_source

-- Enable pgmq extension (requires pg_partman as dependency)
CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pgmq;

-- Create message queues for gear synchronization
-- These queues allow the T3K source adapter to publish sync records
-- that the worker consumes to update gts_core

-- Unified queue for transactional gear+model sync events
SELECT pgmq.create('gear_sync');

-- Dead letter queue for failed sync events
SELECT pgmq.create('gear_sync_dlq');

-- Legacy split queues kept for compatibility during migration
SELECT pgmq.create('gear_pack_sync');
SELECT pgmq.create('gear_model_sync');

-- Queue for preset sync events
SELECT pgmq.create('preset_sync');

-- Legacy dead letter queue (kept for compatibility)
SELECT pgmq.create('sync_dead_letter');

-- Grant queue access to gts user
GRANT ALL ON ALL TABLES IN SCHEMA pgmq TO gts;
GRANT ALL ON ALL SEQUENCES IN SCHEMA pgmq TO gts;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pgmq TO gts;

-- Also enable pgmq on core database for worker-to-worker communication
\c gts_core

CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE EXTENSION IF NOT EXISTS pgmq;

-- Queue for audio processing jobs
SELECT pgmq.create('audio_processing');

-- Queue for video composition jobs
SELECT pgmq.create('video_composition');

-- Queue for notification jobs
SELECT pgmq.create('notifications');

-- Queue for dead letter messages
SELECT pgmq.create('jobs_dead_letter');

GRANT ALL ON ALL TABLES IN SCHEMA pgmq TO gts;
GRANT ALL ON ALL SEQUENCES IN SCHEMA pgmq TO gts;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pgmq TO gts;
