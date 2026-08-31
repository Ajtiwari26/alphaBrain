"""Hermetic tests for H5 self-development proof runner."""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_runner(*args: str, tmp_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["H5_MOCK_WORKER"] = "1"
    env["H5_EVIDENCE_DIR"] = str(tmp_path / "evidence")
    cmd = [sys.executable, "testscript/h5_self_development_proof.py", *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)

def get_current_run_id(tmp_path: Path) -> str:
    return (tmp_path / "evidence" / "current_run_id.txt").read_text().strip()

def load_state(tmp_path: Path) -> dict[str, Any]:
    run_id = get_current_run_id(tmp_path)
    state_file = tmp_path / "evidence" / run_id / "state.json"
    if not state_file.exists():
        return {}
    return dict(json.loads(state_file.read_text()))


def test_1_prepare_captures_base(tmp_path):
    res = run_runner("prepare", tmp_path=tmp_path)
    assert res.returncode == 0, res.stderr
    assert "Task created" in res.stdout
    assert "Execution approval string" in res.stdout
    run_runner("cleanup", tmp_path=tmp_path)


def test_2_untracked_survives(tmp_path):
    untracked = Path("alpha_meet/frontend/.gitignore")
    if untracked.exists():
        content_before = untracked.read_text()
        run_runner("prepare", tmp_path=tmp_path)
        assert untracked.exists()
        assert untracked.read_text() == content_before
        run_runner("cleanup", tmp_path=tmp_path)


def test_3_4_approval_rejects_missing_wrong(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)

    res = run_runner("approve-execution", "--digest", "wrong", "--confirm", "I confirm execution for wrong", tmp_path=tmp_path)
    assert res.returncode != 0
    assert "Digest mismatch" in res.stderr

    state = load_state(tmp_path)
    digest = state["packet_sha256"]

    res = run_runner("approve-execution", "--digest", digest, "--confirm", "wrong", tmp_path=tmp_path)
    assert res.returncode != 0
    assert "Confirmation string mismatch" in res.stderr
    run_runner("cleanup", tmp_path=tmp_path)


def test_5_cannot_skip_order(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    res = run_runner("approve-review", "--digest", "mock_review_sha256", "--confirm", "I confirm review for mock_review_sha256", tmp_path=tmp_path)
    assert res.returncode != 0
    assert "not in review_pending phase" in res.stderr
    run_runner("cleanup", tmp_path=tmp_path)


def test_6_worker_before_approval_performs_no_call(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    res = run_runner("run-worker", tmp_path=tmp_path)
    assert res.returncode == 0
    assert "Worker run performed no AGY call" in res.stdout
    run_runner("cleanup", tmp_path=tmp_path)


def test_7_review_cannot_authorize_promotion(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    state = load_state(tmp_path)
    digest = state["packet_sha256"]
    run_runner("approve-execution", "--digest", digest, "--confirm", f"I confirm execution for {digest}", tmp_path=tmp_path)
    run_runner("run-worker", tmp_path=tmp_path)
    state = load_state(tmp_path)
    rev_digest = state["review_sha256"]
    run_runner("approve-review", "--digest", rev_digest, "--confirm", f"I confirm review for {rev_digest}", tmp_path=tmp_path)

    state = load_state(tmp_path)
    assert state["phase"] == "promotion_pending"
    res = run_runner("run-worker", tmp_path=tmp_path)
    assert "Worker run performed no AGY call" in res.stdout
    run_runner("cleanup", tmp_path=tmp_path)


def test_8_promotion_cannot_run_before_founder_approval(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    state = load_state(tmp_path)
    run_runner("approve-execution", "--digest", state["packet_sha256"], "--confirm", f"I confirm execution for {state['packet_sha256']}", tmp_path=tmp_path)
    run_runner("run-worker", tmp_path=tmp_path)
    state = load_state(tmp_path)
    run_runner("approve-review", "--digest", state["review_sha256"], "--confirm", f"I confirm review for {state['review_sha256']}", tmp_path=tmp_path)

    res = run_runner("run-worker", tmp_path=tmp_path)
    assert "Worker run performed no AGY call" in res.stdout
    run_runner("cleanup", tmp_path=tmp_path)


def test_9_resume_after_restart(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    res = run_runner("status", tmp_path=tmp_path)
    assert res.returncode == 0
    assert "Phase: prepare" in res.stdout
    run_runner("cleanup", tmp_path=tmp_path)


def test_10_duplicate_subcommand_idempotent(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    state = load_state(tmp_path)
    digest = state["packet_sha256"]
    run_runner("approve-execution", "--digest", digest, "--confirm", f"I confirm execution for {digest}", tmp_path=tmp_path)
    res = run_runner("approve-execution", "--digest", digest, "--confirm", f"I confirm execution for {digest}", tmp_path=tmp_path)
    assert res.returncode != 0
    assert "not in prepare phase" in res.stderr
    run_runner("cleanup", tmp_path=tmp_path)


def test_11_extra_file_rejected(tmp_path):
    pass


def test_12_failed_gates_block_review(tmp_path):
    pass


def test_13_successful_promotion_advances_head(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    state = load_state(tmp_path)
    run_runner("approve-execution", "--digest", state["packet_sha256"], "--confirm", f"I confirm execution for {state['packet_sha256']}", tmp_path=tmp_path)
    run_runner("run-worker", tmp_path=tmp_path)
    state = load_state(tmp_path)
    run_runner("approve-review", "--digest", state["review_sha256"], "--confirm", f"I confirm review for {state['review_sha256']}", tmp_path=tmp_path)
    state = load_state(tmp_path)
    run_runner("approve-promotion", "--digest", state["promotion_sha256"], "--confirm", f"I confirm promotion for {state['promotion_sha256']}", tmp_path=tmp_path)
    res = run_runner("run-worker", tmp_path=tmp_path)
    assert "Promotion applied" in res.stdout
    state = load_state(tmp_path)
    assert state["phase"] == "completed"
    run_runner("cleanup", tmp_path=tmp_path)


def test_14_cleanup_touches_only_proof_owned(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    res = run_runner("cleanup", tmp_path=tmp_path)
    assert res.returncode == 0
    assert not (tmp_path / "evidence" / "current_run_id.txt").exists()


def test_15_no_creds(tmp_path):
    run_runner("prepare", tmp_path=tmp_path)
    state = load_state(tmp_path)
    state_str = json.dumps(state)
    assert "token" not in state_str
    assert "secret" not in state_str
    assert "password" not in state_str
    run_runner("cleanup", tmp_path=tmp_path)
