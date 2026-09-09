"""
testscript/test_p9_4_worker_dispatch_and_pr.py
Hermetic tests for Phase 9.4: Worker Dispatch & PR Generation Pipeline.

Verifies:
1. Strict worker blindness: workers ignore PENDING_REVIEW and REJECTED tasks.
2. Emergency stop fail-closed behavior across dispatcher, CLI, and REST API.
3. Content hash integrity check prior to execution.
4. End-to-end worker execution: Worktree isolation -> Git commit -> Gate evidence -> PR proposal -> COMPLETED queue state.
5. P9 Blast radius containment: Worktree modification outside allowed_paths fails closed.
6. Acceptance gate failure handling and retry.
7. Worker REST API lease and result lifecycle, including RBAC and emergency stop checks.
8. Worker CLI cycle execution.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 6.5 & Section 6.6)
"""

import json
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_core.api.app import app, get_triage_queue
from alpha_core.config import settings
from alpha_core.queue.triage_queue import (
    TaskProvenance,
    TaskTriageQueue,
    TriageStatus,
)
from alpha_core.security import AuthPrincipal, PrincipalRole, require_api_principal
from alpha_core.triage_cli import main as cli_main
from alpha_protocol import PlanningAttestation, PlanAssessment
import hashlib
from alpha_worker.triage_dispatcher import PRProposal, TriageTaskDispatcher
from alpha_worker.worktree import WorktreeManager


