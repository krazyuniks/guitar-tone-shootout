# Worker Apps

Per-BC containers for background processing via pgmq messaging.

| Container | BC | Role |
|-----------|-----|------|
| `t3k-sync` | Source: T3K | Polls T3K API, publishes `source_events` via pgmq |
| `audio-worker` | Audio | Consumes `audio_commands`, produces `audio_events` |
| `video-worker` | Video | Consumes `video_commands` and `audio_events`, produces `video_events` |

## Dependencies

| Container | Can import | Cannot import |
|-----------|-----------|---------------|
| `t3k-sync` | core, source_t3k, messaging | audio, video, webapp |
| `audio-worker` | core, audio, messaging | video, sources, webapp |
| `video-worker` | core, video, messaging | audio, sources, webapp |

## Key Patterns

- All containers share one PostgreSQL database (`gts_core`) — BC isolation via table naming and import-linter
- Messaging via pgmq (PostgreSQL Message Queue)
- Transactional outbox: all pgmq publishes within the same DB transaction as the domain state change
- Admin endpoints served by webapp at `/api/admin/*`
