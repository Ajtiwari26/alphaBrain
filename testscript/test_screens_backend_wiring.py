"""
testscript/test_screens_backend_wiring.py
Integration tests for production backend wiring of screens:
- Dashboard Screen (/api/v1/mobile/dashboard)
- Command Node Screen (/api/v1/mobile/command-node)
- Security Enclave Screen (/api/v1/mobile/security-enclave)
- Meeting Setup Screen (/api/v1/mobile/meet/setup & /api/v1/mobile/meet/token)
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_core.api.app import app
from alpha_core.mobile_bridge.service import MobileBridgeService
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue
from alpha_core.security import AuthPrincipal, PrincipalRole, require_api_principal


@pytest.fixture
def temp_service(tmp_path: Path) -> MobileBridgeService:
    db_file = tmp_path / "triage.db"
    lock_file = tmp_path / "emergency.lock"
    queue = TaskTriageQueue(db_path=db_file, emergency_lock_path=lock_file)

    # Seed an active task
    envelope = {
        "task_id": "tsk_cmd_node_test_01",
        "title": "Production Screen Wiring Validation",
        "objective": "Verify screen endpoints",
        "allowed_paths": ["alpha_core/mobile_bridge/"],
        "criteria": ["Endpoints pass verification"],
    }
    content_hash = hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    now = time.time()
    prov = TaskProvenance(
        meeting_id="mtg_screens_test",
        speaker_id="founder",
        utterance_timestamp=now,
        transcript_excerpt="Connect screens to production backend",
        extraction_model="gemini-3.1-pro",
        extraction_confidence=0.99,
        eva_session_id="eva_session_screen_test",
        created_at=now,
        content_hash=content_hash,
    )
    queue.enqueue_task(
        task_id="tsk_cmd_node_test_01",
        envelope=envelope,
        provenance=prov,
    )
    return MobileBridgeService(db_path=db_file, emergency_lock=lock_file)


@pytest.fixture
def client(temp_service: MobileBridgeService, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    import alpha_core.mobile_bridge.api as api_mod

    monkeypatch.setattr(api_mod, "get_service", lambda: temp_service)

    def override_require_api_principal() -> AuthPrincipal:
        return AuthPrincipal(
            subject="founder",
            role=PrincipalRole.FOUNDER,
        )

    app.dependency_overrides[require_api_principal] = override_require_api_principal
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_api_principal, None)


def test_dashboard_screen_production_api(client: TestClient) -> None:
    """Acceptance Test: Dashboard screen loads real production API data without mock values."""
    resp = client.get("/api/v1/mobile/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    assert data["system_status"] in ("operational", "stopped")
    assert "emergency_stop" in data
    assert "telemetry" in data
    assert data["telemetry"]["host_cpu_percent"] >= 0.0
    assert data["telemetry"]["host_ram_percent"] >= 0.0
    assert data["hardware_sync_serial"] == "10BF5P2AZF0010T"

    # AI Quotas, projects, tech dept, triage, and worktree real metrics
    assert "ai_quotas_summary" in data
    assert "%" in data["ai_quotas_summary"]
    assert data["ai_quotas_percent"] >= 0.0
    assert data["active_projects_count"] >= 0
    assert data["tech_dept_agents_count"] >= 0
    assert data["triage_pending_count"] >= 1  # Seeded 1 task
    assert data["worktrees_count"] >= 0
    assert len(data["worktrees_summary"]) > 0


def test_command_node_screen_production_api(client: TestClient) -> None:
    """Acceptance Test: Command Node screen loads real system telemetry, active tasks, and system logs."""
    resp = client.get("/api/v1/mobile/command-node")
    assert resp.status_code == 200
    data = resp.json()

    assert "node_id" in data
    assert len(data["node_id"]) > 0
    assert "hostname" in data
    assert len(data["hostname"]) > 0
    assert data["cluster_name"] == "alphabrain_dogfood"
    assert data["status"] == "operational"

    # Real Metrics
    metrics = data["metrics"]
    assert metrics["cpu_usage"] >= 0.0
    assert metrics["memory_used_mb"] > 0.0
    assert metrics["memory_total_mb"] > 0.0
    assert metrics["disk_total_gb"] > 0.0
    assert metrics["uptime_seconds"] >= 0.0

    # Tasks and Logs
    assert "active_tasks" in data
    assert isinstance(data["active_tasks"], list)
    assert len(data["active_tasks"]) >= 1
    seeded_task = data["active_tasks"][0]
    assert seeded_task["id"] == "tsk_cmd_node_test_01"
    assert seeded_task["title"] == "Production Screen Wiring Validation"

    assert "logs" in data
    assert isinstance(data["logs"], list)
    assert len(data["logs"]) > 0
    for log_item in data["logs"]:
        assert "id" in log_item
        assert "timestamp" in log_item
        assert "stream" in log_item
        assert "text" in log_item


def test_security_enclave_screen_production_api(client: TestClient) -> None:
    """Acceptance Test: Security Enclave screen loads real fingerprint, key vault, and trusted devices."""
    resp = client.get("/api/v1/mobile/security-enclave")
    assert resp.status_code == 200
    data = resp.json()

    assert "node_key_fingerprint" in data
    assert data["node_key_fingerprint"].startswith("SHA256:")
    assert isinstance(data["is_locked"], bool)

    # API Vault Items
    vault = data["vault_items"]
    assert len(vault) >= 4
    aliases = [v["key_alias"] for v in vault]
    assert "ANTHROPIC_API_KEY" in aliases
    assert "GEMINI_API_KEY" in aliases
    assert "OPENAI_API_KEY" in aliases
    assert "GITHUB_TOKEN" in aliases
    for item in vault:
        assert "••••••••" in item["masked_value"]
        assert item["in_keychain"] is True
        assert isinstance(item["is_configured"], bool)
        # Verify zero entropy leakage: suffix exposed is at most 3 chars
        masked_val = item["masked_value"]
        if not masked_val.endswith("[UNCONFIGURED]"):
            suffix_after_dots = masked_val.split("••••••••")[-1]
            assert len(suffix_after_dots) <= 3, f"Leaked too much secret entropy: {masked_val}"

    # Trusted Devices
    devices = data["devices"]
    assert len(devices) >= 1
    assert any("Android" in d["platform"] or "iOS" in d["platform"] for d in devices)


def test_meeting_setup_screen_production_api(client: TestClient) -> None:
    """Acceptance Test: Meeting Setup screen loads room config, LiveKit URL, and derives identity from principal."""
    # Attempting to pass spoofed participant in query param is ignored in favor of authenticated principal
    resp = client.get("/api/v1/mobile/meet/setup?room=briefing-room-prod&participant=SpoofedAttacker")
    assert resp.status_code == 200
    data = resp.json()

    assert data["room_name"] == "briefing-room-prod"
    # Identity must be bound to authenticated subject ("founder"), not "SpoofedAttacker"
    assert data["participant_identity"] == "founder"
    assert "livekit" in data["livekit_url"] or "ws://" in data["livekit_url"] or "wss://" in data["livekit_url"] or "http" in data["livekit_url"]
    assert len(data["token"]) > 10
    assert data["audio_codec"] == "opus"
    assert data["sample_rate"] == 48000
    assert data["audio_active"] is True
    assert data["status"] == "ready"


def test_meeting_token_endpoint(client: TestClient) -> None:
    """Acceptance Test: Direct /meet/token returns valid room token bound to principal."""
    resp = client.get("/api/v1/mobile/meet/token?room=alphabrain-live-briefing&participant=SpoofedUser")
    assert resp.status_code == 200
    data = resp.json()

    assert data["room_name"] == "alphabrain-live-briefing"
    assert len(data["token"]) > 10
    assert data["expires_in_seconds"] == 3600


def test_meeting_setup_client_role_binding(monkeypatch: pytest.MonkeyPatch, temp_service: MobileBridgeService) -> None:
    """Security Boundary: Non-founder principal receives client-scoped meeting setup."""
    import alpha_core.mobile_bridge.api as api_mod

    monkeypatch.setattr(api_mod, "get_service", lambda: temp_service)

    def override_client_principal() -> AuthPrincipal:
        return AuthPrincipal(
            subject="client_contractor_01",
            role=PrincipalRole.CLIENT,
        )

    app.dependency_overrides[require_api_principal] = override_client_principal
    try:
        c = TestClient(app)
        resp = c.get("/api/v1/mobile/meet/setup?room=client-collab-room")
        assert resp.status_code == 200
        data = resp.json()
        assert data["participant_identity"] == "client_contractor_01"
        assert len(data["token"]) > 10
    finally:
        app.dependency_overrides.pop(require_api_principal, None)


def test_screens_unauthorized_without_principal() -> None:
    """Security Boundary: Screens reject unauthenticated access."""
    unauth_client = TestClient(app)
    for endpoint in [
        "/api/v1/mobile/dashboard",
        "/api/v1/mobile/command-node",
        "/api/v1/mobile/security-enclave",
        "/api/v1/mobile/meet/setup",
        "/api/v1/mobile/meet/token",
    ]:
        resp = unauth_client.get(endpoint)
        assert resp.status_code == 401, f"Endpoint {endpoint} allowed unauthenticated access"
