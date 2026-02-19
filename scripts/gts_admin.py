#!/usr/bin/env python3
"""GTS Admin CLI - Python wrapper for worker admin API HTTP endpoints.

Usage:
    just admin source-status <source>
    just admin source-sync <source>
    just admin source-diagnose <source>
    just admin jobs [--status STATUS]
    just admin job-health
    just admin unlock-sync <source>
    just admin unlock-scheduler

Environment:
    GTS_WORKER_URL: Worker API base URL (default: http://worker:8001)
"""

import argparse
import os
import sys

import httpx


def get_base_url() -> str:
    """Get base URL from environment or default to Docker internal URL."""
    return os.environ.get("GTS_WORKER_URL", "http://worker:8001")


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="GTS Admin CLI - Manage worker and source sync operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # source-status subcommand
    status_parser = subparsers.add_parser("source-status", help="Get sync status for a source")
    status_parser.add_argument("source", help="Source name (e.g., t3k)")

    # source-sync subcommand
    sync_parser = subparsers.add_parser("source-sync", help="Trigger sync for a source")
    sync_parser.add_argument("source", help="Source name (e.g., t3k)")

    # source-diagnose subcommand
    diagnose_parser = subparsers.add_parser(
        "source-diagnose", help="Run automated source sync diagnostics"
    )
    diagnose_parser.add_argument("source", help="Source name (e.g., t3k)")

    # jobs subcommand
    jobs_parser = subparsers.add_parser("jobs", help="List jobs")
    jobs_parser.add_argument("--status", help="Filter by status (e.g., running, completed)")

    # job-health subcommand
    subparsers.add_parser("job-health", help="Show worker health status")

    # unlock-sync subcommand
    unlock_sync_parser = subparsers.add_parser("unlock-sync", help="Release sync lock for a source")
    unlock_sync_parser.add_argument("source", help="Source name (e.g., t3k)")

    # unlock-scheduler subcommand
    subparsers.add_parser("unlock-scheduler", help="Release scheduler lock")

    # enqueue-pending subcommand
    enqueue_parser = subparsers.add_parser("enqueue-pending", help="Enqueue all pending jobs")
    enqueue_parser.add_argument(
        "--type",
        dest="job_type",
        help="Filter by job type (e.g., audio_processing, source_sync)",
    )

    return parser


async def source_status(source: str, base_url: str | None = None) -> None:
    """Get sync status for a source.

    Args:
        source: Source name (e.g., t3k)
        base_url: Worker API base URL (default from get_base_url())
    """
    if base_url is None:
        base_url = get_base_url()

    url = f"{base_url}/api/admin/sources/{source}/sync/status"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                sys.exit(1)

            data = response.json()

            # Display as table
            print(f"\nSync Status: {source}")
            print("─" * 50)
            print(f"Status:     {data.get('status', 'unknown')}")
            print(f"Enabled:    {data.get('enabled', False)}")
            print(f"Checkpoint: {data.get('checkpoint', 'none')}")
            print("─" * 50)

    except Exception as e:
        print(f"Error: Could not reach worker at {base_url}")
        print(f"Worker may not be running or reachable: {e}")
        sys.exit(1)


async def source_sync(source: str, base_url: str | None = None) -> None:
    """Trigger sync for a source.

    Args:
        source: Source name (e.g., t3k)
        base_url: Worker API base URL (default from get_base_url())
    """
    if base_url is None:
        base_url = get_base_url()

    url = f"{base_url}/api/admin/sources/{source}/sync"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url)

            if response.status_code not in (200, 202):
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                sys.exit(1)

            data = response.json()
            message = data.get("message", "Sync triggered")
            print(f"\n✓ {message}")

    except Exception as e:
        print(f"Error: Could not reach worker at {base_url}")
        print(f"Worker may not be running or reachable: {e}")
        sys.exit(1)


