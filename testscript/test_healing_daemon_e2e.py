import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_worker.ci_healing_daemon import CIHealingDaemon


@pytest.fixture
def temp_env(tmp_path):
    db_path = tmp_path / "triage.db"
    emergency_lock = tmp_path / "emergency.lock"
    queue = TaskTriageQueue(db_path=db_path, emergency_lock_path=emergency_lock)
    return queue, tmp_path


def test_healing_daemon_e2e_lifecycle(temp_env):
    queue, tmp_path = temp_env
    daemon = CIHealingDaemon(queue, project_id="prj_repair")


    worktree = tmp_path / "worktree_e2e"
    worktree.mkdir()
    evidence_dir = worktree / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "pytest_output.txt").write_text("FAILED tests/test_dummy.py::test_fail\n")

    prov = TaskProvenance(
        meeting_id="m_e2e",
        speaker_id="s_e2e",
        utterance_timestamp=1.0,
        transcript_excerpt="E2E test",
        extraction_model="test",
        extraction_confidence=1.0,
        eva_session_id="session1",
        created_at=1.0,
        content_hash="hash-123",
    )

    root_task_id = "tsk_e2e"
    queue.enqueue_task(
        task_id=root_task_id,
        envelope={"project_id": "prj_repair", "allowed_paths": ["src/", "tests/test_dummy.py"]},
        provenance=prov,
        initial_status=TriageStatus.FAILED,
    )

    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET worktree_path = ? WHERE id = ?",
            (str(worktree), root_task_id),
        )
        conn.commit()

    daemon.run_once()

    rejected = queue.list_tasks(status=TriageStatus.REJECTED)
    assert any(t["id"] == root_task_id for t in rejected)

    pending = queue.list_tasks(status=TriageStatus.PENDING_REVIEW)
    assert len(pending) == 1
    repair_task_0 = pending[0]
    assert repair_task_0["id"] == f"{root_task_id}_repair_1"

    envelope_0 = json.loads(repair_task_0["envelope_json"])
    assert "tests/test_dummy.py" in envelope_0["allowed_paths"]
    assert any(p in ('src', 'src/') for p in envelope_0["allowed_paths"])

    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET status = ?, worktree_path = ? WHERE id = ?",
            (TriageStatus.FAILED.value, str(worktree), repair_task_0["id"]),
        )
        conn.commit()

    daemon.run_once()

    repair_task_1_id = f"{repair_task_0['id']}_repair_2"
    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET status = ?, worktree_path = ? WHERE id = ?",
            (TriageStatus.FAILED.value, str(worktree), repair_task_1_id),
        )
        conn.commit()

    daemon.run_once()

    rejected = queue.list_tasks(status=TriageStatus.REJECTED)
    tripped_task = next((t for t in rejected if t["id"] == repair_task_1_id), None)
    assert tripped_task is not None
    assert "ESCALATED" in tripped_task.get("safety_reason", "")

    pending = queue.list_tasks(status=TriageStatus.PENDING_REVIEW)
    assert not any(t["id"] == f"{repair_task_1_id}_repair_3" for t in pending)

    completed_task_id = "tsk_completed"
    queue.enqueue_task(
        task_id=completed_task_id,
        envelope={"project_id": "prj_repair", "allowed_paths": []},
        provenance=prov,
        initial_status=TriageStatus.COMPLETED,
    )

    with patch("alpha_worker.ci_healing_daemon.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps({"approved": True})),
            MagicMock(returncode=0, stdout=""),
        ]

        daemon.run_once()

        assert mock_run.call_count == 2
        calls = mock_run.call_args_list
        assert "senior-review" in calls[0][0][0]
        assert "merge" in calls[1][0][0]

        assert completed_task_id in daemon.processed_tasks
