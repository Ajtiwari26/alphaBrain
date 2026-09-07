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
        attempt_id="att_1",
        tree_digest="c" * 40,
        nonce="nonce",
        executor_id="worker",
        key_id="alpha_test_key",
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
        attempt_id="att_1",
        tree_digest="c" * 40,
        nonce="nonce",
        executor_id="worker",
        key_id="alpha_test_key",
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
        attempt_id="att_1",
        tree_digest="c" * 40,
        nonce="nonce",
        executor_id="worker",
        key_id="alpha_test_key",
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=True,
        reviewed_at=time.time(),
        evidence=evidence,
        secret=secret,
    )

    assert attestation.verify(wrong_secret) is False


@patch("alpha_worker.senior_review_engine.SeniorReviewEngine._invoke_agy")
def test_senior_review_engine_attestation(mock_invoke_agy, tmp_path):
    # Setup mock
    mock_invoke_agy.side_effect = [
        {"response": "", "structured_output": {"verdict": "APPROVE"}},
        {"response": "", "structured_output": {"verdict": "FINAL_APPROVAL"}},
    ]

    mock_queue = MagicMock()
    mock_task = {
        "status": TriageStatus.COMPLETED.value,
        "worktree_path": str(tmp_path),
        "envelope": {"base_commit": "b" * 40},
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_commit": "a" * 40,
            "gate_result": {"status": "passed"},
        },
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
                "lease_id": "lease_123",
                "fencing_epoch": 1,
            }
        },
    }
    mock_queue.get_task.return_value = mock_task

    with patch("subprocess.check_output") as mock_git:

        def fake_git(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                return "a" * 40 + "\n"
            if cmd[:2] == ["git", "status"]:
                return ""
            return ""

        mock_git.side_effect = fake_git

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


def test_senior_review_engine_rejects_missing_signing_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPHA_SIGNING_SECRET_alpha_test_key", raising=False)
    mock_queue = MagicMock()
    mock_queue.get_task.return_value = {
        "status": TriageStatus.COMPLETED.value,
        "worktree_path": str(tmp_path),
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "a" * 40,
        },
    }
    engine = SeniorReviewEngine(queue=mock_queue, signing_secret=None, key_id="alpha_test_key")
    import pytest

    with pytest.raises(ValueError, match="Missing signing secret for key"):
        engine.execute_senior_review("tsk_123")


def test_senior_review_engine_rejects_missing_or_nonexistent_worktree():
    mock_queue = MagicMock()
    mock_queue.get_task.return_value = {
        "status": TriageStatus.COMPLETED.value,
        "worktree_path": "/nonexistent/path/to/worktree",
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "a" * 40,
        },
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
                "lease_id": "lease_123",
                "fencing_epoch": 1,
            }
        },
    }
    engine = SeniorReviewEngine(queue=mock_queue, signing_secret="secret123")
    import pytest

    with pytest.raises(ValueError, match="Mandatory checkout validation failed"):
        engine.execute_senior_review("tsk_123")


