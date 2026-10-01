"""
testscript/test_remote_sync_cloud_relay.py
Automated verification for Sol MAB Cloud Relay & Mac Node Synchronization.
Tests ingestion of Mac telemetry, worktrees, and SQLite triage into Cloud Relay cache.
"""

import time
import pytest
from alpha_core.mobile_bridge.service import MobileBridgeService


def test_sync_mac_node_populates_cloud_cache():
    service = MobileBridgeService()
    
    mock_payload = {
        "telemetry": {
            "host_cpu_percent": 18.5,
            "host_ram_percent": 68.2,
            "host_ram_used_gb": 10.9,
            "host_ram_total_gb": 16.0,
            "thermal_pressure": "nominal",
            "battery_level_percent": 95.0,
            "battery_charging": True,
            "usb_device_connected": True,
            "usb_device_serial": "10BF5P2AZF0010T",
            "usb_device_name": "iQOO 12 Flagship (Mac Synced)",
        },
        "worktrees": [
            {"name": "alphaBrain", "branch": "main", "commit": "c418d7b6"},
            {"name": "etta", "branch": "master", "commit": "a1b2c3d4"},
        ],
        "projects": [
            {"name": "alphaBrain", "is_active": True},
            {"name": "DeployMate", "is_active": True},
        ],
        "triage_tasks": [
            {
                "task_id": "TSK_TEST_CLOUD_01",
                "title": "Cloud Relay Verification Task",
                "category": "engineering",
                "status": "pending_review",
                "priority": "high",
                "risk_class": "low",
                "created_at": time.time(),
                "updated_at": time.time(),
                "author": "Eva CTO",
                "allowed_paths": [],
                "acceptance_commands": [],
            }
        ],
        "timestamp": time.time(),
    }

    # 1. Ingest into service
    res = service.sync_mac_node(mock_payload)
    assert res["status"] == "ok"
    assert "synced_at" in res

    # 2. Verify hardware telemetry reflects synced Mac metrics
    telemetry = service.get_hardware_telemetry()
    assert telemetry.host_cpu_percent == 18.5
    assert telemetry.host_ram_percent == 68.2
    assert telemetry.host_ram_total_gb == 16.0
    assert telemetry.battery_level_percent == 95.0
    assert telemetry.battery_charging is True

    # 3. Verify worktrees reflection
    wts = service.get_git_worktrees()
    assert len(wts) >= 2
    assert any(w.get("name") == "alphaBrain" for w in wts)

    # 4. Verify projects reflection
    projs = service.get_projects()
    assert any(p.get("name") == "alphaBrain" for p in projs)

    # 5. Verify dashboard aggregates synced telemetry
    dashboard = service.get_dashboard_data()
    assert dashboard.telemetry.host_cpu_percent == 18.5
    assert dashboard.worktrees_count >= 2
