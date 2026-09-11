"""Async Redis and in-memory fallback token-bucket rate limiter for FastAPI endpoints."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import math
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request, Response, status

if TYPE_CHECKING:
    import redis.asyncio as aioredis
else:
    try:
        import redis.asyncio as aioredis
    except ImportError:  # pragma: no cover
        aioredis = None

logger = logging.getLogger(__name__)

# Unit multipliers in seconds
RATE_UNITS: dict[str, float] = {
    "s": 1.0,
    "sec": 1.0,
    "second": 1.0,
    "m": 60.0,
    "min": 60.0,
    "minute": 60.0,
    "h": 3600.0,
    "hr": 3600.0,
    "hour": 3600.0,
    "d": 86400.0,
    "day": 86400.0,
}

RATE_REGEX = re.compile(
    r"^\s*(\d+)\s*(?:/|\s+per\s+)\s*(\d+)?\s*([a-zA-Z]+)\s*$",
    re.IGNORECASE,
)

# Atomic Token Bucket Lua Script for Redis
# KEYS[1]: rate limit key
# ARGV[1]: capacity (max tokens)
# ARGV[2]: refill_rate (tokens per second)
# ARGV[3]: current timestamp (epoch seconds as float)
# ARGV[4]: cost (tokens requested)
# ARGV[5]: ttl (seconds to keep key alive)
REDIS_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local data = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_updated = now
else
    local delta = math.max(0, now - last_updated)
    tokens = math.min(capacity, tokens + (delta * refill_rate))
    last_updated = now
end

local allowed = 0
local retry_after = 0

if tokens >= cost then
    allowed = 1
    tokens = tokens - cost
else
    allowed = 0
    if refill_rate > 0 then
        retry_after = math.ceil((cost - tokens) / refill_rate)
    else
        retry_after = 1
    end
end

redis.call('HSET', key, 'tokens', tokens, 'last_updated', last_updated)
redis.call('EXPIRE', key, ttl)

local remaining = math.floor(tokens)
local reset = 0
if refill_rate > 0 then
    reset = math.ceil((capacity - tokens) / refill_rate)
end

return {allowed, remaining, reset, retry_after}
"""


def parse_rate_string(rate_str: str) -> tuple[int, float]:
    """Parse a human-readable rate limit string into (limit, period_seconds).

    Examples:
        '10/second' -> (10, 1.0)
        '60/minute' -> (60, 60.0)
        '1000/hour' -> (1000, 3600.0)
        '5000/day'  -> (5000, 86400.0)
        '5/10s'     -> (5, 10.0)
    """
    match = RATE_REGEX.match(rate_str)
    if not match:
        raise ValueError(
            f"Invalid rate limit format: '{rate_str}'. "
            "Expected formats like '10/second', '60/minute', '1000/hour', '5000/day'."
        )

    count_str, multiplier_str, unit_str = match.groups()
    limit = int(count_str)
    multiplier = int(multiplier_str) if multiplier_str else 1
    unit_norm = unit_str.lower().rstrip("s")

    # Match normalized unit
    period_seconds: float | None = None
    for key, val in RATE_UNITS.items():
        if unit_norm == key.rstrip("s"):
            period_seconds = val * multiplier
            break

    if period_seconds is None or period_seconds <= 0:
        raise ValueError(f"Unknown time unit '{unit_str}' in rate string '{rate_str}'.")

    if limit <= 0:
        raise ValueError(f"Limit must be greater than zero, got {limit}.")

    return limit, period_seconds