def test_senior_review_engine_rejects_dirty_worktree(tmp_path):
    mock_queue = MagicMock()
    mock_queue.get_task.return_value = {
        "status": TriageStatus.COMPLETED.value,
        "worktree_path": str(tmp_path),
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "a" * 40,
        },
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
                "lease_id": "lease_123",
                "fencing_epoch": 1,
            }
        },
    }
    engine = SeniorReviewEngine(queue=mock_queue, signing_secret="secret123")

    with patch("subprocess.check_output") as mock_git:

        def fake_git(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                return "a" * 40 + "\n"
            if cmd[:2] == ["git", "status"]:
                return " M dirty_file.py\n"
            return ""

        mock_git.side_effect = fake_git

        import pytest

        with pytest.raises(ValueError, match="Worktree is not clean"):
            engine.execute_senior_review("tsk_123")


def test_senior_review_engine_rejects_worktree_head_mismatch(tmp_path):
    mock_queue = MagicMock()
    mock_queue.get_task.return_value = {
        "status": TriageStatus.COMPLETED.value,
        "worktree_path": str(tmp_path),
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "a" * 40,
        },
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
                "lease_id": "lease_123",
                "fencing_epoch": 1,
            }
        },
    }
    engine = SeniorReviewEngine(queue=mock_queue, signing_secret="secret123")

    with patch("subprocess.check_output") as mock_git:

        def fake_git(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                return "b" * 40 + "\n"  # Mismatch with result_sha
            if cmd[:2] == ["git", "status"]:
                return ""
            return ""

        mock_git.side_effect = fake_git

        import pytest

        with pytest.raises(ValueError, match="does not match task result_sha"):
            engine.execute_senior_review("tsk_123")


def test_reproduce_unreachable_checks_in_cmd_merge():
    """
    Reproduce that cmd_merge must independently reject validly signed attestations
    that have wrong task_id, wrong result_sha, wrong base_commit, approved=False,
    or mismatched evidence digest.
    """
    import argparse

    from alpha_core.triage_cli import cmd_merge

    secret = "temp_test_secret_12345"
    task_id = "tsk_test_merge_auth"
    base_commit = "1" * 40
    result_sha = "2" * 40
    evidence = {"test_runs": 5, "passed": True}

    import uuid

    def make_task_and_att(
        att_task_id=task_id,
        att_result_sha=result_sha,
        att_base_commit=base_commit,
        attempt_id="att_1",
        tree_digest="t" * 40,
        nonce=None,
        executor_id="exec_1",
        key_id="alpha_test_key",
        att_approved=True,
        att_pro="APPROVE",
        att_opus="FINAL_APPROVAL",
        att_evidence=evidence,
        corrupt_sig=False,
    ):
        nonce = nonce or uuid.uuid4().hex
        att = ReviewAttestation.create(
            task_id=att_task_id,
            attempt_id="att_1",
            result_sha=att_result_sha,
            base_commit=att_base_commit,
            tree_digest="c" * 40,
            pro_verdict=att_pro,
            opus_verdict=att_opus,
            approved=att_approved,
            reviewed_at=time.time(),
            evidence=att_evidence,
            secret=secret,
            nonce=nonce,
            executor_id=executor_id,
            key_id=key_id,
        )
        if corrupt_sig:
            att.signature = "0" * 64

        task = {
            "id": task_id,
            "status": TriageStatus.COMPLETED.value,
            "branch_name": f"alpha/{task_id}",
            "worktree_path": f"/tmp/worktrees/{task_id}",
            "envelope": {
                "repo": ".",
                "base_commit": base_commit,
            },
            "result": {
                "gates_passed": True,
                "attempt_id": "att_1",
                "worker_id": "exec_1",
                "result_sha": result_sha,
                "evidence": evidence,
                "senior_review": {
                    "approved": True,  # Outer task approved is True to strictly isolate attestation validation
                    "attestation": att.model_dump(),
                },
            },
            "provenance": {
                "lease_metadata": {
                    "worker_id": "exec_1",
                    "attempt_id": "att_1",
                    "lease_id": "lease_123",
                    "fencing_epoch": 1,
                }
            },
        }
        return task

    args = argparse.Namespace(task_id=task_id, json=False)

    def assert_zero_mutating_git(mock_run):
        for call in mock_run.call_args_list:
            cmd = call[0][0] if call[0] else []
            if cmd and cmd[0] == "git":
                assert cmd[1] not in ["merge", "checkout", "branch", "worktree"], (
                    f"Forbidden mutating Git command executed on rejection: {cmd}"
                )

    with patch.dict("os.environ", {"ALPHA_SIGNING_SECRET_alpha_test_key": secret}):
        with patch("subprocess.run") as mock_run:
            # Mock git rev-parse to return matching result_sha
            def fake_git(cmd, **kwargs):
                m = MagicMock()
                if cmd[:2] == ["git", "rev-parse"]:
                    if "^{tree}" in cmd[2]:
                        m.stdout = "c" * 40 + "\n"
                    else:
                        m.stdout = result_sha + "\n"
                    m.returncode = 0
                    return m
                m.stdout = ""
                m.returncode = 0
                return m

            mock_run.side_effect = fake_git

            # Case 1: Wrong task_id in attestation (signed with secret)
            mock_run.reset_mock()
            q = MagicMock()
            q.get_task.return_value = make_task_and_att(att_task_id="tsk_WRONG_TASK")
            assert cmd_merge(args, q) == 1, "Must reject attestation with wrong task_id"
            assert_zero_mutating_git(mock_run)

            # Case 2: Wrong result_sha in attestation (signed with secret)
            mock_run.reset_mock()
            q = MagicMock()
            q.get_task.return_value = make_task_and_att(att_result_sha="3" * 40)
            assert cmd_merge(args, q) == 1, "Must reject attestation with wrong result_sha"
            assert_zero_mutating_git(mock_run)

            # Case 3: Wrong base_commit in attestation (signed with secret)
            mock_run.reset_mock()
            q = MagicMock()
            q.get_task.return_value = make_task_and_att(att_base_commit="4" * 40)
            assert cmd_merge(args, q) == 1, "Must reject attestation with wrong base_commit"
            assert_zero_mutating_git(mock_run)

            # Case 4: Approved is False in attestation (signed with secret, outer task approved=True)
            mock_run.reset_mock()
            q = MagicMock()
            q.get_task.return_value = make_task_and_att(
                att_approved=False, att_pro="REPAIR_REQUIRED", att_opus="REJECT"
            )
            assert cmd_merge(args, q) == 1, (
                "Must reject attestation when attestation approved is False"
            )
            assert_zero_mutating_git(mock_run)

            # Case 5: Inconsistent verdicts (e.g. approved=True but pro='REPAIR_REQUIRED')
            mock_run.reset_mock()
            q = MagicMock()
            q.get_task.return_value = make_task_and_att(
                att_approved=True, att_pro="REPAIR_REQUIRED", att_opus="FINAL_APPROVAL"
            )
            assert cmd_merge(args, q) == 1, "Must reject attestation with inconsistent pro verdict"
            assert_zero_mutating_git(mock_run)

            # Case 6: Evidence digest mismatch (signed with secret)
            mock_run.reset_mock()
            q = MagicMock()
            q.get_task.return_value = make_task_and_att(
                att_evidence={"tampered_evidence": "different"}
            )
            assert cmd_merge(args, q) == 1, (
                "Must reject attestation with mismatched evidence digest"
            )
            assert_zero_mutating_git(mock_run)

            # Case 7: Valid attestation passes
            mock_run.reset_mock()
            q = MagicMock()
            q.get_task.return_value = make_task_and_att()
            with patch("fcntl.flock"):
                assert cmd_merge(args, q) == 0, "Valid attestation must pass"


def make_standalone_task_and_att(
    task_id, attempt_id, nonce, key_id, repo_path, secret="test_secret_123"
):
    import time

    from alpha_core.queue.triage_queue import TriageStatus
    from alpha_protocol.task import ReviewAttestation

    att_dict = ReviewAttestation.create(
        task_id=task_id,
        attempt_id=attempt_id,
        result_sha="2" * 40,
        base_commit="1" * 40,
        tree_digest="c" * 40,
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=True,
        reviewed_at=time.time(),
        evidence={},
        secret=secret,
        nonce=nonce,
        executor_id="exec_1",
        key_id=key_id,
        reviewer_id="SYSTEM_SENIOR_REVIEW_ENGINE",
    )

    t = {
        "id": task_id,
        "status": TriageStatus.COMPLETED.value,
        "branch_name": f"alpha/{task_id}",
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "2" * 40,
            "evidence": {},
            "senior_review": {"approved": True, "attestation": att_dict},
        },
        "envelope": {"repo": str(repo_path), "base_commit": "1" * 40},
    }
    return t


