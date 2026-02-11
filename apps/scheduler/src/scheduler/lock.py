"""Distributed lock implementation using Redis.

Ensures only one scheduler instance executes scheduled tasks at a time.
Uses Redis SET NX with 60s TTL and heartbeat renewal every 30s.
"""

import asyncio
import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class DistributedLock:
    """Redis-based distributed lock with heartbeat renewal.

    Attributes:
        redis_client: Async Redis client for lock operations
        lock_key: Redis key for the lock
        lock_value: Unique value identifying this lock holder
        _heartbeat_task: Background task for lock renewal
        _is_locked: Flag indicating if this instance holds the lock
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        lock_key: str,
        lock_value: str = "scheduler-lock",
    ) -> None:
        """Initialise distributed lock.

        Args:
            redis_client: Async Redis client
            lock_key: Key to use for the lock in Redis
            lock_value: Value to set (identifies lock holder)
        """
        self.redis_client = redis_client
        self.lock_key = lock_key
        self.lock_value = lock_value
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._is_locked = False
        self._stop_heartbeat = False

    async def acquire(self) -> bool:
        """Acquire the distributed lock.

        Uses Redis SET NX (only set if not exists) with 60s TTL.

        Returns:
            True if lock was acquired, False otherwise
        """
        result = await self.redis_client.set(
            self.lock_key,
            self.lock_value,
            nx=True,  # Only set if not exists
            ex=60,  # 60 second TTL
        )
        self._is_locked = bool(result)
        return self._is_locked

    async def release(self) -> bool:
        """Release the distributed lock.

        Returns:
            True if lock was released, False if lock was not held
        """
        result = await self.redis_client.delete(self.lock_key)
        self._is_locked = False
        return bool(result)

    async def _renew_lock(self) -> None:
        """Renew the lock TTL to 60 seconds."""
        await self.redis_client.expire(self.lock_key, 60)

    async def start_heartbeat(self) -> None:
        """Start background heartbeat task to renew lock every 30s.

        This keeps the lock alive as long as the scheduler is running.
        Uses short sleep intervals to allow quick shutdown.
        """
        self._stop_heartbeat = False
        sleep_interval = 1  # Check stop flag every second
        elapsed = 0

        while not self._stop_heartbeat:
            await asyncio.sleep(sleep_interval)
            elapsed += sleep_interval

            # Renew lock every 30 seconds
            if elapsed >= 30:
                elapsed = 0
                if self._is_locked and not self._stop_heartbeat:
                    try:
                        await self._renew_lock()
                        logger.debug("Lock renewed")
                    except Exception as e:
                        logger.error(f"Failed to renew lock: {e}")
                        raise

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat renewal task."""
        self._stop_heartbeat = True
        # Wait for heartbeat loop to exit (checks flag every 1s)
        await asyncio.sleep(1.1)

    def _is_leader(self) -> bool:
        """Check if this instance holds the lock.

        Returns:
            True if this instance is the lock holder (leader)
        """
        return self._is_locked
