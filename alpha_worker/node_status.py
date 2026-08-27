"""Privacy-safe worker status projection for local Node Keeper clients."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from alpha_protocol import WorkerHealthReport


def write_node_status(path: Path, report: WorkerHealthReport, *, paused: bool = False) -> None:
    """Atomically publish health summary; excludes tokens, tasks, paths, and prompts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    payload = {
        "worker_id": report.worker_id,
        "status": report.status.value,
        "battery_percent": report.battery_percent,
        "ac_power": report.ac_power,
        "thermal_pressure": report.thermal_pressure,
        "disk_free_gb": report.disk_free_gb,
        "active_task_count": report.active_task_count,
        "paused": paused,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(payload, output, separators=(",", ":"))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
