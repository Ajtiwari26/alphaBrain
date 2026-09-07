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
        key_id="key",
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
        key_id="key",
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
        key_id="key",
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
            "result_commit": "a" * 40,
            "gate_result": {"status": "passed"},
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
    monkeypatch.delenv("ALPHA_SIGNING_SECRET", raising=False)
    mock_queue = MagicMock()
    mock_queue.get_task.return_value = {
        "status": TriageStatus.COMPLETED.value,
        "worktree_path": str(tmp_path),
        "result": {"gates_passed": True, "result_sha": "a" * 40},
    }
    engine = SeniorReviewEngine(queue=mock_queue, signing_secret=None)
    import pytest

    with pytest.raises(ValueError, match="ALPHA_SIGNING_SECRET is missing"):
        engine.execute_senior_review("tsk_123")


def test_senior_review_engine_rejects_missing_or_nonexistent_worktree():
    mock_queue = MagicMock()
    mock_queue.get_task.return_value = {
        "status": TriageStatus.COMPLETED.value,
        "worktree_path": "/nonexistent/path/to/worktree",
        "result": {"gates_passed": True, "result_sha": "a" * 40},
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
        "result": {"gates_passed": True, "result_sha": "a" * 40},
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
        "result": {"gates_passed": True, "result_sha": "a" * 40},
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
        executor_id="w",
        key_id="k",
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
                "result_sha": result_sha,
                "evidence": evidence,
                "senior_review": {
                    "approved": True,  # Outer task approved is True to strictly isolate attestation validation
                    "attestation": att.model_dump(),
                },
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

    with patch.dict("os.environ", {"ALPHA_SIGNING_SECRET": secret}):
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
        executor_id="exec",
        key_id=key_id,
        reviewer_id="SYSTEM_SENIOR_REVIEW_ENGINE",
    )

    t = {
        "id": task_id,
        "status": TriageStatus.COMPLETED.value,
        "branch_name": f"alpha/{task_id}",
        "result": {
            "gates_passed": True,
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
            executor_id="exec",
            key_id="k1",
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
            key_id="k1",
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
    monkeypatch.setenv("ALPHA_SIGNING_SECRET", "test_secret_123")

    q = MagicMock()
    q.get_task.return_value = make_standalone_task_and_att(
        task_id="tsk_test_merge_auth",
        attempt_id="att_1",
        nonce="my_test_nonce",
        key_id="k1",
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
    monkeypatch.setenv("ALPHA_SIGNING_SECRET", "test_secret_123")
    monkeypatch.setenv("ALPHA_REVOKED_KEYS", "k1,bad_key")

    q = MagicMock()
    q.get_task.return_value = make_standalone_task_and_att(
        task_id="tsk_test_merge_auth",
        attempt_id="att_1",
        nonce="some_other_nonce",
        key_id="k1",
        repo_path=str(tmp_path),
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = fake_git_for_tests
        assert cmd_merge(args, q) == 1
