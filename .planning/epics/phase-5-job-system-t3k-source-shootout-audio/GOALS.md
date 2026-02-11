# Goals: E94 — Phase 5A/5B/5C

## Observable Truths

1. Worker container starts with Redis broker and processes TaskIQ jobs
2. Worker Admin API responds on port 8001 with health, job management endpoints
3. Scheduler container acquires distributed lock and runs cron tasks
4. T3K source adapter can sync gear data from Tone3000 API to staging tables
5. T3K adapter publishes GearSyncRecords to pgmq queues
6. Shootout processing trigger creates parent job that spawns per-chain audio jobs
7. Each chain processes DI track through signal chain, producing FLAC segment
8. All segments are loudness-normalised to EBU R128 (-14.0 LUFS)
9. Master audio concatenates normalised segments
10. WebSocket endpoint delivers real-time job progress to clients
11. `just check` passes
12. `just test-golden-path` passes
