"""
testscript/test_adaptive_manager.py
Unit tests for Adaptive Hardware Concurrency Manager in AlphaBrain.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_worker.adaptive_manager import (
    AdaptiveConcurrencyManager,
    ConcurrencyProfile,
)
from alpha_worker.health import HardwareHealthChecker
from alpha_worker.parallel_dispatcher import ParallelWorkerDispatcher


class MockHealthChecker(HardwareHealthChecker):
    mock_is_ac = True
    mock_battery = 100
    mock_thermal = "nominal"

    @classmethod
    def get_battery_and_power(cls) -> tuple[bool, int]:
        return cls.mock_is_ac, cls.mock_battery

    @classmethod
    def check_thermal_and_load(cls) -> str:
        return cls.mock_thermal


@pytest.fixture
def mock_health():
    MockHealthChecker.mock_is_ac = True
    MockHealthChecker.mock_battery = 100
    MockHealthChecker.mock_thermal = "nominal"
    return MockHealthChecker


@pytest.fixture
def temp_queue():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_triage.db"
        queue = TaskTriageQueue(db_path=db_path)
        yield queue


def test_adaptive_scaling_on_ac_power(mock_health):
    """Verifies concurrency expands with queue depth on AC power."""
    profile = ConcurrencyProfile(
        ac_max_workers=6,
        ac_min_workers=1,
        queue_scale_step=2,
    )
    manager = AdaptiveConcurrencyManager(profile=profile, health_checker=mock_health)

    # Queue depth 0: minimal capacity
    dec_empty = manager.compute_concurrency(queue_depth=0)
    assert dec_empty.target_workers == 1
    assert dec_empty.is_ac_power is True

    # Queue depth 4: scales up (1 + 4 // 2 = 3)
    dec_active = manager.compute_concurrency(queue_depth=4)
    assert dec_active.target_workers == 3

    # Queue depth 20: capped at ac_max_workers (6)
    dec_heavy = manager.compute_concurrency(queue_depth=20)
    assert dec_heavy.target_workers == 6


def test_adaptive_clamping_on_battery_mode(mock_health):
    """Verifies concurrency is bounded on Battery power."""
    mock_health.mock_is_ac = False
    mock_health.mock_battery = 80
    profile = ConcurrencyProfile(
        battery_max_workers=2,
        battery_min_workers=1,
        queue_scale_step=2,
    )
    manager = AdaptiveConcurrencyManager(profile=profile, health_checker=mock_health)

    # Idle queue on battery
    dec_idle = manager.compute_concurrency(queue_depth=0)
    assert dec_idle.target_workers == 1
    assert dec_idle.is_ac_power is False

    # Large queue depth capped at battery_max_workers
    dec_loaded = manager.compute_concurrency(queue_depth=10)
    assert dec_loaded.target_workers == 2


def test_critical_battery_drain_throttling(mock_health):
    """Verifies that low battery (<20%) scales down concurrency to conserve power."""
    mock_health.mock_is_ac = False
    mock_health.mock_battery = 15  # Critical battery (<20%)
    profile = ConcurrencyProfile(critical_battery_threshold=20)
    manager = AdaptiveConcurrencyManager(profile=profile, health_checker=mock_health)

    # Zero pending tasks -> 0 workers
    dec_empty = manager.compute_concurrency(queue_depth=0)
    assert dec_empty.target_workers == 0

    # Pending tasks -> clamped to 1 worker maximum
    dec_active = manager.compute_concurrency(queue_depth=5)
    assert dec_active.target_workers == 1
    assert "critical" in dec_active.reason.lower()


def test_thermal_pressure_throttling(mock_health):
    """Verifies that thermal heat throttles or halts worker dispatches."""
    manager = AdaptiveConcurrencyManager(health_checker=mock_health)

    # Critical thermal pressure halts all dispatches
    mock_health.mock_thermal = "critical"
    dec_crit = manager.compute_concurrency(queue_depth=10)
    assert dec_crit.target_workers == 0
    assert "critical" in dec_crit.reason.lower()

    # Heavy thermal pressure caps concurrency to 1
    mock_health.mock_thermal = "heavy"
    dec_heavy = manager.compute_concurrency(queue_depth=10)
    assert dec_heavy.target_workers == 1

    # Moderate thermal pressure reduces AC allocation by 1 slot
    mock_health.mock_thermal = "moderate"
    dec_mod = manager.compute_concurrency(queue_depth=6)  # Normally 1 + 6//2 = 4, throttled to 3
    assert dec_mod.target_workers == 3


def test_parallel_dispatcher_adaptive_integration(temp_queue, mock_health):
    """Verifies ParallelWorkerDispatcher adjusts available_slots based on power mode."""
    from alpha_core.queue.triage_queue import TaskProvenance, TriageStatus

    # Enqueue approved tasks
    for i in range(4):
        t_id = f"tsk_adaptive_{i}"
        prov = TaskProvenance(
            meeting_id=f"meet_{t_id}",
            speaker_id="speaker_1",
            utterance_timestamp=1000.0,
            transcript_excerpt="test excerpt",
            extraction_model="test-model",
            extraction_confidence=1.0,
            eva_session_id=f"session_{t_id}",
            created_at=1000.0,
            content_hash=f"hash_{t_id}",
        )
        temp_queue.enqueue_task(
            task_id=t_id,
            envelope={"project_id": "alphabrain_dogfood", "title": f"Task {i}"},
            provenance=prov,
            initial_status=TriageStatus.APPROVED,
        )

    # On AC power: dispatcher allows full capacity
    mock_health.mock_is_ac = True
    profile = ConcurrencyProfile(ac_max_workers=4, battery_max_workers=1)
    adaptive_mgr = AdaptiveConcurrencyManager(profile=profile, health_checker=mock_health)

    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=4,
        adaptive_manager=adaptive_mgr,
        enable_adaptive_concurrency=True,
    )

    assert dispatcher.get_effective_max_workers() == 3  # 1 min + 4 // 2 = 3 slots
    assert dispatcher.available_slots() == 3

    # Switch to Battery power: effective max drops to battery limit (1)
    mock_health.mock_is_ac = False
    mock_health.mock_battery = 50
    assert dispatcher.get_effective_max_workers() == 1
    assert dispatcher.available_slots() == 1


def test_dispatch_task_respects_adaptive_limits(temp_queue, mock_health):
    """Verifies that dispatch_task denies dispatches exceeding dynamic battery ceiling."""
    mock_health.mock_is_ac = False
    mock_health.mock_battery = 60
    profile = ConcurrencyProfile(battery_max_workers=1)
    adaptive_mgr = AdaptiveConcurrencyManager(profile=profile, health_checker=mock_health)

    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=4,
        adaptive_manager=adaptive_mgr,
        enable_adaptive_concurrency=True,
        worker_cycle_fn=lambda t: MagicMock(gates_passed=True),
    )

    # Dispatch first task (allowed: active=1, effective_max=1)
    task1 = {"id": "tsk_1", "envelope": {}}
    dispatched1 = dispatcher.dispatch_task(task1)
    assert dispatched1 == "tsk_1"

    # Dispatch second task (rejected: active=1 reaches effective_max=1 on battery)
    task2 = {"id": "tsk_2", "envelope": {}}
    dispatched2 = dispatcher.dispatch_task(task2)
    assert dispatched2 is None