async def source_diagnose(source: str, base_url: str | None = None) -> None:
    """Run automated diagnostics for a source sync pipeline.

    Args:
        source: Source name (e.g., t3k)
        base_url: Worker API base URL (default from get_base_url())
    """
    if base_url is None:
        base_url = get_base_url()

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            health_resp = await client.get(f"{base_url}/health")
            status_resp = await client.get(f"{base_url}/api/admin/sources/{source}/sync/status")
            lag_resp = await client.get(f"{base_url}/api/admin/sources/{source}/sync/lag")
            stats_resp = await client.get(f"{base_url}/api/admin/sources/{source}/sync/stats")
            errors_resp = await client.get(f"{base_url}/api/admin/sources/{source}/errors/summary")
            jobs_resp = await client.get(f"{base_url}/api/admin/jobs?job_type=source_sync")

            responses = [health_resp, status_resp, lag_resp, stats_resp, errors_resp, jobs_resp]
            bad = next((r for r in responses if r.status_code != 200), None)
            if bad is not None:
                print(f"Error: HTTP {bad.status_code}")
                print(bad.text)
                sys.exit(1)

            health = health_resp.json()
            sync_status = status_resp.json()
            lag = lag_resp.json()
            stats = stats_resp.json()
            errors = errors_resp.json()
            jobs = jobs_resp.json()

        running_jobs = [j for j in jobs if j.get("status") == "running"]
        failed_jobs = [j for j in jobs if j.get("status") == "failed"]
        pending_jobs = [j for j in jobs if j.get("status") == "pending"]
        completed_jobs = [j for j in jobs if j.get("status") == "completed"]
        lag_seconds = lag.get("lag_seconds")
        total_synced = stats.get("total_synced")
        error_count = sum(errors.get("errors", {}).values())

        print(f"\nSource Diagnostics: {source}")
        print("─" * 72)
        print(
            f"Worker: status={health.get('status')} redis={health.get('redis')} "
            f"db={health.get('database')}"
        )
        print(
            f"Sync: state={sync_status.get('status')} "
            f"lag_seconds={lag_seconds if lag_seconds is not None else 'unknown'} "
            f"total_synced={total_synced}"
        )
        print(
            f"Jobs(source_sync): total={len(jobs)} running={len(running_jobs)} "
            f"failed={len(failed_jobs)} pending={len(pending_jobs)} completed={len(completed_jobs)}"
        )
        print(f"Errors(24h): total={error_count}")
        if errors.get("errors"):
            top_err = max(errors["errors"].items(), key=lambda kv: kv[1])
            print(f"Top error: {top_err[1]}x {top_err[0][:120]}")
        print("─" * 72)

        print("Diagnosis")
        if health.get("status") in {"unhealthy", "degraded"}:
            print("- Infrastructure issue: worker health degraded/unhealthy.")
        if len(failed_jobs) > 0:
            print("- SOURCE_SYNC failures present: inspect latest failed job details/logs.")
        if sync_status.get("status") == "idle" and len(running_jobs) == 0:
            print("- No active sync run: scheduler may not be dispatching or sync is disabled.")
        if lag_seconds is not None and lag_seconds > 4 * 3600:
            print("- High sync lag detected (>4h): ingestion path is behind.")
        if len(pending_jobs) > 0 and len(running_jobs) == 0:
            print("- Pending SOURCE_SYNC jobs without runners: dispatch/worker throughput issue.")
        if (
            health.get("status") == "healthy"
            and len(failed_jobs) == 0
            and (lag_seconds is None or lag_seconds <= 3600)
        ):
            print("- No obvious control-plane fault from admin API signals.")

    except Exception as e:
        print(f"Error: Could not reach worker at {base_url}")
        print(f"Worker may not be running or reachable: {e}")
        sys.exit(1)


async def list_jobs(status: str | None = None, base_url: str | None = None) -> None:
    """List jobs, optionally filtered by status.

    Args:
        status: Filter by status (e.g., running, completed)
        base_url: Worker API base URL (default from get_base_url())
    """
    if base_url is None:
        base_url = get_base_url()

    url = f"{base_url}/api/admin/jobs"
    if status:
        url += f"?status={status}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                sys.exit(1)

            jobs = response.json()

            # Display as table
            print(f"\nJobs ({len(jobs)} found)")
            print("─" * 80)
            if jobs:
                print(f"{'ID':<36}  {'Type':<20}  {'Status':<12}  {'Created'}")
                print("─" * 80)
                for job in jobs:
                    job_id = str(job.get("id", ""))[:36]
                    job_type = job.get("job_type", "unknown")[:20]
                    job_status = job.get("status", "unknown")[:12]
                    created = job.get("created_at", "")[:19]
                    print(f"{job_id:<36}  {job_type:<20}  {job_status:<12}  {created}")
            else:
                print("No jobs found")
            print("─" * 80)

    except Exception as e:
        print(f"Error: Could not reach worker at {base_url}")
        print(f"Worker may not be running or reachable: {e}")
        sys.exit(1)


