import json
from unittest.mock import MagicMock, patch

from alpha_core.healing.circuit_breaker import CircuitBreaker, CircuitBreakerState, TripReason
from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_worker.ci_healing_daemon import CIHealingDaemon


def test_circuit_breaker_serialization_roundtrip():
    cb = CircuitBreaker(max_identical_signatures=3, max_attempts=5)
    cb.record_failure("SIG_TEST_001")
    assert cb.attempts == 1
    assert cb.identical_count == 1
    assert cb.last_signature == "SIG_TEST_001"

    data = cb.to_dict()
    assert isinstance(data, dict)
    assert data["attempts"] == 1
    assert data["last_signature"] == "SIG_TEST_001"
    assert data["state"] == CircuitBreakerState.CLOSED.value

    restored = CircuitBreaker.from_dict(data)
    assert restored.attempts == 1
    assert restored.identical_count == 1
    assert restored.last_signature == "SIG_TEST_001"
    assert restored.state == CircuitBreakerState.CLOSED
    assert restored.trip_reason == TripReason.NONE


def test_queue_circuit_breaker_persistence(tmp_path):
    db_file = tmp_path / "test_queue.db"
    queue1 = TaskTriageQueue(db_path=db_file)

    cb = CircuitBreaker()
    cb.record_failure("SIG_DATABASE_LOCK")
    queue1.save_circuit_breaker("task_root_001", cb.to_dict())

    # Create a completely new queue instance simulating daemon restart
    queue2 = TaskTriageQueue(db_path=db_file)
    loaded_data = queue2.get_circuit_breaker("task_root_001")
    assert loaded_data is not None

    restored_cb = CircuitBreaker.from_dict(loaded_data)
    assert restored_cb.attempts == 1
    assert restored_cb.last_signature == "SIG_DATABASE_LOCK"


def test_daemon_restart_preserves_failure_attempts(tmp_path):
    db_file = tmp_path / "triage.db"
    queue = TaskTriageQueue(db_path=db_file)

    daemon1 = CIHealingDaemon(queue=queue, project_id="prj_test")

    # Simulate failure handling in daemon 1
    cb_dict = daemon1.queue.get_circuit_breaker("tsk_abc_123")
    cb1 = __import__("alpha_core.healing.circuit_breaker", fromlist=["CircuitBreaker"]).CircuitBreaker.from_dict(cb_dict) if cb_dict else __import__("alpha_core.healing.circuit_breaker", fromlist=["CircuitBreaker"]).CircuitBreaker()
    cb1.record_failure("SIG_TIMEOUT_ERR")
    queue.save_circuit_breaker("tsk_abc_123", cb1.to_dict())

    assert cb1.attempts == 1

    # Simulate daemon crash / restart: daemon 2 starts fresh with no in-memory state
    daemon2 = CIHealingDaemon(queue=queue, project_id="prj_test")

    # Probe should NOT reset 1 -> 0; child repair should look up root_id and resume at 1
    cb_dict2 = daemon2.queue.get_circuit_breaker("tsk_abc_123")
    cb2 = __import__("alpha_core.healing.circuit_breaker", fromlist=["CircuitBreaker"]).CircuitBreaker.from_dict(cb_dict2) if cb_dict2 else __import__("alpha_core.healing.circuit_breaker", fromlist=["CircuitBreaker"]).CircuitBreaker()
    assert cb2.attempts == 1
    assert cb2.last_signature == "SIG_TIMEOUT_ERR"

    # Second failure should increment to 2
    cb2.record_failure("SIG_TIMEOUT_ERR")
    queue.save_circuit_breaker("tsk_abc_123_repair_1", cb2.to_dict())
    assert cb2.attempts == 2
    assert cb2.identical_count == 2


@patch("alpha_worker.ci_healing_daemon.subprocess.run")
def test_failed_senior_review_does_not_suppress_retries(mock_run, tmp_path):
    db_file = tmp_path / "triage.db"
    queue = TaskTriageQueue(db_path=db_file)
    daemon = CIHealingDaemon(queue=queue, project_id="prj_test")

    # Senior review process exits with error
    mock_run.return_value = MagicMock(returncode=1, stderr="Subprocess review failed", stdout="")

    task = {"id": "tsk_completed_001"}
    daemon.process_completed_task(task)

    # Must NOT enter processed_tasks
    assert not daemon.is_task_processed("tsk_completed_001")

    # Senior review unapproved verdict
    mock_run.return_value = MagicMock(
        returncode=0,
        stderr="",
        stdout=json.dumps({"approved": False, "verdict": "REPAIR_REQUIRED"}),
    )
    daemon.process_completed_task(task)
    assert not daemon.is_task_processed("tsk_completed_001")


@patch("alpha_worker.ci_healing_daemon.subprocess.run")
def test_failed_merge_does_not_suppress_retries(mock_run, tmp_path):
    db_file = tmp_path / "triage.db"
    queue = TaskTriageQueue(db_path=db_file)
    daemon = CIHealingDaemon(queue=queue, project_id="prj_test")

    def side_effect(cmd, **kwargs):
        if "senior-review" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps({"approved": True}), stderr="")
        if "merge" in cmd:
            return MagicMock(returncode=1, stderr="Git merge conflict on main", stdout="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect

    task = {"id": "tsk_completed_002"}
    daemon.process_completed_task(task)

    # Must NOT enter processed_tasks because merge failed
    assert not daemon.is_task_processed("tsk_completed_002")


@patch("alpha_worker.ci_healing_daemon.subprocess.run")
def test_successful_merge_enters_processed_tasks_and_resets_cb(mock_run, tmp_path):
    db_file = tmp_path / "triage.db"
    queue = TaskTriageQueue(db_path=db_file)
    daemon = CIHealingDaemon(queue=queue, project_id="prj_test")

    # Pre-record a failure attempt on this root task
    cb_dict3 = daemon.queue.get_circuit_breaker("tsk_completed_003")
    cb = __import__("alpha_core.healing.circuit_breaker", fromlist=["CircuitBreaker"]).CircuitBreaker.from_dict(cb_dict3) if cb_dict3 else __import__("alpha_core.healing.circuit_breaker", fromlist=["CircuitBreaker"]).CircuitBreaker()
    cb.record_failure("SIG_PREV_ERR")
    queue.save_circuit_breaker("tsk_completed_003", cb.to_dict())
    assert cb.attempts == 1

    def side_effect(cmd, **kwargs):
        if "senior-review" in cmd:
            return MagicMock(returncode=0, stdout=json.dumps({"approved": True}), stderr="")
        if "merge" in cmd:
            return MagicMock(returncode=0, stdout="Merge successful", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect

    task = {"id": "tsk_completed_003"}
    daemon.process_completed_task(task)

    # Successful merge MUST enter processed_tasks
    assert daemon.is_task_processed("tsk_completed_003")

    # And circuit breaker must be reset
    saved_cb_data = queue.get_circuit_breaker("tsk_completed_003")
    assert saved_cb_data is not None
    assert saved_cb_data["attempts"] == 0
    assert saved_cb_data["state"] == CircuitBreakerState.CLOSED.value