def test_attestation_expiration_rejected():
    import time

    import pytest
    from pydantic import ValidationError

    from alpha_protocol.task import ReviewAttestation

    with pytest.raises(ValidationError) as exc_info:
        ReviewAttestation.create(
            task_id="tsk_1",
            attempt_id="att_1",
            result_sha="2" * 40,
            base_commit="1" * 40,
            tree_digest="c" * 40,
            pro_verdict="APPROVE",
            opus_verdict="FINAL_APPROVAL",
            approved=True,
            reviewed_at=time.time(),
            issued_at=time.time() - 7200,
            expires_at=time.time() - 3600,
            evidence={},
            secret="test_secret",
            nonce="nonce",
            executor_id="exec_1",
            key_id="alpha_test_key",
        )
    assert "Attestation has expired" in str(exc_info.value)


def test_principal_collision_rejected():
    import time

    import pytest
    from pydantic import ValidationError

    from alpha_protocol.task import ReviewAttestation

    with pytest.raises(ValidationError) as exc_info:
        ReviewAttestation.create(
            task_id="tsk_1",
            attempt_id="att_1",
            result_sha="2" * 40,
            base_commit="1" * 40,
            tree_digest="c" * 40,
            pro_verdict="APPROVE",
            opus_verdict="FINAL_APPROVAL",
            approved=True,
            reviewed_at=time.time(),
            evidence={},
            secret="test_secret",
            nonce="nonce",
            executor_id="SYSTEM_SENIOR_REVIEW_ENGINE",
            reviewer_id="SYSTEM_SENIOR_REVIEW_ENGINE",
            key_id="alpha_test_key",
        )
    assert "Principal separation failed" in str(exc_info.value)


def fake_git_for_tests(cmd, **kwargs):
    from unittest.mock import MagicMock

    m = MagicMock()
    if cmd[:2] == ["git", "rev-parse"]:
        if "^{tree}" in cmd[2]:
            m.stdout = "c" * 40 + "\n"
        else:
            m.stdout = "2" * 40 + "\n"
        m.returncode = 0
        return m
    m.stdout = ""
    m.returncode = 0
    return m


