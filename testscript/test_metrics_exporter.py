"""
testscript/test_metrics_exporter.py
Unit tests verifying the AlphaBrain Operational Monitoring & Live Metrics Telemetry Exporter.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from alpha_core.monitoring.metrics_exporter import (
    AccountQuotaState,
    MetricsExporter,
)
from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus


def test_gate_runtime_stats_computation():
    """Verifies gate runtime tracking, pass rates, min/max/average durations."""
    exporter = MetricsExporter()

    # Record 3 runs for unit_test (2 passed, 1 failed)
    exporter.record_gate_runtime("unit_test", duration_seconds=10.0, passed=True)
    exporter.record_gate_runtime("unit_test", duration_seconds=20.0, passed=True)
    exporter.record_gate_runtime("unit_test", duration_seconds=15.0, passed=False)

    # Record 1 run for lint (passed)
    exporter.record_gate_runtime("lint", duration_seconds=5.0, passed=True)

    metrics = exporter.collect_gate_metrics()
    summary = metrics["summary"]
    assert summary["total_gate_runs"] == 4
    assert summary["total_passed"] == 3
    assert summary["total_failed"] == 1
    assert summary["overall_pass_rate"] == 0.75

    by_gate = metrics["by_gate"]
    assert "unit_test" in by_gate
    ut = by_gate["unit_test"]
    assert ut["total_runs"] == 3
    assert ut["passed_runs"] == 2
    assert ut["failed_runs"] == 1
    assert ut["pass_rate"] == round(2 / 3, 4)
    assert ut["total_duration_seconds"] == 45.0
    assert ut["average_duration_seconds"] == 15.0
    assert ut["min_duration_seconds"] == 10.0
    assert ut["max_duration_seconds"] == 20.0
    assert ut["last_duration_seconds"] == 15.0

    lint = by_gate["lint"]
    assert lint["total_runs"] == 1
    assert lint["passed_runs"] == 1
    assert lint["failed_runs"] == 0
    assert lint["pass_rate"] == 1.0
    assert lint["average_duration_seconds"] == 5.0


def test_account_quota_utility_scores():
    """Verifies OC-EDS Tiered Utility Score calculation across all priority tiers."""
    # Tier 1: Idle First (W_i >= 99.0, timer unstarted T_w >= 6.9)
    tier1 = AccountQuotaState(
        account_id="idle@example.com",
        model="claude-opus-4-6-thinking",
        weekly_quota_percent=100.0,
        weekly_reset_days=7.0,
        five_hour_quota_percent=95.0,
        five_hour_reset_hours=5.0,
    )
    score1 = tier1.calculate_utility_score()
    assert score1 == 1000.0 + 95.0

    # Tier 2: Expiring soon (0 < T_w <= 2.0)
    tier2 = AccountQuotaState(
        account_id="expiring@example.com",
        model="claude-opus-4-6-thinking",
        weekly_quota_percent=50.0,
        weekly_reset_days=1.0,
        five_hour_quota_percent=80.0,
        five_hour_reset_hours=2.0,
    )
    score2 = tier2.calculate_utility_score()
    assert score2 > 100.0

    # Tier 3: Normal OC-EDS Rotation (T_w > 2.0)
    tier3 = AccountQuotaState(
        account_id="normal@example.com",
        model="gemini-3.1-pro-high",
        weekly_quota_percent=80.0,
        weekly_reset_days=4.5,
        five_hour_quota_percent=60.0,
        five_hour_reset_hours=3.0,
    )
    score3 = tier3.calculate_utility_score()
    assert 0.0 < score3 < 100.0

    # Tier 4: Disqualified (W_i <= 0)
    tier4 = AccountQuotaState(
        account_id="exhausted@example.com",
        model="gemini-3.1-pro-high",
        weekly_quota_percent=0.0,
        weekly_reset_days=3.0,
        five_hour_quota_percent=0.0,
        five_hour_reset_hours=1.0,
    )
    assert tier4.calculate_utility_score() == -float("inf")
    # In JSON dict representation, -inf becomes None for JSON compatibility
    assert tier4.to_dict()["utility_score"] is None


def test_account_quota_best_routing_selection():
    """Verifies best account recommendation by highest utility score."""
    exporter = MetricsExporter()

    exporter.record_account_quota(
        account_id="acct_normal@example.com",
        model="gemini-3.1-pro-high",
        weekly_quota_percent=50.0,
        weekly_reset_days=5.0,
        five_hour_quota_percent=40.0,
        five_hour_reset_hours=3.0,
    )

    exporter.record_account_quota(
        account_id="acct_idle@example.com",
        model="claude-opus-4-6-thinking",
        weekly_quota_percent=100.0,
        weekly_reset_days=7.0,
        five_hour_quota_percent=100.0,
        five_hour_reset_hours=5.0,
    )

    exporter.record_account_quota(
        account_id="acct_exhausted@example.com",
        model="claude-opus-4-6-thinking",
        weekly_quota_percent=0.0,
        weekly_reset_days=2.0,
        five_hour_quota_percent=0.0,
        five_hour_reset_hours=1.0,
        state="rate_limited",
    )

    quotas = exporter.collect_quota_metrics()
    assert quotas["total_accounts_tracked"] == 3
    assert quotas["available_accounts_count"] == 2
    assert quotas["rate_limited_accounts_count"] == 1
    assert quotas["best_account"] == "acct_idle@example.com"
    assert quotas["best_model"] == "claude-opus-4-6-thinking"


def test_worktree_disk_metrics_computation(tmp_path: Path):
    """Verifies worktree count and byte calculations on mock directory tree."""
    worktrees_dir = tmp_path / "worktrees"
    worktrees_dir.mkdir()

    wt1 = worktrees_dir / "tsk_001"
    wt1.mkdir()
    (wt1 / "file1.txt").write_bytes(b"A" * 1024)
    (wt1 / "subdir").mkdir()
    (wt1 / "subdir" / "file2.txt").write_bytes(b"B" * 2048)

    wt2 = worktrees_dir / "tsk_002"
    wt2.mkdir()
    (wt2 / "code.py").write_bytes(b"C" * 4096)

    exporter = MetricsExporter(worktrees_dir=worktrees_dir)
    disk_metrics = exporter.collect_disk_metrics()

    assert disk_metrics["worktrees_count"] == 2
    assert disk_metrics["worktrees_used_bytes"] == 1024 + 2048 + 4096
    assert disk_metrics["per_worktree_bytes"]["tsk_001"] == 3072
    assert disk_metrics["per_worktree_bytes"]["tsk_002"] == 4096
    assert disk_metrics["disk_total_bytes"] > 0
    assert disk_metrics["disk_free_bytes"] > 0
    assert 0.0 <= disk_metrics["disk_used_percent"] <= 100.0


def test_queue_metrics_and_active_leases():
    """Verifies queue stats, status distribution, and active/expired leases."""
    queue = MagicMock()
    queue.get_stats.return_value = {
        "total_tasks": 4,
        "by_status": {
            TriageStatus.PENDING_REVIEW.value: 1,
            TriageStatus.APPROVED.value: 1,
            TriageStatus.EXECUTING.value: 1,
            TriageStatus.COMPLETED.value: 1,
            TriageStatus.FAILED.value: 0,
        },
        "queue_wait_seconds": {"average": 12.5, "median": 10.0},
        "execution_duration_seconds": {"average": 45.0, "median": 40.0},
    }

    queue.list_tasks.return_value = [
        {"id": "t1", "status": "pending_review"},
        {"id": "t2", "status": "approved"},
        {
            "id": "t3",
            "status": "executing",
            "started_at": 1000.0,
            "provenance": {
                "lease_metadata": {
                    "worker_id": "worker_prod_1",
                    "lease_id": "lease_abc_123",
                    "fencing_epoch": 123456789,
                }
            },
        },
        {"id": "t4", "status": "completed"},
    ]

    exporter = MetricsExporter(queue=queue, lease_timeout_seconds=300.0)
    q_metrics = exporter.collect_queue_metrics()

    assert q_metrics["total_tasks"] == 4
    assert q_metrics["by_status"]["executing"] == 1
    assert q_metrics["active_lease_count"] == 1
    assert q_metrics["expired_lease_count"] == 1  # 1000.0 is way in the past -> expired

    active_lease = q_metrics["active_leases"][0]
    assert active_lease["task_id"] == "t3"
    assert active_lease["worker_id"] == "worker_prod_1"
    assert active_lease["lease_id"] == "lease_abc_123"
    assert active_lease["is_expired"] is True


def test_real_task_triage_queue_integration(tmp_path: Path):
    """Verifies end-to-end metrics scraping against a real SQLite TaskTriageQueue."""
    import sqlite3
    import time

    db_file = tmp_path / "test_triage.db"
    lock_file = tmp_path / "emergency.lock"
    queue = TaskTriageQueue(db_path=db_file, emergency_lock_path=lock_file)
    now = time.time()

    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            INSERT INTO task_triage_queue (
                id, status, envelope_json, provenance_json, content_hash, started_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "tsk_live_exec",
                TriageStatus.EXECUTING.value,
                json.dumps({"project_id": "test_proj"}),
                json.dumps({
                    "lease_metadata": {
                        "worker_id": "worker_live_42",
                        "lease_id": "lease_live_999",
                        "fencing_epoch": 123456,
                    }
                }),
                "hash-exec",
                now - 15.0,
                now - 100.0,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO task_triage_queue (
                id, status, envelope_json, provenance_json, content_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "tsk_live_pending",
                TriageStatus.PENDING_REVIEW.value,
                json.dumps({"project_id": "test_proj"}),
                json.dumps({}),
                "hash-pending",
                now - 50.0,
                now,
            ),
        )

    exporter = MetricsExporter(queue=queue)
    metrics = exporter.collect_queue_metrics()

    assert metrics["total_tasks"] == 2
    assert metrics["by_status"][TriageStatus.EXECUTING.value] == 1
    assert metrics["by_status"][TriageStatus.PENDING_REVIEW.value] == 1
    assert metrics["active_lease_count"] == 1
    assert metrics["expired_lease_count"] == 0

    lease_info = metrics["active_leases"][0]
    assert lease_info["task_id"] == "tsk_live_exec"
    assert lease_info["worker_id"] == "worker_live_42"
    assert lease_info["lease_id"] == "lease_live_999"
    assert lease_info["is_expired"] is False


def test_json_exposition_export():
    """Verifies schema compliance of JSON telemetry export."""
    exporter = MetricsExporter()
    exporter.record_gate_runtime("unit_test", 12.0, True)
    exporter.record_account_quota(
        "test@example.com", "gemini-3.1-pro-high", 90.0, 6.0, 80.0, 4.0
    )

    json_output = exporter.export_json(indent=2)
    data = json.loads(json_output)

    assert data["schema_version"] == "1.0"
    assert "timestamp" in data
    assert "iso_timestamp" in data
    assert "queue" in data
    assert "disk" in data
    assert "gates" in data
    assert "quotas" in data
    assert data["gates"]["summary"]["total_gate_runs"] == 1
    assert len(data["quotas"]["accounts"]) == 1


def test_prometheus_exposition_export(tmp_path: Path):
    """Verifies Prometheus text formatting and metric labels."""
    worktrees_dir = tmp_path / "worktrees"
    worktrees_dir.mkdir()

    exporter = MetricsExporter(worktrees_dir=worktrees_dir)
    exporter.record_gate_runtime("unit_test", 8.5, True)
    exporter.record_gate_runtime("lint", 1.2, False)
    exporter.record_account_quota(
        "user_prod@example.com",
        "claude-opus-4-6-thinking",
        99.5,
        7.0,
        90.0,
        5.0,
        state="available",
    )

    prom_text = exporter.export_prometheus()

    assert prom_text.endswith("\n")
    assert "# HELP alphabrain_scrape_errors_total" in prom_text
    assert "# TYPE alphabrain_scrape_errors_total counter" in prom_text
    assert "alphabrain_scrape_errors_total 0" in prom_text

    assert '# HELP alphabrain_gate_execution_count' in prom_text
    assert 'alphabrain_gate_execution_count{gate="unit_test",outcome="passed"} 1' in prom_text
    assert 'alphabrain_gate_execution_count{gate="lint",outcome="failed"} 1' in prom_text

    assert '# HELP alphabrain_account_utility_score' in prom_text
    assert 'alphabrain_account_utility_score{account="user_prod@example.com",model="claude-opus-4-6-thinking"}' in prom_text
    assert "alphabrain_worktrees_count 0" in prom_text


def test_prometheus_label_escaping():
    """Verifies proper escaping of quotes and backslashes in Prometheus labels."""
    exporter = MetricsExporter()
    exporter.record_gate_runtime('gate_"special"\\name', 2.5, True)
    prom_text = exporter.export_prometheus()

    assert r'gate="gate_\"special\"\\name"' in prom_text


def test_default_exporter_empty_state():
    """Verifies that an unconfigured exporter returns empty valid telemetry."""
    exporter = MetricsExporter()
    snapshot = exporter.collect()

    assert snapshot.queue["total_tasks"] == 0
    assert snapshot.queue["active_lease_count"] == 0
    assert snapshot.gates["summary"]["total_gate_runs"] == 0
    assert snapshot.quotas["total_accounts_tracked"] == 0

    json_text = exporter.export_json(snapshot)
    assert json.loads(json_text)["schema_version"] == "1.0"

    prom_text = exporter.export_prometheus(snapshot)
    assert "alphabrain_queue_total_tasks 0" in prom_text
    assert "alphabrain_active_leases_total 0" in prom_text


def test_error_handling_and_fault_tolerance():
    """Verifies that subsystem failures are isolated and scrape errors are recorded."""
    # Create an exporter with a failing queue
    failing_queue = MagicMock()
    failing_queue.get_stats.side_effect = RuntimeError("Database locked")

    exporter = MetricsExporter(
        queue=failing_queue,
        worktrees_dir=Path("/non/existent/worktree/directory/path"),
    )
    exporter.record_gate_runtime("unit_test", 5.0, True)

    snapshot = exporter.collect()
    assert len(snapshot.scrape_errors) == 1
    assert "queue: Database locked" in snapshot.scrape_errors[0]
    assert snapshot.queue["total_tasks"] == 0

    # Disk metrics should fail gracefully with 0 worktrees
    assert snapshot.disk["worktrees_count"] == 0
    assert snapshot.disk["worktrees_used_bytes"] == 0

    # Gate metrics should still be gathered successfully
    assert snapshot.gates["summary"]["total_gate_runs"] == 1

    # Prometheus export includes the incremented scrape error counter
    prom_text = exporter.export_prometheus(snapshot)
    assert "alphabrain_scrape_errors_total 1" in prom_text
