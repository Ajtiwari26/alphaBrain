"""Unit tests for async Redis and in-memory fallback token-bucket rate limiter.

Covers:
- Rate string parsing and validation
- In-memory token bucket replenishment, bursting, and eviction
- Key extraction functions (IP, forwarded, user ID, auth token)
- Redis Lua script execution and response parsing via async client mock
- Graceful Redis error handling and in-memory fallback
- FastAPI integration via dependency and decorator
- Rate limit headers (X-RateLimit-Limit, Remaining, Reset, Retry-After)
- HTTP 429 Too Many Requests exceptions
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI, Request, Response
from fastapi.testclient import TestClient

from alpha_core.api.rate_limiter import (
    AsyncRateLimiter,
    InMemoryTokenBucket,
    RateLimitResult,
    get_client_ip,
    get_user_id,
    parse_rate_string,
)

# ============================================================================
# Rate String Parsing Tests
# ============================================================================


def test_parse_rate_string_valid() -> None:
    """Verify standard rate strings parse into (limit, period_seconds)."""
    assert parse_rate_string("10/second") == (10, 1.0)
    assert parse_rate_string("10/s") == (10, 1.0)
    assert parse_rate_string("60/minute") == (60, 60.0)
    assert parse_rate_string("60/m") == (60, 60.0)
    assert parse_rate_string("1000/hour") == (1000, 3600.0)
    assert parse_rate_string("1000/h") == (1000, 3600.0)
    assert parse_rate_string("5000/day") == (5000, 86400.0)
    assert parse_rate_string("5000/d") == (5000, 86400.0)
    assert parse_rate_string("5/10s") == (5, 10.0)
    assert parse_rate_string("100 per minute") == (100, 60.0)


def test_parse_rate_string_invalid() -> None:
    """Verify invalid rate strings raise ValueError with helpful messages."""
    with pytest.raises(ValueError, match="Invalid rate limit format"):
        parse_rate_string("invalid")

    with pytest.raises(ValueError, match="Invalid rate limit format"):
        parse_rate_string("not-a-rate")

    with pytest.raises(ValueError, match="Unknown time unit"):
        parse_rate_string("10/lightyear")

    with pytest.raises(ValueError, match="Limit must be greater than zero"):
        parse_rate_string("0/second")


# ============================================================================
# RateLimitResult & Headers Tests
# ============================================================================


def test_rate_limit_result_headers_allowed() -> None:
    """Allowed results include X-RateLimit headers but no Retry-After."""
    result = RateLimitResult(allowed=True, limit=60, remaining=59, reset=60, retry_after=0)
    headers = result.headers
    assert headers["X-RateLimit-Limit"] == "60"
    assert headers["X-RateLimit-Remaining"] == "59"
    assert headers["X-RateLimit-Reset"] == "60"
    assert "Retry-After" not in headers


def test_rate_limit_result_headers_blocked() -> None:
    """Blocked results include Retry-After header with minimum 1 second."""
    result = RateLimitResult(allowed=False, limit=60, remaining=0, reset=30, retry_after=5)
    headers = result.headers
    assert headers["X-RateLimit-Limit"] == "60"
    assert headers["X-RateLimit-Remaining"] == "0"
    assert headers["X-RateLimit-Reset"] == "30"
    assert headers["Retry-After"] == "5"


# ============================================================================
# InMemoryTokenBucket Tests
# ============================================================================


@pytest.mark.asyncio
async def test_in_memory_token_bucket_enforcement() -> None:
    """Token bucket enforces rate limit and replenishes tokens over time."""
    bucket = InMemoryTokenBucket()
    t0 = 1000.0

    # Capacity 2, refill rate 1 token/sec
    res1 = await bucket.check("test-client", capacity=2, refill_rate=1.0, cost=1.0, now=t0)
    assert res1.allowed is True
    assert res1.remaining == 1

    res2 = await bucket.check("test-client", capacity=2, refill_rate=1.0, cost=1.0, now=t0)
    assert res2.allowed is True
    assert res2.remaining == 0

    # Exhausted: immediate next check rejected
    res3 = await bucket.check("test-client", capacity=2, refill_rate=1.0, cost=1.0, now=t0)
    assert res3.allowed is False
    assert res3.remaining == 0
    assert res3.retry_after >= 1

    # After 1.1s, 1 token has replenished
    res4 = await bucket.check("test-client", capacity=2, refill_rate=1.0, cost=1.0, now=t0 + 1.1)
    assert res4.allowed is True
    assert res4.remaining == 0


@pytest.mark.asyncio
async def test_in_memory_token_bucket_burst_and_reset() -> None:
    """Token bucket handles burst capacity and reset fixture."""
    bucket = InMemoryTokenBucket()
    # Capacity 5
    for _ in range(5):
        res = await bucket.check("burst-client", capacity=5, refill_rate=1.0, cost=1.0)
        assert res.allowed is True

    # 6th request fails
    res_overflow = await bucket.check("burst-client", capacity=5, refill_rate=1.0, cost=1.0)
    assert res_overflow.allowed is False

    # Reset clears table
    bucket.reset()
    res_post_reset = await bucket.check("burst-client", capacity=5, refill_rate=1.0, cost=1.0)
    assert res_post_reset.allowed is True


@pytest.mark.asyncio
async def test_in_memory_token_bucket_prune() -> None:
    """Stale keys older than 1 hour are pruned."""
    bucket = InMemoryTokenBucket()
    now = time.time()
    await bucket.check("old-key", capacity=10, refill_rate=1.0, now=now - 4000.0)
    await bucket.check("new-key", capacity=10, refill_rate=1.0, now=now)

    bucket._last_prune = 0.0  # Force prune on next check
    await bucket.check("trigger-key", capacity=10, refill_rate=1.0, now=now)

    assert "old-key" not in bucket._buckets
    assert "new-key" in bucket._buckets


# ============================================================================
# Key Extractor Tests
# ============================================================================


def test_get_client_ip_variations() -> None:
    """Verify IP extraction handles headers, client host, and fallback."""
    # X-Forwarded-For takes precedence
    req_forwarded = Request(
        scope={
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
            "client": ("10.0.0.1", 12345),
        }
    )
    assert get_client_ip(req_forwarded) == "203.0.113.195"

    # X-Real-IP
    req_real = Request(
        scope={
            "type": "http",
            "headers": [(b"x-real-ip", b"198.51.100.1")],
            "client": ("10.0.0.1", 12345),
        }
    )
    assert get_client_ip(req_real) == "198.51.100.1"

    # Client socket host
    req_client = Request(
        scope={
            "type": "http",
            "headers": [],
            "client": ("192.168.1.50", 12345),
        }
    )
    assert get_client_ip(req_client) == "192.168.1.50"

    # Fallback when client is None
    req_none = Request(scope={"type": "http", "headers": [], "client": None})
    assert get_client_ip(req_none) == "127.0.0.1"


def test_get_user_id_variations() -> None:
    """Verify user ID extraction from state, principal, token, and IP."""
    # From request.state.user string
    req_user_str = Request(scope={"type": "http", "headers": [], "client": None})
    req_user_str.state.user = "usr_999"
    assert get_user_id(req_user_str) == "usr_999"

    # From request.state.user object
    class UserObj:
        id = "usr_888"

    req_user_obj = Request(scope={"type": "http", "headers": [], "client": None})
    req_user_obj.state.user = UserObj()
    assert get_user_id(req_user_obj) == "usr_888"

    # From request.state.principal object
    class PrincipalObj:
        id = "principal_777"

    req_principal = Request(scope={"type": "http", "headers": [], "client": None})
    req_principal.state.principal = PrincipalObj()
    assert get_user_id(req_principal) == "principal_777"

    # From Bearer token header
    req_bearer = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", b"Bearer secret_token_1234567890")],
            "client": None,
        }
    )
    assert get_user_id(req_bearer) == "bearer:secret_token_123"

    # Fallback to IP
    req_fallback = Request(
        scope={
            "type": "http",
            "headers": [(b"x-real-ip", b"1.2.3.4")],
            "client": None,
        }
    )
    assert get_user_id(req_fallback) == "1.2.3.4"


# ============================================================================
# Async Redis Backend & Fallback Tests
# ============================================================================


@pytest.mark.asyncio
async def test_redis_backend_success() -> None:
    """Redis backend executes Lua script and correctly formats RateLimitResult."""
    mock_redis = AsyncMock()
    # Mock return: [allowed (1), remaining (9), reset (60), retry_after (0)]
    mock_redis.eval.return_value = [1, 9, 60, 0]

    limiter = AsyncRateLimiter(redis_client=mock_redis)
    result = await limiter.check("client_123", rate="10/minute")

    assert result.allowed is True
    assert result.limit == 10
    assert result.remaining == 9
    assert result.reset == 60
    assert result.retry_after == 0
    assert mock_redis.eval.await_count == 1


@pytest.mark.asyncio
async def test_redis_backend_exceeded() -> None:
    """Redis backend correctly handles rate limit exceeded from Lua."""
    mock_redis = AsyncMock()
    # Mock return: [allowed (0), remaining (0), reset (45), retry_after (6)]
    mock_redis.eval.return_value = [0, 0, 45, 6]

    limiter = AsyncRateLimiter(redis_client=mock_redis)
    result = await limiter.check("client_123", rate="10/minute")

    assert result.allowed is False
    assert result.remaining == 0
    assert result.retry_after == 6
    assert result.headers["Retry-After"] == "6"


@pytest.mark.asyncio
async def test_redis_backend_fallback_on_error() -> None:
    """When Redis raises an error, fallback to in-memory backend without breaking."""
    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = ConnectionError("Redis connection refused")

    limiter = AsyncRateLimiter(redis_client=mock_redis, fallback_on_error=True)
    # Should not raise; smoothly falls back to memory backend
    res1 = await limiter.check("client_err", rate="2/second")
    assert res1.allowed is True
    assert res1.remaining == 1

    res2 = await limiter.check("client_err", rate="2/second")
    assert res2.allowed is True
    assert res2.remaining == 0

    res3 = await limiter.check("client_err", rate="2/second")
    assert res3.allowed is False
    assert res3.headers["Retry-After"] is not None


@pytest.mark.asyncio
async def test_redis_backend_no_fallback_raises() -> None:
    """When fallback_on_error=False, Redis errors propagate to caller."""
    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = ConnectionError("Redis down")

    limiter = AsyncRateLimiter(redis_client=mock_redis, fallback_on_error=False)
    with pytest.raises(ConnectionError, match="Redis down"):
        await limiter.check("client_nofallback", rate="10/minute")


# ============================================================================
# FastAPI Integration Tests (Dependency & Decorator)
# ============================================================================


def test_fastapi_dependency_rate_limiting() -> None:
    """FastAPI endpoint protected with limiter.dependency enforces rate limit."""
    limiter = AsyncRateLimiter()
    app = FastAPI()

    @app.get("/items", dependencies=[Depends(limiter.dependency("3/minute"))])
    def get_items() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    # 1st request
    r1 = client.get("/items", headers={"X-Real-IP": "10.0.0.1"})
    assert r1.status_code == 200
    assert r1.headers["X-RateLimit-Limit"] == "3"
    assert r1.headers["X-RateLimit-Remaining"] == "2"

    # 2nd request
    r2 = client.get("/items", headers={"X-Real-IP": "10.0.0.1"})
    assert r2.status_code == 200
    assert r2.headers["X-RateLimit-Remaining"] == "1"

    # 3rd request
    r3 = client.get("/items", headers={"X-Real-IP": "10.0.0.1"})
    assert r3.status_code == 200
    assert r3.headers["X-RateLimit-Remaining"] == "0"

    # 4th request: rate limit exceeded -> 429
    r4 = client.get("/items", headers={"X-Real-IP": "10.0.0.1"})
    assert r4.status_code == 429
    assert r4.json() == {"detail": "Too Many Requests"}
    assert "Retry-After" in r4.headers
    assert r4.headers["X-RateLimit-Remaining"] == "0"

    # Different IP should have its own separate limit
    r_diff = client.get("/items", headers={"X-Real-IP": "10.0.0.2"})
    assert r_diff.status_code == 200
    assert r_diff.headers["X-RateLimit-Remaining"] == "2"


def test_fastapi_decorator_rate_limiting() -> None:
    """FastAPI endpoint decorated with @limiter.limit enforces rate limit."""
    limiter = AsyncRateLimiter()
    app = FastAPI()

    @app.get("/users")
    @limiter.limit("2/minute")
    async def get_users(request: Request, response: Response) -> dict[str, str]:
        return {"message": "users list"}

    client = TestClient(app)

    # 1st request
    r1 = client.get("/users", headers={"X-Real-IP": "192.168.1.1"})
    assert r1.status_code == 200
    assert r1.headers["X-RateLimit-Limit"] == "2"
    assert r1.headers["X-RateLimit-Remaining"] == "1"

    # 2nd request
    r2 = client.get("/users", headers={"X-Real-IP": "192.168.1.1"})
    assert r2.status_code == 200
    assert r2.headers["X-RateLimit-Remaining"] == "0"

    # 3rd request: rate limit exceeded -> 429
    r3 = client.get("/users", headers={"X-Real-IP": "192.168.1.1"})
    assert r3.status_code == 429
    assert r3.json() == {"detail": "Too Many Requests"}
    assert "Retry-After" in r3.headers


def test_fastapi_custom_key_func_sync_and_async() -> None:
    """Custom key function extracts custom headers and segregates quota."""
    limiter = AsyncRateLimiter()
    app = FastAPI()

    # Sync key func
    def api_key_extractor(request: Request) -> str:
        return request.headers.get("x-api-key", "anonymous")

    # Async key func
    async def async_tenant_extractor(request: Request) -> str:
        return request.headers.get("x-tenant-id", "default-tenant")

    @app.get("/sync-keyed", dependencies=[Depends(limiter.dependency("2/minute", key_func=api_key_extractor))])
    def sync_keyed() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/async-keyed", dependencies=[Depends(limiter.dependency("2/minute", key_func=async_tenant_extractor))])
    def async_keyed() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    # Sync key func test
    c1_1 = client.get("/sync-keyed", headers={"x-api-key": "key-alpha"})
    c1_2 = client.get("/sync-keyed", headers={"x-api-key": "key-alpha"})
    c1_3 = client.get("/sync-keyed", headers={"x-api-key": "key-alpha"})
    assert c1_1.status_code == 200
    assert c1_2.status_code == 200
    assert c1_3.status_code == 429

    c2_1 = client.get("/sync-keyed", headers={"x-api-key": "key-beta"})
    assert c2_1.status_code == 200  # Independent key

    # Async key func test
    t1_1 = client.get("/async-keyed", headers={"x-tenant-id": "tenant-1"})
    t1_2 = client.get("/async-keyed", headers={"x-tenant-id": "tenant-1"})
    t1_3 = client.get("/async-keyed", headers={"x-tenant-id": "tenant-1"})
    assert t1_1.status_code == 200
    assert t1_2.status_code == 200
    assert t1_3.status_code == 429


def test_decorator_missing_request_error() -> None:
    """Decorator raises RuntimeError if route function has no Request parameter."""
    limiter = AsyncRateLimiter()
    app = FastAPI()

    @app.get("/broken")
    @limiter.limit("10/minute")
    async def broken_route() -> dict[str, str]:
        return {"status": "bad"}

    client = TestClient(app)
    with pytest.raises(RuntimeError, match=r"@limiter\.limit requires a Request parameter"):
        client.get("/broken")


@pytest.mark.asyncio
async def test_dependency_direct_invocation() -> None:
    """Dependency can be directly invoked with Request and Response objects."""
    limiter = AsyncRateLimiter()
    dep = limiter.dependency("2/second")
    req = Request(scope={"type": "http", "headers": [], "client": ("127.0.0.1", 8000), "path": "/test"})
    resp = Response()
    res1 = await dep(request=req, response=resp)
    assert res1.allowed is True
    assert res1.remaining == 1
    assert resp.headers["X-RateLimit-Limit"] == "2"

    res2 = await dep(request=req, response=resp)
    assert res2.allowed is True
    assert res2.remaining == 0


def test_decorator_sync_function_returning_response() -> None:
    """Decorator handles sync route handlers that return a Response object."""
    limiter = AsyncRateLimiter()
    app = FastAPI()

    @app.get("/sync-endpoint")
    @limiter.limit("5/minute")
    def sync_route(request: Request) -> Response:
        return Response(content="sync response", media_type="text/plain")

    client = TestClient(app)
    resp = client.get("/sync-endpoint")
    assert resp.status_code == 200
    assert resp.text == "sync response"
    assert resp.headers["X-RateLimit-Limit"] == "5"
    assert resp.headers["X-RateLimit-Remaining"] == "4"


@pytest.mark.asyncio
async def test_burst_and_variable_cost() -> None:
    """Limiter supports explicit burst limit and cost > 1."""
    limiter = AsyncRateLimiter()
    # rate 10/minute, but burst capacity 20
    res1 = await limiter.check("burst_key", rate="10/minute", burst=20, cost=5.0)
    assert res1.allowed is True
    assert res1.limit == 20
    assert res1.remaining == 15

    # Cost exceeding remaining tokens
    res2 = await limiter.check("burst_key", rate="10/minute", burst=20, cost=16.0)
    assert res2.allowed is False
    assert res2.remaining == 15

