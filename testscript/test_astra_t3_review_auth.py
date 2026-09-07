import time
from unittest.mock import MagicMock, patch

from alpha_core.queue.triage_queue import TriageStatus
from alpha_protocol.task import ReviewAttestation
from alpha_worker.senior_review_engine import SeniorReviewEngine


def test_valid_attestation_creation_and_verification():
    secret = b"test_secret"
    evidence = {"tests": 10, "passed": True}

    attestation = ReviewAttestation.create(
        task_id="tsk_123",
        result_sha="a" * 40,
        base_commit="b" * 40,
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=True,
        reviewed_at=time.time(),
        evidence=evidence,
        secret=secret,
    )

    assert attestation.verify(secret) is True


def test_tamper_detection():
    secret = b"test_secret"
    evidence = {"tests": 10, "passed": True}

    attestation = ReviewAttestation.create(
        task_id="tsk_123",
        result_sha="a" * 40,
        base_commit="b" * 40,
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=True,
        reviewed_at=time.time(),
        evidence=evidence,
        secret=secret,
    )

    # Modify result_sha
    attestation.result_sha = "c" * 40
    assert attestation.verify(secret) is False
    attestation.result_sha = "a" * 40

    # Modify base_commit
    attestation.base_commit = "c" * 40
    assert attestation.verify(secret) is False
    attestation.base_commit = "b" * 40

    # Modify pro_verdict
    attestation.pro_verdict = "REPAIR_REQUIRED"
    assert attestation.verify(secret) is False
    attestation.pro_verdict = "APPROVE"

    # Modify opus_verdict
    attestation.opus_verdict = "REJECT"
    assert attestation.verify(secret) is False
    attestation.opus_verdict = "FINAL_APPROVAL"

    # Modify evidence_digest
    attestation.evidence_digest = "c" * 64
    assert attestation.verify(secret) is False


def test_wrong_secret():
    secret = b"test_secret"
    wrong_secret = b"wrong_secret"
    evidence = {"tests": 10, "passed": True}

    attestation = ReviewAttestation.create(
        task_id="tsk_123",
        result_sha="a" * 40,
        base_commit="b" * 40,
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=True,
        reviewed_at=time.time(),
        evidence=evidence,
        secret=secret,
    )

    assert attestation.verify(wrong_secret) is False


@patch("alpha_worker.senior_review_engine.SeniorReviewEngine._invoke_agy")
def test_senior_review_engine_attestation(mock_invoke_agy):
    # Setup mock
    mock_invoke_agy.side_effect = [
        {"response": "", "structured_output": {"verdict": "APPROVE"}},
        {"response": "", "structured_output": {"verdict": "FINAL_APPROVAL"}}
    ]

    mock_queue = MagicMock()
    mock_task = {
        "status": TriageStatus.COMPLETED.value,
        "envelope": {"base_commit": "b" * 40},
        "result": {
            "gates_passed": True,
            "result_commit": "a" * 40,
            "gate_result": {"status": "passed"},
        },
    }
    mock_queue.get_task.return_value = mock_task

    engine = SeniorReviewEngine(queue=mock_queue, signing_secret=b"engine_secret")

    verdict = engine.execute_senior_review("tsk_123")

    assert verdict.approved is True
    assert verdict.attestation is not None

    # Verify the generated attestation
    att = ReviewAttestation(**verdict.attestation)
    assert att.verify(b"engine_secret") is True
    assert att.result_sha == "a" * 40
    assert att.base_commit == "b" * 40
    assert att.pro_verdict == "APPROVE"
    assert att.opus_verdict == "FINAL_APPROVAL"
