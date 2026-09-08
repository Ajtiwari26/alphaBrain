"""
Chaos Invariants Test Suite

Validates blast radius enforcement, tamper detection, circuit breaker trips,
lease epoch fencing, and secret redaction.
"""

import hashlib
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from alpha_core.healing.circuit_breaker import CircuitBreaker, CircuitBreakerState, TripReason
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue
from alpha_core.safety.gate import SafetyGate
from alpha_core.security import redact_secrets
from alpha_protocol import TaskEnvelope


def test_blast_radius_enforcement():
    """Verify that the SafetyGate enforces the exact blast radius boundary."""
    gate = SafetyGate(max_allowed_files=10)

    # 10 files should pass
    env_pass = TaskEnvelope(
        task_id="test_blast_pass",
        project_id="prj_test",
        objective="test",
        repo="local",
        base_commit="a" * 40,
        allowed_paths=tuple([f"file_{i}.py" for i in range(10)]),
    )
    verdict_pass = gate.evaluate_envelope(env_pass)
    assert verdict_pass.passed

    # 11 files should fail
    env_fail = TaskEnvelope(
        task_id="test_blast_fail",
        project_id="prj_test",
        objective="test",
        repo="local",
        base_commit="a" * 40,
        allowed_paths=tuple([f"file_{i}.py" for i in range(11)]),
    )
    verdict_fail = gate.evaluate_envelope(env_fail)
    assert not verdict_fail.passed
    assert "Blast radius violation" in verdict_fail.reason


def test_tamper_detection():
    """Verify that tampering with task JSON after hash computation is detectable."""
    env = {
        "task_id": "tamper_task",
        "objective": "Benign task",
        "repo": "local",
        "base_commit": "a" * 40,
        "allowed_paths": ["safe.py"],
    }
    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    original_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()

    prov = TaskProvenance(
        meeting_id="meet_1",
        speaker_id="speaker_1",
        utterance_timestamp=time.time(),
        transcript_excerpt="test",
        extraction_model="test",
        extraction_confidence=1.0,
        eva_session_id="session_1",
        created_at=time.time(),
        content_hash=original_hash,
    )

    # Tamper the envelope payload before enqueuing
    tampered_env = dict(env)
    tampered_env["allowed_paths"] = ["safe.py", "/etc/shadow", "malicious.py"]

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_queue.sqlite3"
        queue = TaskTriageQueue(db_path=str(db_path))

        import pytest

        with pytest.raises(ValueError, match="Content hash mismatch"):
            # Enqueueing with the original provenance hash but a tampered envelope
            # should trigger the application-level tamper rejection.
            queue.enqueue_task("tamper_task", tampered_env, prov)


def test_circuit_breaker_trips():
    """Verify that the circuit breaker trips and resets appropriately."""
    cb = CircuitBreaker(max_identical_signatures=2, reset_timeout_sec=0.1)

    # 1. Different signatures remain CLOSED
    cb.record_failure("error_signature_1")
    assert cb.state == CircuitBreakerState.CLOSED
    cb.record_failure("error_signature_2")
    assert cb.state == CircuitBreakerState.CLOSED

    # 2. Repeated identical failures trip to OPEN
    cb.record_failure("error_signature_2")
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.trip_reason == TripReason.ESCALATED_HUMAN_REVIEW

    # 3. Time passage transitions to HALF_OPEN
    time.sleep(0.3)
    cb.record_failure("error_signature_3")
    # A failure in HALF_OPEN trips immediately back to OPEN
    assert cb.state == CircuitBreakerState.OPEN

    # 4. Success transitions to CLOSED
    time.sleep(0.3)
    assert cb.can_attempt()  # triggers internal _update_state to HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED


def test_secret_redaction():
    """Verify that secrets are correctly redacted from text."""
    raw_log = "Error accessing API with token=sk-live-12345ABCD and secret=my-super-secret in url"
    redacted = redact_secrets(raw_log)
    assert "sk-live-12345" not in redacted
    assert "my-super-secret" not in redacted
    assert "[REDACTED]" in redacted


def test_lease_epoch_fencing():
    """Verify that completing a task requires matching fencing epoch."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_queue.sqlite3"
        queue = TaskTriageQueue(db_path=str(db_path))

        env = {
            "task_id": "lease_task",
            "objective": "Lease task",
            "repo": "local",
            "base_commit": "a" * 40,
            "allowed_paths": [],
        }
        env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
        content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
        prov = TaskProvenance(
            meeting_id="meet_1",
            speaker_id="speaker_1",
            utterance_timestamp=time.time(),
            transcript_excerpt="test",
            extraction_model="test",
            extraction_confidence=1.0,
            eva_session_id="session_1",
            created_at=time.time(),
            content_hash=content_hash,
        )

        queue.enqueue_task("lease_task", env, prov)
        queue.approve_task("lease_task")

        leased = queue.lease_next_approved_task()
        assert leased is not None

        worker_id = leased["worker_id"]
        attempt_id = leased["attempt_id"]
        lease_id = leased["lease_id"]
        fencing_epoch = leased["fencing_epoch"]

        # Wrong epoch
        success_wrong_epoch = queue.complete_task(
            "lease_task",
            result={"status": "done"},
            worker_id=worker_id,
            attempt_id=attempt_id,
            lease_id=lease_id,
            fencing_epoch=fencing_epoch + 1,
        )
        assert not success_wrong_epoch, "Completed task with wrong fencing epoch"

        # Correct epoch
        success_correct_epoch = queue.complete_task(
            "lease_task",
            result={"status": "done"},
            worker_id=worker_id,
            attempt_id=attempt_id,
            lease_id=lease_id,
            fencing_epoch=fencing_epoch,
        )
        assert success_correct_epoch, "Failed to complete task with correct epoch"
