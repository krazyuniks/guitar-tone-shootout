# T3K Source Bounded Context

Tone3000 source adapter. OAuth authentication, gear sync, model downloading.

## Dependencies

Can import: core
Cannot import: audio, video, other sources, apps

## Key Patterns

- Hexagonal architecture: inbound adapters (API client, OAuth) → domain → outbound adapters (models, pgmq publisher)
- Single database (`gts_core`) — BC isolation via table naming (`t3k_*`) and import-linter contracts
- Circuit breaker + rate limiter for external API resilience
- OAuth tokens encrypted at rest (Fernet via `OAUTH_ENCRYPTION_KEY`)
- Publishes sync events via pgmq — webapp and other BCs consume them

## Key Files

- `src/source_t3k/services/sync_service.py` — Main sync orchestrator
- `src/source_t3k/adapters/inbound/api_client.py` — Tone3000 API client
- `src/source_t3k/adapters/inbound/oauth.py` — OAuth flow
- `src/source_t3k/adapters/inbound/circuit_breaker.py` — Resilience pattern
- `src/source_t3k/adapters/outbound/publisher.py` — pgmq event publisher
