"""
Backward-compatibility stub for rate limiter.
Re-exports from app.core.rate_limiter.
"""

from app.core.rate_limiter import (
    RateLimiter,
    emergency_rate_limiter,
    report_rate_limiter,
    route_rate_limiter,
)

__all__ = [
    "RateLimiter",
    "report_rate_limiter",
    "route_rate_limiter",
    "emergency_rate_limiter",
]
