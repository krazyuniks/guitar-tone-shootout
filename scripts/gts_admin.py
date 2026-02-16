#!/usr/bin/env python3
"""GTS Admin CLI - Python wrapper for worker admin API HTTP endpoints.

Usage:
    just admin source-status <source>
    just admin source-sync <source>
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

            # Fetch auth status too
            auth_url = f"{base_url}/api/admin/sources/{source}/auth/status"
            auth_response = await client.get(auth_url)
            auth_data = auth_response.json() if auth_response.status_code == 200 else {}

            # Display as table
            print(f"\nSource Status: {source}")
            print("─" * 50)
            print(f"Sync:       {data.get('status', 'unknown')}")
            print(f"Enabled:    {data.get('enabled', False)}")
            print(f"Checkpoint: {data.get('checkpoint', 'none')}")
            auth_status = auth_data.get("status", "unknown")
            can_proceed = auth_data.get("can_proceed", False)
            print(f"Auth:       {auth_status} ({'ok' if can_proceed else 'BLOCKED'})")
            if auth_data.get("expires_at"):
                print(f"Expires:    {auth_data['expires_at']}")
            if auth_data.get("message"):
                print(f"Message:    {auth_data['message']}")
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
    elif args.command == "jobs":
        await list_jobs(status=args.status)
    elif args.command == "job-health":
        await job_health()
    elif args.command == "unlock-sync":
        await unlock_sync(args.source)
    elif args.command == "unlock-scheduler":
        await unlock_scheduler()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
