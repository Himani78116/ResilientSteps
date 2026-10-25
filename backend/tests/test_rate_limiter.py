import unittest

from fastapi import HTTPException
from starlette.requests import Request

from app.core import rate_limiter as rate_limiter_module
from app.core.rate_limiter import RateLimiter


def _request(peer_ip: str, forwarded: str | None = None, user_id: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/nearby-places",
            "query_string": b"",
            "headers": headers,
            "client": (peer_ip, 4321),
        }
    )
    if user_id is not None:
        request.state.user_id = user_id
    return request


class RateLimiterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._depth = rate_limiter_module._TRUSTED_PROXY_DEPTH
        rate_limiter_module._TRUSTED_PROXY_DEPTH = 0

    def tearDown(self):
        rate_limiter_module._TRUSTED_PROXY_DEPTH = self._depth

    async def _consume(self, limiter: RateLimiter, request: Request, times: int) -> None:
        for _ in range(times):
            await limiter(request)

    async def _assert_throttled(
        self, limiter: RateLimiter, request: Request, times: int
    ) -> None:
        with self.assertRaises(HTTPException) as caught:
            await self._consume(limiter, request, times)
        self.assertEqual(caught.exception.status_code, 429)

    async def test_identity_gets_independent_buckets_from_one_address(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        shared_ip = "203.0.113.10"

        alice = _request(shared_ip, user_id="alice")
        bob = _request(shared_ip, user_id="bob")

        await self._consume(limiter, alice, 2)
        await self._consume(limiter, bob, 2)

        await self._assert_throttled(limiter, alice, 1)

    async def test_identity_is_bucketed_across_addresses(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        await self._consume(limiter, _request("203.0.113.10", user_id="u1"), 1)
        await self._consume(limiter, _request("198.51.100.7", user_id="u1"), 1)

        await self._assert_throttled(limiter, _request("192.0.2.5", user_id="u1"), 1)

    async def test_tunnelled_clients_are_not_merged_into_one_bucket(self):
        """Regression: ngrok forwards every request from 127.0.0.1."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        first = _request("127.0.0.1", forwarded="203.0.113.10")
        second = _request("127.0.0.1", forwarded="198.51.100.7")

        await self._consume(limiter, first, 2)
        await self._consume(limiter, second, 2)

        await self._assert_throttled(limiter, first, 1)

    async def test_tunnel_uses_the_address_appended_by_the_tunnel(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        spoofed = "1.2.3.4, 203.0.113.10"

        await self._consume(limiter, _request("127.0.0.1", forwarded=spoofed), 1)

        # Different spoofed prefix, same tunnel-observed client: same bucket.
        await self._assert_throttled(
            limiter, _request("127.0.0.1", forwarded="5.6.7.8, 203.0.113.10"), 1
        )

    async def test_forwarded_header_is_ignored_from_a_direct_peer(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        await self._consume(limiter, _request("203.0.113.10", forwarded="1.2.3.4"), 1)

        await self._assert_throttled(
            limiter, _request("203.0.113.10", forwarded="5.6.7.8"), 1
        )

    async def test_configured_proxy_depth_keys_on_the_client(self):
        rate_limiter_module._TRUSTED_PROXY_DEPTH = 1
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        first = _request("172.17.0.1", forwarded="203.0.113.10")
        second = _request("172.17.0.1", forwarded="198.51.100.7")

        await self._consume(limiter, first, 2)
        await self._consume(limiter, second, 2)

        await self._assert_throttled(limiter, first, 1)

    async def test_configured_proxy_depth_skips_caller_supplied_entries(self):
        rate_limiter_module._TRUSTED_PROXY_DEPTH = 2
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        # Spoofed prefix, real client appended by the outermost trusted proxy,
        # then the inner proxy's own address.
        await self._consume(
            limiter, _request("172.17.0.1", forwarded="9.9.9.9, 203.0.113.10, 172.17.0.2"), 1
        )

        await self._assert_throttled(
            limiter, _request("172.17.0.1", forwarded="8.8.8.8, 203.0.113.10, 172.17.0.2"), 1
        )

    async def test_short_forwarded_chain_falls_back_to_the_peer(self):
        rate_limiter_module._TRUSTED_PROXY_DEPTH = 3
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        await self._consume(limiter, _request("172.17.0.1", forwarded="9.9.9.9"), 1)

        # Fewer hops than configured means the header cannot be trusted, so the
        # spoofable entry must not become a fresh bucket.
        await self._assert_throttled(
            limiter, _request("172.17.0.1", forwarded="8.8.8.8"), 1
        )

    async def test_limit_is_still_enforced(self):
        limiter = RateLimiter(max_requests=20, window_seconds=60)
        client = _request("203.0.113.10")

        await self._consume(limiter, client, 20)
        await self._assert_throttled(limiter, client, 1)

    async def test_stale_ip_buckets_are_cleaned_up(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter._cleanup_interval = 0.0
        limiter._last_cleanup = 0.0

        await self._consume(limiter, _request("203.0.113.10"), 1)
        stale = rate_limiter_module._TokenBucket(capacity=1, tokens=0.0)
        stale.last_refill -= 10_000.0
        limiter._buckets["ip:198.51.100.7"] = stale

        await self._consume(limiter, _request("192.0.2.44"), 1)

        self.assertNotIn("ip:198.51.100.7", limiter._buckets)
        self.assertIn("ip:203.0.113.10", limiter._buckets)
