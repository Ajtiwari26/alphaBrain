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
    isolated_queue.enqueue_task(
        "sec_task",
        {"base_commit": "a" * 40},
        TaskProvenance(
            meeting_id="m1",
            speaker_id="s1",
            utterance_timestamp=1.0,
            transcript_excerpt="",
            extraction_model="",
            extraction_confidence=1.0,
            eva_session_id="",
            created_at=1.0,
            content_hash="c0fd89b027ee6da2820eb7f6a2da074f9716b143e90d9058c08ee7c5e761cbb8",
        ),
    )
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
        },
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
        },
    )
    assert res.status_code == 403
    assert "Executor cannot submit trusted senior_review" in res.json()["detail"]


def test_dispatcher_rejects_mutable_head(isolated_queue: TaskTriageQueue):
    dispatcher = TriageTaskDispatcher(isolated_queue)
    with pytest.raises(ValueError, match="mutable HEAD or missing base_commit"):
        dispatcher.execute_task({"id": "tsk_head", "envelope": {"base_commit": "HEAD"}})


def test_merge_rejects_missing_result_sha(isolated_queue: TaskTriageQueue):
    import argparse

    from alpha_core.triage_cli import cmd_merge

    isolated_queue.enqueue_task(
        "tsk_merge",
        {"repo": ".", "base_commit": "a" * 40},
        TaskProvenance(
            meeting_id="m1",
            speaker_id="s1",
            utterance_timestamp=1.0,
            transcript_excerpt="",
            extraction_model="",
            extraction_confidence=1.0,
            eva_session_id="",
            created_at=1.0,
            content_hash="5738110c53adb65ebf764ca89521d35781019c9d5d24c54f09433c635cf48531",
        ),
    )
    isolated_queue.approve_task("tsk_merge")
    isolated_queue.lease_next_approved_task()
    isolated_queue.complete_task("tsk_merge", {"gates_passed": True}, branch_name="test_branch")

    # Record senior review but don't include result_sha
    isolated_queue.record_senior_review("tsk_merge", "APPROVE", "FINAL_APPROVAL", True)

    args = argparse.Namespace(task_id="tsk_merge")
    ret = cmd_merge(args, isolated_queue)
    assert ret == 1  # Fails due to missing result_sha binding


def test_senior_review_parser_strict_json():
    engine = SeniorReviewEngine(None)  # Queue not needed for parser tests

    # 1. Valid Pro output
    valid_pro = 'Great work.\n{"verdict": "APPROVE"}'
    assert (
        engine.parse_verdict_line(valid_pro, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "APPROVE"
    )

    # 2. Valid Opus output
    valid_opus = 'Looks good.\n{"verdict": "FINAL_APPROVAL"}'
    assert (
        engine.parse_verdict_line(valid_opus, ["FINAL_APPROVAL", "REJECT"], "REJECT")
        == "FINAL_APPROVAL"
    )

    # 3. Wrong enum (Opus evaluating Pro output)
    assert engine.parse_verdict_line(valid_pro, ["FINAL_APPROVAL", "REJECT"], "REJECT") == "REJECT"

    # 4. JSON embedded but not on the last line
    embedded = 'Here is the verdict: {"verdict": "APPROVE"}\nBut wait, final decision: REJECT'
    assert (
        engine.parse_verdict_line(embedded, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )

    # 5. Extra keys in JSON
    extra_keys = '{"verdict": "APPROVE", "reason": "good"}'
    assert (
        engine.parse_verdict_line(extra_keys, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )

    # 6. Duplicate keys in JSON
    duplicate = '{"verdict": "REPAIR_REQUIRED", "verdict": "APPROVE"}'
    assert (
        engine.parse_verdict_line(duplicate, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )

    # 7. Quoted or fenced JSON
    fenced = '```json\n{"verdict": "APPROVE"}\n```'
    assert (
        engine.parse_verdict_line(fenced, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )

    # 8. Trailing text on the same line
    trailing = '{"verdict": "APPROVE"} and some text'
    assert (
        engine.parse_verdict_line(trailing, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )

    # 9. Multiple valid terminal markers across different lines
    multiple_valid = '{"verdict": "APPROVE"}\n{"verdict": "APPROVE"}'
    assert (
        engine.parse_verdict_line(multiple_valid, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )

    # 10. Valid terminal marker, but not on the last line
    not_last_line = '{"verdict": "APPROVE"}\nsome trailing text'
    assert (
        engine.parse_verdict_line(not_last_line, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED")
        == "REPAIR_REQUIRED"
    )
