import time

import httpx
import pytest
from fastapi.testclient import TestClient

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.security import create_worker_identity_token
from alpha_worker.control_plane import (
    ControlPlaneClient,
    ControlPlaneProtocolError,
    ControlPlaneUnavailable,
)

client = TestClient(app)


def test_issuance():
    response = client.post(
        "/api/workers/worker-123/identity",
        headers={"Authorization": f"Bearer {settings.ALPHA_WORKER_TOKEN}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "identity_token" in data
    assert "expires_at" in data

    # Expiration is bounded to approximately 3600 seconds
    now = time.time()
    assert 3500 < data["expires_at"] - now <= 3600

    # Decode token to check subject matches exactly
    import base64
    import json

    parts = data["identity_token"].split(".")
    assert len(parts) == 2
    padded = parts[0] + "=" * (4 - len(parts[0]) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    assert decoded["sub"] == "worker-123"


def test_issuance_missing_token():
    response = client.post("/api/workers/worker-123/identity")
    assert response.status_code == 401


def test_issuance_wrong_token():
    response = client.post(
        "/api/workers/worker-123/identity",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


def test_issuance_unsafe_worker_id():
    response = client.post(
        "/api/workers/worker-123!/identity",
        headers={"Authorization": f"Bearer {settings.ALPHA_WORKER_TOKEN}"},
    )
    assert response.status_code == 422, response.text


def test_expiry_and_tampering():
    expired_token = create_worker_identity_token("worker-123", ttl_seconds=-3600)
    response = client.post(
        "/api/tasks/lease",
        json={"worker_id": "worker-123"},
        headers={"X-Alpha-Worker-Identity": expired_token},
    )
    assert response.status_code == 401

    tampered_token = create_worker_identity_token("worker-123") + "bad"
    response = client.post(
        "/api/tasks/lease",
        json={"worker_id": "worker-123"},
        headers={"X-Alpha-Worker-Identity": tampered_token},
    )
    assert response.status_code == 401


def test_subject_mismatch():
    token = create_worker_identity_token("worker-wrong")
    response = client.post(
        "/api/tasks/lease",
        json={"worker_id": "worker-123"},
        headers={"X-Alpha-Worker-Identity": token},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_refresh_and_outage():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/identity"):
            if len(calls) == 3:
                raise httpx.ConnectError("Network is down")
            return httpx.Response(
                200, json={"identity_token": "new-token", "expires_at": int(time.time()) + 3600}
            )
        if request.url.path == "/api/workers/register":
            if request.headers.get("x-alpha-worker-identity") == "new-token":
                return httpx.Response(200, json={"status": "registered"})
            return httpx.Response(401, json={"detail": "Expired"})
        return httpx.Response(200, json={"status": "ok"})

    cp = ControlPlaneClient(
        "http://test", "worker-123", "token", transport=httpx.MockTransport(handler)
    )

    # First call triggers identity fetch
    await cp._request("POST", "/api/workers/register", {})
    assert "/api/workers/worker-123/identity" in calls

    # Force expiration to trigger refresh
    cp._identity_expires_at = 0

    # Second call triggers refresh, which raises outage error
    with pytest.raises(ControlPlaneUnavailable):
        await cp._request("POST", "/api/workers/register", {})

    await cp.aclose()


@pytest.mark.asyncio
async def test_successful_client_refresh_proof():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/identity"):
            return httpx.Response(
                200,
                json={
                    "identity_token": f"token-{len(calls)}",
                    "expires_at": int(time.time()) + 3600,
                },
            )

        # Operational request
        if request.headers.get("x-alpha-worker-identity") == "token-1":
            # Simulate 401 on first use
            return httpx.Response(401, json={"detail": "Invalid token"})
        if request.headers.get("x-alpha-worker-identity") == "token-3":
            # Succeed on retry
            return httpx.Response(200, json={"status": "ok"})

        return httpx.Response(500, json={"detail": "Unexpected state"})

    cp = ControlPlaneClient(
        "http://test", "worker-123", "token", transport=httpx.MockTransport(handler)
    )

    response = await cp._request("POST", "/api/workers/register", {})
    assert response == {"status": "ok"}

    # Assert exact sequence
    assert calls == [
        "/api/workers/worker-123/identity",  # identity issuance
        "/api/workers/register",  # operational request returns 401
        "/api/workers/worker-123/identity",  # forced identity refresh
        "/api/workers/register",  # operational retry succeeds
    ]

    await cp.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_json",
    [
        ["not", "an", "object"],  # list/non-object JSON
        {"expires_at": int(time.time()) + 3600},  # missing token
        {"identity_token": "", "expires_at": int(time.time()) + 3600},  # empty token
        {"identity_token": "token"},  # missing expiry
        {"identity_token": "token", "expires_at": "3600"},  # string expiry
        {"identity_token": "token", "expires_at": float(int(time.time()) + 3600)},  # float expiry
        {"identity_token": "token", "expires_at": True},  # boolean expiry
        {"identity_token": "token", "expires_at": int(time.time()) - 100},  # expired expiry
        {"identity_token": "token", "expires_at": int(time.time()) + 10},  # too-soon expiry
        {
            "identity_token": "token",
            "expires_at": int(time.time()) + 5000,
        },  # excessively distant expiry
    ],
)
async def test_strict_identity_response_contract(response_json):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_json)

    cp = ControlPlaneClient(
        "http://test", "worker-123", "token", transport=httpx.MockTransport(handler)
    )
    # Set a valid state to verify it gets unset
    cp._identity_token = "valid-token"
    cp._identity_expires_at = int(time.time()) + 3600

    with pytest.raises(ControlPlaneProtocolError):
        await cp._ensure_identity(force_refresh=True)

    # Verify cache is cleared
    assert cp._identity_token is None
    assert cp._identity_expires_at == 0

    await cp.aclose()
