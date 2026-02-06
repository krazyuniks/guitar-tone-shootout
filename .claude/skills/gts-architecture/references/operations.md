# Operations

## Observability

### Logging (structlog)

Structured logging via structlog with JSON output:
- Context binding (`logger.bind(user_id=123)`)
- OpenTelemetry correlation (trace_id, span_id)
- Sensitive data filtering (passwords, tokens, credentials redacted)

**Mandatory context:** request_id, user_id, trace_id (where applicable).

structlog bridges to OpenTelemetry via stdlib integration for unified log export.

### Tracing (OpenTelemetry)

Distributed tracing with OTLP export:

| Auto-instrumented | Attributes |
|-------------------|------------|
| FastAPI requests | http.method, http.route, http.status_code |
| SQLAlchemy queries | db.system, db.statement, db.operation |
| HTTPX outbound | http.url, http.status_code |
| Redis commands | db.system, db.statement |

Trace context propagation to background workers via inject/extract.

### Metrics (OpenTelemetry -> Prometheus)

OpenTelemetry SDK for instrumentation, exported to Prometheus for storage and PromQL querying.

| Category | Examples |
|----------|----------|
| **HTTP** | Request count, latency, in-progress by method/route/status |
| **Business** | Shootouts created/processed, signal chains, gear items |
| **Jobs** | Queue depth, in-progress count |
| **External APIs** | T3K request count, latency, error rates |
| **Infrastructure** | DB connection pool, circuit breaker state |

### Health Checks

| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `/health` | Liveness probe | Process alive |
| `/health/ready` | Readiness probe | Database, external APIs |

**Graceful shutdown:** Returns 503 during shutdown for load balancer draining.

**Status levels:** HEALTHY, DEGRADED, UNHEALTHY.

### SLIs and SLOs

Service Level Indicators and Objectives for the ingestion pipeline. Each aggregate or source declares its freshness and completeness SLO targets.

| Category | SLI | Target | Measurement |
|----------|-----|--------|-------------|
| **Freshness** | Time from source change detection to core persistence | 99% of sources within 15 minutes | `data_freshness_seconds` gauge |
| **Completeness** | Record counts per source/interval against expected bands | Anomaly-based | `ingest_completion_rate` |
| **Reliability** | Sync attempts that succeed | 99.9% | `sync_records_total{status="success"}` / total |
| **Quality** | Records passing validation | > 99% | `validation_failure_rate` |

Alerts are based on SLO breach and error budgets.

### Alerting Strategy

- Multi-window burn-rate alerting to prevent fatigue
- Error budget consumption alerts
- Stale source detection (no updates in N minutes, configurable per source)
- Queue depth warnings

### Dashboards

**Pipeline Overview:**
- Total throughput (records/min)
- Error rate trend
- Source status summary (healthy/degraded/stale)

**Source Health:**
- Per-source latency distribution
- Per-source error rates
- Last sync timestamps

**Queue Health:**
- Queue depth over time
- Consumer lag trends
- DLQ accumulation

## Error Handling & Resilience

### Retry Strategies

External API calls use bounded retries with exponential backoff and full jitter to prevent thundering herd.

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max attempts | 5 | Sufficient for transient failures |
| Base delay | 60s | Allows temporary issues to resolve |
| Backoff formula | `base x 2^(attempt-1)` + jitter | Exponential spacing with randomisation |
| Jitter | Full (0 to delay) | Distributes retry load |

**Retry only transient errors:**
- Network failures (timeout, connection refused)
- Rate limits (429)
- Server errors (5xx)

**Do not retry:**
- Client errors (4xx except 429)
- Authentication failures (401 after token refresh attempt)
- Validation errors

### Circuit Breaker

Circuit breakers protect against cascading failures when external services are unavailable.

| State | Behaviour |
|-------|-----------|
| **Closed** | Requests pass through; failures counted |
| **Open** | Requests rejected immediately; return cached/degraded response |
| **Half-open** | Single probe request allowed; success closes, failure reopens |

**Configuration:**
- Failure threshold: 5 consecutive failures to open
- Recovery timeout: 30 seconds before half-open probe
- Scope: Per external source (not global)

Circuit breakers wrap retry logic -- when open, retries are skipped entirely.

### Rate Limiting

**External APIs:**
- Respect rate limit headers (`X-RateLimit-*`, `Retry-After`)
- Adaptive throttling on 429 responses
- Token bucket algorithm for smooth request distribution
- Redis-backed for coordination across processes

**Source Ingestion:**
- Source sync jobs respect configured rate limits per source
- Adaptive throttling when approaching limits
- Metrics emitted for rate limit events (`source_rate_limit_total`)

**Internal APIs:**
- Bulk ingest endpoints rate-limited per source
- Batch size limits per request
- Payload size limits enforced

### Backpressure

