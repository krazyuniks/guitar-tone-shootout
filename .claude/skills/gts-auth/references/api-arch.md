# API Authentication Architecture

GTS separates user-facing APIs from internal admin operations. Admin APIs are decentralised -- each component owns its own admin endpoints.

## User API (Webapp -- port 8000)

| Route Prefix | Purpose | Auth Required |
|--------------|---------|---------------|
| `/api/v1/jobs` | User's own jobs | `CurrentUser` |
| `/api/v1/auth` | Auth operations | Varies by endpoint |
| `/api/v1/*` | All user operations | `CurrentUser` |

User endpoints require `CurrentUser` authentication via session cookie.
Users can only access their own resources.

## Internal Admin API (Worker -- port 8001)

Admin endpoints have NO authentication. Access is controlled at the network level -- port not exposed publicly.

All admin endpoints served by the worker container:

```
/admin/jobs/              # Job list with status filter
/admin/jobs/{id}          # Job details
/admin/jobs/dead-lettered # Dead-lettered jobs
/admin/jobs/{id}/retry    # Retry failed job
/admin/t3k/sync/status    # Current sync state
/admin/t3k/sync           # Trigger catalog sync (POST)
/admin/t3k/sync/stats     # Pack/model counts
/admin/t3k/auth/status    # T3K OAuth token validity
/health                   # Composite health check
```

**Why worker serves T3K endpoints:** Worker already connects to `gts_t3k_source` for the pgmq consumer, so it can query sync status from the same database.

## CLI Tool

```bash
# All commands target Worker (port 8001)
gts-admin jobs            # List all jobs
gts-admin job <id>        # Get job details
gts-admin t3k-status      # Sync status
gts-admin auth-status     # T3K auth check
```
