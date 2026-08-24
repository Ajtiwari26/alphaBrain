"""
testscript/test_adapters.py
Automated tests for Antigravity session harness, Stitch MCP configuration, and Health Checker.
"""

from alpha_protocol import (
    TaskEnvelope,
)
from alpha_worker.adapters.antigravity import AntigravityAdapter
from alpha_worker.adapters.stitch_mcp import StitchMCPAdapter
from alpha_worker.health import HardwareHealthChecker


def test_stitch_mcp_gemini_3_1_pro_compliance():
    adapter = StitchMCPAdapter()
    assert adapter.model_id == "gemini-3.1-pro"

    payload = adapter.build_generate_screen_payload(
        project_id="prj_alpha",
        screen_name="Dashboard",
        prompt="Modern dark mode analytics dashboard",
    )
    assert payload["modelId"] == "gemini-3.1-pro"
    assert payload["screenName"] == "Dashboard"


def test_antigravity_session_setup(tmp_path):
    adapter = AntigravityAdapter()
    adapter.memory_graph_path = tmp_path

    task = TaskEnvelope(
        task_id="tsk_adapter_01",
        project_id="prj_alpha",
        repo=str(tmp_path),
        objective="Implement memory graph integration",
        allowed_paths=["."],
    )

    worktree_path = tmp_path / "mock_worktree"
    worktree_path.mkdir(parents=True, exist_ok=True)

    session_dir = adapter.setup_session_in_memory_graph(task, worktree_path)
    assert session_dir.exists()
    assert (session_dir / ".system_generated" / "logs" / "overview.txt").exists()
    assert (session_dir / "artifacts").exists()


def test_hardware_health_checker():
    health, metrics = HardwareHealthChecker.evaluate_worker_health()
    assert health in ["online", "degraded", "draining"]
    assert "battery_percentage" in metrics
    assert "thermal_state" in metrics
