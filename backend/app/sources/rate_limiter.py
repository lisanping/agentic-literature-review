"""Token bucket rate limiter for external API calls."""

import asyncio
import time


class RateLimiter:
    """Async token bucket rate limiter.

    Args:
        rate: Maximum number of requests allowed in the time window.
        per_seconds: Length of the time window in seconds.
    """

    def __init__(self, rate: int, per_seconds: int) -> None:
        self.rate = rate
        self.per_seconds = per_seconds
        self._tokens = float(rate)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        async with self._lock:
            await self._wait_for_token()
            self._tokens -= 1

    async def _wait_for_token(self) -> None:
        while True:
            self._refill()
            if self._tokens >= 1:
                return
            # Calculate how long to wait for at least one token
            deficit = 1 - self._tokens
            wait_time = deficit * (self.per_seconds / self.rate)
            await asyncio.sleep(wait_time)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        refill = elapsed * (self.rate / self.per_seconds)
        self._tokens = min(self.rate, self._tokens + refill)
        self._last_refill = now