def test_replay_attack_rejected(monkeypatch, tmp_path):
    import argparse
    from unittest.mock import MagicMock, patch

    from alpha_core.triage_cli import cmd_merge

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    nonce_file = repo_path / ".alphabrain" / "seen_nonces.txt"
    nonce_file.parent.mkdir(parents=True)
    nonce_file.write_text("my_test_nonce\n")

    args = argparse.Namespace(task_id="tsk_test_merge_auth", json=False)
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_secret_123")

    q = MagicMock()
    q.get_task.return_value = make_standalone_task_and_att(
        task_id="tsk_test_merge_auth",
        attempt_id="att_1",
        nonce="my_test_nonce",
        key_id="alpha_test_key",
        repo_path=str(repo_path),
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = fake_git_for_tests
        assert cmd_merge(args, q) == 1


def test_key_revocation_rejected(monkeypatch, tmp_path):
    import argparse
    from unittest.mock import MagicMock, patch

    from alpha_core.triage_cli import cmd_merge

    args = argparse.Namespace(task_id="tsk_test_merge_auth", json=False)
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_secret_123")
    monkeypatch.setenv("ALPHA_REVOKED_KEYS", "k1,bad_key")

    q = MagicMock()
    q.get_task.return_value = make_standalone_task_and_att(
        task_id="tsk_test_merge_auth",
        attempt_id="att_1",
        nonce="some_other_nonce",
        key_id="alpha_test_key",
        repo_path=str(tmp_path),
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = fake_git_for_tests
        assert cmd_merge(args, q) == 1


def test_attestation_exact_expiry_rejected():
    import time

    import pytest
    from pydantic import ValidationError

    from alpha_protocol.task import ReviewAttestation

    now = time.time()
    with pytest.raises(ValidationError, match="Attestation has expired"):
        with patch("time.time", return_value=now):
            ReviewAttestation.create(
                task_id="tsk_1",
                attempt_id="att_1",
                result_sha="2" * 40,
                base_commit="1" * 40,
                tree_digest="c" * 40,
                pro_verdict="APPROVE",
                opus_verdict="FINAL_APPROVAL",
                approved=True,
                reviewed_at=now - 5,
                issued_at=now - 10,
                expires_at=now,
                evidence={},
                secret="test_secret",
                nonce="nonce",
                executor_id="exec_1",
                key_id="alpha_test_key",
            )


def test_attestation_future_issued_rejected():
    import time

    import pytest
    from pydantic import ValidationError

    from alpha_protocol.task import ReviewAttestation

    now = time.time()
    with pytest.raises(ValidationError, match="Attestation issued in the future"):
        ReviewAttestation.create(
            task_id="tsk_1",
            attempt_id="att_1",
            result_sha="2" * 40,
            base_commit="1" * 40,
            tree_digest="c" * 40,
            pro_verdict="APPROVE",
            opus_verdict="FINAL_APPROVAL",
            approved=True,
            reviewed_at=now,
            issued_at=now + 65.0,
            expires_at=now + 3600.0,
            evidence={},
            secret="test",
            nonce="nonce",
            executor_id="exec_1",
            key_id="alpha_test_key",
        )


def test_attestation_non_finite_timestamps_rejected():
    import math
    import time

    import pytest
    from pydantic import ValidationError

    from alpha_protocol.task import ReviewAttestation

    now = time.time()
    with pytest.raises(ValidationError, match="Timestamps must be finite"):
        ReviewAttestation.create(
            task_id="tsk_1",
            attempt_id="att_1",
            result_sha="2" * 40,
            base_commit="1" * 40,
            tree_digest="c" * 40,
            pro_verdict="APPROVE",
            opus_verdict="FINAL_APPROVAL",
            approved=True,
            reviewed_at=now,
            issued_at=now,
            expires_at=math.inf,
            evidence={},
            secret="test",
            nonce="nonce",
            executor_id="exec_1",
            key_id="alpha_test_key",
        )


def test_attestation_ttl_bounds_rejected():
    import time

    import pytest
    from pydantic import ValidationError

    from alpha_protocol.task import ReviewAttestation

    now = time.time()
    with pytest.raises(ValidationError, match=r"TTL must be between 10\.0 and 7200\.0 seconds"):
        ReviewAttestation.create(
            task_id="tsk_1",
            attempt_id="att_1",
            result_sha="2" * 40,
            base_commit="1" * 40,
            tree_digest="c" * 40,
            pro_verdict="APPROVE",
            opus_verdict="FINAL_APPROVAL",
            approved=True,
            reviewed_at=now,
            issued_at=now,
            expires_at=now + 5.0,  # Too short
            evidence={},
            secret="test",
            nonce="nonce",
            executor_id="exec_1",
            key_id="alpha_test_key",
        )

    with pytest.raises(ValidationError, match=r"TTL must be between 10\.0 and 7200\.0 seconds"):
        ReviewAttestation.create(
            task_id="tsk_1",
            attempt_id="att_1",
            result_sha="2" * 40,
            base_commit="1" * 40,
            tree_digest="c" * 40,
            pro_verdict="APPROVE",
            opus_verdict="FINAL_APPROVAL",
            approved=True,
            reviewed_at=now,
            issued_at=now,
            expires_at=now + 8000.0,  # Too long
            evidence={},
            secret="test",
            nonce="nonce",
            executor_id="exec_1",
            key_id="alpha_test_key",
        )


def test_cmd_merge_unknown_key_rejected(monkeypatch, tmp_path):
    import argparse
    from unittest.mock import MagicMock, patch

    from alpha_core.triage_cli import cmd_merge

    args = argparse.Namespace(task_id="tsk_test_merge_auth", json=False)
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_secret_123")

    q = MagicMock()
    q.get_task.return_value = make_standalone_task_and_att(
        task_id="tsk_test_merge_auth",
        attempt_id="att_1",
        nonce="my_test_nonce",
        key_id="unknown_key_123",
        repo_path=str(tmp_path),
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = fake_git_for_tests
        assert cmd_merge(args, q) == 1


def test_cmd_merge_missing_attempt_or_worker_rejected(monkeypatch, tmp_path):
    import argparse
    import time
    from unittest.mock import MagicMock, patch

    from alpha_core.queue.triage_queue import TriageStatus
    from alpha_core.triage_cli import cmd_merge
    from alpha_protocol.task import ReviewAttestation

    args = argparse.Namespace(task_id="tsk_test_merge_auth", json=False)
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_secret_123")

    att_dict = ReviewAttestation.create(
        task_id="tsk_test_merge_auth",
        attempt_id="att_1",
        result_sha="2" * 40,
        base_commit="1" * 40,
        tree_digest="c" * 40,
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=True,
        reviewed_at=time.time(),
        evidence={},
        secret="test_secret_123",
        nonce="n1",
        executor_id="exec_1",
        key_id="alpha_test_key",
        reviewer_id="SYSTEM_SENIOR_REVIEW_ENGINE",
    ).model_dump()

    # 1. Missing attempt_id in result
    t = {
        "id": "tsk_test_merge_auth",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/tsk_test_merge_auth",
        "result": {
            "gates_passed": True,
            "worker_id": "exec_1",
            "result_sha": "2" * 40,
            "evidence": {},
            "senior_review": {"approved": True, "attestation": att_dict},
        },
        "envelope": {"repo": str(tmp_path), "base_commit": "1" * 40},
    }

    q = MagicMock()
    q.get_task.return_value = t

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = fake_git_for_tests
        # Missing attempt_id -> rejected
        assert cmd_merge(args, q) == 1

        # Missing worker_id -> rejected
        t["result"]["attempt_id"] = "att_1"
        del t["result"]["worker_id"]
        assert cmd_merge(args, q) == 1

        # Placeholder worker_id -> rejected
        t["result"]["worker_id"] = "worker_unknown"
        assert cmd_merge(args, q) == 1

        # Placeholder attempt_id -> rejected
        t["result"]["worker_id"] = "exec_1"
        t["result"]["attempt_id"] = "att_unknown"
        assert cmd_merge(args, q) == 1

        # Mismatched attempt_id -> rejected
        t["result"]["attempt_id"] = "att_mismatch"
        assert cmd_merge(args, q) == 1


def test_cmd_merge_freshness_revalidation_failure(monkeypatch, tmp_path):
    import argparse
    import time
    from unittest.mock import MagicMock, patch

    from alpha_core.queue.triage_queue import TriageStatus
    from alpha_core.triage_cli import cmd_merge
    from alpha_protocol.task import ReviewAttestation

    args = argparse.Namespace(task_id="tsk_test_merge_auth", json=False)
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_secret_123")

    now = time.time()

    with patch("time.time", return_value=now - 2000.0):
        # Create an attestation that is signed 2000s ago, expiring in 1000s. (So currently expired).
        att_dict = ReviewAttestation.create(
            task_id="tsk_test_merge_auth",
            attempt_id="att_1",
            result_sha="2" * 40,
            base_commit="1" * 40,
            tree_digest="c" * 40,
            pro_verdict="APPROVE",
            opus_verdict="FINAL_APPROVAL",
            approved=True,
            reviewed_at=now - 2000.0,
            issued_at=now - 2000.0,
            expires_at=now - 1000.0,  # Expires before now
            evidence={},
            secret="test_secret_123",
            nonce="n1",
            executor_id="exec_1",
            key_id="alpha_test_key",
            reviewer_id="SYSTEM_SENIOR_REVIEW_ENGINE",
        ).model_dump()

    t = {
        "id": "tsk_test_merge_auth",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/tsk_test_merge_auth",
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "2" * 40,
            "evidence": {},
            "senior_review": {"approved": True, "attestation": att_dict},
        },
        "envelope": {"repo": str(tmp_path), "base_commit": "1" * 40},
    }

    q = MagicMock()
    q.get_task.return_value = t

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = fake_git_for_tests
        assert cmd_merge(args, q) == 1


def test_senior_review_engine_purges_all_signing_secrets_from_agy_subprocess(monkeypatch, tmp_path):
    from unittest.mock import MagicMock, patch

    from alpha_worker.senior_review_engine import SeniorReviewEngine

    monkeypatch.setenv("ALPHA_SIGNING_SECRET", "generic_secret")
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_production_v1", "prod_secret_123")
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_secret_456")
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_custom", "custom_secret_789")
    monkeypatch.setenv("ALPHA_SAFE_VAR", "safe_value")

    schema_file = tmp_path / "schema.json"
    schema_file.write_text("{}")

    engine = SeniorReviewEngine(queue=MagicMock())
    captured_env = None

    def fake_subprocess_run(cmd, **kwargs):
        nonlocal captured_env
        captured_env = kwargs.get("env")
        m = MagicMock()
        m.returncode = 0
        m.stdout = '{"verdict": "APPROVE"}'
        m.stderr = ""
        return m

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        engine._invoke_agy(
            prompt="test prompt",
            model="gemini-3.1-pro-high",
            schema_path=str(schema_file),
            cwd=str(tmp_path),
        )

    assert captured_env is not None
    assert captured_env.get("ALPHA_SAFE_VAR") == "safe_value"
    # Ensure zero signing secrets leaked to AGY subprocess
    signing_keys_leaked = [k for k in captured_env if k.startswith("ALPHA_SIGNING_SECRET")]
    assert signing_keys_leaked == [], f"Found leaked signing secrets: {signing_keys_leaked}"


def test_lease_metadata_ownership_binding_in_review_and_merge(tmp_path, monkeypatch):
    import argparse
    import time
    from unittest.mock import MagicMock, patch

    import pytest

    from alpha_core.queue.triage_queue import TriageStatus
    from alpha_core.triage_cli import cmd_merge
    from alpha_protocol.task import ReviewAttestation
    from alpha_worker.senior_review_engine import SeniorReviewEngine

    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_secret_123")

    task_record = {
        "id": "tsk_lease_test",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/tsk_lease_test",
        "worktree_path": str(tmp_path),
        "envelope": {"repo": str(tmp_path), "base_commit": "a" * 40},
        "provenance": {
            "lease_metadata": {
                "worker_id": "auth_worker_real",
                "attempt_id": "auth_att_real",
                "lease_id": "lease_123",
                "fencing_epoch": 123456,
            }
        },
        "result": {
            "gates_passed": True,
            "worker_id": "forged_worker_fake",
            "attempt_id": "auth_att_real",
            "result_sha": "b" * 40,
            "evidence": {},
        },
    }

    mock_queue = MagicMock()
    mock_queue.get_task.return_value = task_record

    engine = SeniorReviewEngine(
        queue=mock_queue, key_id="alpha_test_key", signing_secret="test_secret_123"
    )

    def fake_git_checkout(cmd, **kwargs):
        if cmd[:2] == ["git", "rev-parse"]:
            return "b" * 40 + "\n"
        if cmd[:2] == ["git", "status"]:
            return ""
        return ""

    with (
        patch("subprocess.check_output", side_effect=fake_git_checkout),
        patch.object(
            SeniorReviewEngine,
            "_invoke_agy",
            return_value={"response": "", "structured_output": {"verdict": "APPROVE"}},
        ),
    ):
        # Senior review must reject execution when worker_id mismatches authoritative lease provenance
        with pytest.raises(ValueError, match="does not match authoritative lease worker_id"):
            engine.execute_senior_review("tsk_lease_test")

        # Now fix result worker_id but tamper attempt_id
        task_record["result"]["worker_id"] = "auth_worker_real"
        task_record["result"]["attempt_id"] = "forged_att_fake"
        with pytest.raises(ValueError, match="does not match authoritative lease attempt_id"):
            engine.execute_senior_review("tsk_lease_test")

    # Now verify cmd_merge also strictly enforces authoritative lease metadata
    att_dict = ReviewAttestation.create(
        task_id="tsk_lease_test",
        attempt_id="forged_att_fake",
        result_sha="b" * 40,
        base_commit="a" * 40,
        tree_digest="c" * 40,
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=True,
        reviewed_at=time.time(),
        evidence={},
        secret="test_secret_123",
        nonce="nonce_lease_1",
        executor_id="auth_worker_real",
        key_id="alpha_test_key",
    ).model_dump()
    task_record["result"]["senior_review"] = {"approved": True, "attestation": att_dict}

    args = argparse.Namespace(task_id="tsk_lease_test", json=False)
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = fake_git_for_tests
        assert cmd_merge(args, mock_queue) == 1


def test_cmd_merge_freshness_recheck_inside_lock_critical_section_rejects_expiry_during_intervening_work(
    monkeypatch, tmp_path
):
    import argparse
    import time
    from unittest.mock import MagicMock, patch

    from alpha_core.queue.triage_queue import TriageStatus
    from alpha_core.triage_cli import cmd_merge
    from alpha_protocol.task import ReviewAttestation

    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_secret_123")
    args = argparse.Namespace(task_id="tsk_crit_freshness", json=False)

    base_time = time.time()

    # Attestation expires in 100 seconds
    att_dict = ReviewAttestation.create(
        task_id="tsk_crit_freshness",
        attempt_id="att_1",
        result_sha="2" * 40,
        base_commit="1" * 40,
        tree_digest="c" * 40,
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=True,
        reviewed_at=base_time,
        issued_at=base_time,
        expires_at=base_time + 100.0,
        evidence={},
        secret="test_secret_123",
        nonce="nonce_crit_1",
        executor_id="exec_1",
        key_id="alpha_test_key",
    ).model_dump()

    t = {
        "id": "tsk_crit_freshness",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/tsk_crit_freshness",
        "worktree_path": str(tmp_path),
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "2" * 40,
            "evidence": {},
            "senior_review": {"approved": True, "attestation": att_dict},
        },
        "envelope": {"repo": str(tmp_path), "base_commit": "1" * 40},
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
            }
        },
    }

    q = MagicMock()
    q.get_task.return_value = t

    # Simulate time advancing: fresh (+10s) at initial outer check,
    # but expired (+150s) inside the lock critical section.
    time_calls = [
        base_time + 10.0,  # initial check before git inspection: valid!
        base_time + 150.0,  # inside lock critical section: EXPIRED!
    ]

    def mock_time():
        if time_calls:
            return time_calls.pop(0)
        return base_time + 200.0

    git_calls = []

    def mock_git_tracking(cmd, **kwargs):
        git_calls.append(cmd)
        return fake_git_for_tests(cmd, **kwargs)

    with (
        patch("time.time", side_effect=mock_time),
        patch("subprocess.run", side_effect=mock_git_tracking),
    ):
        exit_code = cmd_merge(args, q)
        assert exit_code == 1

        # Verify mutation commands were NEVER executed
        for cmd in git_calls:
            assert cmd[:3] != ["git", "merge", "--ff-only"], (
                "git merge --ff-only must not be called"
            )
            assert cmd[:3] != ["git", "checkout", "main"], "git checkout main must not be called"


