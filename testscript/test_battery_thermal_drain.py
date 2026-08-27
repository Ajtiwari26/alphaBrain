"""
testscript/test_battery_thermal_drain.py
Tests hardware power and thermal pressure sensing, safe task drain thresholds, and intake pausing.
"""

from unittest.mock import AsyncMock

import pytest

from alpha_core.config import settings
from alpha_protocol.enums import WorkerHealth
from alpha_worker.daemon import AlphaWorkerDaemon
from alpha_worker.health import HardwareHealthChecker


def test_battery_threshold_draining_when_below_twenty_percent_on_battery(monkeypatch):
    monkeypatch.setattr(HardwareHealthChecker, "get_battery_and_power", lambda: (False, 19))
    monkeypatch.setattr(HardwareHealthChecker, "check_thermal_and_load", lambda: "nominal")

    health, metrics = HardwareHealthChecker.evaluate_worker_health()
    assert health == WorkerHealth.DRAINING
    assert metrics["is_ac_power"] is False
    assert metrics["battery_percentage"] == 19


def test_battery_degraded_when_above_twenty_percent_on_battery(monkeypatch):
    monkeypatch.setattr(HardwareHealthChecker, "get_battery_and_power", lambda: (False, 55))
    monkeypatch.setattr(HardwareHealthChecker, "check_thermal_and_load", lambda: "nominal")

    health, metrics = HardwareHealthChecker.evaluate_worker_health()
    assert health == WorkerHealth.DEGRADED
    assert metrics["is_ac_power"] is False
    assert metrics["battery_percentage"] == 55


def test_thermal_heavy_causes_draining_even_on_full_ac_power(monkeypatch):
    monkeypatch.setattr(HardwareHealthChecker, "get_battery_and_power", lambda: (True, 100))
    monkeypatch.setattr(HardwareHealthChecker, "check_thermal_and_load", lambda: "heavy")

    health, metrics = HardwareHealthChecker.evaluate_worker_health()
    assert health == WorkerHealth.DRAINING
    assert metrics["thermal_state"] == "heavy"


def test_thermal_critical_causes_draining_even_on_full_ac_power(monkeypatch):
    monkeypatch.setattr(HardwareHealthChecker, "get_battery_and_power", lambda: (True, 100))
    monkeypatch.setattr(HardwareHealthChecker, "check_thermal_and_load", lambda: "critical")

    health, metrics = HardwareHealthChecker.evaluate_worker_health()
    assert health == WorkerHealth.DRAINING
    assert metrics["thermal_state"] == "critical"


def test_nominal_ac_power_returns_online(monkeypatch):
    monkeypatch.setattr(HardwareHealthChecker, "get_battery_and_power", lambda: (True, 100))
    monkeypatch.setattr(HardwareHealthChecker, "check_thermal_and_load", lambda: "nominal")

    health, metrics = HardwareHealthChecker.evaluate_worker_health()
    assert health == WorkerHealth.ONLINE
    assert metrics["thermal_state"] == "nominal"
    assert metrics["is_ac_power"] is True


@pytest.mark.asyncio
async def test_daemon_remote_cycle_pauses_when_draining(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "WORKER_STATE_DIR", tmp_path / "worker")
    monkeypatch.setattr(settings, "WORKTREE_BASE_DIR", tmp_path / "worktrees")

    daemon = AlphaWorkerDaemon(worker_id="worker-drain-test")
    daemon.control_plane = AsyncMock()
    daemon.spool = AsyncMock()

    # Simulate low battery drain state
    monkeypatch.setattr(HardwareHealthChecker, "get_battery_and_power", lambda: (False, 15))
    monkeypatch.setattr(HardwareHealthChecker, "check_thermal_and_load", lambda: "nominal")

    processed = await daemon.execute_remote_cycle()
    assert processed is False
    # Ensure no lease was attempted when draining
    daemon.control_plane.lease_next.assert_not_called()
