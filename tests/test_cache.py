"""Tests for in-memory cache store."""

import time

from llmops.cache import InMemoryCacheStore, compute_cache_key


class TestInMemoryCacheStore:
    """Test TTL cache behavior."""

    def test_set_and_get(self):
        cache = InMemoryCacheStore(max_entries=10, ttl_seconds=5)
        cache.set("a", {"value": 1})
        assert cache.get("a") == {"value": 1}

    def test_expiry(self):
        cache = InMemoryCacheStore(max_entries=10, ttl_seconds=0.1)
        cache.set("b", {"value": 2})
        time.sleep(0.2)
        assert cache.get("b") is None

    def test_eviction_when_full(self):
        cache = InMemoryCacheStore(max_entries=1, ttl_seconds=5)
        cache.set("k1", {"value": 1})
        cache.set("k2", {"value": 2})
        assert cache.get("k1") is None
        assert cache.get("k2") == {"value": 2}


class TestComputeCacheKey:
    """Test cache key computation stability."""

    def test_same_payload_same_key(self):
        payload = {"a": 1, "b": {"c": 2}}
        key1 = compute_cache_key(payload)
        key2 = compute_cache_key(payload)
        assert key1 == key2

    def test_different_payloads_different_keys(self):
        key1 = compute_cache_key({"a": 1})
        key2 = compute_cache_key({"a": 2})
        assert key1 != key2
