# T3K API Reference (subset)

Endpoints and parameters used by the GTS sync service.
Full reference: https://www.tone3000.com/api#tones

## Authentication

Bearer token via `Authorization: Bearer <jwt>` header. Tokens obtained via
passwordless OAuth flow, refreshed via `POST /api/v1/auth/session/refresh`.

## Rate Limits

100 requests per minute (default). We run at ~0.75 req/s (~45/min) to stay
well under the limit with headroom for bursts.

## Max page_size per Resource

| Resource | Endpoint | Max page_size |
|----------|----------|---------------|
| Search Tones | `/api/v1/tones/search` | 25 |
| Models | `/api/v1/models` | 100 |
| Users | `/api/v1/users` | 10 |
| Created Tones | `/api/v1/users/{id}/tones` | 100 |
| Favorited Tones | `/api/v1/users/{id}/favorites` | 100 |

## Endpoints

### GET /api/v1/tones/search

Search and paginate tones.

| Parameter   | Type   | Default | Notes                      |
|-------------|--------|---------|----------------------------|
| `page`      | int    | 1       |                            |
| `page_size` | int    | 10      | Max 25                     |
| `sort`      | string | —       | See TonesSort enum below   |
| `query`     | string | —       | Keyword search             |
| `gear`      | array  | —       | Filter by gear type        |
| `sizes`     | array  | —       | Filter by model size       |

**TonesSort enum:** `best-match`, `newest`, `oldest`, `trending`, `downloads-all-time`

**Response:** `{ "data": [Tone, ...], "total": int, "has_next": bool }`

### GET /api/v1/models

Fetch models for a specific tone.

| Parameter   | Type | Default | Notes  |
|-------------|------|---------|--------|
| `tone_id`   | int  | —       | Required |
| `page`      | int  | 1       |        |
| `page_size` | int  | 10      | Max 100 |

**Response:** `{ "data": [Model, ...], "total": int, "has_next": bool }`

### GET /api/v1/users

List users with public content.

| Parameter   | Type   | Default  | Notes     |
|-------------|--------|----------|-----------|
| `page`      | int    | 1        |           |
| `page_size` | int    | 10       | Max 10    |
| `sort`      | string | `tones`  | UsersSort |
| `query`     | string | —        | Username search |

## Model Download

Model files are downloaded via `model_url` from the models response. URL
pattern: `https://www.tone3000.com/api/v1/models/{model_id}/download/{hash}.nam`

Requires same Bearer token auth. Subject to same rate limits.