def test_authoritative_lease_provenance_boundaries_in_review_merge_and_dispatcher(
    monkeypatch, tmp_path
):
    """
    Exhaustively tests authoritative lease provenance boundary enforcement:
    1. Reviewer path: absent, empty, missing individual fields, mismatches, valid case.
    2. Merge path: absent, empty, missing individual fields, mismatches, valid case.
    3. Dispatcher path: absent, empty, incomplete lease tuple, complete tuple.
    Asserts rejected cases invoke NEITHER AGY nor mutating Git commands.
    """
    import argparse
    import time
    from unittest.mock import MagicMock, patch

    import pytest

    from alpha_core.queue.triage_queue import TriageStatus
    from alpha_core.triage_cli import cmd_merge
    from alpha_protocol.task import ReviewAttestation
    from alpha_worker.senior_review_engine import SeniorReviewEngine
    from alpha_worker.triage_dispatcher import TriageTaskDispatcher

    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "secret_auth_boundary_123")

    # Helper to build baseline valid task dict
    def build_valid_task():
        return {
            "id": "tsk_boundary_test",
            "status": TriageStatus.COMPLETED.value,
            "branch_name": "alpha/tsk_boundary_test",
            "worktree_path": str(tmp_path),
            "envelope": {"repo": str(tmp_path), "base_commit": "1" * 40},
            "provenance": {
                "lease_metadata": {
                    "worker_id": "auth_exec_1",
                    "attempt_id": "auth_att_1",
                    "lease_id": "lease_123",
                    "fencing_epoch": 1000,
                }
            },
            "result": {
                "gates_passed": True,
                "worker_id": "auth_exec_1",
                "attempt_id": "auth_att_1",
                "result_sha": "2" * 40,
                "evidence": {"test": "ok"},
            },
        }

    # 1. REVIEWER PATH BOUNDARIES
    invalid_reviewer_cases = [
        (
            "absent_provenance",
            lambda t: t.pop("provenance", None),
            "missing or invalid authoritative lease attempt_id",
        ),
        (
            "none_provenance",
            lambda t: t.update({"provenance": None}),
            "missing or invalid authoritative lease attempt_id",
        ),
        (
            "missing_lease_metadata",
            lambda t: t["provenance"].pop("lease_metadata", None),
            "missing or invalid authoritative lease attempt_id",
        ),
        (
            "empty_lease_metadata",
            lambda t: t["provenance"].update({"lease_metadata": {}}),
            "missing or invalid authoritative lease attempt_id",
        ),
        (
            "missing_worker_id",
            lambda t: t["provenance"]["lease_metadata"].pop("worker_id"),
            "missing or invalid authoritative lease worker_id",
        ),
        (
            "empty_worker_id",
            lambda t: t["provenance"]["lease_metadata"].update({"worker_id": ""}),
            "missing or invalid authoritative lease worker_id",
        ),
        (
            "placeholder_worker_id",
            lambda t: t["provenance"]["lease_metadata"].update({"worker_id": "worker_unknown"}),
            "missing or invalid authoritative lease worker_id",
        ),
        (
            "missing_attempt_id",
            lambda t: t["provenance"]["lease_metadata"].pop("attempt_id"),
            "missing or invalid authoritative lease attempt_id",
        ),
        (
            "empty_attempt_id",
            lambda t: t["provenance"]["lease_metadata"].update({"attempt_id": ""}),
            "missing or invalid authoritative lease attempt_id",
        ),
        (
            "placeholder_attempt_id",
            lambda t: t["provenance"]["lease_metadata"].update({"attempt_id": "att_unknown"}),
            "missing or invalid authoritative lease attempt_id",
        ),
        (
            "mismatch_worker_id",
            lambda t: t["result"].update({"worker_id": "wrong_worker"}),
            "does not match authoritative lease worker_id",
        ),
        (
            "mismatch_attempt_id",
            lambda t: t["result"].update({"attempt_id": "wrong_attempt"}),
            "does not match authoritative lease attempt_id",
        ),
    ]

    for _label, mutate_fn, expected_match in invalid_reviewer_cases:
        task = build_valid_task()
        mutate_fn(task)
        q = MagicMock()
        q.get_task.return_value = task
        engine = SeniorReviewEngine(
            queue=q, key_id="alpha_test_key", signing_secret="secret_auth_boundary_123"
        )

        with (
            patch.object(SeniorReviewEngine, "_invoke_agy") as mock_agy,
            patch("subprocess.check_output") as mock_check_output,
            patch("subprocess.run") as mock_sub_run,
        ):
            with pytest.raises(ValueError, match=expected_match):
                engine.execute_senior_review("tsk_boundary_test")

            # Assert rejected cases invoke neither AGY nor mutating Git commands
            mock_agy.assert_not_called()
            mock_check_output.assert_not_called()
            mock_sub_run.assert_not_called()

    # Valid reviewer case passes and invokes AGY
    valid_task = build_valid_task()
    q_valid = MagicMock()
    q_valid.get_task.return_value = valid_task
    engine_valid = SeniorReviewEngine(
        queue=q_valid, key_id="alpha_test_key", signing_secret="secret_auth_boundary_123"
    )

    def fake_git_read(cmd, **kwargs):
        if cmd[:2] == ["git", "rev-parse"]:
            return ("c" * 40 if "^{tree}" in cmd[2] else "2" * 40) + "\n"
        if cmd[:2] == ["git", "status"]:
            return ""
        return ""

    with (
        patch.object(
            SeniorReviewEngine,
            "_invoke_agy",
            side_effect=[
                {"response": "", "structured_output": {"verdict": "APPROVE"}},
                {"response": "", "structured_output": {"verdict": "FINAL_APPROVAL"}},
            ],
        ) as mock_agy,
        patch("subprocess.check_output", side_effect=fake_git_read),
    ):
        verdict = engine_valid.execute_senior_review("tsk_boundary_test")
        assert verdict.approved is True
        assert mock_agy.call_count == 2  # Round 1 & Round 2 executed for valid case

    # 2. MERGE PATH BOUNDARIES
    args = argparse.Namespace(task_id="tsk_boundary_test", json=False)

    def attach_valid_attestation(task):
        att = ReviewAttestation.create(
            task_id="tsk_boundary_test",
            attempt_id="auth_att_1",
            result_sha="2" * 40,
            base_commit="1" * 40,
            tree_digest="c" * 40,
            pro_verdict="APPROVE",
            opus_verdict="FINAL_APPROVAL",
            approved=True,
            reviewed_at=time.time(),
            evidence={"test": "ok"},
            secret="secret_auth_boundary_123",
            nonce="nonce_boundary_123",
            executor_id="auth_exec_1",
            key_id="alpha_test_key",
        )
        task["result"]["senior_review"] = {
            "approved": True,
            "attestation": att.model_dump(),
        }

    invalid_merge_cases = [
        ("absent_provenance", lambda t: t.pop("provenance", None)),
        ("none_provenance", lambda t: t.update({"provenance": None})),
        ("missing_lease_metadata", lambda t: t["provenance"].pop("lease_metadata", None)),
        ("empty_lease_metadata", lambda t: t["provenance"].update({"lease_metadata": {}})),
        ("missing_worker_id", lambda t: t["provenance"]["lease_metadata"].pop("worker_id")),
        (
            "empty_worker_id",
            lambda t: t["provenance"]["lease_metadata"].update({"worker_id": ""}),
        ),
        (
            "placeholder_worker_id",
            lambda t: t["provenance"]["lease_metadata"].update({"worker_id": "worker_unknown"}),
        ),
        ("missing_attempt_id", lambda t: t["provenance"]["lease_metadata"].pop("attempt_id")),
        (
            "empty_attempt_id",
            lambda t: t["provenance"]["lease_metadata"].update({"attempt_id": ""}),
        ),
        (
            "placeholder_attempt_id",
            lambda t: t["provenance"]["lease_metadata"].update({"attempt_id": "att_unknown"}),
        ),
        ("mismatch_result_worker", lambda t: t["result"].update({"worker_id": "forged_worker"})),
        ("mismatch_result_attempt", lambda t: t["result"].update({"attempt_id": "forged_attempt"})),
    ]

    for label, mutate_fn in invalid_merge_cases:
        task = build_valid_task()
        attach_valid_attestation(task)
        mutate_fn(task)
        q = MagicMock()
        q.get_task.return_value = task

        with patch("subprocess.run") as mock_sub_run:
            mock_sub_run.side_effect = fake_git_for_tests
            code = cmd_merge(args, q)
            assert code == 1, f"Merge must reject invalid case: {label}"

            # Verify mutating git commands are NEVER invoked
            for call in mock_sub_run.call_args_list:
                cmd = call[0][0] if call[0] else []
                if cmd and cmd[0] == "git":
                    assert cmd[1] not in ["merge", "checkout", "branch", "reset"], (
                        f"Forbidden mutating Git command executed on rejected merge ({label}): {cmd}"
                    )

    # Valid merge case passes and performs merge
    valid_merge_task = build_valid_task()
    attach_valid_attestation(valid_merge_task)
    q_valid_merge = MagicMock()
    q_valid_merge.get_task.return_value = valid_merge_task

    with patch("subprocess.run") as mock_sub_run:
        mock_sub_run.side_effect = fake_git_for_tests
        code = cmd_merge(args, q_valid_merge)
        assert code == 0

    # 3. DISPATCHER PATH BOUNDARIES (execute_task)
    invalid_dispatcher_cases = [
        ("absent_provenance", lambda t: t.pop("provenance", None)),
        ("none_provenance", lambda t: t.update({"provenance": None})),
        ("missing_lease_metadata", lambda t: t["provenance"].pop("lease_metadata", None)),
        ("empty_lease_metadata", lambda t: t["provenance"].update({"lease_metadata": {}})),
        ("missing_worker_id", lambda t: t["provenance"]["lease_metadata"].pop("worker_id")),
        ("missing_attempt_id", lambda t: t["provenance"]["lease_metadata"].pop("attempt_id")),
        ("missing_lease_id", lambda t: t["provenance"]["lease_metadata"].pop("lease_id")),
        ("missing_fencing_epoch", lambda t: t["provenance"]["lease_metadata"].pop("fencing_epoch")),
    ]

    for label, mutate_fn in invalid_dispatcher_cases:
        leased_task = {
            "id": "tsk_disp_boundary",
            "status": TriageStatus.EXECUTING.value,
            "envelope": {"repo": str(tmp_path), "base_commit": "a" * 40, "title": "test"},
            "provenance": {
                "lease_metadata": {
                    "worker_id": "auth_exec_1",
                    "attempt_id": "auth_att_1",
                    "lease_id": "lease_123",
                    "fencing_epoch": 1000,
                }
            },
        }
        mutate_fn(leased_task)

        mock_disp_queue = MagicMock()
        mock_worktree_mgr = MagicMock()
        mock_bridge = MagicMock()
        mock_bridge.check_readiness.return_value = (True, "Ready")

        disp = TriageTaskDispatcher(
            queue=mock_disp_queue,
            worktree_mgr=mock_worktree_mgr,
            live_bridge=mock_bridge,
            enable_agent_execution=True,
        )

        with patch("subprocess.run") as mock_disp_git:
            res = disp.execute_task(leased_task)
            assert res is None, f"Dispatcher must return None on invalid case: {label}"
            mock_disp_queue.fail_task.assert_called_once()
            # Assert neither worktree manager nor Git commands nor complete_task invoked
            mock_worktree_mgr.create_or_resume_worktree.assert_not_called()
            mock_disp_queue.complete_task.assert_not_called()
            mock_disp_git.assert_not_called()
