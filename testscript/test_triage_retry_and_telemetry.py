import json
import tempfile
from argparse import Namespace
from pathlib import Path

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_core.triage_cli import cmd_retry
from alpha_worker.triage_dispatcher import TriageTaskDispatcher


@pytest.fixture
def temp_queue():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_queue.db"
        lock_path = Path(tmpdir) / "emergency.lock"
        yield TaskTriageQueue(db_path=db_path, emergency_lock_path=lock_path)


def make_test_provenance(task_id: str, content_hash: str) -> TaskProvenance:
    return TaskProvenance(
        meeting_id="meet_fixture_123",
        speaker_id="founder_1",
        utterance_timestamp=1725345600.0,
        transcript_excerpt="Operator approved task",
        extraction_model="gemini-3.1-pro-high",
        extraction_confidence=0.98,
        eva_session_id="eva_sess_001",
        created_at=1725345600.0,
        content_hash=content_hash,
    )


def test_retry_task_resets_count_and_transitions_failed_to_approved(temp_queue: TaskTriageQueue):
    envelope = {
        "title": "Failing Task",
        "repo": ".",
        "allowed_paths": ["foo.py"],
        "acceptance_plan": {"commands": []},
    }
    provenance = make_test_provenance(
        "task_failing", "aa6b12bc9f29fddcd781f5bf429c93576e79b5285f0d626f267e9bdd4d111ccc"
    )
    task_id = "task_failing"
    temp_queue.enqueue_task(task_id, envelope, provenance)
    temp_queue.approve_task(task_id)

    # First attempt: lease and fail
    leased = temp_queue.lease_next_approved_task()
    assert leased is not None
    assert leased["id"] == task_id
    temp_queue.fail_task(
        task_id,
        error_details={
            "error": "Lint failed",
            "evidence": [{"gate_type": "lint", "passed": False}],
        },
        max_retries=1,
    )

    # Task retried once -> should be APPROVED with retry_count = 1
    t = temp_queue.get_task(task_id)
    assert t["status"] == TriageStatus.APPROVED.value
    assert t["retry_count"] == 1

    # Second attempt: lease and fail again -> reaches max_retries
    leased2 = temp_queue.lease_next_approved_task()
    assert leased2 is not None
    temp_queue.fail_task(
        task_id,
        error_details={
            "error": "Second lint fail",
            "evidence": [{"gate_type": "lint", "passed": False, "stdout_snippet": "error line 42"}],
        },
        max_retries=1,
    )

    # Now permanently FAILED
    t_failed = temp_queue.get_task(task_id)
    assert t_failed["status"] == TriageStatus.FAILED.value
    assert t_failed["retry_count"] == 1
    result_data = json.loads(t_failed["result_json"])
    assert result_data["error"] == "Second lint fail"

    # Execute retry_task
    ok = temp_queue.retry_task(task_id, operator_notes="Testing manual retry")
    assert ok is True

    # Check resurrected task
    t_resurrected = temp_queue.get_task(task_id)
    assert t_resurrected["status"] == TriageStatus.APPROVED.value
    assert t_resurrected["retry_count"] == 0
    assert t_resurrected["completed_at"] is None

    # Crucial: result_json failure telemetry preserved for repair directive injection
    res_json_after = json.loads(t_resurrected["result_json"])
    assert res_json_after["evidence"][0]["stdout_snippet"] == "error line 42"

    # Audit history updated
    prov_after = json.loads(t_resurrected["provenance_json"])
    actions = [a["action"] for a in prov_after.get("audit_history", [])]
    assert "task_retried" in actions


def test_retry_non_failed_task_rejected(temp_queue: TaskTriageQueue):
    envelope = {"title": "Pending Task", "repo": "."}
    provenance = make_test_provenance(
        "task_p1", "46ed35ae5ebfec9c6b7fd80f5dab267cffc601b7e2bdba697ee2c9af4d47216f"
    )
    task_id = "task_p1"
    temp_queue.enqueue_task(task_id, envelope, provenance)
    # Task is in PENDING_REVIEW, not FAILED
    assert temp_queue.retry_task(task_id) is False

    temp_queue.approve_task(task_id)
    # Task is in APPROVED, not FAILED
    assert temp_queue.retry_task(task_id) is False


def test_cli_retry_command(temp_queue: TaskTriageQueue, capsys):
    envelope = {"title": "Task for CLI", "repo": "."}
    provenance = make_test_provenance(
        "task_cli", "5b44742b7fb9f8fb9d5e88b12e5f6bb3690ea6c2aa0c1ad8307970ae9a86588c"
    )
    task_id = "task_cli"
    temp_queue.enqueue_task(task_id, envelope, provenance)
    temp_queue.approve_task(task_id)
    temp_queue.lease_next_approved_task()
    temp_queue.fail_task(task_id, error_details="Permanent failure", allow_retry=False)

    args = Namespace(task_id=task_id, notes="CLI operator retry", json=True)
    ret = cmd_retry(args, temp_queue)
    assert ret == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["task_id"] == task_id
    assert data["status"] == "approved"

    task = temp_queue.get_task(task_id)
    assert task["status"] == TriageStatus.APPROVED.value


def test_telemetry_snippet_retention(temp_queue: TaskTriageQueue):
    dispatcher = TriageTaskDispatcher(temp_queue, enable_agent_execution=False)
    long_output = "X" * 4500
    with tempfile.TemporaryDirectory() as workdir:
        # Mock run_command_in_worktree to return 4500-char string
        dispatcher.run_command_in_worktree = lambda path, cmd: (1, long_output, "")
        passed, evidence = dispatcher.run_acceptance_gates(
            Path(workdir),
            {
                "acceptance_plan": {
                    "commands": [
                        {"executable": "ruff", "args": ["check", "."], "gate_type": "lint"}
                    ]
                }
            },
        )
        assert passed is False
        assert len(evidence) == 1
        # Proves retention expands to full 4500 chars (exceeding old 1000 char cap)
        assert len(evidence[0]["stdout_snippet"]) == 4500
