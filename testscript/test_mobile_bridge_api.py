"""
testscript/test_mobile_bridge_api.py
Comprehensive unit tests for AlphaBrain Founder Companion mobile bridge (P14).
Tests all 14 DeployMate Locomotive endpoints, service logic, and emergency stop.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_core.mobile_bridge.api import create_mobile_bridge_app
from alpha_core.mobile_bridge.service import MobileBridgeService


@pytest.fixture
def temp_service(tmp_path: Path) -> MobileBridgeService:
    db_file = tmp_path / "triage.db"
    lock_file = tmp_path / "emergency.lock"
    return MobileBridgeService(db_path=db_file, emergency_lock=lock_file)


@pytest.fixture
def client(temp_service: MobileBridgeService, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = create_mobile_bridge_app()
    import alpha_core.mobile_bridge.api as api_mod

    monkeypatch.setattr(api_mod, "get_service", lambda: temp_service)
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["supported_screens"] == 14
    assert data["target_device"] == "10BF5P2AZF0010T"


def test_screen_01_overview(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["system_status"] in ("operational", "stopped")
    assert "telemetry" in data
    assert data["telemetry"]["usb_device_serial"] == "10BF5P2AZF0010T"
    assert data["triage_backlog_count"] >= 0


def test_screen_02_triage_list_and_filter(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/triage")
    assert resp.status_code == 200
    tasks = resp.json()
    assert isinstance(tasks, list)
    assert len(tasks) > 0

    # Test status filter
    resp_exec = client.get("/api/v1/mobile/triage?status=executing")
    assert resp_exec.status_code == 200
    exec_tasks = resp_exec.json()
    assert all(t["status"] == "executing" for t in exec_tasks)


def test_screen_02_triage_review(client: TestClient) -> None:
    # Test Approve
    resp_app = client.post(
        "/api/v1/mobile/triage/tsk_eva_1d262851bd6a/review",
        json={"action": "approve", "founder_notes": "Ship to device"},
    )
    assert resp_app.status_code == 200
    data_app = resp_app.json()
    assert data_app["success"] is True
    assert data_app["new_status"] == "approved"

    # Test Reject
    resp_rej = client.post(
        "/api/v1/mobile/triage/tsk_eva_1d262851bd6a/review",
        json={"action": "reject", "founder_notes": "Needs repair"},
    )
    assert resp_rej.status_code == 200
    data_rej = resp_rej.json()
    assert data_rej["success"] is True
    assert data_rej["new_status"] == "rejected"


def test_screen_03_task_detail(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/tasks/tsk_eva_1d262851bd6a")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["task_id"] == "tsk_eva_1d262851bd6a"
    assert "gate_results" in detail
    assert "checkpoints" in detail


def test_screen_04_task_diff(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/tasks/tsk_eva_1d262851bd6a/diff")
    assert resp.status_code == 200
    diff = resp.json()
    assert diff["task_id"] == "tsk_eva_1d262851bd6a"
    assert len(diff["files"]) > 0
    assert diff["total_additions"] > 0


def test_screen_05_voice_briefing_and_command(client: TestClient) -> None:
    # Voice briefing
    resp_vb = client.get("/api/v1/mobile/voice/briefing")
    assert resp_vb.status_code == 200
    vb = resp_vb.json()
    assert "Eva (DeployMate CTO)" in vb["speaker"]
    assert len(vb["recommended_actions"]) > 0

    # Spoken command
    resp_cmd = client.post(
        "/api/v1/mobile/voice/command",
        json={"command_text": "Eva, optimize rate limiter and trigger unit tests"},
    )
    assert resp_cmd.status_code == 200
    cmd_res = resp_cmd.json()
    assert cmd_res["acknowledged"] is True
    assert "tsk_eva_" in cmd_res["proposed_task_id"]


def test_screen_06_sprint_overview(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/sprint")
    assert resp.status_code == 200
    sprint = resp.json()
    assert sprint["max_workers"] >= 1
    assert len(sprint["slots"]) > 0


def test_screen_07_pr_promotion(client: TestClient) -> None:
    resp = client.post("/api/v1/mobile/tasks/tsk_eva_1d262851bd6a/promote")
    assert resp.status_code == 200
    promo = resp.json()
    assert promo["merge_status"] == "merged"
    assert promo["fast_forward"] is True
    assert len(promo["commit_sha"]) > 0


def test_screen_08_deployments_and_rollback(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/deployments")
    assert resp.status_code == 200
    deployments = resp.json()
    assert len(deployments) >= 2

    # Rollback
    target_id = deployments[0]["id"]
    resp_rb = client.post(f"/api/v1/mobile/deployments/{target_id}/rollback", json={"reason": "Regression test"})
    assert resp_rb.status_code == 200
    assert resp_rb.json()["status"] == "rolled_back"


def test_screen_09_self_healing_radar(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/self-healing")
    assert resp.status_code == 200
    radar = resp.json()
    assert radar["daemon_running"] is True
    assert len(radar["circuit_breakers"]) > 0


def test_screen_10_hardware_telemetry(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/telemetry")
    assert resp.status_code == 200
    telem = resp.json()
    assert telem["host_cpu_percent"] >= 0.0
    assert telem["usb_device_serial"] == "10BF5P2AZF0010T"
    assert telem["battery_level_percent"] > 0


def test_screen_11_privacy_and_purge(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/privacy")
    assert resp.status_code == 200
    priv = resp.json()
    assert priv["gdpr_status"] == "compliant"
    assert priv["redaction_enabled"] is True

    # Purge
    resp_purge = client.post("/api/v1/mobile/privacy/purge")
    assert resp_purge.status_code == 200
    assert resp_purge.json()["status"] == "success"


def test_screen_12_model_scores(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/models")
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) >= 2
    # Verify OC-EDS tier representation
    assert any("Tier 1" in m["tier"] for m in models)


def test_screen_13_audit_trail(client: TestClient) -> None:
    resp = client.get("/api/v1/mobile/audit?limit=10")
    assert resp.status_code == 200
    trail = resp.json()
    assert len(trail) > 0
    assert "sha256_hash" in trail[0]


def test_screen_14_emergency_stop_toggle(client: TestClient, temp_service: MobileBridgeService) -> None:
    # Verify initial state is not active
    resp_init = client.get("/api/v1/mobile/emergency-stop")
    assert resp_init.status_code == 200
    assert resp_init.json()["active"] is False

    # Enable emergency stop
    resp_enable = client.post(
        "/api/v1/mobile/emergency-stop",
        json={"enable_stop": True, "reason": "Founder drill"},
    )
    assert resp_enable.status_code == 200
    assert resp_enable.json()["active"] is True
    assert temp_service.emergency_lock.exists()

    # Disable emergency stop
    resp_disable = client.post(
        "/api/v1/mobile/emergency-stop",
        json={"enable_stop": False, "reason": "Drill ended"},
    )
    assert resp_disable.status_code == 200
    assert resp_disable.json()["active"] is False
    assert not temp_service.emergency_lock.exists()
