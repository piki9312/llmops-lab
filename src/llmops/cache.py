"""Lightweight in-memory cache with TTL support.

Design:
- Simple dict-based store with TTL expiry
- Optional max_entries eviction (oldest expiry first)
- Utility to compute stable cache keys
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional


class InMemoryCacheStore:
    """TTL-aware in-memory cache."""

    def __init__(self, max_entries: int = 256, ttl_seconds: int = 600):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, tuple[float, Dict[str, Any]]] = {}

    def _now(self) -> float:
        return time.time()

    def _is_expired(self, expires_at: float) -> bool:
        return self._now() > expires_at

    def _evict_one(self) -> None:
        """Evict the entry with the earliest expiry."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][0])
        self._store.pop(oldest_key, None)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if self._is_expired(expires_at):
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Dict[str, Any]) -> None:
        if self.max_entries > 0 and len(self._store) >= self.max_entries:
            self._evict_one()
        # ttl_seconds <=0 means effectively no expiry for now (large horizon)
        ttl = self.ttl_seconds if self.ttl_seconds > 0 else 10**9
        expires_at = self._now() + ttl
        self._store[key] = (expires_at, value)

    def cleanup(self) -> None:
        """Remove expired entries."""
        for key in list(self._store.keys()):
            expires_at, _ = self._store[key]
            if self._is_expired(expires_at):
                self._store.pop(key, None)


def compute_cache_key(payload: Dict[str, Any]) -> str:
    """Compute stable sha256 hash for cache key.

    Args:
        payload: Cache payload dict (must be JSON-serializable)

    Returns:
        Hex digest string
    """
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()
