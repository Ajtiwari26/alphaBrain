"""P5 local controls and Keychain-bound daemon behavior."""

import subprocess

import pytest

from alpha_core.config import settings
from alpha_worker.credentials import KeychainError, MacOSKeychain
from alpha_worker.daemon import AlphaWorkerDaemon
from alpha_worker.health import HardwareHealthChecker
from alpha_worker.node_status import write_node_status
from alpha_worker.runtime_control import WorkerControlStore


def test_control_store_persists_pause_then_resume(tmp_path):
    first = WorkerControlStore(tmp_path / "state")
    assert first.read().paused is False
    first.pause("maintenance")
    second = WorkerControlStore(tmp_path / "state")
    assert second.read().paused is True
    assert second.read().reason == "maintenance"
    assert second.resume().paused is False


def test_keychain_rejects_missing_credential(monkeypatch):
    monkeypatch.setattr(
        "alpha_worker.credentials.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 44, stdout="", stderr="missing"),
    )
    with pytest.raises(KeychainError, match="Missing Keychain credential"):
        MacOSKeychain("com.deploymate.test").get("worker-token")


def test_production_daemon_requires_keychain_for_remote_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "WORKER_CONTROL_PLANE_URL", "https://control.example")
    monkeypatch.setattr(settings, "WORKER_USE_KEYCHAIN", False)
    monkeypatch.setattr(settings, "WORKER_STATE_DIR", tmp_path / "state")
    with pytest.raises(RuntimeError, match="WORKER_USE_KEYCHAIN"):
        AlphaWorkerDaemon()


def test_thermal_pressure_drains_even_on_ac_power(monkeypatch):
    monkeypatch.setattr(HardwareHealthChecker, "get_battery_and_power", lambda: (True, 100))
    monkeypatch.setattr(HardwareHealthChecker, "check_thermal_and_load", lambda: "critical")
    health, metrics = HardwareHealthChecker.evaluate_worker_health()
    assert health.value == "draining"
    assert metrics["thermal_state"] == "critical"


def test_escalation_record_is_durable_and_redacted(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "WORKER_STATE_DIR", tmp_path / "worker")
    daemon = AlphaWorkerDaemon(worker_id="worker-test")
    daemon._record_escalation("task-1", "execution_failed", "token=secret-token-value")
    record = (tmp_path / "worker" / "escalations.jsonl").read_text()
    assert "task-1" in record
    assert "secret-token-value" not in record
    assert (tmp_path / "worker" / "escalations.jsonl").stat().st_mode & 0o777 == 0o600


def test_node_keeper_status_projection_excludes_task_payload(tmp_path):
    from alpha_protocol import WorkerHealth, WorkerHealthReport

    report = WorkerHealthReport(
        worker_id="worker-test",
        status=WorkerHealth.ONLINE,
        battery_percent=90,
        ac_power=True,
        thermal_pressure="nominal",
        disk_free_gb=50,
        active_task_count=1,
    )
    path = tmp_path / "worker" / "status.json"
    write_node_status(path, report)
    payload = path.read_text()
    assert "worker_id" in payload and "active_task_count" in payload
    assert "objective" not in payload and "token" not in payload
