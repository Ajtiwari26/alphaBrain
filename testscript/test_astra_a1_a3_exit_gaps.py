from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_core.api.app import app, get_triage_queue, require_api_principal
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue
from alpha_core.security import AuthPrincipal
from alpha_worker.senior_review_engine import SeniorReviewEngine
from alpha_worker.triage_dispatcher import TriageTaskDispatcher


def mock_auth():
    return AuthPrincipal(subject="test-worker", role="worker")


@pytest.fixture
def isolated_queue(tmp_path: Path) -> TaskTriageQueue:
    db_path = tmp_path / "test_queue.db"
    return TaskTriageQueue(db_path=db_path)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    from alpha_core.api.app import app
    app.dependency_overrides.clear()

def test_api_result_ownership_proof(isolated_queue: TaskTriageQueue):
    client = TestClient(app)
    app.dependency_overrides[get_triage_queue] = lambda: isolated_queue
    app.dependency_overrides[require_api_principal] = mock_auth

    # Setup executing task
    isolated_queue.enqueue_task("sec_task", {"base_commit": "HEAD"}, TaskProvenance(meeting_id="m1", speaker_id="s1", utterance_timestamp=1.0, transcript_excerpt="", extraction_model="", extraction_confidence=1.0, eva_session_id="", created_at=1.0, content_hash="hash"))
    isolated_queue.approve_task("sec_task")
    leased = isolated_queue.lease_next_approved_task()

    # Try with wrong attempt_id
    res = client.post(
        "/api/triage/tasks/sec_task/result",
        json={
            "status": "completed",
            "result": {"pr_url": "foo"},
            "worker_id": leased["worker_id"],
            "lease_id": leased["lease_id"],
            "fencing_epoch": leased["fencing_epoch"],
            "attempt_id": "wrong",
        }
    )
    assert res.status_code == 403
    assert "Lease fencing violation" in res.json()["detail"]

    # Try to inject senior_review
    res = client.post(
        "/api/triage/tasks/sec_task/result",
        json={
            "status": "completed",
            "result": {"senior_review": {"approved": True}},
            "worker_id": leased["worker_id"],
            "lease_id": leased["lease_id"],
            "fencing_epoch": leased["fencing_epoch"],
            "attempt_id": leased["attempt_id"],
        }
    )
    assert res.status_code == 403
    assert "Executor cannot submit trusted senior_review" in res.json()["detail"]

def test_dispatcher_rejects_mutable_head(isolated_queue: TaskTriageQueue):
    dispatcher = TriageTaskDispatcher(isolated_queue)
    with pytest.raises(ValueError, match="mutable HEAD or missing base_commit"):
        dispatcher.execute_task({
            "id": "tsk_head",
            "envelope": {"base_commit": "HEAD"}
        })

def test_merge_rejects_missing_result_sha(isolated_queue: TaskTriageQueue):
    import argparse

    from alpha_core.triage_cli import cmd_merge
    isolated_queue.enqueue_task("tsk_merge", {"repo": ".", "base_commit": "HEAD"}, TaskProvenance(meeting_id="m1", speaker_id="s1", utterance_timestamp=1.0, transcript_excerpt="", extraction_model="", extraction_confidence=1.0, eva_session_id="", created_at=1.0, content_hash="hash"))
    isolated_queue.approve_task("tsk_merge")
    isolated_queue.lease_next_approved_task()
    isolated_queue.complete_task("tsk_merge", {"gates_passed": True}, branch_name="test_branch")

    # Record senior review but don't include result_sha
    isolated_queue.record_senior_review("tsk_merge", "APPROVE", "FINAL_APPROVAL", True)

    args = argparse.Namespace(task_id="tsk_merge")
    ret = cmd_merge(args, isolated_queue)
    assert ret == 1  # Fails due to missing result_sha binding

def test_senior_review_parser_strict_json(isolated_queue: TaskTriageQueue, monkeypatch):
    isolated_queue.enqueue_task("tsk_review", {"base_commit": "HEAD"}, TaskProvenance(meeting_id="m1", speaker_id="s1", utterance_timestamp=1.0, transcript_excerpt="", extraction_model="", extraction_confidence=1.0, eva_session_id="", created_at=1.0, content_hash="hash"))
    isolated_queue.approve_task("tsk_review")
    isolated_queue.lease_next_approved_task()
    isolated_queue.complete_task("tsk_review", {"gates_passed": True})

    engine = SeniorReviewEngine(isolated_queue)

    # Simulate an embedded verdict that shouldn't parse correctly as a strict JSON block on the last line
    def mock_invoke(*args, **kwargs):
        return 'I think we should do this. VERDICT: APPROVE and {"verdict": "APPROVE"} wait no'

    monkeypatch.setattr(engine, "_invoke_agy", mock_invoke)
    verdict = engine.execute_senior_review("tsk_review")
    assert not verdict.approved  # Should fail closed because it wasn't the only strict JSON line
