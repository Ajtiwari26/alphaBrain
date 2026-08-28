"""Tests for P5 outbound control-plane contract and encrypted recovery spool."""

import asyncio
import json
import time
from unittest.mock import AsyncMock

import httpx
import pytest
from cryptography.fernet import Fernet

from alpha_protocol import AgentType, TaskEnvelope, TaskResult, TaskStatus
from alpha_worker.control_plane import ControlPlaneClient, DurableEventSpool
from alpha_worker.daemon import AlphaWorkerDaemon


def make_task() -> TaskEnvelope:
    return TaskEnvelope(
        task_id="tsk_control_plane_01",
        project_id="prj_control_plane",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Verify control plane transport",
        allowed_paths=["."],
    )


@pytest.mark.asyncio
async def test_control_plane_leases_heartbeats_and_submits_with_identity_header():
    calls: list[tuple[str, str, dict[str, str], dict[str, object]]] = []
    task = make_task()

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        calls.append((request.method, request.url.path, dict(request.headers), body))
        if request.url.path.endswith("/identity"):
            return httpx.Response(
                200,
                json={"identity_token": "signed-identity", "expires_at": int(time.time()) + 3600},
            )
        if request.url.path == "/api/tasks/lease":
            return httpx.Response(
                200,
                json={
                    "status": "leased",
                    "lease_token": "lease_control",
                    "task": task.model_dump(mode="json"),
                },
            )
        return httpx.Response(200, json={"status": "ok"})

    client = ControlPlaneClient(
        "https://control.example",
        "worker-one",
        "worker-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        lease = await client.lease_next("worker-one")
        assert lease and lease.task.task_id == task.task_id
        await client.heartbeat(task.task_id, lease.lease_token)
        await client.submit_result(
            TaskResult(
                attempt_id="att_control_plane_01",
                task_id=task.task_id,
                status=TaskStatus.RETRYABLE_FAILED,
                agent=AgentType.ANTIGRAVITY,
                model="test",
                base_commit="HEAD",
            ),
            lease.lease_token,
        )
    finally:
        await client.aclose()

    assert [call[1] for call in calls] == [
        "/api/workers/worker-one/identity",
        "/api/tasks/lease",
        f"/api/tasks/{task.task_id}/heartbeat",
        f"/api/tasks/{task.task_id}/result",
    ]
    assert calls[1][2]["x-alpha-worker-identity"] == "signed-identity"
    assert calls[1][3]["worker_id"] == "worker-one"


@pytest.mark.asyncio
async def test_encrypted_spool_replays_in_order_without_plaintext(tmp_path):
    spool = DurableEventSpool(tmp_path / "spool", Fernet.generate_key())
    first = spool.enqueue("health", {"battery_percent": 93})
    second = spool.enqueue("result", {"task_id": "tsk_spool_01"})

    assert b"battery_percent" not in first.read_bytes()
    assert b"tsk_spool_01" not in second.read_bytes()
    delivered: list[tuple[str, dict[str, object]]] = []

    async def deliver(event_type: str, payload: dict[str, object]) -> None:
        delivered.append((event_type, payload))

    assert await spool.replay(deliver) == 2
    assert delivered == [
        ("health", {"battery_percent": 93}),
        ("result", {"task_id": "tsk_spool_01"}),
    ]
    assert spool.pending() == []


@pytest.mark.asyncio
async def test_spool_keeps_event_when_delivery_fails(tmp_path):
    spool = DurableEventSpool(tmp_path / "spool", Fernet.generate_key())
    spool.enqueue("result", {"task_id": "tsk_spool_retry"})

    async def failing_delivery(_event_type: str, _payload: dict[str, object]) -> None:
        raise RuntimeError("offline")

    with pytest.raises(RuntimeError, match="offline"):
        await spool.replay(failing_delivery)
    assert len(spool.pending()) == 1


@pytest.mark.asyncio
async def test_spool_coalesces_health_without_reordering_result(tmp_path):
    spool = DurableEventSpool(tmp_path / "spool", Fernet.generate_key())
    spool.enqueue("health", {"battery_percent": 71}, coalesce=True)
    result_path = spool.enqueue("result", {"task_id": "tsk_spool_order"})
    spool.enqueue("health", {"battery_percent": 72}, coalesce=True)
    delivered: list[tuple[str, dict[str, object]]] = []

    async def deliver(event_type: str, payload: dict[str, object]) -> None:
        delivered.append((event_type, payload))

    assert result_path.exists()
    assert await spool.replay(deliver) == 2
    assert delivered == [
        ("result", {"task_id": "tsk_spool_order"}),
        ("health", {"battery_percent": 72}),
    ]


@pytest.mark.asyncio
async def test_remote_heartbeat_cancels_active_execution(monkeypatch):
    daemon = AlphaWorkerDaemon.__new__(AlphaWorkerDaemon)
    daemon.control_plane = AsyncMock()
    daemon.control_plane.heartbeat.return_value = "cancel_requested"
    monkeypatch.setattr("alpha_worker.daemon.settings.WORKER_HEARTBEAT_SECONDS", 0)
    execution_task = asyncio.create_task(asyncio.sleep(30))
    cancel_requested = asyncio.Event()

    await daemon._remote_heartbeat_loop(
        "tsk_cancel",
        "lease_cancel",
        execution_task,  # type: ignore[arg-type]
        cancel_requested,
    )

    assert cancel_requested.is_set()
    with pytest.raises(asyncio.CancelledError):
        await execution_task
