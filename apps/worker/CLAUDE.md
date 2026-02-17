# Worker Bounded Context

Background job processor via TaskIQ. Port 8001 (admin API, no auth). Bridges gts_core and gts_t3k_source databases.

## Dependencies

Can import: core, audio, video
Cannot import: sources (consumes pgmq messages instead of direct imports)

## Key Patterns

- Admin API on port 8001 has NO authentication — network-level access only
- Consumes pgmq messages from T3K source adapter via `consumers/`
- `gear_mapper.py` maps T3K gear data to core domain entities
- Audio/video processing jobs are CPU-bound — runs in worker, not webapp
- Redis broker shared with scheduler (TaskIQ ListQueueBroker)

## Key Files

- `src/worker/main.py` — TaskIQ broker initialisation
- `src/worker/entrypoint.py` — CLI worker runner
- `src/worker/admin.py` — Admin HTTP API (port 8001)
- `src/worker/jobs/` — Job handlers (audio, video, source sync)
- `src/worker/consumers/gear_sync.py` — pgmq gear sync consumer
- `src/worker/services/gear_mapper.py` — T3K → core gear mapping
