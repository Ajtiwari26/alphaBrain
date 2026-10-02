"""AlphaBrain Hermetic Upstash REST Cache Client.

Implements INV-M02: REST-based edge cache, sub-15ms cached GETs, graceful degradation.
Uses standard HTTP/REST requests against Upstash without native binary driver dependencies.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("alphabrain.cache.upstash")

DEFAULT_UPSTASH_URL = "https://concise-amoeba-225602.upstash.io"
DEFAULT_UPSTASH_TOKEN = (
    "gQAAAAAAA3FCAAIgcDEzZmU1MWY5N2U3MDQ0NWY2YWFhNGE1ZmZkMjBkZWFhNQ"
)


class UpstashCacheClient:
    """Async Upstash Redis client using REST API with graceful degradation."""

    def __init__(
        self,
        rest_url: str | None = None,
        rest_token: str | None = None,
        default_ttl: int = 30,
        timeout: float = 2.0,
    ) -> None:
        raw_url = (
            rest_url
            if rest_url is not None
            else (os.environ.get("UPSTASH_REDIS_REST_URL") or DEFAULT_UPSTASH_URL)
        )
        self._url = raw_url.rstrip("/") if raw_url else ""
        self._token = (
            rest_token
            if rest_token is not None
            else (
                os.environ.get("UPSTASH_REDIS_REST_TOKEN")
                or DEFAULT_UPSTASH_TOKEN
            )
        )
        self._default_ttl = default_ttl
        self._timeout = timeout
        self._enabled = bool(self._url and self._token)
        self._client: httpx.AsyncClient | None = None

        if not self._enabled:
            logger.warning(
                "Upstash Redis credentials not configured — cache disabled"
            )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._url,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=self._timeout,
            )
        return self._client

    async def get(self, key: str) -> Any | None:
        """GET cached value. Returns None on miss or error (graceful degradation)."""
        if not self._enabled:
            return None
        try:
            client = await self._get_client()
            resp = await client.get(f"/get/{key}")
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("result")
                if result is not None:
                    if isinstance(result, str):
                        try:
                            return json.loads(result)
                        except Exception:
                            return result
                    return result
            return None
        except Exception as exc:
            logger.debug(
                "Upstash GET %s failed (graceful degradation): %s", key, exc
            )
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """SET cached value with TTL. Returns False on error (graceful degradation)."""
        if not self._enabled:
            return False
        try:
            client = await self._get_client()
            ex = ttl or self._default_ttl
            serialized = (
                json.dumps(value) if not isinstance(value, str) else value
            )
            # Use POST pipeline command for robust escaping
            payload = [["set", key, serialized, "ex", str(ex)]]
            resp = await client.post("/pipeline", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return bool(data and data[0].get("result") == "OK")
            return False
        except Exception as exc:
            logger.debug(
                "Upstash SET %s failed (graceful degradation): %s", key, exc
            )
            return False

    async def delete(self, *keys: str) -> bool:
        """DELETE one or more keys. Returns False on error (graceful degradation)."""
        if not self._enabled or not keys:
            return False
        try:
            client = await self._get_client()
            payload = [["del", *keys]]
            resp = await client.post("/pipeline", json=payload)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug(
                "Upstash DEL %s failed (graceful degradation): %s", keys, exc
            )
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching glob pattern. Returns count of deleted keys."""
        if not self._enabled:
            return 0
        try:
            client = await self._get_client()
            resp = await client.post(
                "/pipeline",
                json=[["keys", pattern]],
            )
            if resp.status_code != 200:
                return 0
            results = resp.json()
            matching_keys = results[0].get("result", []) if results else []
            if not matching_keys:
                return 0
            del_resp = await client.post(
                "/pipeline",
                json=[["del", *matching_keys]],
            )
            return len(matching_keys) if del_resp.status_code == 200 else 0
        except Exception as exc:
            logger.debug("Upstash pattern delete %s failed: %s", pattern, exc)
            return 0

    async def ping(self) -> bool:
        """Ping the Upstash Redis instance to verify network connectivity."""
        if not self._enabled:
            return False
        try:
            client = await self._get_client()
            resp = await client.get("/ping")
            return resp.status_code == 200 and resp.json().get("result") == "PONG"
        except Exception as exc:
            logger.debug("Upstash PING failed: %s", exc)
            return False

    async def close(self) -> None:
        """Close the HTTP client connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
