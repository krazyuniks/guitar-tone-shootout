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

## Internal Admin API (Webapp -- `/api/admin/*`)

Admin endpoints have NO authentication. Access is controlled at the network level.

All admin endpoints served by the webapp container:

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

**Why webapp serves admin endpoints:** All containers share the single `gts_core` database. The webapp already has database access and serves the admin API at `/api/admin/*`. T3K sync operations run in the dedicated t3k-sync container.

## CLI Tool

```bash
# All commands target Webapp admin API (/api/admin/*)
gts-admin jobs            # List all jobs
gts-admin job <id>        # Get job details
gts-admin t3k-status      # Sync status
gts-admin auth-status     # T3K auth check
```
