import time

import httpx
import pytest
from fastapi.testclient import TestClient

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.security import create_worker_identity_token
from alpha_worker.control_plane import (
    ControlPlaneClient,
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
                200, json={"identity_token": "new-token", "expires_at": time.time() + 3600}
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
