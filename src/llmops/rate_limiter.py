"""Rate limiting with Token Bucket algorithm.

Supports both QPS (queries per second) and TPM (tokens per minute) limits.
Thread-safe for async FastAPI applications.
"""

import asyncio
import time
from typing import Optional


class TokenBucket:
    """Token bucket rate limiter.

    Tokens regenerate at a fixed rate. Each request consumes tokens.
    If no tokens available, request is rate limited.

    Args:
        capacity: Maximum tokens in bucket
        refill_rate: Tokens added per second
        initial_tokens: Starting token count (defaults to capacity)
    """

    def __init__(self, capacity: float, refill_rate: float, initial_tokens: Optional[float] = None):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens available and consumed, False if rate limited
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill

            # Refill tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            # Try to consume
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    async def get_available(self) -> float:
        """Get current available tokens (for monitoring)."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            return min(self.capacity, self.tokens + elapsed * self.refill_rate)


class RateLimiter:
    """Combined QPS and TPM rate limiter.

    Args:
        max_qps: Maximum queries per second (None = no limit)
        max_tpm: Maximum tokens per minute (None = no limit)
    """

    def __init__(self, max_qps: Optional[float] = None, max_tpm: Optional[float] = None):
        self.max_qps = max_qps
        self.max_tpm = max_tpm

        # QPS bucket: 1 token per request, refills at max_qps rate
        self.qps_bucket = (
            TokenBucket(
                capacity=max_qps if max_qps else float("inf"),
                refill_rate=max_qps if max_qps else float("inf"),
            )
            if max_qps
            else None
        )

        # TPM bucket: tokens based on request size, refills at max_tpm/60 rate
        self.tpm_bucket = (
            TokenBucket(
                capacity=max_tpm if max_tpm else float("inf"),
                refill_rate=(max_tpm / 60.0) if max_tpm else float("inf"),
            )
            if max_tpm
            else None
        )

    async def check_rate_limit(self, estimated_tokens: int = 0) -> tuple[bool, Optional[str]]:
        """Check if request is within rate limits.

        Args:
            estimated_tokens: Estimated token count for request (for TPM limit)

        Returns:
            (allowed, reason) where:
                - allowed: True if request should proceed
                - reason: None if allowed, otherwise "qps_limit" or "tpm_limit"
        """
        # Check QPS limit
        if self.qps_bucket:
            if not await self.qps_bucket.consume(1.0):
                return False, "qps_limit"

        # Check TPM limit
        if self.tpm_bucket and estimated_tokens > 0:
            if not await self.tpm_bucket.consume(float(estimated_tokens)):
                return False, "tpm_limit"

        return True, None

    async def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        stats = {}

        if self.qps_bucket:
            stats["qps_available"] = await self.qps_bucket.get_available()
            stats["qps_capacity"] = self.qps_bucket.capacity

        if self.tpm_bucket:
            stats["tpm_available"] = await self.tpm_bucket.get_available()
            stats["tpm_capacity"] = self.tpm_bucket.capacity

        return stats
