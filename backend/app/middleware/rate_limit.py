"""Rate limiting middleware for Eleanor API.

Provides protection against brute force attacks and API abuse using
Redis-backed sliding window rate limiting.
"""

import logging
import time
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.database import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class RateLimiter:
    """Redis-backed rate limiter using sliding window algorithm."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_limit: int = 20,
    ):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Max requests per minute per client
            requests_per_hour: Max requests per hour per client
            burst_limit: Max burst requests in 10 seconds
        """
        self.rpm = requests_per_minute
        self.rph = requests_per_hour
        self.burst = burst_limit

    async def check_rate_limit(
        self,
        key: str,
        endpoint_weight: int = 1,
    ) -> tuple[bool, int | None]:
        """Check if request is within rate limits.

        Args:
            key: Rate limit key (usually IP or user ID)
            endpoint_weight: Weight multiplier for expensive endpoints

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        redis = await get_redis()
        now = time.time()
        now_ms = int(now * 1000)

        # Use pipeline for atomic operations
        pipe = redis.pipeline()

        # Keys for different time windows
        burst_key = f"rl:burst:{key}"
        minute_key = f"rl:minute:{key}"
        hour_key = f"rl:hour:{key}"

        # Remove expired entries and count current
        for window_key, window_seconds in [
            (burst_key, 10),
            (minute_key, 60),
            (hour_key, 3600),
        ]:
            cutoff = now_ms - (window_seconds * 1000)
            pipe.zremrangebyscore(window_key, 0, cutoff)
            pipe.zcard(window_key)

        results = await pipe.execute()

        # Parse results (zremrangebyscore doesn't return useful info)
        burst_count = results[1]
        minute_count = results[3]
        hour_count = results[5]

        # Apply weight
        weighted_cost = endpoint_weight

        # Check limits
        if burst_count + weighted_cost > self.burst:
            return False, 10

        if minute_count + weighted_cost > self.rpm:
            return False, 60

        if hour_count + weighted_cost > self.rph:
            return False, 3600

        # Record this request
        pipe = redis.pipeline()
        for window_key, window_seconds in [
            (burst_key, 10),
            (minute_key, 60),
            (hour_key, 3600),
        ]:
            for _ in range(weighted_cost):
                pipe.zadd(window_key, {f"{now_ms}:{_}": now_ms})
            pipe.expire(window_key, window_seconds + 1)

        await pipe.execute()

        return True, None

    async def get_remaining(self, key: str) -> dict[str, int]:
        """Get remaining requests for a key.

        Returns:
            Dict with remaining requests for each window
        """
        redis = await get_redis()
        now_ms = int(time.time() * 1000)

        pipe = redis.pipeline()
        for window_key, window_seconds in [
            (f"rl:burst:{key}", 10),
            (f"rl:minute:{key}", 60),
            (f"rl:hour:{key}", 3600),
        ]:
            cutoff = now_ms - (window_seconds * 1000)
            pipe.zcount(window_key, cutoff, now_ms)

        counts = await pipe.execute()

        return {
            "burst": max(0, self.burst - counts[0]),
            "minute": max(0, self.rpm - counts[1]),
            "hour": max(0, self.rph - counts[2]),
        }


# Default rate limiter instance
default_rate_limiter = RateLimiter(
    requests_per_minute=60,
    requests_per_hour=1000,
    burst_limit=20,
)

# Stricter limiter for auth endpoints
auth_rate_limiter = RateLimiter(
    requests_per_minute=10,
    requests_per_hour=50,
    burst_limit=5,
)


# Endpoint weights for expensive operations
ENDPOINT_WEIGHTS = {
    "/api/v1/search/query": 3,
    "/api/v1/search/export": 5,
    "/api/v1/collection/collect": 2,
    "/api/v1/collection/hunts": 3,
    "/api/v1/response/isolate": 5,
    "/api/v1/response/release": 5,
    "/api/v1/enrichment/bulk": 3,
    "/api/v1/parsing/upload": 2,
}

# Paths that use auth rate limiter
AUTH_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/token",
    "/api/v1/auth/register",
    "/api/v1/auth/reset-password",
}

# Paths to skip rate limiting
SKIP_PATHS = {
    "/health",
    "/api/health",
    "/api/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def get_client_identifier(request: Request) -> str:
    """Extract client identifier for rate limiting.

    Uses authenticated user ID if available, otherwise falls back to IP.
    """
    # Check for authenticated user (set by auth middleware)
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"

    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"

    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(
        self,
        app,
        default_limiter: RateLimiter = default_rate_limiter,
        auth_limiter: RateLimiter = auth_rate_limiter,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.default_limiter = default_limiter
        self.auth_limiter = auth_limiter
        self.enabled = enabled

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request with rate limiting."""
        # Skip if disabled or path is excluded
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        if path in SKIP_PATHS:
            return await call_next(request)

        # Get client identifier
        client_key = get_client_identifier(request)

        # Select limiter and weight
        if path in AUTH_PATHS:
            limiter = self.auth_limiter
        else:
            limiter = self.default_limiter

        weight = ENDPOINT_WEIGHTS.get(path, 1)

        try:
            # Check rate limit
            allowed, retry_after = await limiter.check_rate_limit(
                client_key,
                endpoint_weight=weight,
            )

            if not allowed:
                logger.warning(
                    "Rate limit exceeded for %s on %s",
                    client_key,
                    path,
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limiter.rpm),
                    },
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            remaining = await limiter.get_remaining(client_key)
            response.headers["X-RateLimit-Limit"] = str(limiter.rpm)
            response.headers["X-RateLimit-Remaining"] = str(remaining["minute"])
            response.headers["X-RateLimit-Reset"] = str(60)

            return response

        except Exception as e:
            # Don't block requests if rate limiting fails
            logger.error("Rate limiting error: %s", e)
            return await call_next(request)


def create_rate_limit_middleware(
    app,
    enabled: bool = True,
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    auth_requests_per_minute: int = 10,
) -> RateLimitMiddleware:
    """Create rate limit middleware with custom settings.

    Args:
        app: FastAPI application
        enabled: Whether rate limiting is enabled
        requests_per_minute: Default requests per minute
        requests_per_hour: Default requests per hour
        auth_requests_per_minute: Auth endpoint requests per minute

    Returns:
        Configured RateLimitMiddleware
    """
    default_limiter = RateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
    )
    auth_limiter = RateLimiter(
        requests_per_minute=auth_requests_per_minute,
        requests_per_hour=auth_requests_per_minute * 5,
        burst_limit=3,
    )

    return RateLimitMiddleware(
        app,
        default_limiter=default_limiter,
        auth_limiter=auth_limiter,
        enabled=enabled,
    )
