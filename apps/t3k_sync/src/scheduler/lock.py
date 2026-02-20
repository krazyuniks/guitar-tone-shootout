"""Distributed lock implementation using Redis."""

import asyncio
import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class DistributedLock:
    """Redis-based distributed lock with heartbeat renewal."""

    def __init__(
        self,
        redis_client: redis.Redis,
        lock_key: str,
        lock_value: str = "scheduler-lock",
    ) -> None:
        self.redis_client = redis_client
        self.lock_key = lock_key
        self.lock_value = lock_value
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._is_locked = False
        self._stop_heartbeat = False

    async def acquire(self) -> bool:
        """Acquire the distributed lock."""
        result = await self.redis_client.set(
            self.lock_key,
            self.lock_value,
            nx=True,
            ex=60,
        )
        self._is_locked = bool(result)
        return self._is_locked

    async def release(self) -> bool:
        """Release the distributed lock."""
        result = await self.redis_client.delete(self.lock_key)
        self._is_locked = False
        return bool(result)

    async def _renew_lock(self) -> None:
        """Renew the lock TTL to 60 seconds."""
        await self.redis_client.expire(self.lock_key, 60)

    async def renew(self) -> None:
        """Renew the lock TTL to 60 seconds (public interface)."""
        await self._renew_lock()

    async def start_heartbeat(self) -> None:
        """Start background heartbeat task to renew lock every 30s."""
        self._stop_heartbeat = False
        sleep_interval = 1
        elapsed = 0

        while not self._stop_heartbeat:
            await asyncio.sleep(sleep_interval)
            elapsed += sleep_interval

            if elapsed >= 30:
                elapsed = 0
                if self._is_locked and not self._stop_heartbeat:
                    try:
                        await self._renew_lock()
                        logger.debug("Lock renewed")
                    except Exception as error:
                        logger.error("Failed to renew lock: %s", error)
                        raise

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat renewal task."""
        self._stop_heartbeat = True
        await asyncio.sleep(1.1)

    def _is_leader(self) -> bool:
        """Check if this instance holds the lock."""
        return self._is_locked
