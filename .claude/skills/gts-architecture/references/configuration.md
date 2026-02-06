# Configuration

Configuration follows 12-Factor methodology. All settings come from environment variables, with Pydantic Settings handling validation and type coercion.

## Environment Variables

| Category | Variables | Required |
|----------|-----------|----------|
| **Application** | `DEBUG`, `APP_NAME`, `APP_URL`, `FRONTEND_URL` | No (defaults) |
| **Database** | `DATABASE_URL` or `DB_PASSWORD` + components | Yes |
| **Redis** | `REDIS_URL` | No (default: `redis://redis:6379`) |
| **Security** | `SECRET_KEY`, `OAUTH_ENCRYPTION_KEY` | Production only |
| **OAuth** | `{PROVIDER}_CLIENT_ID`, `{PROVIDER}_CLIENT_SECRET` | Per-provider |
| **Storage** | `STORAGE_ROOT`, `MODEL_CACHE_DIR`, `UPLOAD_DIR`, `SEGMENTS_DIR`, `VIDEOS_DIR` | No (defaults) |
| **Observability** | `OTLP_ENDPOINT`, `LOG_LEVEL`, `LOG_FORMAT`, `METRICS_ENABLED` | No |
| **Sources** | Per-source API credentials, rate limits, sync schedules | Per-source |

## Secrets Management

| Environment | Mechanism |
|-------------|-----------|
| Development | `.env` file (gitignored) |
| Production | Platform secrets (injected at runtime) |
| Docker | `{NAME}_FILE` pattern (reads from `/run/secrets/`) |

**Supported Docker secrets:** `SECRET_KEY_FILE`, `DB_PASSWORD_FILE`, `OAUTH_ENCRYPTION_KEY_FILE`

**Token encryption:** Fernet symmetric encryption for OAuth tokens at rest.

## Production Validation

Production mode (`DEBUG=false`) enforces:
- `SECRET_KEY` must not be default value
- `OAUTH_ENCRYPTION_KEY` must be set
- `DATABASE_URL` or `DB_PASSWORD` must be set

Development mode logs warnings but continues with defaults.

## Per-Source Configuration

Each source adapter has independent configuration:

| Setting | Purpose |
|---------|---------|
| API endpoint | External API URL |
| API credentials | Injected via secrets (not in code) |
| Sync schedule | Cron expression for incremental sync |
| Batch size | Records per bulk operation |
| Rate limits | Requests per window |
| Retry limits | Max attempts before failure |
| Timeouts | Connection and operation limits |

## Configuration Precedence

1. Environment variable (highest)
2. Docker secret file (`{NAME}_FILE`)
3. `.env` file
4. Default value (lowest)
