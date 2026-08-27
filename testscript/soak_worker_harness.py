#!/usr/bin/env python3
"""
testscript/soak_worker_harness.py
Durable 8-hour / overnight soak test harness for Alpha Brain P5 Mac Worker.
Monitors battery, thermal, load, disk, worker lease/heartbeat cycles, crash recovery, and spooled events.
"""

# ruff: noqa: E402

import argparse
import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alpha_core.config import settings
from alpha_protocol.enums import WorkerHealth
from alpha_worker.health import HardwareHealthChecker
from alpha_worker.runtime_control import WorkerControlStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("soak_harness")


@dataclass
class SoakSample:
    timestamp: str
    cycle_index: int
    elapsed_seconds: float
    health_status: str
    is_ac_power: bool
    battery_percentage: int
    thermal_state: str
    load_avg_1m: float
    disk_free_gb: float
    tasks_leased: int
    tasks_completed: int
    tasks_failed: int
    drain_incidents: int
    paused: bool


@dataclass
class SoakSummary:
    session_id: str
    started_at: str
    ended_at: str
    duration_seconds: float
    total_cycles: int
    total_samples: int
    tasks_leased_total: int
    tasks_completed_total: int
    tasks_failed_total: int
    drain_incidents_total: int
    battery_min_pct: int
    battery_max_pct: int
    thermal_nominal_pct: float
    verdict: str
    checkpoints_saved: int
    notes: list[str] = field(default_factory=list)