async def job_health(base_url: str | None = None) -> None:
    """Show worker health status.

    Args:
        base_url: Worker API base URL (default from get_base_url())
    """
    if base_url is None:
        base_url = get_base_url()

    try:
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{base_url}/health")

            if health_response.status_code != 200:
                print(f"Error: HTTP {health_response.status_code}")
                print(health_response.text)
                sys.exit(1)

            health = health_response.json()

            # Display health info
            print("\nWorker Health")
            print("─" * 50)
            print(f"Status:    {health.get('status', 'unknown')}")
            print(f"Redis:     {health.get('redis', 'unknown')}")
            print(f"Database:  {health.get('database', 'unknown')}")
            print(f"Uptime:    {health.get('uptime', 0):.1f}s")
            print("Active jobs: use 'just admin jobs' to list")
            print("─" * 50)

    except Exception as e:
        print(f"Error: Could not reach worker at {base_url}")
        print(f"Worker may not be running or reachable: {e}")
        sys.exit(1)


async def unlock_sync(source: str, base_url: str | None = None) -> None:
    """Release sync lock for a source.

    Args:
        source: Source name (e.g., t3k)
        base_url: Worker API base URL (default from get_base_url())
    """
    if base_url is None:
        base_url = get_base_url()

    url = f"{base_url}/api/admin/sources/{source}/sync/unlock"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url)

            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                sys.exit(1)

            data = response.json()
            message = data.get("message", "Sync lock released")
            print(f"\n✓ {message}")

    except Exception as e:
        print(f"Error: Could not reach worker at {base_url}")
        print(f"Worker may not be running or reachable: {e}")
        sys.exit(1)


async def enqueue_pending(job_type: str | None = None, base_url: str | None = None) -> None:
    """Enqueue all pending jobs via the worker admin API.

    Args:
        job_type: Optional filter by job type (e.g., audio_processing)
        base_url: Worker API base URL (default from get_base_url())
    """
    if base_url is None:
        base_url = get_base_url()

    url = f"{base_url}/api/admin/jobs?status=pending"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                sys.exit(1)

            jobs = response.json()

            if job_type:
                jobs = [j for j in jobs if j.get("job_type") == job_type]

            if not jobs:
                print("No pending jobs found")
                return

            print(f"\nEnqueuing {len(jobs)} pending jobs...")
            dispatched = 0
            failed = 0

            for job in jobs:
                job_id = job["id"]
                job_t = job.get("job_type", "unknown")
                try:
                    r = await client.post(
                        f"{base_url}/api/admin/enqueue",
                        json={"job_id": job_id},
                    )
                    if r.status_code < 300:
                        dispatched += 1
                    else:
                        failed += 1
                        print(f"  ✗ {job_t} {job_id}: HTTP {r.status_code}")
                except Exception as e:
                    failed += 1
                    print(f"  ✗ {job_t} {job_id}: {e}")

            print(f"\n✓ Dispatched: {dispatched}  ✗ Failed: {failed}")

    except Exception as e:
        print(f"Error: Could not reach worker at {base_url}")
        print(f"Worker may not be running or reachable: {e}")
        sys.exit(1)


async def unlock_scheduler(base_url: str | None = None) -> None:
    """Release scheduler lock.

    Args:
        base_url: Worker API base URL (default from get_base_url())
    """
    if base_url is None:
        base_url = get_base_url()

    url = f"{base_url}/api/admin/scheduler/unlock"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url)

            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                sys.exit(1)

            data = response.json()
            message = data.get("message", "Scheduler lock released")
            print(f"\n✓ {message}")

    except Exception as e:
        print(f"Error: Could not reach worker at {base_url}")
        print(f"Worker may not be running or reachable: {e}")
        sys.exit(1)


async def main() -> None:
    """Main entry point - parse args and route to handler."""
    parser = create_parser()
    args = parser.parse_args()

    # Route to appropriate handler
    if args.command == "source-status":
        await source_status(args.source)
    elif args.command == "source-sync":
        await source_sync(args.source)
    elif args.command == "source-diagnose":
        await source_diagnose(args.source)
    elif args.command == "jobs":
        await list_jobs(status=args.status)
    elif args.command == "job-health":
        await job_health()
    elif args.command == "unlock-sync":
        await unlock_sync(args.source)
    elif args.command == "unlock-scheduler":
        await unlock_scheduler()
    elif args.command == "enqueue-pending":
        await enqueue_pending(job_type=getattr(args, "job_type", None))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