Backpressure prevents sources from overwhelming the core consumer:

- **Bounded queue size** -- pgmq queue depth monitored; sources pause publishing when depth exceeds threshold.
- **Adaptive batch sizing** -- Consumer batch size decreases when processing latency increases.
- **Metrics emitted** -- `queue_backpressure_applied_total` incremented when backpressure engages, enabling alerting and capacity planning.

### Job Failure Handling

Background jobs follow a defined failure lifecycle:

```
RUNNING -> FAILED -> [retry if attempts remain] -> PENDING
                -> [max attempts reached] -> DEAD_LETTERED
```

**Retry scheduling:**
- Jobs marked FAILED with `next_retry_at` timestamp
- Scheduler polls for jobs ready for retry
- Exponential backoff between attempts

**Dead-letter handling:**
- Jobs exceeding max attempts enter DEAD_LETTERED state
- Require manual investigation via admin tooling
- Can be reset for retry after root cause resolution

### Heartbeat Monitoring

Long-running jobs emit heartbeats to detect worker crashes:

| Parameter | Value |
|-----------|-------|
| Heartbeat interval | 30 seconds |
| Stale threshold | 5 minutes |
| Detection frequency | 2 minutes |

Jobs with stale heartbeats are marked FAILED and scheduled for retry.

### Partial Failure Handling

Batch operations handle partial failures gracefully:

- Per-item errors logged with context (record ID, error type, message)
- Successful items committed; failed items tracked
- Configurable: retry failed subset vs full batch retry
- Alerting when failure rate exceeds threshold

### Graceful Degradation

When external services are unavailable:

| Component | Degradation Strategy |
|-----------|----------------------|
| T3K API unavailable | Serve cached gear data; disable sync |
| Job queue full | Apply backpressure; return 503 to new requests |
| Database read replica lag | Route to primary for consistency-critical reads |

### Error Classification

Errors are classified for appropriate handling:

| Category | Examples | Action |
|----------|----------|--------|
| **Transient** | Network timeout, rate limit | Retry with backoff |
| **Permanent** | Validation error, not found | Fail immediately |
| **Auth** | Token expired | Attempt refresh, then fail |
| **System** | Out of memory, disk full | Alert; manual intervention |

## Runbooks

### Graceful Shutdown

**Consumer shutdown sequence:**
1. **Receive SIGTERM** -- Stop accepting new messages
2. **Drain in-flight** -- Complete processing of active messages
3. **Commit checkpoints** -- Persist final offsets before exit
4. **Close connections** -- Release database and queue connections
5. **Exit cleanly** -- Return exit code 0

**Job scheduler shutdown:**
1. Stop scheduling new jobs
2. Wait for running jobs to complete (or timeout)
3. Persist scheduler state
4. Exit cleanly

### Failure Scenarios

| Scenario | Detection | Response |
|----------|-----------|----------|
| Consumer crash | Missing heartbeat, lag growth | Auto-restart, verify checkpoint resume |
| External API down | Circuit breaker open | Wait for recovery, catchup sync |
| Queue overflow | Depth metric spike | Scale consumers or pause sources |
| Poison message | Repeated DLQ entries | Isolate message, fix or archive |
| Schema mismatch | Validation errors spike | Deploy compatible consumers, drain |
| Database unavailable | Connection errors | Failover or wait for recovery |

### DLQ Processing

1. Monitor DLQ depth (alert if > threshold)
2. Sample messages, classify failure type
3. **Transient:** Wait for recovery, then redrive
4. **Permanent:** Fix data or archive with reason
5. **System bug:** Deploy fix first, then redrive
6. Verify DLQ emptying, main processing succeeding

### Incident Classification

| Severity | Impact | Response Time |
|----------|--------|---------------|
| P1 | Complete pipeline failure | < 15 minutes |
| P2 | Significant degradation, SLA breach | < 1 hour |
| P3 | Minor impact, single consumer issue | < 4 hours |
| P4 | Low impact, non-critical | Next business day |

### Disaster Recovery

**Recovery Targets:**

| Tier | Data | RTO | RPO |
|------|------|-----|-----|
| Critical | Core database (users, shootouts, chains) | < 1 hour | < 15 minutes (checkpoint frequency) |
| High | Source staging data (T3K packs, models) | < 4 hours | Last successful sync checkpoint |
| Normal | Queue state, job history | < 8 hours | Replay from source checkpoints |

**Recovery Strategy:**
1. Restore core database from latest backup
2. Restore queue state or replay from source checkpoints
3. Reingest from source staging data if needed
4. Verify data consistency post-recovery (canary tests + quality checks)

**Backup Requirements:**
- Regular database backups with tested restore procedures
- Checkpoint data retained for the full recovery window
- Source staging data retained for reingest capability
- Restore procedures exercised quarterly (at minimum)
