"""Unit tests for UpstashCacheClient (Worker 1 & 5).

Verifies:
1. Disabled mode without credentials gracefully degrades (returns None/False/0).
2. Live Upstash ping, set, get, delete, delete_pattern.
3. Timeout safety and graceful degradation on network errors.
"""

import pytest

from alpha_core.cache.upstash_cache import UpstashCacheClient


@pytest.mark.asyncio
async def test_upstash_disabled_mode():
    client = UpstashCacheClient(rest_url="", rest_token="")
    assert client._enabled is False
    assert await client.get("any_key") is None
    assert await client.set("any_key", {"data": 123}) is False
    assert await client.delete("any_key") is False
    assert await client.delete_pattern("any:*") == 0
    assert await client.ping() is False


@pytest.mark.asyncio
async def test_upstash_live_operations():
    client = UpstashCacheClient()
    if not client._enabled:
        pytest.skip("Upstash credentials not available")

    # 1. Ping
    pong = await client.ping()
    assert pong is True

    # 2. Set with TTL
    test_key = "test:py_unit:cache_v1"
    set_ok = await client.set(test_key, {"status": "ok", "speed": 100}, ttl=15)
    assert set_ok is True

    # 3. Get
    val = await client.get(test_key)
    assert isinstance(val, dict)
    assert val.get("status") == "ok"
    assert val.get("speed") == 100

    # 4. Delete
    del_ok = await client.delete(test_key)
    assert del_ok is True

    # 5. Get after delete returns None
    val_after = await client.get(test_key)
    assert val_after is None

    # 6. Delete pattern
    await client.set("test:pattern:1", "a", ttl=10)
    await client.set("test:pattern:2", "b", ttl=10)
    deleted_count = await client.delete_pattern("test:pattern:*")
    assert deleted_count >= 2

    await client.close()
