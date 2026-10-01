"""Test bidirectional remote triage dispatch between Render Cloud Relay and Mac host.
Verifies:
1. MobileBridgeService in cloud mode (without local DB) updates cached state and queues command in _pending_remote_commands.
2. sync_mac_node returns the queued command and clears the queue.
3. TaskDetail lookup falls back to cached projection in cloud mode.
"""
from pathlib import Path

from alpha_core.mobile_bridge.schemas import TriageAction
from alpha_core.mobile_bridge.service import MobileBridgeService


def test_bidirectional_triage_flow():
    # Simulate cloud service where db_path does not exist
    fake_cloud_db = Path("/tmp/nonexistent_triage_db.sqlite")
    service = MobileBridgeService(db_path=fake_cloud_db)

    # 1. Simulate Mac host syncing its state initially
    initial_sync = {
        "telemetry": {"cpu_percent": 12.0, "ram_percent": 60.0},
        "worktrees": [{"path": "/Users/ajaytiwari/Desktop/Projects/alphaBrain", "branch": "main"}],
        "triage_tasks": [
            {
                "task_id": "tsk_test_123",
                "title": "Fix memory leak in webview",
                "status": "pending_review",
                "priority": "high",
                "category": "engineering",
            }
        ],
    }
    sync_resp = service.sync_mac_node(initial_sync)
    assert sync_resp["status"] == "ok"
    assert sync_resp["pending_commands"] == []

    # 2. Check task detail fallback works
    detail = service.get_task_detail("tsk_test_123")
    assert detail is not None
    assert detail.task_id == "tsk_test_123"
    assert detail.title == "Fix memory leak in webview"
    assert detail.status == "pending_review"

    # 3. Simulate phone sending approval verdict
    review_resp = service.review_triage_task(
        task_id="tsk_test_123",
        action=TriageAction.APPROVE,
        founder_notes="LGTM approved via mobile app",
    )
    assert review_resp.success is True
    assert review_resp.new_status == "approved"

    # 4. Verify detail reflects approved status in cloud projection
    detail_updated = service.get_task_detail("tsk_test_123")
    assert detail_updated is not None
    assert detail_updated.status == "approved"

    # 5. Simulate next Mac streamer poll (sync_mac_node)
    next_sync_resp = service.sync_mac_node(initial_sync)
    assert len(next_sync_resp["pending_commands"]) == 1
    cmd = next_sync_resp["pending_commands"][0]
    assert cmd["command"] == "triage_verdict"
    assert cmd["task_id"] == "tsk_test_123"
    assert cmd["action"] == "approve"
    assert cmd["notes"] == "LGTM approved via mobile app"

    # 6. Verify subsequent poll has empty pending_commands (drained)
    third_sync = service.sync_mac_node(initial_sync)
    assert third_sync["pending_commands"] == []
    print("ALL BIDIRECTIONAL TRIAGE TESTS PASSED!")


if __name__ == "__main__":
    test_bidirectional_triage_flow()
