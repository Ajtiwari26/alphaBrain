"""
testscript/test_cloud_dispatch.py
Comprehensive unit and integration tests for Cloud-First Provisioning, Node Registry,
Task Dispatch Lease, and Stream Broadcast API (Invariants I-52 through I-60).
Includes tests for SQLite persistence, Founder RBAC, and timing-safe comparisons.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest
from fastapi import WebSocket, WebSocketDisconnect, status
from fastapi.testclient import TestClient

import alpha_core.api.cloud_dispatch as cd_mod
from alpha_core.api.app import app
from alpha_core.api.cloud_dispatch import (
    BroadcastStreamHub,
    DeviceRegistry,
    NodeRegistry,
    ProvisioningSessionStore,
)
from alpha_core.config import settings
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_core.security import (
    AuthPrincipal,
    PrincipalRole,
    create_scoped_principal_token,
    create_scoped_stream_token,
    require_api_principal,
)
from testscript.planning_fixtures import approve_with_plan


@pytest.fixture
def clean_stores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[dict[str, object], None, None]:
    """Provides isolated, clean stores and a fresh TaskTriageQueue for each test."""
    dispatch_db = tmp_path / "cloud_dispatch.db"
    p_store = ProvisioningSessionStore(db_path=dispatch_db)
    d_registry = DeviceRegistry(db_path=dispatch_db)
    n_registry = NodeRegistry(db_path=dispatch_db)
    hub = cd_mod.BroadcastStreamHub()

    db_file = tmp_path / "triage.db"
    lock_file = tmp_path / "emergency.lock"
    queue = TaskTriageQueue(db_path=db_file, emergency_lock_path=lock_file)

    monkeypatch.setattr(cd_mod, "_provisioning_store", p_store)
    monkeypatch.setattr(cd_mod, "_device_registry", d_registry)
    monkeypatch.setattr(cd_mod, "_node_registry", n_registry)
    monkeypatch.setattr(cd_mod, "_stream_hub", hub)
    monkeypatch.setattr(cd_mod, "_default_triage_queue", queue)
    monkeypatch.setattr(cd_mod, "get_triage_queue", lambda: queue)

    yield {
        "db_path": dispatch_db,
        "provisioning_store": p_store,
        "device_registry": d_registry,
        "node_registry": n_registry,
        "stream_hub": hub,
        "queue": queue,
    }


@pytest.fixture
def client(clean_stores: dict[str, object]) -> Generator[TestClient, None, None]:
    """Test client with default founder principal override for authenticated endpoints."""

    def override_require_api_principal() -> AuthPrincipal:
        return AuthPrincipal(
            subject="founder",
            role=PrincipalRole.FOUNDER,
            project_ids=["*"],
        )

    app.dependency_overrides[require_api_principal] = override_require_api_principal
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.pop(require_api_principal, None)


# ---------------------------------------------------------------------------
# Invariant I-52: Ephemeral Provisioning Session TTL & Single-Use
# ---------------------------------------------------------------------------


def test_provision_session_creation(client: TestClient) -> None:
    """POST /api/auth/provision-session generates ephemeral pairing session (Invariant I-52)."""
    resp = client.post(
        "/api/auth/provision-session",
        json={"client_name": "Pixel Companion", "metadata": {"os": "android"}},
    )
    assert resp.status_code == 201
    data = resp.json()

    assert "session_id" in data
    assert data["pairing_code"].startswith("AB-")
    assert "provision_token" in data
    assert data["expires_in_seconds"] == 300
    assert data["status"] == "pending"

    # Verify QR payload is valid JSON and contains required keys
    qr_data = json.loads(data["qr_payload"])
    assert qr_data["session_id"] == data["session_id"]
    assert qr_data["pairing_code"] == data["pairing_code"]
    assert qr_data["provision_token"] == data["provision_token"]


def test_provision_session_requires_founder(clean_stores: dict[str, object]) -> None:
    """POST /api/auth/provision-session rejects unauthenticated or non-founder callers (Finding 1)."""

    def override_client_principal() -> AuthPrincipal:
        return AuthPrincipal(
            subject="untrusted_client",
            role=PrincipalRole.CLIENT,
        )

    app.dependency_overrides[require_api_principal] = override_client_principal
    try:
        with TestClient(app) as tc:
            resp = tc.post("/api/auth/provision-session", json={})
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_api_principal, None)


def test_provision_session_single_use(client: TestClient) -> None:
    """A provisioning session cannot be claimed more than once (Invariant I-52 & I-53)."""
    # 1. Provision
    prov_resp = client.post("/api/auth/provision-session", json={})
    assert prov_resp.status_code == 201
    session_id = prov_resp.json()["session_id"]
    provision_token = prov_resp.json()["provision_token"]

    # 2. First Claim -> Success
    claim_resp_1 = client.post(
        "/api/auth/claim-session",
        json={
            "session_id": session_id,
            "provision_token": provision_token,
            "device_id": "device-1",
            "device_name": "Founder Pixel",
        },
    )
    assert claim_resp_1.status_code == 200
    assert claim_resp_1.json()["status"] == "claimed"

    # 3. Second Claim -> 409 Conflict
    claim_resp_2 = client.post(
        "/api/auth/claim-session",
        json={
            "session_id": session_id,
            "provision_token": provision_token,
            "device_id": "device-2",
            "device_name": "Rogue Device",
        },
    )
    assert claim_resp_2.status_code == 409
    assert "already claimed" in claim_resp_2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_provision_session_expired(
    clean_stores: dict[str, object], client: TestClient
) -> None:
    """Expired provisioning sessions are rejected with 400 Bad Request (Invariant I-52)."""
    store = clean_stores["provisioning_store"]
    assert isinstance(store, ProvisioningSessionStore)

    # Create session with -10 second TTL (expired immediately)
    session = await store.create_session(created_by="founder", ttl_seconds=-10)

    claim_resp = client.post(
        "/api/auth/claim-session",
        json={
            "session_id": session.session_id,
            "provision_token": session.provision_token,
            "device_id": "device-expired",
        },
    )
    assert claim_resp.status_code == 400
    assert "expired" in claim_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Invariant I-53: Atomic Session Claim & Founder Binding
# ---------------------------------------------------------------------------


def test_claim_session_by_pairing_code(client: TestClient) -> None:
    """Claiming via pairing code and provision_token binds device and issues token (Invariant I-53)."""
    prov_resp = client.post("/api/auth/provision-session", json={})
    pairing_code = prov_resp.json()["pairing_code"]
    provision_token = prov_resp.json()["provision_token"]

    claim_resp = client.post(
        "/api/auth/claim-session",
        json={
            "pairing_code": pairing_code,
            "provision_token": provision_token,
            "device_id": "10BF5P2AZF0010T",
            "device_name": "Founder Android Device",
            "device_type": "mobile_android",
        },
    )
    assert claim_resp.status_code == 200
    data = claim_resp.json()
    assert data["status"] == "claimed"
    assert data["token_type"] == "Bearer"
    assert "session_token" in data
    assert data["device"]["device_id"] == "10BF5P2AZF0010T"
    assert data["device"]["name"] == "Founder Android Device"
    assert data["device"]["status"] == "active"


def test_claim_session_by_provision_token(client: TestClient) -> None:
    """Claiming via provision_token succeeds (Invariant I-53)."""
    prov_resp = client.post("/api/auth/provision-session", json={})
    provision_token = prov_resp.json()["provision_token"]

    claim_resp = client.post(
        "/api/auth/claim-session",
        json={
            "provision_token": provision_token,
            "device_id": "device-tablet",
            "device_name": "Founder Companion Tablet",
        },
    )
    assert claim_resp.status_code == 200
    assert claim_resp.json()["status"] == "claimed"


def test_claim_session_invalid_token(client: TestClient) -> None:
    """Claiming with mismatched provision token returns 401 Unauthorized (Finding 3)."""
    prov_resp = client.post("/api/auth/provision-session", json={})
    session_id = prov_resp.json()["session_id"]

    claim_resp = client.post(
        "/api/auth/claim-session",
        json={
            "session_id": session_id,
            "provision_token": "wrong-secret-token",
            "device_id": "device-attacker",
        },
    )
    assert claim_resp.status_code == 401
    assert "invalid provision token" in claim_resp.json()["detail"].lower()


def test_claim_session_missing_identifier(client: TestClient) -> None:
    """Attempting claim without required provision_token returns 422 Unprocessable Entity."""
    resp = client.post(
        "/api/auth/claim-session",
        json={"device_id": "device-orphan"},
    )
    assert resp.status_code == 422


def test_claim_session_nonexistent(client: TestClient) -> None:
    """Attempting claim on non-existent session returns 404 Not Found."""
    resp = client.post(
        "/api/auth/claim-session",
        json={
            "session_id": "non-existent-uuid",
            "provision_token": "some-token",
            "device_id": "dev-1",
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Invariant I-54: Device Registry & SQLite Persistence
# ---------------------------------------------------------------------------


def test_devices_listing_and_revocation(client: TestClient) -> None:
    """GET /api/auth/devices and DELETE /api/auth/devices/{id} (Invariant I-54)."""
    # 1. Claim two devices
    p1 = client.post("/api/auth/provision-session", json={}).json()
    client.post(
        "/api/auth/claim-session",
        json={
            "session_id": p1["session_id"],
            "provision_token": p1["provision_token"],
            "device_id": "dev-alpha",
            "device_name": "Device Alpha",
        },
    )

    p2 = client.post("/api/auth/provision-session", json={}).json()
    client.post(
        "/api/auth/claim-session",
        json={
            "session_id": p2["session_id"],
            "provision_token": p2["provision_token"],
            "device_id": "dev-beta",
            "device_name": "Device Beta",
        },
    )

    # 2. List devices
    list_resp = client.get("/api/auth/devices")
    assert list_resp.status_code == 200
    devices = list_resp.json()
    assert len(devices) == 2
    dev_ids = {d["device_id"] for d in devices}
    assert "dev-alpha" in dev_ids
    assert "dev-beta" in dev_ids

    # 3. Revoke dev-alpha via DELETE
    del_resp = client.delete("/api/auth/devices/dev-alpha")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"status": "revoked", "device_id": "dev-alpha"}

    # 4. Verify dev-alpha status is revoked
    list_resp_2 = client.get("/api/auth/devices?status_filter=active")
    active_devices = list_resp_2.json()
    assert len(active_devices) == 1
    assert active_devices[0]["device_id"] == "dev-beta"

    # 5. Revoke dev-beta via POST /api/auth/devices/revoke
    post_del_resp = client.post("/api/auth/devices/revoke", json={"device_id": "dev-beta"})
    assert post_del_resp.status_code == 200
    assert post_del_resp.json() == {"status": "revoked", "device_id": "dev-beta"}

    # 6. Revoke non-existent device returns 404
    non_existent_resp = client.delete("/api/auth/devices/unknown-device")
    assert non_existent_resp.status_code == 404


@pytest.mark.asyncio
async def test_device_registry_sqlite_persistence(clean_stores: dict[str, object]) -> None:
    """Device registry persists records across registry instances via SQLite (Finding 2)."""
    db_path = clean_stores["db_path"]
    assert isinstance(db_path, Path)

    # Instance 1 registers device
    reg_1 = DeviceRegistry(db_path=db_path)
    await reg_1.register_device(
        device_id="persistent-device-1",
        name="Mac Runner Node",
        device_type="node",
        metadata={"os": "darwin"},
    )

    # Instance 2 (simulating restart) reads from same SQLite database
    reg_2 = DeviceRegistry(db_path=db_path)
    device = await reg_2.get_device("persistent-device-1")
    assert device is not None
    assert device.device_id == "persistent-device-1"
    assert device.name == "Mac Runner Node"
    assert device.status == "active"
    assert device.metadata == {"os": "darwin"}


def test_devices_rbac_requires_founder(clean_stores: dict[str, object]) -> None:
    """Non-founder or unauthenticated calls to /api/auth/devices are rejected (Invariant I-54)."""

    def override_client_principal() -> AuthPrincipal:
        return AuthPrincipal(
            subject="guest_client",
            role=PrincipalRole.CLIENT,
        )

    app.dependency_overrides[require_api_principal] = override_client_principal
    try:
        with TestClient(app) as tc:
            resp = tc.get("/api/auth/devices")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_api_principal, None)


# ---------------------------------------------------------------------------
# Invariants I-55 & I-56: Node Registry WSS & Disconnection
# ---------------------------------------------------------------------------


def test_node_register_wss_authentication_failure(client: TestClient) -> None:
    """Connecting to /api/nodes/register without valid token is closed with 1008 (Invariant I-55)."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/nodes/register?token=invalid-token") as ws:
            ws.receive_text()
    assert exc_info.value.code == 1008


