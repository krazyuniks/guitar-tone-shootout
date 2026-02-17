# Scheduler Bounded Context

TaskIQ cron job scheduling. Distributed locks, periodic tasks.

## Dependencies

Can import: core
Cannot import: audio, video, sources

## Key Patterns

- Shared Redis broker with worker (TaskIQ ListQueueBroker)
- `LabelScheduleSource` for cron-style scheduling
- Distributed locks via `lock.py` prevent concurrent execution
- Scheduled tasks defined in `schedules/` — each module registers tasks via broker labels

## Key Files

- `src/scheduler/main.py` — TaskIQ scheduler initialisation
- `src/scheduler/config.py` — Scheduler settings
- `src/scheduler/lock.py` — Distributed lock implementation
- `src/scheduler/schedules/backup.py` — Backup scheduled tasks
- `src/scheduler/schedules/jobs.py` — Job scheduling tasks