def get_client_ip(request: Request) -> str:
    """Extract client IP address from Request, respecting reverse proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


def get_user_id(request: Request) -> str:
    """Extract authenticated user identifier or fallback to client IP."""
    # Check request state (e.g. auth middleware or dependencies)
    user = getattr(request.state, "user", None)
    if user is not None:
        if isinstance(user, str):
            return user
        user_id = getattr(user, "id", None) or getattr(user, "user_id", None)
        if user_id:
            return str(user_id)

    principal = getattr(request.state, "principal", None)
    if principal is not None:
        principal_id = getattr(principal, "id", None) or getattr(principal, "principal_id", None)
        if principal_id:
            return str(principal_id)

    user_id_state = getattr(request.state, "user_id", None)
    if user_id_state:
        return str(user_id_state)

    # Check Authorization header bearer token or fallback
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            # Use hash prefix of bearer token as an identifier
            return f"bearer:{token[:16]}"

    return get_client_ip(request)


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset: int
    retry_after: int

    @property
    def headers(self) -> dict[str, str]:
        """Standard HTTP rate limit headers."""
        hdr = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(max(0, self.reset)),
        }
        if not self.allowed:
            hdr["Retry-After"] = str(max(1, self.retry_after))
        return hdr


class InMemoryTokenBucket:
    """Thread-safe & async-safe in-memory token bucket implementation."""

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_updated)
        self._lock = asyncio.Lock()
        self._last_prune = time.time()

    async def check(
        self,
        key: str,
        capacity: int,
        refill_rate: float,
        cost: float = 1.0,
        now: float | None = None,
    ) -> RateLimitResult:
        """Atomically evaluate token availability and consume tokens if allowed."""
        if now is None:
            now = time.time()

        async with self._lock:
            # Periodic prune of stale keys if table grows
            if now - self._last_prune > 300.0:
                self._prune(now)

            record = self._buckets.get(key)
            if record is None:
                tokens = float(capacity)
                last_updated = now
            else:
                tokens, last_updated = record
                delta = max(0.0, now - last_updated)
                tokens = min(float(capacity), tokens + (delta * refill_rate))
                last_updated = now

            if tokens >= cost:
                allowed = True
                tokens -= cost
                remaining = math.floor(tokens)
                reset = math.ceil((capacity - tokens) / refill_rate) if refill_rate > 0 else 0
                retry_after = 0
            else:
                allowed = False
                remaining = math.floor(tokens)
                deficit = cost - tokens
                retry_after = (
                    math.ceil(deficit / refill_rate) if refill_rate > 0 else int(deficit)
                )
                retry_after = max(1, retry_after)
                reset = math.ceil((capacity - tokens) / refill_rate) if refill_rate > 0 else 0

            self._buckets[key] = (tokens, last_updated)

            return RateLimitResult(
                allowed=allowed,
                limit=capacity,
                remaining=remaining,
                reset=reset,
                retry_after=retry_after,
            )

    def _prune(self, now: float) -> None:
        """Evict records not touched in over 1 hour."""
        cutoff = now - 3600.0
        keys_to_remove = [k for k, (_, last_t) in self._buckets.items() if last_t < cutoff]
        for k in keys_to_remove:
            self._buckets.pop(k, None)
        self._last_prune = now

    def reset(self) -> None:
        """Clear all in-memory buckets (useful for test fixtures)."""
        self._buckets.clear()
        self._last_prune = time.time()


class AsyncRateLimiter:
    """Async Redis-backed token bucket rate limiter with automatic in-memory fallback."""

    def __init__(
        self,
        redis_client: Any | None = None,
        key_prefix: str = "alphabrain:ratelimit",
        default_rate: str = "60/minute",
        fallback_on_error: bool = True,
    ) -> None:
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self.default_rate = default_rate
        self.fallback_on_error = fallback_on_error
        self.memory_backend = InMemoryTokenBucket()

    def _resolve_rate(
        self,
        rate: str | None = None,
        capacity: int | None = None,
        period_seconds: float | None = None,
        burst: int | None = None,
    ) -> tuple[int, float, int]:
        """Resolve (capacity, refill_rate, period_seconds)."""
        effective_rate = rate or self.default_rate
        base_limit, period = parse_rate_string(effective_rate)

        if capacity is not None:
            base_limit = capacity
        if period_seconds is not None:
            period = period_seconds

        effective_capacity = burst if burst is not None else base_limit
        refill_rate = base_limit / period
        return effective_capacity, refill_rate, math.ceil(period * 2)

    async def check(
        self,
        key: str,
        rate: str | None = None,
        capacity: int | None = None,
        period_seconds: float | None = None,
        burst: int | None = None,
        cost: float = 1.0,
    ) -> RateLimitResult:
        """Check and consume rate limit tokens for a given key."""
        eff_capacity, refill_rate, ttl = self._resolve_rate(
            rate=rate,
            capacity=capacity,
            period_seconds=period_seconds,
            burst=burst,
        )

        full_key = f"{self.key_prefix}:{key}"

        # If Redis client is configured, attempt atomic Lua script
        if self.redis_client is not None:
            try:
                now = time.time()
                # Run Lua script
                res = await self.redis_client.eval(
                    REDIS_TOKEN_BUCKET_LUA,
                    1,
                    full_key,
                    eff_capacity,
                    refill_rate,
                    now,
                    cost,
                    ttl,
                )
                allowed_int, remaining, reset, retry_after = res
                return RateLimitResult(
                    allowed=bool(allowed_int == 1),
                    limit=eff_capacity,
                    remaining=int(remaining),
                    reset=int(reset),
                    retry_after=int(retry_after),
                )
            except Exception as exc:
                if not self.fallback_on_error:
                    raise
                logger.warning(
                    "Redis rate limiter unavailable (%s); falling back to in-memory backend for key %s",
                    exc,
                    key,
                )

        # Fallback or primary in-memory check
        return await self.memory_backend.check(
            key=full_key,
            capacity=eff_capacity,
            refill_rate=refill_rate,
            cost=cost,
        )

    def dependency(
        self,
        rate: str | None = None,
        key_func: Callable[[Request], str | Awaitable[str]] | None = None,
        burst: int | None = None,
        cost: float = 1.0,
        scope: str | None = None,
    ) -> Callable[..., Awaitable[RateLimitResult]]:
        """Create a FastAPI dependency that enforces the rate limit.

        Example:
            @app.get("/items", dependencies=[Depends(limiter.dependency("10/minute"))])
            def get_items():
                ...
        """
        extracted_key_func = key_func or get_client_ip

        async def _rate_limit_dependency(
            request: Request,
            response: Response,
        ) -> RateLimitResult:
            if inspect.iscoroutinefunction(extracted_key_func):
                raw_key = await extracted_key_func(request)
            else:
                raw_key = extracted_key_func(request)

            resolved_scope = scope or request.url.path
            compound_key = f"{resolved_scope}:{raw_key}"

            result = await self.check(
                key=compound_key,
                rate=rate,
                burst=burst,
                cost=cost,
            )

            # Apply headers to response if present
            if response is not None:
                for header_name, header_val in result.headers.items():
                    response.headers[header_name] = header_val

            if not result.allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too Many Requests",
                    headers=result.headers,
                )

            return result

        return _rate_limit_dependency

    def limit(
        self,
        rate: str | None = None,
        key_func: Callable[[Request], str | Awaitable[str]] | None = None,
        burst: int | None = None,
        cost: float = 1.0,
        scope: str | None = None,
    ) -> Callable[..., Any]:
        """Decorator for FastAPI endpoint route handlers.

        Example:
            @app.get("/items")
            @limiter.limit("20/minute")
            async def get_items(request: Request, response: Response):
                return {"items": []}
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            extracted_key_func = key_func or get_client_ip

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Find Request and optional Response in kwargs or positional args
                request: Request | None = kwargs.get("request")
                response: Response | None = kwargs.get("response")

                if request is None:
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break

                if response is None:
                    for arg in args:
                        if isinstance(arg, Response):
                            response = arg
                            break

                if request is None:
                    raise RuntimeError(
                        f"@limiter.limit requires a Request parameter in {func.__name__}"
                    )

                if inspect.iscoroutinefunction(extracted_key_func):
                    raw_key = await extracted_key_func(request)
                else:
                    raw_key = extracted_key_func(request)

                resolved_scope = scope or request.url.path
                compound_key = f"{resolved_scope}:{raw_key}"

                result = await self.check(
                    key=compound_key,
                    rate=rate,
                    burst=burst,
                    cost=cost,
                )

                if response is not None:
                    for header_name, header_val in result.headers.items():
                        response.headers[header_name] = header_val

                if not result.allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too Many Requests",
                        headers=result.headers,
                    )

                res = func(*args, **kwargs)
                if inspect.iscoroutine(res):
                    res = await res

                # If the function returned a Response directly, attach headers
                if isinstance(res, Response):
                    for header_name, header_val in result.headers.items():
                        res.headers[header_name] = header_val

                return res

            return wrapper

        return decorator