def create_fixture_git_repo(repo_dir: Path) -> Path:
    """Initializes a clean Git repository with an initial commit."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@alphabrain.ai"], cwd=str(repo_dir), check=True
    )

    readme = repo_dir / "README.md"
    readme.write_text("# Test Fixture Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)
    return repo_dir


@pytest.fixture
def isolated_queue(tmp_path: Path) -> TaskTriageQueue:
    db_path = tmp_path / "test_triage.db"
    lock_path = tmp_path / "emergency_stop.lock"
    return TaskTriageQueue(db_path=db_path, emergency_lock_path=lock_path)


@pytest.fixture
def fixture_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = create_fixture_git_repo(tmp_path / "repo")
    # Allow this tmp_path repo root in settings
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", [tmp_path])
    monkeypatch.setattr(settings, "WORKTREE_BASE_DIR", tmp_path / "worktrees")
    return repo



def attach_fake_plan(queue, task_id, base_sha):
    bp_dict = {
        "task_id": task_id,
        "base_sha": base_sha,
        "plan_markdown": "Test plan",
        "modified_files": [],
        "created_at": 0.0
    }
    bp_json = json.dumps(bp_dict)
    bp_digest = hashlib.sha256(bp_json.encode("utf-8")).hexdigest()

    att = PlanningAttestation(
        task_id=task_id,
        project_id="default",
        repository_identity="local",
        base_sha=base_sha,
        blueprint_digest=bp_digest,
        pro_assessment=PlanAssessment(
            reviewer_principal="pro",
            role="drafting",
            plan_digest=bp_digest,
            verdict="APPROVE",
            findings="ok"
        ),
        opus_assessment=PlanAssessment(
            reviewer_principal="opus",
            role="critique",
            plan_digest=bp_digest,
            verdict="APPROVE",
            findings="ok"
        ),
        key_id="test",
        issued_at=0.0,
        expires_at=0.0,
        signature="a" * 64
    )
    
    att_dict = json.loads(att.model_dump_json())
    queue.attach_plan(task_id, att_dict, bp_dict)


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


def test_worker_blindness_to_unapproved_tasks(
    isolated_queue: TaskTriageQueue, fixture_repo: Path
) -> None:
    """Worker dispatcher strictly leases APPROVED tasks; ignores PENDING_REVIEW and REJECTED."""
    dispatcher = TriageTaskDispatcher(queue=isolated_queue)

    # 1. Enqueue task in PENDING_REVIEW
    env1 = {
        "task_id": "task_unvetted_1",
        "objective": "Unvetted task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["README.md"],
    }
    prov1 = make_test_provenance("task_unvetted_1", "hash_1")
    isolated_queue.enqueue_task("task_unvetted_1", env1, prov1)

    # 2. Worker attempts to lease -> MUST return None
    assert dispatcher.lease_task() is None

    # 3. Enqueue another task and reject it
    env2 = {
        "task_id": "task_rejected_2",
        "objective": "Rejected task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["README.md"],
    }
    prov2 = make_test_provenance("task_rejected_2", "hash_2")
    isolated_queue.enqueue_task("task_rejected_2", env2, prov2)
    isolated_queue.reject_task("task_rejected_2", reason="Security rejection")

    # 4. Worker attempts to lease -> MUST still return None
    assert dispatcher.lease_task() is None


def test_emergency_stop_halts_worker_leasing(
    isolated_queue: TaskTriageQueue, fixture_repo: Path
) -> None:
    """Active emergency stop halts worker leasing fail-closed."""
    dispatcher = TriageTaskDispatcher(queue=isolated_queue)

    env = {
        "task_id": "task_appr_1",
        "objective": "Approved task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["README.md"],
    }
    prov = make_test_provenance("task_appr_1", "hash_appr_1")
    isolated_queue.enqueue_task("task_appr_1", env, prov)
    attach_fake_plan(isolated_queue, "task_appr_1", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_appr_1")

    # Activate emergency stop
    isolated_queue.emergency_stop("Security incident underway")

    # Worker lease MUST fail-closed
    assert dispatcher.lease_task() is None
    assert dispatcher.execute_next_cycle() is None

    # Resume emergency stop
    isolated_queue.emergency_resume()

    # Now leasing succeeds
    leased = dispatcher.lease_task()
    assert leased is not None
    assert leased["id"] == "task_appr_1"
    assert leased["status"] == TriageStatus.EXECUTING.value


def test_content_hash_mismatch_fails_closed(
    isolated_queue: TaskTriageQueue, fixture_repo: Path
) -> None:
    """If stored content_hash does not match recomputed envelope hash, execution fails closed."""
    dispatcher = TriageTaskDispatcher(queue=isolated_queue)

    env = {
        "task_id": "task_tampered_1",
        "objective": "Legitimate objective",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["README.md"],
    }
    # Provide intentionally mismatched hash
    prov = make_test_provenance(
        "task_tampered_1", "6845a3483ac64d5aa1697e22ba2f5aac9a617d3b8bee689360b7dcd30a44edb0"
    )
    import pytest

    with pytest.raises(ValueError, match="Content hash mismatch"):
        isolated_queue.enqueue_task("task_tampered_1", env, prov)
    return  # The rest of the test is obsolete since it is blocked at the queue level
    attach_fake_plan(isolated_queue, "task_tampered_1", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_tampered_1")

    # Dispatcher runs cycle
    proposal = dispatcher.execute_next_cycle()
    assert proposal is None

    # Verify task was marked FAILED with security violation in queue
    task = isolated_queue.get_task("task_tampered_1")
    assert task is not None
    assert task["status"] == TriageStatus.FAILED.value
    assert "Security Violation: Content hash mismatch" in str(task["result_json"])


def test_end_to_end_worker_dispatch_and_pr_generation(
    isolated_queue: TaskTriageQueue, fixture_repo: Path, tmp_path: Path
) -> None:
    """Full execution lifecycle: lease -> worktree branch -> git commit -> PR proposal -> queue COMPLETED."""
    wt_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    env = {
        "task_id": "task_valid_e2e",
        "project_id": "proj_alpha",
        "objective": "Add features doc",
        "detailed_instructions": "Create FEATURES.md with feature list",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["FEATURES.md"],
        "acceptance_plan": {
            "commands": [
                {
                    "executable": "python",
                    "args": ["-c", "import sys; sys.exit(0)"],
                    "gate_type": "unit_test",
                }
            ]
        },
    }
    # Deterministic content hash
    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    import hashlib

    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("task_valid_e2e", content_hash)

    isolated_queue.enqueue_task("task_valid_e2e", env, prov)
    attach_fake_plan(isolated_queue, "task_valid_e2e", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_valid_e2e")

    # Simulate agent writing the file inside worktree prior to commit
    # We can pre-create or let execute_task create worktree
    # To simulate file change:
    wt_path = wt_mgr.create_or_resume_worktree(
        repo_path=str(fixture_repo),
        task_id="task_valid_e2e",
        base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
    )
    features_file = wt_path / "FEATURES.md"
    features_file.write_text("# Feature List\n- Feature A\n- Feature B\n")

    # Run dispatcher cycle
    proposal = dispatcher.execute_next_cycle()
    assert proposal is not None
    assert isinstance(proposal, PRProposal)
    assert proposal.task_id == "task_valid_e2e"
    assert proposal.project_id == "proj_alpha"
    assert proposal.branch_name == "alpha/task_valid_e2e"
    assert proposal.gates_passed is True
    assert "FEATURES.md" in proposal.files_changed
    assert proposal.head_commit != "HEAD"

    # Queue state check
    task = isolated_queue.get_task("task_valid_e2e")
    assert task is not None
    assert task["status"] == TriageStatus.COMPLETED.value
    assert task["branch_name"] == "alpha/task_valid_e2e"
    assert task["worktree_path"] == str(wt_path)

    # Result payload in queue
    result_data = json.loads(task["result_json"])
    assert result_data["head_commit"] == proposal.head_commit
    assert result_data["gates_passed"] is True


def test_worker_disallowed_path_fails_closed(
    isolated_queue: TaskTriageQueue, fixture_repo: Path, tmp_path: Path
) -> None:
    """Worker modifying files outside allowed_paths is rejected and marked FAILED."""
    wt_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    env = {
        "task_id": "task_disallowed_paths",
        "objective": "Modify restricted file",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["docs/safe.md"],
        "acceptance_plan": {
            "commands": [
                {"executable": "python", "args": ["-c", "exit(0)"], "gate_type": "unit_test"}
            ]
        },
    }
    import hashlib

    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("task_disallowed_paths", content_hash)

    isolated_queue.enqueue_task("task_disallowed_paths", env, prov)
    attach_fake_plan(isolated_queue, "task_disallowed_paths", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_disallowed_paths")

    # Pre-create worktree and write to disallowed file outside allowed_paths
    wt_path = wt_mgr.create_or_resume_worktree(
        repo_path=str(fixture_repo),
        task_id="task_disallowed_paths",
        base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
    )
    forbidden_file = wt_path / "danger.sh"
    forbidden_file.write_text("echo hacked\n")

    proposal = dispatcher.execute_next_cycle()
    assert proposal is None

    # Check task failed
    task = isolated_queue.get_task("task_disallowed_paths")
    assert task is not None
    assert task["status"] == TriageStatus.FAILED.value
    assert "Security Violation: Modified files outside allowed_paths" in str(task["result_json"])


def test_worker_acceptance_gate_failure(
    isolated_queue: TaskTriageQueue, fixture_repo: Path, tmp_path: Path
) -> None:
    """Failing acceptance gate prevents commit/completion and marks task for retry/failed."""
    wt_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    env = {
        "task_id": "task_gate_fail",
        "objective": "Broken test task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["test.py"],
        "acceptance_plan": {
            "commands": [
                {
                    "executable": "python",
                    "args": ["-c", "import sys; sys.exit(42)"],
                    "gate_type": "unit_test",
                }
            ]
        },
    }
    import hashlib

    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("task_gate_fail", content_hash)

    isolated_queue.enqueue_task("task_gate_fail", env, prov)
    attach_fake_plan(isolated_queue, "task_gate_fail", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_gate_fail")

    proposal = dispatcher.execute_next_cycle()
    assert proposal is None

    task = isolated_queue.get_task("task_gate_fail")
    assert task is not None
    # Gate failure moves task to APPROVED with retry_count incremented
    assert task["status"] in {TriageStatus.APPROVED.value, TriageStatus.FAILED.value}
    assert task["retry_count"] >= 1
    assert "Acceptance gates failed" in str(task["result_json"])


def test_api_worker_endpoints_and_rbac(
    isolated_queue: TaskTriageQueue,
    fixture_repo: Path,
) -> None:
    """Verifies REST API endpoints /api/triage/tasks/lease and result."""
    app.dependency_overrides[get_triage_queue] = lambda: isolated_queue
    client = TestClient(app)

    # 1. Anonymous request returns 401
    res = client.post("/api/triage/tasks/lease")
    assert res.status_code == 401

    # 2. Client role returns 403
    client_principal = AuthPrincipal(subject="client_charlie", role=PrincipalRole.CLIENT)
    app.dependency_overrides[require_api_principal] = lambda: client_principal
    res = client.post("/api/triage/tasks/lease")
    assert res.status_code == 403

    # 3. Worker role succeeds on empty queue
    worker_principal = AuthPrincipal(
        subject="worker_bob", role=PrincipalRole.WORKER, project_ids=("proj_1",)
    )
    app.dependency_overrides[require_api_principal] = lambda: worker_principal
    res = client.post("/api/triage/tasks/lease")
    assert res.status_code == 200
    assert res.json()["task"] is None

    # 4. Enqueue and approve a task
    env = {
        "task_id": "api_worker_task_1",
        "objective": "API worker task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["doc.md"],
        "project_id": "proj_1",
    }
    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    import hashlib

    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("api_worker_task_1", content_hash)
    isolated_queue.enqueue_task("api_worker_task_1", env, prov)
    attach_fake_plan(isolated_queue, "api_worker_task_1", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("api_worker_task_1")

    # 5. Worker leases task
    res = client.post("/api/triage/tasks/lease")
    assert res.status_code == 200
    leased = res.json()["task"]
    assert leased is not None
    assert leased["id"] == "api_worker_task_1"
    assert leased["status"] == TriageStatus.EXECUTING.value

    # 6. Worker posts completion result
    task_db = isolated_queue.get_task("api_worker_task_1")
    res = client.post(
        "/api/triage/tasks/api_worker_task_1/result",
        json={
            "status": "completed",
            "result": {"pr_url": "https://github.com/org/repo/pull/1"},
            "branch_name": "alpha/api_worker_task_1",
            "worktree_path": "/tmp/wt/1",
            "worker_id": task_db.get("provenance", {}).get("lease_metadata", {}).get("worker_id"),
            "lease_id": task_db.get("provenance", {}).get("lease_metadata", {}).get("lease_id"),
            "fencing_epoch": task_db.get("provenance", {})
            .get("lease_metadata", {})
            .get("fencing_epoch"),
            "attempt_id": task_db.get("provenance", {}).get("lease_metadata", {}).get("attempt_id"),
        },
    )
    assert res.status_code == 200
    assert res.json()["state"] == "completed"

    task = isolated_queue.get_task("api_worker_task_1")
    assert task is not None
    assert task["status"] == TriageStatus.COMPLETED.value

    # 7. Emergency stop blocks lease with 409
    isolated_queue.emergency_stop("API test stop")
    res = client.post("/api/triage/tasks/lease")
    assert res.status_code == 409

    app.dependency_overrides.clear()


def test_cli_worker_cycle_command(
    isolated_queue: TaskTriageQueue,
    fixture_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI worker-cycle executes approved tasks or exits cleanly when empty."""
    db_arg = str(isolated_queue.db_path)
    lock_arg = str(isolated_queue.emergency_lock_path)

    # 1. Idle queue
    ret = cli_main(["--db-path", db_arg, "--emergency-lock", lock_arg, "worker-cycle", "--json"])
    assert ret == 0

    # 2. Enqueue and approve task
    env = {
        "task_id": "cli_worker_task_1",
        "project_id": "cli_proj",
        "objective": "CLI worker test",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["cli.txt"],
        "acceptance_plan": {
            "commands": [
                {"executable": "python", "args": ["-c", "exit(0)"], "gate_type": "unit_test"}
            ]
        },
    }
    import hashlib

    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("cli_worker_task_1", content_hash)
    isolated_queue.enqueue_task("cli_worker_task_1", env, prov)
    attach_fake_plan(isolated_queue, "cli_worker_task_1", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("cli_worker_task_1")

    # 3. Simulate worktree modification prior to worker-cycle
    wt_mgr = WorktreeManager()
    wt_path = wt_mgr.create_or_resume_worktree(
        repo_path=str(fixture_repo),
        task_id="cli_worker_task_1",
        base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
    )
    (wt_path / "cli.txt").write_text("CLI test output\n")

    # 4. Run worker-cycle via CLI
    ret = cli_main(["--db-path", db_arg, "--emergency-lock", lock_arg, "worker-cycle"])
    assert ret == 0

    task = isolated_queue.get_task("cli_worker_task_1")
    assert task is not None
    assert task["status"] == TriageStatus.COMPLETED.value


def test_empty_allowed_paths_strictly_blocks_any_file_modification(
    isolated_queue: TaskTriageQueue, fixture_repo: Path, tmp_path: Path
) -> None:
    """Regression test for Finding 1 (P0): Empty allowed_paths must strictly block ANY file modification."""
    wt_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    env = {
        "task_id": "task_empty_allowed",
        "objective": "Read only task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": [],  # STRICTLY NO FILES ALLOWED
    }
    import hashlib

    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("task_empty_allowed", content_hash)

    isolated_queue.enqueue_task("task_empty_allowed", env, prov)
    attach_fake_plan(isolated_queue, "task_empty_allowed", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_empty_allowed")

    # Modify a file in worktree
    wt_path = wt_mgr.create_or_resume_worktree(
        repo_path=str(fixture_repo),
        task_id="task_empty_allowed",
        base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
    )
    mod_file = wt_path / "rogue.txt"
    mod_file.write_text("unauthorized write\n")

    proposal = dispatcher.execute_next_cycle()
    assert proposal is None

    task = isolated_queue.get_task("task_empty_allowed")
    assert task is not None
    assert task["status"] == TriageStatus.FAILED.value
    assert "Security Violation: Modified files outside allowed_paths" in str(task["result_json"])


def test_in_flight_task_completion_and_failure_survive_emergency_stop(
    isolated_queue: TaskTriageQueue,
) -> None:
    """Regression test for Finding 2 (P2): Active in-flight tasks must complete/fail cleanly under emergency stop."""
    env = {"task_id": "task_in_flight", "objective": "In flight task"}
    prov = make_test_provenance("task_in_flight", "hash_in_flight")
    isolated_queue.enqueue_task("task_in_flight", env, prov)
    attach_fake_plan(isolated_queue, "task_in_flight", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_in_flight")

    # Worker leases task (moves to EXECUTING)
    leased = isolated_queue.lease_next_approved_task()
    assert leased is not None
    assert leased["id"] == "task_in_flight"

    # Emergency stop is triggered while worker is executing
    isolated_queue.emergency_stop("Critical incident")
    assert isolated_queue.is_emergency_stopped() is True

    # In-flight worker completes execution without crashing with EmergencyStopActiveError
    success = isolated_queue.complete_task(
        "task_in_flight",
        result={"summary": "Successfully finished before stop"},
        worktree_path="/tmp/wt/in_flight",
        branch_name="alpha/task_in_flight",
    )
    assert success is True

    task = isolated_queue.get_task("task_in_flight")
    assert task is not None
    assert task["status"] == TriageStatus.COMPLETED.value
    assert task["result"]["summary"] == "Successfully finished before stop"


def test_reap_stale_executing_tasks_recovers_orphaned_tasks(
    isolated_queue: TaskTriageQueue,
) -> None:
    """Watchdog reaper recovers executing tasks if a worker crashes or reboots."""
    env = {"task_id": "task_orphaned", "objective": "Orphaned worker task"}
    prov = make_test_provenance("task_orphaned", "hash_orphaned")
    isolated_queue.enqueue_task("task_orphaned", env, prov)
    attach_fake_plan(isolated_queue, "task_orphaned", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_orphaned")

    leased = isolated_queue.lease_next_approved_task()
    assert leased is not None

    # Artificially age the started_at timestamp by 2 hours
    with isolated_queue._get_connection() as conn:
        conn.execute(
            "UPDATE task_triage_queue SET started_at = ? WHERE id = ?;",
            (time.time() - 7200.0, "task_orphaned"),
        )
        conn.commit()

    # Run reaper with 1-hour timeout
    reaped = isolated_queue.reap_stale_executing_tasks(timeout_seconds=3600.0)
    assert reaped == 1

    task = isolated_queue.get_task("task_orphaned")
    assert task is not None
    assert task["status"] == TriageStatus.FAILED.value
    assert "Watchdog timeout" in str(task["result_json"])


def test_zero_diff_worktree_fails_closed(
    isolated_queue: TaskTriageQueue, fixture_repo: Path, tmp_path: Path
) -> None:
    """R1 (P0): If an agent produces 0 modified files, the dispatcher must fail closed."""
    wt_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    env = {
        "task_id": "task_zero_diff",
        "objective": "Zero diff task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["README.md"],
        "acceptance_plan": {
            "commands": [
                {"executable": "python", "args": ["-c", "exit(0)"], "gate_type": "unit_test"}
            ]
        },
    }
    import hashlib

    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("task_zero_diff", content_hash)

    isolated_queue.enqueue_task("task_zero_diff", env, prov)
    attach_fake_plan(isolated_queue, "task_zero_diff", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_zero_diff")

    # Do not modify any files in the worktree
    proposal = dispatcher.execute_next_cycle()
    assert proposal is None

    task = isolated_queue.get_task("task_zero_diff")
    assert task is not None
    assert task["status"] in (TriageStatus.APPROVED.value, TriageStatus.FAILED.value)
    assert "Fail-Closed Violation" in str(task["result_json"])


def test_failure_evidence_injected_on_retry(
    isolated_queue: TaskTriageQueue, fixture_repo: Path, tmp_path: Path
) -> None:
    """Verifies that gate failures from a previous attempt are injected into detailed_instructions."""
    wt_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    env = {
        "task_id": "task_retry_loop",
        "objective": "Retry loop test",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
        "allowed_paths": ["failing.txt"],
        "detailed_instructions": "Initial instructions.",
        "acceptance_plan": {
            "commands": [
                {"executable": "python", "args": ["-c", "exit(1)"], "gate_type": "unit_test"}
            ]
        },
    }
    import hashlib

    env_json = json.dumps(env, sort_keys=True, separators=(",", ":"), default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("task_retry_loop", content_hash)

    isolated_queue.enqueue_task("task_retry_loop", env, prov)
    attach_fake_plan(isolated_queue, "task_retry_loop", env.get("base_commit", "a" * 40))
    isolated_queue.approve_task("task_retry_loop")

    # Cycle 1: Modifies file but gate fails (exit 1)
    wt_path = wt_mgr.create_or_resume_worktree(
        repo_path=str(fixture_repo),
        task_id="task_retry_loop",
        base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo)
        .decode("utf-8")
        .strip(),
    )
    (wt_path / "failing.txt").write_text("modified\n")

    proposal = dispatcher.execute_next_cycle()
    assert proposal is None

    # The task should have failed and been requeued for retry (status=approved, retry_count=1)
    task = isolated_queue.get_task("task_retry_loop")
    assert task is not None
    assert task["status"] == TriageStatus.APPROVED.value
    assert int(task["retry_count"]) == 1
    assert "result" in task
    assert "evidence" in task["result"]

    # Cycle 2: We intercept `_build_task_envelope` via a mock to check the injected instructions
    leased = isolated_queue.lease_next_approved_task()
    assert leased is not None

    # We directly invoke _build_task_envelope to verify the injection
    task_env = dispatcher._build_task_envelope(leased, wt_path)

    # Assert instructions contain the failure directives
    assert "PREVIOUS ATTEMPT GATE FAILURES" in task_env.detailed_instructions
    assert "Failed Gate: python -c exit(1) (Exit 1)" in task_env.detailed_instructions
    assert "Initial instructions." in task_env.detailed_instructions
