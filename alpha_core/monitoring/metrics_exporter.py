"""
alpha_core/monitoring/metrics_exporter.py
P9.7 Operational Monitoring and Live Metrics Telemetry Exporter for AlphaBrain.

Tracks:
- Active worker leases (leased tasks, workers, durations, expirations)
- Queue depth by status (pending_review, approved, executing, completed, failed, etc.)
- Worktree disk utilization (worktree counts, used bytes, filesystem free/total, usage %)
- Gate runtimes (durations, pass/fail counts, pass rates, min/max/average per gate)
- Account quota states (weekly/5-hour remaining, reset deadlines, OC-EDS Utility Scores)

Provides exposition in:
- Structured JSON format (with schema versioning and secret redaction)
- Standard Prometheus text exposition format (gauges, counters, summaries, labels)
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus

logger = logging.getLogger("alphabrain.monitoring.metrics_exporter")

DEFAULT_WORKTREES_DIR = Path.home() / "Library" / "Application Support" / "AlphaBrain" / "worktrees"
DEFAULT_LEASE_TIMEOUT_SECONDS = 3600.0


def utc_iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclasses.dataclass
class LeaseMetric:
    task_id: str
    worker_id: str
    lease_id: str
    leased_at: float
    duration_seconds: float
    is_expired: bool
    fencing_epoch: int | None = None
    attempt_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class GateRuntimeStats:
    gate_name: str
    total_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    total_duration_seconds: float = 0.0
    min_duration_seconds: float = 0.0
    max_duration_seconds: float = 0.0
    last_duration_seconds: float = 0.0

    @property
    def pass_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return round(self.passed_runs / self.total_runs, 4)

    @property
    def average_duration_seconds(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return round(self.total_duration_seconds / self.total_runs, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "total_runs": self.total_runs,
            "passed_runs": self.passed_runs,
            "failed_runs": self.failed_runs,
            "pass_rate": self.pass_rate,
            "total_duration_seconds": round(self.total_duration_seconds, 4),
            "average_duration_seconds": self.average_duration_seconds,
            "min_duration_seconds": round(self.min_duration_seconds, 4),
            "max_duration_seconds": round(self.max_duration_seconds, 4),
            "last_duration_seconds": round(self.last_duration_seconds, 4),
        }


@dataclasses.dataclass
class AccountQuotaState:
    account_id: str
    model: str
    weekly_quota_percent: float
    weekly_reset_days: float
    five_hour_quota_percent: float
    five_hour_reset_hours: float
    state: str = "available"  # available, cooldown, rate_limited, auth_failed, disabled, unknown
    last_updated: float = dataclasses.field(default_factory=time.time)

    def calculate_utility_score(self) -> float:
        """
        Calculates the Tiered Opportunity-Cost / Earliest-Deadline Scheduling (OC-EDS) Utility Score.
        Tiers per AlphaBrain Architecture Standards:
        - Tier 1 (Idle First): W_i >= 99.0% and weekly countdown unstarted (T_w,i >= 7.0) -> U_i = 1000.0 + F_i
        - Tier 2 (Expiring <= 2 Days): 0 < T_w,i <= 2.0 and W_i > 0.0 ->
            U_i = 100.0 + [100.0 / (T_w,i + 0.1)] * [sqrt(max(0.1, W_i)) / 10.0]
        - Tier 3 (Normal OC-EDS Rotation): T_w,i > 2.0 and W_i > 0.0 ->
            U_i = [ln(1 + W_i) / (T_w,i + 1.0)] * [sqrt(max(0, F_i)) + 2.0 / (T_f,i + 1.0)]
        - Tier 4 (Disqualified): W_i <= 0.0 -> -inf
        """
        w_i = float(self.weekly_quota_percent)
        t_w_i = max(0.0, float(self.weekly_reset_days))
        f_i = float(self.five_hour_quota_percent)
        t_f_i = max(0.0, float(self.five_hour_reset_hours))

        if w_i <= 0.0:
            return -float("inf")

        # Tier 1: Idle First (seal unbroken, full weekly quota, timer ~7 days or unstarted)
        if w_i >= 99.0 and t_w_i >= 6.9:
            return 1000.0 + f_i

        # Tier 2: Expiring soon (<= 2 days)
        if 0.0 < t_w_i <= 2.0:
            urgency = 100.0 / (t_w_i + 0.1)
            quota_factor = math.sqrt(max(0.1, w_i)) / 10.0
            return 100.0 + (urgency * quota_factor)

        # Tier 3: Normal OC-EDS Rotation
        weekly_component = math.log(1.0 + w_i) / (t_w_i + 1.0)
        five_hour_component = math.sqrt(max(0.0, f_i)) + (2.0 / (t_f_i + 1.0))
        return weekly_component * five_hour_component

    def to_dict(self) -> dict[str, Any]:
        score = self.calculate_utility_score()
        # Ensure score is JSON-compliant (replace -inf with string or None for pure JSON)
        safe_score = None if math.isinf(score) and score < 0 else round(score, 4)
        return {
            "account_id": self.account_id,
            "model": self.model,
            "weekly_quota_percent": round(self.weekly_quota_percent, 2),
            "weekly_reset_days": round(self.weekly_reset_days, 2),
            "five_hour_quota_percent": round(self.five_hour_quota_percent, 2),
            "five_hour_reset_hours": round(self.five_hour_reset_hours, 2),
            "state": self.state,
            "utility_score": safe_score,
            "last_updated": round(self.last_updated, 2),
        }


@dataclasses.dataclass
class MetricsSnapshot:
    timestamp: float
    iso_timestamp: str
    schema_version: str
    queue: dict[str, Any]
    disk: dict[str, Any]
    gates: dict[str, Any]
    quotas: dict[str, Any]
    scrape_errors: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "iso_timestamp": self.iso_timestamp,
            "schema_version": self.schema_version,
            "queue": self.queue,
            "disk": self.disk,
            "gates": self.gates,
            "quotas": self.quotas,
            "scrape_errors": self.scrape_errors,
        }


class MetricsExporter:
    """
    Operational monitoring and Prometheus/JSON metrics exporter for AlphaBrain.
    Gathers active leases, queue depth by status, worktree disk utilization,
    gate runtimes, and AI account quota states.
    """

    SCHEMA_VERSION: str = "1.0"

    def __init__(
        self,
        queue: TaskTriageQueue | None = None,
        worktrees_dir: Path | str | None = None,
        lease_timeout_seconds: float = DEFAULT_LEASE_TIMEOUT_SECONDS,
    ) -> None:
        self.queue = queue
        self.worktrees_dir = Path(worktrees_dir) if worktrees_dir else DEFAULT_WORKTREES_DIR
        self.lease_timeout_seconds = lease_timeout_seconds
        self._gate_stats: dict[str, GateRuntimeStats] = {}
        self._account_quotas: dict[str, AccountQuotaState] = {}
        self._scrape_error_count: int = 0

    # -----------------------------------------------------------------------
    # Gate Runtime Registration & Aggregation
    # -----------------------------------------------------------------------

    def record_gate_runtime(
        self,
        gate_name: str,
        duration_seconds: float,
        passed: bool,
    ) -> GateRuntimeStats:
        """Records a single execution of a gate (e.g. unit_test, lint)."""
        duration = max(0.0, float(duration_seconds))
        if gate_name not in self._gate_stats:
            stats = GateRuntimeStats(
                gate_name=gate_name,
                total_runs=1,
                passed_runs=1 if passed else 0,
                failed_runs=0 if passed else 1,
                total_duration_seconds=duration,
                min_duration_seconds=duration,
                max_duration_seconds=duration,
                last_duration_seconds=duration,
            )
            self._gate_stats[gate_name] = stats
            return stats

        stats = self._gate_stats[gate_name]
        stats.total_runs += 1
        if passed:
            stats.passed_runs += 1
        else:
            stats.failed_runs += 1

        stats.total_duration_seconds += duration
        stats.min_duration_seconds = min(stats.min_duration_seconds, duration)
        stats.max_duration_seconds = max(stats.max_duration_seconds, duration)
        stats.last_duration_seconds = duration
        return stats

    # -----------------------------------------------------------------------
    # Account Quota Registration
    # -----------------------------------------------------------------------

    def record_account_quota(
        self,
        account_id: str,
        model: str,
        weekly_quota_percent: float,
        weekly_reset_days: float,
        five_hour_quota_percent: float,
        five_hour_reset_hours: float,
        state: str = "available",
    ) -> AccountQuotaState:
        """Records or updates the live quota and availability state for an account/model."""
        key = f"{account_id}:{model}"
        quota_state = AccountQuotaState(
            account_id=account_id,
            model=model,
            weekly_quota_percent=weekly_quota_percent,
            weekly_reset_days=weekly_reset_days,
            five_hour_quota_percent=five_hour_quota_percent,
            five_hour_reset_hours=five_hour_reset_hours,
            state=state,
            last_updated=time.time(),
        )
        self._account_quotas[key] = quota_state
        return quota_state

    # -----------------------------------------------------------------------
    # Subsystem Collectors
    # -----------------------------------------------------------------------

    def collect_queue_metrics(self) -> dict[str, Any]:
        """Collects queue depth by status, duration aggregates, and active leases."""
        if self.queue is None:
            return {
                "total_tasks": 0,
                "by_status": {s.value: 0 for s in TriageStatus},
                "queue_wait_seconds": {"average": 0.0, "median": 0.0},
                "execution_duration_seconds": {"average": 0.0, "median": 0.0},
                "active_leases": [],
                "active_lease_count": 0,
                "expired_lease_count": 0,
            }

        stats = self.queue.get_stats()
        now = time.time()
        tasks = self.queue.list_tasks(limit=10000)

        active_leases: list[LeaseMetric] = []
        for t in tasks:
            if t.get("status") == TriageStatus.EXECUTING.value:
                prov = t.get("provenance") or {}
                lease_meta = prov.get("lease_metadata") or {}
                started_at = t.get("started_at") or now
                elapsed = max(0.0, now - float(started_at))
                is_expired = elapsed > self.lease_timeout_seconds

                lease = LeaseMetric(
                    task_id=t.get("id", "unknown"),
                    worker_id=lease_meta.get("worker_id") or t.get("worker_id") or "unknown_worker",
                    lease_id=lease_meta.get("lease_id") or t.get("lease_id") or "unknown_lease",
                    leased_at=float(started_at),
                    duration_seconds=round(elapsed, 2),
                    is_expired=is_expired,
                    fencing_epoch=lease_meta.get("fencing_epoch"),
                    attempt_id=lease_meta.get("attempt_id"),
                )
                active_leases.append(lease)

        expired_count = sum(1 for lease_item in active_leases if lease_item.is_expired)

        return {
            "total_tasks": stats.get("total_tasks", len(tasks)),
            "by_status": stats.get("by_status", {}),
            "queue_wait_seconds": stats.get("queue_wait_seconds", {"average": 0.0, "median": 0.0}),
            "execution_duration_seconds": stats.get(
                "execution_duration_seconds", {"average": 0.0, "median": 0.0}
            ),
            "active_leases": [lease_item.to_dict() for lease_item in active_leases],
            "active_lease_count": len(active_leases),
            "expired_lease_count": expired_count,
        }

    def collect_disk_metrics(self) -> dict[str, Any]:
        """Calculates worktree disk utilization and filesystem free/total space."""
        base_dir = self.worktrees_dir
        worktree_count = 0
        worktrees_used_bytes = 0
        per_worktree_bytes: dict[str, int] = {}

        if base_dir.exists() and base_dir.is_dir():
            try:
                for entry in base_dir.iterdir():
                    if entry.is_dir() and not entry.is_symlink():
                        worktree_count += 1
                        wt_size = 0
                        try:
                            for file_path in entry.rglob("*"):
                                if file_path.is_file() and not file_path.is_symlink():
                                    try:
                                        wt_size += file_path.stat().st_size
                                    except OSError:
                                        pass
                        except OSError as e:
                            logger.warning("Error reading worktree entry %s: %s", entry, e)
                        per_worktree_bytes[entry.name] = wt_size
                        worktrees_used_bytes += wt_size
            except OSError as e:
                logger.warning("Error iterating worktrees dir %s: %s", base_dir, e)

        # Filesystem disk usage
        fs_target = base_dir if base_dir.exists() else base_dir.parent
        if not fs_target.exists():
            fs_target = Path("/")

        try:
            usage = shutil.disk_usage(fs_target)
            disk_total = usage.total
            disk_free = usage.free
            disk_used = usage.used
            disk_used_percent = (
                round((disk_used / disk_total) * 100.0, 2) if disk_total > 0 else 0.0
            )
        except OSError as e:
            logger.warning("Error determining disk usage for %s: %s", fs_target, e)
            disk_total = 0
            disk_free = 0
            disk_used = 0
            disk_used_percent = 0.0

        return {
            "worktrees_dir": str(base_dir),
            "worktrees_count": worktree_count,
            "worktrees_used_bytes": worktrees_used_bytes,
            "worktrees_used_mb": round(worktrees_used_bytes / (1024 * 1024), 2),
            "worktrees_used_gb": round(worktrees_used_bytes / (1024**3), 4),
            "per_worktree_bytes": per_worktree_bytes,
            "disk_total_bytes": disk_total,
            "disk_free_bytes": disk_free,
            "disk_used_bytes": disk_used,
            "disk_used_percent": disk_used_percent,
        }

    def collect_gate_metrics(self) -> dict[str, Any]:
        """Collects summary and per-gate runtime statistics."""
        total_runs = sum(s.total_runs for s in self._gate_stats.values())
        passed_runs = sum(s.passed_runs for s in self._gate_stats.values())
        failed_runs = sum(s.failed_runs for s in self._gate_stats.values())
        pass_rate = round(passed_runs / total_runs, 4) if total_runs > 0 else 0.0

        return {
            "summary": {
                "total_gate_runs": total_runs,
                "total_passed": passed_runs,
                "total_failed": failed_runs,
                "overall_pass_rate": pass_rate,
            },
            "by_gate": {name: stats.to_dict() for name, stats in self._gate_stats.items()},
        }

    def collect_quota_metrics(self) -> dict[str, Any]:
        """Collects account and model quota states and utility scores."""
        accounts_list = [q.to_dict() for q in self._account_quotas.values()]

        # Determine best available account by utility score
        best_account: str | None = None
        best_model: str | None = None
        max_score = -float("inf")

        for q in self._account_quotas.values():
            if q.state == "available":
                score = q.calculate_utility_score()
                if score > max_score:
                    max_score = score
                    best_account = q.account_id
                    best_model = q.model

        available_count = sum(1 for q in self._account_quotas.values() if q.state == "available")
        rate_limited_count = sum(
            1 for q in self._account_quotas.values() if q.state in ("rate_limited", "cooldown")
        )

        return {
            "total_accounts_tracked": len(self._account_quotas),
            "available_accounts_count": available_count,
            "rate_limited_accounts_count": rate_limited_count,
            "best_account": best_account,
            "best_model": best_model,
            "accounts": accounts_list,
        }

    # -----------------------------------------------------------------------
    # Comprehensive Scrape & Snapshot
    # -----------------------------------------------------------------------

    def collect(self) -> MetricsSnapshot:
        """Gathers telemetry across all subsystems into an immutable snapshot."""
        scrape_errors: list[str] = []
        now_ts = time.time()
        iso_ts = utc_iso_now()

        # 1. Queue metrics
        try:
            queue_data = self.collect_queue_metrics()
        except Exception as e:
            logger.exception("Failed to collect queue metrics")
            self._scrape_error_count += 1
            scrape_errors.append(f"queue: {e}")
            queue_data = {"error": str(e), "total_tasks": 0, "by_status": {}}

        # 2. Disk metrics
        try:
            disk_data = self.collect_disk_metrics()
        except Exception as e:
            logger.exception("Failed to collect disk metrics")
            self._scrape_error_count += 1
            scrape_errors.append(f"disk: {e}")
            disk_data = {"error": str(e), "worktrees_count": 0, "worktrees_used_bytes": 0}

        # 3. Gate metrics
        try:
            gate_data = self.collect_gate_metrics()
        except Exception as e:
            logger.exception("Failed to collect gate metrics")
            self._scrape_error_count += 1
            scrape_errors.append(f"gates: {e}")
            gate_data = {"error": str(e), "summary": {}, "by_gate": {}}

        # 4. Quota metrics
        try:
            quota_data = self.collect_quota_metrics()
        except Exception as e:
            logger.exception("Failed to collect quota metrics")
            self._scrape_error_count += 1
            scrape_errors.append(f"quotas: {e}")
            quota_data = {"error": str(e), "accounts": []}

        return MetricsSnapshot(
            timestamp=now_ts,
            iso_timestamp=iso_ts,
            schema_version=self.SCHEMA_VERSION,
            queue=queue_data,
            disk=disk_data,
            gates=gate_data,
            quotas=quota_data,
            scrape_errors=scrape_errors,
        )

    # -----------------------------------------------------------------------
    # Exposition Serializers (JSON & Prometheus)
    # -----------------------------------------------------------------------

    def export_json(self, snapshot: MetricsSnapshot | None = None, indent: int = 2) -> str:
        """Serializes operational telemetry snapshot as formatted JSON."""
        if snapshot is None:
            snapshot = self.collect()
        return json.dumps(snapshot.to_dict(), indent=indent, default=str)

    def export_prometheus(self, snapshot: MetricsSnapshot | None = None) -> str:
        """
        Serializes operational telemetry into standard Prometheus text format.
        Compliant with OpenMetrics / Prometheus exposition standard:
        - # HELP and # TYPE headers
        - Strictly formatted gauges, counters, and summaries
        - Label escaping
        """
        if snapshot is None:
            snapshot = self.collect()
        lines: list[str] = []

        def sanitize_label(val: Any) -> str:
            s = str(val)
            return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

        # Exporter Scrape Errors
        lines.append("# HELP alphabrain_scrape_errors_total Cumulative scrape error count")
        lines.append("# TYPE alphabrain_scrape_errors_total counter")
        lines.append(f"alphabrain_scrape_errors_total {self._scrape_error_count}")

        # Queue Depth & Totals
        q = snapshot.queue
        if "by_status" in q and isinstance(q["by_status"], dict):
            lines.append(
                "# HELP alphabrain_queue_tasks_by_status Task count in triage queue partitioned by status"
            )
            lines.append("# TYPE alphabrain_queue_tasks_by_status gauge")
            for st, count in q["by_status"].items():
                lines.append(
                    f'alphabrain_queue_tasks_by_status{{status="{sanitize_label(st)}"}} {count}'
                )

        lines.append("# HELP alphabrain_queue_total_tasks Total number of tasks in triage queue")
        lines.append("# TYPE alphabrain_queue_total_tasks gauge")
        lines.append(f"alphabrain_queue_total_tasks {q.get('total_tasks', 0)}")

        # Wait and execution durations
        qw = q.get("queue_wait_seconds", {})
        lines.append(
            "# HELP alphabrain_queue_wait_seconds_average Average queue wait time in seconds"
        )
        lines.append("# TYPE alphabrain_queue_wait_seconds_average gauge")
        lines.append(f"alphabrain_queue_wait_seconds_average {qw.get('average', 0.0)}")

        ed = q.get("execution_duration_seconds", {})
        lines.append(
            "# HELP alphabrain_execution_duration_seconds_average Average execution duration in seconds"
        )
        lines.append("# TYPE alphabrain_execution_duration_seconds_average gauge")
        lines.append(f"alphabrain_execution_duration_seconds_average {ed.get('average', 0.0)}")

        # Active Leases
        lines.append("# HELP alphabrain_active_leases_total Current count of active worker leases")
        lines.append("# TYPE alphabrain_active_leases_total gauge")
        lines.append(f"alphabrain_active_leases_total {q.get('active_lease_count', 0)}")

        lines.append(
            "# HELP alphabrain_expired_leases_total Current count of expired worker leases"
        )
        lines.append("# TYPE alphabrain_expired_leases_total gauge")
        lines.append(f"alphabrain_expired_leases_total {q.get('expired_lease_count', 0)}")

        for lease in q.get("active_leases", []):
            task_id = sanitize_label(lease.get("task_id", ""))
            worker_id = sanitize_label(lease.get("worker_id", ""))
            dur = lease.get("duration_seconds", 0.0)
            lines.append(
                f'alphabrain_lease_duration_seconds{{task_id="{task_id}",worker_id="{worker_id}"}} {dur}'
            )

        # Disk Utilization
        d = snapshot.disk
        lines.append(
            "# HELP alphabrain_worktrees_count Current count of task worktree directories"
        )
        lines.append("# TYPE alphabrain_worktrees_count gauge")
        lines.append(f"alphabrain_worktrees_count {d.get('worktrees_count', 0)}")

        lines.append(
            "# HELP alphabrain_worktrees_used_bytes Total bytes consumed by task worktrees"
        )
        lines.append("# TYPE alphabrain_worktrees_used_bytes gauge")
        lines.append(f"alphabrain_worktrees_used_bytes {d.get('worktrees_used_bytes', 0)}")

        lines.append(
            "# HELP alphabrain_disk_free_bytes Available free filesystem bytes on worktree volume"
        )
        lines.append("# TYPE alphabrain_disk_free_bytes gauge")
        lines.append(f"alphabrain_disk_free_bytes {d.get('disk_free_bytes', 0)}")

        lines.append(
            "# HELP alphabrain_disk_total_bytes Total filesystem bytes on worktree volume"
        )
        lines.append("# TYPE alphabrain_disk_total_bytes gauge")
        lines.append(f"alphabrain_disk_total_bytes {d.get('disk_total_bytes', 0)}")

        lines.append(
            "# HELP alphabrain_disk_used_percent Percentage of filesystem disk space utilized"
        )
        lines.append("# TYPE alphabrain_disk_used_percent gauge")
        lines.append(f"alphabrain_disk_used_percent {d.get('disk_used_percent', 0.0)}")

        # Gate Runtimes
        g = snapshot.gates
        summary = g.get("summary", {})
        lines.append("# HELP alphabrain_gate_runs_total Total gate executions across all types")
        lines.append("# TYPE alphabrain_gate_runs_total counter")
        lines.append(f"alphabrain_gate_runs_total {summary.get('total_gate_runs', 0)}")

        lines.append(
            "# HELP alphabrain_gate_pass_rate Overall pass rate across all gate executions (0.0 to 1.0)"
        )
        lines.append("# TYPE alphabrain_gate_pass_rate gauge")
        lines.append(f"alphabrain_gate_pass_rate {summary.get('overall_pass_rate', 0.0)}")

        by_gate = g.get("by_gate", {})
        if by_gate:
            lines.append(
                "# HELP alphabrain_gate_execution_count Number of executions partitioned by gate name and outcome"
            )
            lines.append("# TYPE alphabrain_gate_execution_count counter")
            for name, st in by_gate.items():
                g_name = sanitize_label(name)
                lines.append(
                    f'alphabrain_gate_execution_count{{gate="{g_name}",outcome="passed"}} {st.get("passed_runs", 0)}'
                )
                lines.append(
                    f'alphabrain_gate_execution_count{{gate="{g_name}",outcome="failed"}} {st.get("failed_runs", 0)}'
                )

            lines.append(
                "# HELP alphabrain_gate_duration_seconds Summary of gate execution durations in seconds"
            )
            lines.append("# TYPE alphabrain_gate_duration_seconds summary")
            for name, st in by_gate.items():
                g_name = sanitize_label(name)
                tot_dur = st.get("total_duration_seconds", 0.0)
                tot_runs = st.get("total_runs", 0)
                lines.append(
                    f'alphabrain_gate_duration_seconds_sum{{gate="{g_name}"}} {tot_dur}'
                )
                lines.append(
                    f'alphabrain_gate_duration_seconds_count{{gate="{g_name}"}} {tot_runs}'
                )

        # Account Quota Telemetry
        quotas = snapshot.quotas
        lines.append(
            "# HELP alphabrain_available_accounts_count Total available AI accounts ready for routing"
        )
        lines.append("# TYPE alphabrain_available_accounts_count gauge")
        lines.append(f"alphabrain_available_accounts_count {quotas.get('available_accounts_count', 0)}")

        lines.append(
            "# HELP alphabrain_rate_limited_accounts_count Total accounts currently rate limited or in cooldown"
        )
        lines.append("# TYPE alphabrain_rate_limited_accounts_count gauge")
        lines.append(
            f"alphabrain_rate_limited_accounts_count {quotas.get('rate_limited_accounts_count', 0)}"
        )

        accts = quotas.get("accounts", [])
        if accts:
            lines.append(
                "# HELP alphabrain_account_weekly_quota_percent Weekly remaining quota percentage per account"
            )
            lines.append("# TYPE alphabrain_account_weekly_quota_percent gauge")
            for a in accts:
                acct_id = sanitize_label(a.get("account_id", ""))
                model = sanitize_label(a.get("model", ""))
                lines.append(
                    f'alphabrain_account_weekly_quota_percent{{account="{acct_id}",model="{model}"}} {a.get("weekly_quota_percent", 0.0)}'
                )

            lines.append(
                "# HELP alphabrain_account_5h_quota_percent 5-hour rolling remaining quota percentage per account"
            )
            lines.append("# TYPE alphabrain_account_5h_quota_percent gauge")
            for a in accts:
                acct_id = sanitize_label(a.get("account_id", ""))
                model = sanitize_label(a.get("model", ""))
                lines.append(
                    f'alphabrain_account_5h_quota_percent{{account="{acct_id}",model="{model}"}} {a.get("five_hour_quota_percent", 0.0)}'
                )

            lines.append(
                "# HELP alphabrain_account_utility_score OC-EDS Tiered Utility Score for model routing"
            )
            lines.append("# TYPE alphabrain_account_utility_score gauge")
            for a in accts:
                acct_id = sanitize_label(a.get("account_id", ""))
                model = sanitize_label(a.get("model", ""))
                score = a.get("utility_score")
                # Disqualified accounts output -999999.0 in Prometheus if score is None or -inf
                val = -999999.0 if score is None else score
                lines.append(
                    f'alphabrain_account_utility_score{{account="{acct_id}",model="{model}"}} {val}'
                )

        # End with single trailing newline as per Prometheus standard
        return "\n".join(lines) + "\n"
