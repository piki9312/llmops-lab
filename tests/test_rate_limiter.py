"""Tests for rate limiting functionality."""

import asyncio

import pytest

from llmops.rate_limiter import RateLimiter, TokenBucket


class TestTokenBucket:
    """Test Token Bucket algorithm."""

    @pytest.mark.asyncio
    async def test_consume_within_capacity(self):
        """Test consuming tokens within capacity."""
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0, initial_tokens=10.0)

        # Should allow consuming 5 tokens
        assert await bucket.consume(5.0) is True

        # Should have 5 tokens left
        available = await bucket.get_available()
        assert 4.5 <= available <= 5.5  # Allow for timing variance

    @pytest.mark.asyncio
    async def test_consume_exceeds_capacity(self):
        """Test consuming more tokens than available."""
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0, initial_tokens=3.0)

        # Should reject consuming 5 tokens (only 3 available)
        assert await bucket.consume(5.0) is False

        # Tokens should remain unchanged
        available = await bucket.get_available()
        assert 2.5 <= available <= 3.5

    @pytest.mark.asyncio
    async def test_refill_over_time(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10.0, refill_rate=10.0, initial_tokens=0.0)

        # Wait 0.5 seconds (should refill ~5 tokens at rate 10/sec)
        await asyncio.sleep(0.5)

        available = await bucket.get_available()
        assert 4.0 <= available <= 6.0  # Allow for timing variance

        # Should allow consuming 4 tokens
        assert await bucket.consume(4.0) is True

    @pytest.mark.asyncio
    async def test_capacity_cap(self):
        """Test that tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=5.0, refill_rate=10.0, initial_tokens=5.0)

        # Wait 1 second (would refill 10 tokens but capped at capacity)
        await asyncio.sleep(1.0)

        available = await bucket.get_available()
        assert available <= 5.0  # Should not exceed capacity


class TestRateLimiter:
    """Test combined QPS and TPM rate limiting."""

    @pytest.mark.asyncio
    async def test_qps_limit_allows(self):
        """Test QPS limit allows requests within limit."""
        limiter = RateLimiter(max_qps=10.0, max_tpm=None)

        # Should allow 5 requests immediately
        for _ in range(5):
            allowed, reason = await limiter.check_rate_limit(0)
            assert allowed is True
            assert reason is None

    @pytest.mark.asyncio
    async def test_qps_limit_rejects(self):
        """Test QPS limit rejects requests exceeding limit."""
        limiter = RateLimiter(max_qps=2.0, max_tpm=None)

        # Consume all tokens (2 requests)
        assert (await limiter.check_rate_limit(0))[0] is True
        assert (await limiter.check_rate_limit(0))[0] is True

        # Should reject 3rd request
        allowed, reason = await limiter.check_rate_limit(0)
        assert allowed is False
        assert reason == "qps_limit"

    @pytest.mark.asyncio
    async def test_tpm_limit_allows(self):
        """Test TPM limit allows requests within limit."""
        limiter = RateLimiter(max_qps=None, max_tpm=1000.0)

        # Should allow requests totaling 500 tokens
        allowed, reason = await limiter.check_rate_limit(250)
        assert allowed is True
        assert reason is None

        allowed, reason = await limiter.check_rate_limit(250)
        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_tpm_limit_rejects(self):
        """Test TPM limit rejects requests exceeding limit."""
        limiter = RateLimiter(max_qps=None, max_tpm=100.0)

        # Consume 80 tokens
        assert (await limiter.check_rate_limit(80))[0] is True

        # Should reject request for 50 more tokens (total would be 130)
        allowed, reason = await limiter.check_rate_limit(50)
        assert allowed is False
        assert reason == "tpm_limit"

    @pytest.mark.asyncio
    async def test_combined_limits(self):
        """Test both QPS and TPM limits together."""
        limiter = RateLimiter(max_qps=5.0, max_tpm=1000.0)

        # Should allow 3 requests with 100 tokens each
        for _ in range(3):
            allowed, reason = await limiter.check_rate_limit(100)
            assert allowed is True
            assert reason is None

        # 4th request with 800 tokens should fail TPM limit (total would be 1100)
        allowed, reason = await limiter.check_rate_limit(800)
        assert allowed is False
        assert reason == "tpm_limit"

    @pytest.mark.asyncio
    async def test_no_limits(self):
        """Test that None limits allow unlimited requests."""
        limiter = RateLimiter(max_qps=None, max_tpm=None)

        # Should allow many requests
        for _ in range(100):
            allowed, reason = await limiter.check_rate_limit(1000)
            assert allowed is True
            assert reason is None

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting rate limiter statistics."""
        limiter = RateLimiter(max_qps=10.0, max_tpm=1000.0)

        stats = await limiter.get_stats()

        assert "qps_available" in stats
        assert "qps_capacity" in stats
        assert "tpm_available" in stats
        assert "tpm_capacity" in stats

        assert stats["qps_capacity"] == 10.0
        assert stats["tpm_capacity"] == 1000.0
