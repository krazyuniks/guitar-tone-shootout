---
name: incident-response
description: Production incident response for GTS. Use for outages, degraded performance, security incidents, and emergency rollbacks.
context: fork
---

# Incident Response Skill

Production incident response procedures for Guitar Tone Shootout.

**When to Use:** Site down, elevated error rates, security incidents, database issues, or any production emergency.

## GTS Deployment Context

### Architecture Overview

| Component | Technology | Location |
|-----------|------------|----------|
| Reverse Proxy | nginx:alpine | Docker container |
| Application | FastAPI + uvicorn | Docker container |
| Database | PostgreSQL 18 | Docker container, volume: `postgres_data` |
| Cache/Queue | Redis 8.4 | Docker container, volume: `redis_data` |
| Task Workers | TaskIQ | Docker container (2 workers) |
| Scheduler | TaskIQ Scheduler | Docker container (single instance) |
| Static Assets | Pre-built Astro | `astro/dist/` bind-mounted to nginx |

### Service Dependencies

```
nginx (entry point, port 80/443)
  └── backend (port 8000)
        ├── db (PostgreSQL, port 5432)
        └── redis (port 6379)
              ├── worker (TaskIQ)
              └── scheduler (TaskIQ)
```

**Critical Path:** nginx → backend → db + redis

### Key Files & Paths

| Resource | Path |
|----------|------|
| Compose (dev) | `docker-compose.yml` |
| Compose (prod) | `docker-compose.prod.yml` |
| nginx config | `nginx.conf.template` |
| Backend code | `apps/webapp/src/webapp/` |
| Static assets | `astro/dist/` |
| Migrations | `backend/alembic/` |
| Secrets (prod) | `./secrets/` (file-based Docker secrets) |

### Production Secrets

Secrets managed via Docker secrets (not env vars):
- `/run/secrets/secret_key` - JWT signing key
- `/run/secrets/db_password` - PostgreSQL password

Note: T3K auth uses passwordless OAuth - no client secret. Tokens in `.gts-auth.json`.

## Incident Classification

### Severity Levels

| Level | Definition | Response Time | Examples |
|-------|------------|---------------|----------|
| **P1** | Complete outage | Immediate | Site down, DB unreachable |
| **P2** | Major degradation | < 15 min | Auth broken, API errors > 50% |
| **P3** | Partial impact | < 1 hour | Feature broken, slow performance |
| **P4** | Minor issue | < 24 hours | UI bug, non-critical error |

### Incident Types

| Type | Indicators | First Action |
|------|------------|--------------|
| **Outage** | nginx returns 502/503/504 | Check service health |
| **DB Issue** | Connection errors, slow queries | Check PostgreSQL |
| **Redis Issue** | Session loss, job failures | Check Redis |
| **Worker Issue** | Jobs stuck, not processing | Check TaskIQ workers |
| **Security** | Unusual access, data anomaly | Isolate, preserve evidence |

## Diagnostic Procedures

### Quick Health Check (30 seconds)

```bash
# All services running?
docker compose ps

# nginx health
curl -sf http://localhost/health || echo "nginx DOWN"

# Backend health
curl -sf http://localhost:8000/health/ready || echo "backend DOWN"

# Database
docker compose exec -T db pg_isready -U shootout || echo "db DOWN"

# Redis
docker compose exec -T redis redis-cli ping || echo "redis DOWN"
```

### Detailed Diagnostics

```bash
# Recent logs (all services)
docker compose logs --tail=100

# Service-specific logs with timestamps
docker compose logs -t --tail=50 backend
docker compose logs -t --tail=50 worker
docker compose logs -t --tail=50 nginx

# Resource usage
docker stats --no-stream

# Database connections
docker compose exec -T db psql -U shootout -c "SELECT count(*) FROM pg_stat_activity;"

# Redis memory
docker compose exec -T redis redis-cli info memory | grep used_memory_human

# Pending jobs
docker compose exec -T redis redis-cli llen taskiq:queue:default
```

### Common Error Patterns

| Log Pattern | Likely Cause | Check |
|-------------|--------------|-------|
| `connection refused` | Service down | `docker compose ps` |
| `too many connections` | Connection leak | DB connection pool |
| `FATAL: role "shootout" does not exist` | DB not initialized | Migrations |
| `OOM killed` | Memory exhaustion | Resource limits |
| `timeout waiting for` | Service slow/hung | Resource usage |
| `permission denied` | Volume/secret issue | File permissions |

## Mitigation Procedures

### 1. Service Restart (First Response)

```bash
# Restart single service
docker compose restart backend

# Restart with dependency chain
docker compose restart backend worker scheduler

# Full restart (preserves data)
docker compose down && docker compose up -d
```

### 2. Database Issues

**Connection Pool Exhausted:**
```bash
# Kill idle connections
docker compose exec -T db psql -U shootout -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND query_start < now() - interval '5 minutes';"
```

**Slow Queries:**
```bash
# Find slow queries
docker compose exec -T db psql -U shootout -c "
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC
LIMIT 5;"

# Kill specific query
docker compose exec -T db psql -U shootout -c "SELECT pg_cancel_backend(<pid>);"
```

**Database Corruption (Emergency):**
```bash
# Stop all services accessing DB
docker compose stop backend worker scheduler

# Check for corruption
docker compose exec -T db psql -U shootout -c "SELECT * FROM pg_catalog.pg_database WHERE datname = 'shootout';"

# If backup available, restore (see Rollback section)
```