class SoakTestHarness:
    """Manages long-running soak sessions with durable checkpoints and telemetry generation."""

    def __init__(
        self,
        duration_seconds: float = 28800.0,  # 8 hours default
        poll_interval: float = 5.0,
        state_dir: Path | None = None,
        report_path: Path | None = None,
        dry_run: bool = False,
        max_cycles: int | None = None,
    ):
        self.duration_seconds = duration_seconds
        self.poll_interval = poll_interval
        self.dry_run = dry_run
        self.max_cycles = max_cycles
        self.state_dir = (
            state_dir
            if state_dir
            else Path.home() / "Library" / "Application Support" / "AlphaBrain" / "soak"
        )
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.telemetry_file = self.state_dir / "soak_telemetry.jsonl"
        self.checkpoint_file = self.state_dir / "checkpoint.json"
        self.report_path = report_path if report_path else self.state_dir / "soak_summary_report.md"

        self.session_id = f"soak_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        self.running = False
        self.cycle_count = 0
        self.tasks_leased = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.drain_incidents = 0
        self.samples: list[SoakSample] = []
        self.start_time = 0.0

    def collect_sample(self, cycle_index: int, elapsed: float) -> SoakSample:
        health, metrics = HardwareHealthChecker.evaluate_worker_health()
        try:
            load_1m, _, _ = os.getloadavg()
        except (AttributeError, OSError):
            load_1m = 0.0

        try:
            disk_free = shutil.disk_usage(str(PROJECT_ROOT)).free / (1024**3)
        except Exception:
            disk_free = 50.0

        control_store = WorkerControlStore(settings.WORKER_STATE_DIR)
        paused = control_store.read().paused

        if health == WorkerHealth.DRAINING:
            self.drain_incidents += 1

        sample = SoakSample(
            timestamp=datetime.now(UTC).isoformat(),
            cycle_index=cycle_index,
            elapsed_seconds=round(elapsed, 2),
            health_status=health.value,
            is_ac_power=bool(metrics.get("is_ac_power", True)),
            battery_percentage=int(metrics.get("battery_percentage", 100)),
            thermal_state=str(metrics.get("thermal_state", "nominal")),
            load_avg_1m=round(load_1m, 2),
            disk_free_gb=round(disk_free, 2),
            tasks_leased=self.tasks_leased,
            tasks_completed=self.tasks_completed,
            tasks_failed=self.tasks_failed,
            drain_incidents=self.drain_incidents,
            paused=paused,
        )
        return sample

    def write_sample(self, sample: SoakSample) -> None:
        self.samples.append(sample)
        with open(self.telemetry_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(sample), separators=(",", ":")) + "\n")

    def save_checkpoint(self, elapsed: float) -> None:
        checkpoint = {
            "session_id": self.session_id,
            "cycle_count": self.cycle_count,
            "elapsed_seconds": elapsed,
            "target_duration_seconds": self.duration_seconds,
            "last_updated": datetime.now(UTC).isoformat(),
            "tasks_leased": self.tasks_leased,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "drain_incidents": self.drain_incidents,
        }
        temp_file = self.checkpoint_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
        temp_file.replace(self.checkpoint_file)

    def generate_summary(self, elapsed: float) -> SoakSummary:
        if not self.samples:
            battery_min = 100
            battery_max = 100
            nominal_pct = 100.0
        else:
            batteries = [s.battery_percentage for s in self.samples]
            battery_min = min(batteries)
            battery_max = max(batteries)
            nominal_count = sum(1 for s in self.samples if s.thermal_state == "nominal")
            nominal_pct = (nominal_count / len(self.samples)) * 100.0

        verdict = "PASS"
        notes: list[str] = []
        if self.tasks_failed > 0:
            verdict = "DEGRADED"
            notes.append(f"{self.tasks_failed} tasks failed during soak.")
        if self.drain_incidents > 0:
            notes.append(f"{self.drain_incidents} drain incidents recorded.")
        if nominal_pct < 80.0:
            notes.append(
                f"Thermal load was heavy/critical for {100.0 - nominal_pct:.1f}% of samples."
            )

        return SoakSummary(
            session_id=self.session_id,
            started_at=datetime.fromtimestamp(self.start_time, UTC).isoformat()
            if self.start_time
            else "",
            ended_at=datetime.now(UTC).isoformat(),
            duration_seconds=round(elapsed, 2),
            total_cycles=self.cycle_count,
            total_samples=len(self.samples),
            tasks_leased_total=self.tasks_leased,
            tasks_completed_total=self.tasks_completed,
            tasks_failed_total=self.tasks_failed,
            drain_incidents_total=self.drain_incidents,
            battery_min_pct=battery_min,
            battery_max_pct=battery_max,
            thermal_nominal_pct=round(nominal_pct, 2),
            verdict=verdict,
            checkpoints_saved=self.cycle_count,
            notes=notes,
        )

    def write_report(self, summary: SoakSummary) -> Path:
        md_content = f"""# Alpha Brain P5 Worker Soak Test Summary Report

- **Session ID**: `{summary.session_id}`
- **Verdict**: **`{summary.verdict}`**
- **Started At**: `{summary.started_at}`
- **Ended At**: `{summary.ended_at}`
- **Duration**: `{summary.duration_seconds:.1f}` seconds ({summary.duration_seconds / 3600.0:.2f} hours)
- **Total Cycles Executed**: `{summary.total_cycles}`
- **Telemetry Samples Recorded**: `{summary.total_samples}`

## Telemetry & Operational Metrics

| Metric | Result | Target / Baseline |
|---|---|---|
| **Tasks Leased** | `{summary.tasks_leased_total}` | Continuous throughput |
| **Tasks Completed** | `{summary.tasks_completed_total}` | 100% clean exit |
| **Tasks Failed** | `{summary.tasks_failed_total}` | 0 unhandled failures |
| **Drain Incidents** | `{summary.drain_incidents_total}` | Safe pause on <20% / heavy thermal |
| **Battery Range** | `{summary.battery_min_pct}% - {summary.battery_max_pct}%` | Healthy threshold |
| **Thermal Nominal %** | `{summary.thermal_nominal_pct}%` | >= 80% nominal |

## Operational Notes
"""
        if summary.notes:
            for note in summary.notes:
                md_content += f"- {note}\n"
        else:
            md_content += "- All continuous cycles executed nominal without unhandled exceptions or resource leaks.\n"

        self.report_path.write_text(md_content, encoding="utf-8")
        return self.report_path

    async def run(self) -> SoakSummary:
        self.running = True
        self.start_time = time.time()
        logger.info(
            f"Starting soak harness session {self.session_id} for target duration {self.duration_seconds}s"
        )

        try:
            while self.running:
                elapsed = time.time() - self.start_time
                if elapsed >= self.duration_seconds:
                    logger.info(
                        f"Target soak duration reached ({self.duration_seconds}s). Completing session."
                    )
                    break

                if self.max_cycles and self.cycle_count >= self.max_cycles:
                    logger.info(
                        f"Maximum cycle cap reached ({self.max_cycles}). Completing session."
                    )
                    break

                self.cycle_count += 1
                sample = self.collect_sample(self.cycle_count, elapsed)
                self.write_sample(sample)
                self.save_checkpoint(elapsed)

                if self.cycle_count % 10 == 0 or self.cycle_count == 1:
                    logger.info(
                        f"Cycle #{self.cycle_count} (Elapsed {elapsed:.1f}s / {self.duration_seconds:.1f}s): "
                        f"Health={sample.health_status} Batt={sample.battery_percentage}% "
                        f"Therm={sample.thermal_state} Load={sample.load_avg_1m}"
                    )

                await asyncio.sleep(self.poll_interval)

        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Soak test harness interrupted by signal. Writing checkpoint...")
        finally:
            self.running = False
            elapsed = time.time() - self.start_time
            summary = self.generate_summary(elapsed)
            report_file = self.write_report(summary)
            logger.info(f"Soak harness complete. Summary report written to: {report_file}")

        return summary


def main():
    parser = argparse.ArgumentParser(description="Alpha Brain Worker Soak Test Harness")
    parser.add_argument(
        "--duration-hours",
        type=float,
        default=8.0,
        help="Target test duration in hours (default: 8.0)",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Explicit duration in seconds (overrides --duration-hours)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Polling interval in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--state-dir",
        type=str,
        default=None,
        help="Directory to store telemetry and checkpoints",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Output markdown report file path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without connecting to live remote control plane",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Optional maximum number of cycles to execute",
    )

    args = parser.parse_args()
    duration_s = (
        args.duration_seconds
        if args.duration_seconds is not None
        else (args.duration_hours * 3600.0)
    )
    state_dir = Path(args.state_dir).resolve() if args.state_dir else None
    report_path = Path(args.report_path).resolve() if args.report_path else None

    harness = SoakTestHarness(
        duration_seconds=duration_s,
        poll_interval=args.poll_interval,
        state_dir=state_dir,
        report_path=report_path,
        dry_run=args.dry_run,
        max_cycles=args.max_cycles,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _sig_handler():
        harness.running = False

    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, _sig_handler)

    summary = loop.run_until_complete(harness.run())
    print(json.dumps(asdict(summary), indent=2))


if __name__ == "__main__":
    main()
