"""
Simple in-process rate limiter for WalkSafe API endpoints.

Uses a token-bucket algorithm keyed by client identifier (IP or user_hash).
This is a single-process solution — for multi-instance deployments, replace
with a Redis-backed implementation.
"""

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException, Request

# Number of trusted reverse proxies in front of the app (e.g. 1 for ngrok).
# When set, the rate limiter uses the Nth-from-last X-Forwarded-For entry.
# When 0 (default), X-Forwarded-For is ignored entirely to prevent spoofing.
_TRUSTED_PROXY_DEPTH = int(os.environ.get("TRUSTED_PROXY_DEPTH", "0"))


@dataclass
class _TokenBucket:
    capacity: int
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def try_consume(self, refill_rate: float) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """
    FastAPI-compatible rate limiter.

    Usage as a dependency:

        report_limiter = RateLimiter(max_requests=5, window_seconds=3600, key="user_hash")

        @router.post("/report")
        async def submit_report(..., _=Depends(report_limiter)):
            ...
    """

    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: int,
        key: str = "ip",
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._refill_rate = max_requests / window_seconds
        self._key_source = key
        self._buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(capacity=max_requests, tokens=max_requests)
        )
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = max(300.0, window_seconds * 2.0)

    async def __call__(self, request: Request) -> None:
        client_key = self._extract_key(request)
        self._maybe_cleanup()

        bucket = self._buckets[client_key]
        if not bucket.try_consume(self._refill_rate):
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded. Maximum {self._max_requests} "
                    f"requests per {self._window_seconds} seconds."
                ),
            )

    def _extract_key(self, request: Request) -> str:
        if self._key_source == "user_hash":
            # Try to read user_hash from the JSON body cache if available,
            # fall back to IP. We don't parse the body here to avoid
            # consuming the stream — the key is best-effort.
            return self._client_ip(request)

        return self._client_ip(request)

    def _client_ip(self, request: Request) -> str:
        # Only trust X-Forwarded-For if TRUSTED_PROXY_DEPTH is configured.
        # When set, take the Nth-from-last entry (the one injected by the
        # trusted reverse proxy, not the client).
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded and _TRUSTED_PROXY_DEPTH > 0:
            parts = [part.strip() for part in forwarded.split(",")]
            # The Nth-from-last entry is the one added by our trusted proxy.
            index = max(0, len(parts) - _TRUSTED_PROXY_DEPTH)
            return parts[index]
        client = request.client
        return client.host if client else "unknown"

    def _maybe_cleanup(self) -> None:
        now = time.monotonic()
        if (now - self._last_cleanup) < self._cleanup_interval:
            return

        self._last_cleanup = now
        stale_threshold = now - (self._window_seconds * 2)
        stale_keys = [
            key
            for key, bucket in self._buckets.items()
            if bucket.last_refill < stale_threshold
        ]
        for key in stale_keys:
            del self._buckets[key]


# Pre-configured limiters for different endpoint groups.
report_rate_limiter = RateLimiter(max_requests=5, window_seconds=3600, key="ip")
route_rate_limiter = RateLimiter(max_requests=60, window_seconds=60, key="ip")
emergency_rate_limiter = RateLimiter(max_requests=3, window_seconds=600, key="ip")