### 3. Redis Issues

**Memory Full:**
```bash
# Check memory
docker compose exec -T redis redis-cli info memory

# Clear expired keys
docker compose exec -T redis redis-cli --scan --pattern '*' | head -100

# Emergency: flush non-critical data (loses sessions!)
docker compose exec -T redis redis-cli flushdb
```

**Job Queue Stuck:**
```bash
# Check queue length
docker compose exec -T redis redis-cli llen taskiq:queue:default

# Check dead letter queue
docker compose exec -T redis redis-cli llen taskiq:dlq:default

# Clear stuck jobs (last resort)
docker compose exec -T redis redis-cli del taskiq:queue:default
```

### 4. Worker/Scheduler Issues

**Workers Not Processing:**
```bash
# Check worker logs
docker compose logs --tail=50 worker

# Restart workers
docker compose restart worker

# Scale workers (if needed)
docker compose up -d --scale worker=4
```

**Duplicate Scheduled Tasks:**
```bash
# Ensure only ONE scheduler
docker compose ps scheduler

# If multiple, stop extras
docker compose stop scheduler
docker compose up -d scheduler
```

### 5. nginx/Routing Issues

**502 Bad Gateway:**
```bash
# Backend unreachable from nginx
docker compose exec nginx curl -sf http://backend:8000/health

# Check nginx config
docker compose exec nginx nginx -t

# Reload nginx config
docker compose exec nginx nginx -s reload
```

**Static Assets Not Loading:**
```bash
# Verify bind mount
docker compose exec nginx ls -la /static/

# Check file permissions
ls -la astro/dist/
```

## Rollback Procedures

### Code Rollback

```bash
# 1. Find last known good commit
git log --oneline -10

# 2. Check out previous version
git checkout <commit-sha>

# 3. Rebuild and restart (if code change)
docker compose build backend
docker compose up -d backend worker scheduler

# 4. Verify
curl -sf http://localhost:8000/health/ready
```

### Database Migration Rollback

```bash
# 1. Check current revision
docker compose exec backend alembic current

# 2. Downgrade one step
docker compose exec backend alembic downgrade -1

# 3. Or downgrade to specific revision
docker compose exec backend alembic downgrade <revision>

# 4. Verify
docker compose exec backend alembic current
```

### Full System Rollback

For complete disaster recovery:

```bash
# 1. Stop all services
docker compose down

# 2. Restore DB from backup
docker volume rm postgres_data
docker volume create postgres_data
# Restore from backup (provider-specific)

# 3. Checkout known-good commit
git checkout <last-known-good-sha>

# 4. Start services
docker compose up -d

# 5. Run migrations (if needed)
docker compose exec backend alembic upgrade head

# 6. Verify all services
docker compose ps
curl -sf http://localhost/health
```

### Secrets Rotation (Security Incident)

```bash
# 1. Generate new secrets
openssl rand -hex 32 > secrets/secret_key
openssl rand -hex 32 > secrets/db_password

# 2. Update PostgreSQL password
docker compose exec -T db psql -U postgres -c "ALTER USER shootout PASSWORD '<new-password>';"

# 3. Restart services to pick up new secrets
docker compose restart backend worker scheduler

# 4. Invalidate existing sessions (if compromised)
docker compose exec -T redis redis-cli flushdb
```

## GTS-Specific Incidents

### T3K OAuth Token Expired

**Symptoms:** Auth failures, T3K sync not working
```bash
# Check auth status
./worktree.py auth-status

# Re-authenticate
./worktree.py auth-login

# Restore session
./worktree.py auth-restore
```

### Job Processing Backlog

**Symptoms:** UI shows "Processing..." indefinitely
```bash
# Check queue depth
docker compose exec -T redis redis-cli llen taskiq:queue:default

# Check for failed jobs
docker compose exec -T redis redis-cli llen taskiq:dlq:default

# Scale workers temporarily
docker compose up -d --scale worker=4

# After backlog cleared, scale back
docker compose up -d --scale worker=2
```

### Audio Processing Failures

**Symptoms:** Shootout creation fails, audio not processing
```bash
# Check storage mount
docker compose exec backend ls -la /app/storage/

# Check disk space
df -h

# Check worker logs for FFmpeg errors
docker compose logs worker | grep -i ffmpeg
```

## Incident Documentation

After any P1/P2 incident, document:

```markdown
## Incident Report: [Title]

**Date:** YYYY-MM-DD
**Duration:** Start time - End time
**Severity:** P1/P2/P3

### Timeline
- HH:MM - [Event]
- HH:MM - [Action taken]
- HH:MM - [Resolution]

### Root Cause
[What caused the incident]

### Impact
- Users affected: ~N
- Data loss: Yes/No
- Features impacted: [list]

### Resolution
[What fixed it]

### Prevention
[What changes prevent recurrence]
```

## Monitoring Checklist

Run periodically or after incidents:

- [ ] All containers running (`docker compose ps`)
- [ ] Health endpoints responding
- [ ] DB connections within limits
- [ ] Redis memory within limits
- [ ] Job queue not growing unbounded
- [ ] Error rate in logs acceptable
- [ ] Disk space sufficient
- [ ] Recent backups valid

## Related

- `.claude/skills/docker-infra/SKILL.md` - Container operations
- `.claude/skills/backend-dev/SKILL.md` - Backend debugging
- `.claude/rules/authentication.md` - Auth architecture
- `.github/workflows/ci.yml` - CI/CD pipeline