def test_node_register_wss_lifecycle(clean_stores: dict[str, object], client: TestClient) -> None:
    """Full node register WSS lifecycle: connect, register, heartbeat, disconnect (Invariants I-55 & I-56)."""
    node_registry = clean_stores["node_registry"]
    assert isinstance(node_registry, NodeRegistry)

    # Generate a valid scoped principal token for worker node
    token = create_scoped_principal_token(
        subject="node-mac-runner",
        role=PrincipalRole.WORKER,
        project_ids=["*"],
        ttl_seconds=3600,
    )

    with client.websocket_connect(f"/api/nodes/register?token={token}") as ws:
        # 1. Send initial registration handshake
        ws.send_text(
            json.dumps(
                {
                    "type": "register",
                    "node_id": "node-mac-runner",
                    "hostname": "macbook-pro.local",
                    "capabilities": ["python3.12", "git", "gradle"],
                    "labels": {"arch": "arm64"},
                }
            )
        )

        # 2. Receive confirmation
        reg_ack = json.loads(ws.receive_text())
        assert reg_ack["type"] == "registered"
        assert reg_ack["node_id"] == "node-mac-runner"
        assert reg_ack["heartbeat_interval_seconds"] == 5

        # 3. Send heartbeat
        ws.send_text(json.dumps({"type": "heartbeat", "load": 0.35, "active_tasks": []}))
        hb_ack = json.loads(ws.receive_text())
        assert hb_ack["type"] == "heartbeat_ack"
        assert hb_ack["node_id"] == "node-mac-runner"

        # 4. Send ping
        ws.send_text(json.dumps({"type": "ping"}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == "pong"

    # Invariant I-56: After WebSocket disconnection, node status is marked offline
    node = None
    for _ in range(20):
        node = asyncio.run(node_registry.get_node("node-mac-runner"))
        if node and node.status == "offline":
            break
        time.sleep(0.05)
    assert node is not None
    assert node.status == "offline"


# ---------------------------------------------------------------------------
# Invariant I-57: Atomic Task Dispatch Lease via Registry
# ---------------------------------------------------------------------------


def test_dispatch_lease_unauthenticated(clean_stores: dict[str, object]) -> None:
    """Lease request without authentication returns 401 Unauthorized (Directive 1 & 4)."""
    orig = app.dependency_overrides.pop(require_api_principal, None)
    try:
        with TestClient(app) as tc:
            resp = tc.post("/api/dispatch/lease", json={"node_id": "test-node"})
            assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
    finally:
        if orig:
            app.dependency_overrides[require_api_principal] = orig


def test_dispatch_lease_client_role_forbidden(clean_stores: dict[str, object]) -> None:
    """Client role cannot lease tasks (requires founder, admin, or worker)."""
    orig = app.dependency_overrides.get(require_api_principal)
    app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
        subject="client-user",
        role=PrincipalRole.CLIENT,
    )
    try:
        with TestClient(app) as tc:
            resp = tc.post("/api/dispatch/lease", json={"node_id": "test-node"})
            assert resp.status_code == status.HTTP_403_FORBIDDEN
            assert "Principal lacks required role" in resp.json()["detail"]
    finally:
        if orig:
            app.dependency_overrides[require_api_principal] = orig
        else:
            app.dependency_overrides.pop(require_api_principal, None)


@pytest.mark.asyncio
async def test_dispatch_lease_worker_identity_mismatch(
    clean_stores: dict[str, object],
) -> None:
    """Worker role attempting to lease for a different node_id is rejected with 403 Forbidden."""
    node_registry = clean_stores["node_registry"]
    assert isinstance(node_registry, NodeRegistry)
    await node_registry.register_node(
        node_id="node-other", hostname="host-other", capabilities=["python3.12"]
    )

    orig = app.dependency_overrides.get(require_api_principal)
    app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
        subject="node-worker-A",
        role=PrincipalRole.WORKER,
    )
    try:
        with TestClient(app) as tc:
            resp = tc.post("/api/dispatch/lease", json={"node_id": "node-other"})
            assert resp.status_code == status.HTTP_403_FORBIDDEN
            assert "does not match target node_id" in resp.json()["detail"]
    finally:
        if orig:
            app.dependency_overrides[require_api_principal] = orig
        else:
            app.dependency_overrides.pop(require_api_principal, None)


