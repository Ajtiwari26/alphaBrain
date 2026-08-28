"""
testscript/test_outage_and_duplicate_safety.py
Proves network outage buffering via encrypted spool, replay without duplicate execution, and idempotent task completion.
"""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from cryptography.fernet import Fernet

from alpha_core.config import settings
from alpha_protocol import (
    AgentType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    WorkerHealth,
    WorkerHealthReport,
)
from alpha_worker.control_plane import (
    ControlPlaneClient,
    DurableEventSpool,
    LeasedTask,
)
from alpha_worker.daemon import AlphaWorkerDaemon
from alpha_worker.runtime_control import WorkerControlStore


@pytest.fixture
def mock_spool(tmp_path):
    fernet_key = Fernet.generate_key()
    return DurableEventSpool(tmp_path / "spool", fernet_key)


@pytest.mark.asyncio
async def test_outage_buffers_result_then_replays_cleanly(tmp_path, mock_spool, monkeypatch):
    """Proves that a network outage during task execution safely spools the result and replays without loss."""
    monkeypatch.setattr(settings, "WORKER_STATE_DIR", tmp_path / "worker")
    monkeypatch.setattr(settings, "WORKTREE_BASE_DIR", tmp_path / "worktrees")

    submitted_results: list[dict[str, object]] = []

    # Mock control plane that is initially offline
    is_online = False

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal is_online
        if not is_online:
            raise httpx.ConnectError("Network is down")
        if request.url.path.endswith("/identity"):
            return httpx.Response(
                200, json={"identity_token": "test-identity", "expires_at": int(time.time()) + 3600}
            )
        if request.url.path.endswith("/result"):
            import json

            submitted_results.append(json.loads(request.content))
            return httpx.Response(200, json={"status": "result_recorded"})
        if request.url.path.endswith("/health"):
            return httpx.Response(200, json={"status": "recorded"})
        if request.url.path == "/api/workers/register":
            return httpx.Response(200, json={"status": "registered"})
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(mock_handler)
    cp_client = ControlPlaneClient(
        base_url="https://control.example",
        worker_id="mac-worker-test",
        worker_token="test-token",
        transport=transport,
    )

    daemon = AlphaWorkerDaemon(
        worker_id="mac-worker-test",
        control_plane=cp_client,
        spool=mock_spool,
        control_store=WorkerControlStore(tmp_path / "worker"),
    )

    # Mock adapter execution returning completed task
    task = TaskEnvelope(
        task_id="tsk_outage_01",
        project_id="prj_outage",
        repo=str(tmp_path / "repo"),
        objective="Test outage safety",
        base_commit="HEAD",
        allowed_paths=["."],
    )
    lease = LeasedTask(lease_token="lease_outage_tok", task=task)

    mock_result = TaskResult(
        attempt_id="att_outage_01",
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="gemini-3.7-flash-high",
        base_commit="HEAD",
    )

    daemon.worktree_mgr = MagicMock()
    daemon.worktree_mgr.create_or_resume_worktree.return_value = Path(tmp_path / "worktree")
    daemon.worktree_mgr.remove_worktree.return_value = None

    mock_adapter = AsyncMock()
    mock_adapter.execute.return_value = mock_result
    daemon.select_adapter = lambda _agent: mock_adapter  # type: ignore[assignment]

    # 1. Execute remote lease while network is down -> throws ControlPlaneUnavailable and spools result
    processed = await daemon._execute_remote_lease(lease)
    assert processed is True
    assert len(mock_spool.pending()) == 1, "Result must be queued in spool"
    assert len(submitted_results) == 0, "No result could reach offline control plane"

    # Verify escalation was logged
    escalations_file = tmp_path / "worker" / "escalations.jsonl"
    assert escalations_file.exists()
    assert "result_delivery_deferred" in escalations_file.read_text()

    # 2. Bring network online and sync presence
    is_online = True
    health = WorkerHealthReport(
        worker_id="mac-worker-test",
        status=WorkerHealth.ONLINE,
        battery_percent=95,
        ac_power=True,
        thermal_pressure="nominal",
        disk_free_gb=100.0,
        active_task_count=0,
    )

    await daemon._sync_remote_presence(health)

    # 3. Verify spool was completely drained and delivered exactly once
    assert len(mock_spool.pending()) == 0, "Spool must be empty after successful replay"
    assert len(submitted_results) == 1, "Result must be delivered exactly once"
    assert submitted_results[0]["lease_token"] == "lease_outage_tok"
    assert submitted_results[0]["result"]["task_id"] == "tsk_outage_01"  # type: ignore[index]

    await cp_client.aclose()


@pytest.mark.asyncio
async def test_coalesced_health_prevents_duplicate_queue_bloat(mock_spool):
    """Proves that repeated offline health events coalesce to latest without multiplying pending events."""
    mock_spool.enqueue("health", {"battery_percent": 80}, coalesce=True)
    mock_spool.enqueue("health", {"battery_percent": 75}, coalesce=True)
    mock_spool.enqueue("health", {"battery_percent": 70}, coalesce=True)

    pending = mock_spool.pending()
    assert len(pending) == 1, "Health events must coalesce to the latest state"

    latest = mock_spool.read(pending[0])
    assert latest["payload"]["battery_percent"] == 70
