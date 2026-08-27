"""
testscript/test_soak_harness.py
Tests the 8-hour / overnight soak testing harness, checkpointing, and telemetry report generation.
"""

import pytest

from testscript.soak_worker_harness import SoakTestHarness


@pytest.mark.asyncio
async def test_soak_harness_executes_bounded_cycles_and_emits_report(tmp_path):
    state_dir = tmp_path / "soak_state"
    report_file = tmp_path / "soak_report.md"

    harness = SoakTestHarness(
        duration_seconds=10.0,
        poll_interval=0.01,
        state_dir=state_dir,
        report_path=report_file,
        dry_run=True,
        max_cycles=5,
    )

    summary = await harness.run()

    # Verify execution completed bounded cycles
    assert summary.total_cycles == 5
    assert summary.total_samples == 5
    assert summary.verdict in {"PASS", "DEGRADED"}
    assert summary.checkpoints_saved == 5

    # Verify telemetry file exists and contains valid JSON lines
    telemetry_file = state_dir / "soak_telemetry.jsonl"
    assert telemetry_file.exists()
    lines = [
        line.strip()
        for line in telemetry_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 5

    # Verify checkpoint file exists
    checkpoint_file = state_dir / "checkpoint.json"
    assert checkpoint_file.exists()

    # Verify markdown report rendered correctly
    assert report_file.exists()
    report_content = report_file.read_text(encoding="utf-8")
    assert "Alpha Brain P5 Worker Soak Test Summary Report" in report_content
    assert summary.session_id in report_content
    assert "Telemetry & Operational Metrics" in report_content