@pytest.mark.asyncio
async def test_dispatch_lease_worker_identity_matching(
    clean_stores: dict[str, object],
) -> None:
    """Worker role leasing for its own matching node_id succeeds."""
    node_registry = clean_stores["node_registry"]
    assert isinstance(node_registry, NodeRegistry)
    await node_registry.register_node(
        node_id="node-worker-A", hostname="host-worker-a", capabilities=["python3.12"]
    )

    orig = app.dependency_overrides.get(require_api_principal)
    app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
        subject="node-worker-A",
        role=PrincipalRole.WORKER,
    )
    try:
        with TestClient(app) as tc:
            resp = tc.post("/api/dispatch/lease", json={"node_id": "node-worker-A"})
            assert resp.status_code == status.HTTP_200_OK
            assert resp.json()["status"] == "no_tasks"
    finally:
        if orig:
            app.dependency_overrides[require_api_principal] = orig
        else:
            app.dependency_overrides.pop(require_api_principal, None)


@pytest.mark.asyncio
async def test_dispatch_lease_unregistered_node(client: TestClient) -> None:
    """Lease request from unregistered node fails with 403 Forbidden (Invariant I-57)."""
    resp = client.post(
        "/api/dispatch/lease",
        json={"node_id": "unregistered-node"},
    )
    assert resp.status_code == 403
    assert "not registered or is offline" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_dispatch_lease_no_tasks(
    clean_stores: dict[str, object], client: TestClient
) -> None:
    """Lease request when queue has no approved tasks returns status 'no_tasks'."""
    node_registry = clean_stores["node_registry"]
    assert isinstance(node_registry, NodeRegistry)

    # Register node
    await node_registry.register_node(
        node_id="active-runner-1",
        hostname="runner1",
        capabilities=["python3.12"],
    )

    resp = client.post(
        "/api/dispatch/lease",
        json={"node_id": "active-runner-1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no_tasks"
    assert data["task"] is None
    assert data["node_id"] == "active-runner-1"


@pytest.mark.asyncio
async def test_dispatch_lease_approved_task(
    clean_stores: dict[str, object], client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lease request successfully acquires approved task from triage queue (Invariant I-57)."""
    node_registry = clean_stores["node_registry"]
    queue = clean_stores["queue"]
    assert isinstance(node_registry, NodeRegistry)
    assert isinstance(queue, TaskTriageQueue)

    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv(
        "ALPHA_SIGNING_SECRET",
        settings.ALPHA_SIGNING_SECRET or "0123456789abcdef0123456789abcdef",
    )

    # 1. Register active node
    await node_registry.register_node(
        node_id="runner-compute-1",
        hostname="compute-node",
        capabilities=["python3.12"],
    )

    # 2. Enqueue and approve a task in the triage queue
    task_id = "tsk_test_lease_001"
    envelope = {
        "task_id": task_id,
        "project_id": "prj_test",
        "objective": "Test cloud lease allocation",
        "allowed_paths": ["alpha_core/api/cloud_dispatch.py"],
        "base_commit": "0" * 40,
        "risk_class": "low",
        "created_at": "2026-09-13T12:00:00Z",
        "acceptance_plan": {"gate_commands": {"unit_test": "pytest"}},
    }
    prov = TaskProvenance(
        meeting_id="meet_001",
        speaker_id="founder",
        utterance_timestamp=1700000000.0,
        transcript_excerpt="lease task test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="session_001",
        created_at=1700000000.0,
        content_hash="hash-tsk_test_lease_001",
    )
    queue.enqueue_task(
        task_id=task_id,
        envelope=envelope,
        provenance=prov,
        initial_status=TriageStatus.PENDING_REVIEW,
    )
    approve_with_plan(queue, task_id)

    # 3. Node requests lease
    resp = client.post(
        "/api/dispatch/lease",
        json={"node_id": "runner-compute-1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "leased"
    assert data["task_id"] == task_id
    assert data["node_id"] == "runner-compute-1"
    assert data["lease_token"] is not None

    # Verify node status updated to busy
    node = await node_registry.get_node("runner-compute-1")
    assert node is not None
    assert node.status == "busy"
    assert task_id in node.active_tasks


# ---------------------------------------------------------------------------
# Invariant I-60: Emergency Stop & Kill Switch Propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_lease_emergency_stop_refusal(
    clean_stores: dict[str, object], client: TestClient
) -> None:
    """Task lease is refused with 503 during active Emergency Stop (Invariant I-60)."""
    node_registry = clean_stores["node_registry"]
    queue = clean_stores["queue"]
    assert isinstance(node_registry, NodeRegistry)
    assert isinstance(queue, TaskTriageQueue)

    await node_registry.register_node(
        node_id="runner-emergency",
        hostname="compute-node",
        capabilities=["python3.12"],
    )

    # Activate emergency stop
    queue.emergency_stop(reason="Operator test emergency stop")
    assert queue.is_emergency_stopped() is True

    # Attempt lease -> must return 503
    resp = client.post(
        "/api/dispatch/lease",
        json={"node_id": "runner-emergency"},
    )
    assert resp.status_code == 503
    assert "Emergency stop is active" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Invariants I-58 & I-59: Broadcast Stream Hub WSS
# ---------------------------------------------------------------------------


def test_stream_hub_authentication_failure(client: TestClient) -> None:
    """Stream Hub rejects connection without valid token with WS 1008 (Invariant I-58)."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/stream/broadcast/tsk_test_999?token=invalid") as ws:
            ws.receive_text()
    assert exc_info.value.code == 1008


def test_stream_hub_fanout_and_envelope_integrity(client: TestClient) -> None:
    """
    Broadcaster sends execution logs/thoughts; Subscriber receives structured envelopes
    with monotonic sequence numbers (Invariants I-58 & I-59).
    """
    task_id = "tsk_stream_broadcast_001"
    token = create_scoped_stream_token(f"stream:{task_id}", ttl_seconds=3600)

    # 1. Connect Subscriber
    with client.websocket_connect(
        f"/api/stream/broadcast/{task_id}?token={token}&role=subscriber"
    ) as sub_ws:
        sub_ack = json.loads(sub_ws.receive_text())
        assert sub_ack["type"] == "connected"
        assert sub_ack["task_id"] == task_id
        assert sub_ack["role"] == "subscriber"

        # 2. Connect Broadcaster
        with client.websocket_connect(
            f"/api/stream/broadcast/{task_id}?token={token}&role=broadcaster"
        ) as broad_ws:
            broad_ack = json.loads(broad_ws.receive_text())
            assert broad_ack["type"] == "connected"
            assert broad_ack["role"] == "broadcaster"

            # 3. Broadcaster publishes agent thought
            thought_payload = {
                "thought": "Analyzing ast.parse results for Invariant I-52",
                "phase": "execution",
            }
            broad_ws.send_text(
                json.dumps(
                    {
                        "type": "agent_thought",
                        "payload": thought_payload,
                    }
                )
            )

            # 4. Subscriber receives broadcast envelope (Invariant I-59)
            received_envelope = json.loads(sub_ws.receive_text())
            assert received_envelope["task_id"] == task_id
            assert received_envelope["seq"] == 1
            assert received_envelope["type"] == "agent_thought"
            assert received_envelope["sender"] == "broadcaster"
            assert received_envelope["payload"] == thought_payload
            assert "timestamp" in received_envelope

            # 5. Broadcaster publishes system log
            sys_payload = {"log": "[SYS] Gate execution passed (0)", "status": "ok"}
            broad_ws.send_text(
                json.dumps(
                    {
                        "type": "sys_log",
                        "payload": sys_payload,
                    }
                )
            )

            # 6. Subscriber receives second message with seq=2
            received_sys = json.loads(sub_ws.receive_text())
            assert received_sys["task_id"] == task_id
            assert received_sys["seq"] == 2
            assert received_sys["type"] == "sys_log"
            assert received_sys["payload"] == sys_payload


def test_stream_hub_emergency_stop_announcement(
    clean_stores: dict[str, object], client: TestClient
) -> None:
    """When emergency stop is active, stream hub immediately notifies connectee (Invariant I-60)."""
    queue = clean_stores["queue"]
    assert isinstance(queue, TaskTriageQueue)
    queue.emergency_stop(reason="Aborting runaway task")

    task_id = "tsk_emergency_stream_001"
    token = create_scoped_stream_token(f"stream:{task_id}", ttl_seconds=3600)

    with client.websocket_connect(
        f"/api/stream/broadcast/{task_id}?token={token}&role=subscriber"
    ) as ws:
        # Invariant I-60: Emergency stop frame received
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "EMERGENCY_STOP"
        assert frame["task_id"] == task_id


@pytest.mark.asyncio
async def test_broadcast_stream_hub_emergency_stop_notifies_both() -> None:
    """BroadcastStreamHub sends emergency stop frame to both broadcasters and subscribers (Directive 2)."""
    hub = BroadcastStreamHub()
    task_id = "tsk_unit_stop_001"

    class MockWebSocket:
        def __init__(self) -> None:
            self.sent_messages: list[str] = []

        async def send_text(self, text: str) -> None:
            self.sent_messages.append(text)

    sub_ws = MockWebSocket()
    broad_ws = MockWebSocket()

    await hub.register_subscriber(task_id, cast(WebSocket, sub_ws))
    await hub.register_broadcaster(task_id, cast(WebSocket, broad_ws))

    await hub.broadcast_emergency_stop(task_id, reason="Unit test stop")

    assert len(sub_ws.sent_messages) == 1
    sub_msg = json.loads(sub_ws.sent_messages[0])
    assert sub_msg["type"] == "EMERGENCY_STOP"
    assert sub_msg["payload"]["reason"] == "Unit test stop"

    assert len(broad_ws.sent_messages) == 1
    broad_msg = json.loads(broad_ws.sent_messages[0])
    assert broad_msg["type"] == "EMERGENCY_STOP"
    assert broad_msg["payload"]["reason"] == "Unit test stop"


def test_stream_hub_dynamic_emergency_stop(
    clean_stores: dict[str, object], client: TestClient
) -> None:
    """Active stream dynamically detects emergency stop and halts broadcaster (Directive 2)."""
    queue = clean_stores["queue"]
    assert isinstance(queue, TaskTriageQueue)

    task_id = "tsk_dyn_stop_001"
    token = create_scoped_stream_token(f"stream:{task_id}", ttl_seconds=3600)

    with client.websocket_connect(
        f"/api/stream/broadcast/{task_id}?token={token}&role=broadcaster"
    ) as broad_ws:
        ack = json.loads(broad_ws.receive_text())
        assert ack["type"] == "connected"

        # Trigger emergency stop while broadcaster is active
        queue.emergency_stop(reason="Mid-stream operator kill")

        # Broadcaster sends a message; receiver loop checks queue and responds with EMERGENCY_STOP
        broad_ws.send_text(json.dumps({"type": "progress", "payload": {}}))
        stop_frame = json.loads(broad_ws.receive_text())
        assert stop_frame["type"] == "EMERGENCY_STOP"
        assert "Emergency stop is active" in stop_frame["payload"]["reason"]


def test_node_register_handshake_timeout(
    clean_stores: dict[str, object],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nodes that stall during initial registration handshake are disconnected (Directive 3)."""
    monkeypatch.setattr(cd_mod, "DEFAULT_HANDSHAKE_TIMEOUT_SECONDS", 0.05)
    token = create_scoped_stream_token("worker-token", ttl_seconds=3600)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/nodes/register?token={token}") as ws:
            # Client connects but does not send initial registration frame
            err_frame = json.loads(ws.receive_text())
            assert err_frame["type"] == "error"
            assert "Registration handshake timed out" in err_frame["error"]
            # After sending error frame, server closes with WS_1008_POLICY_VIOLATION
            ws.receive_text()
    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION
