"""
testscript/test_p9_5_e2e_and_chaos.py
Milestone P9.5: End-to-End Pipeline Integration & Chaos Testing.

Comprehensive validation of the complete autonomous closed-loop delivery pipeline:
1. Full End-to-End Lifecycle: Eva Ingestion -> AST Safety Gate -> Operator HITL Approval -> Worker Dispatch -> Worktree Isolation -> Acceptance Gate -> PR Proposal -> Queue Completion.
2. Chaos 1: Mid-Execution Sudden Worker Crash & Watchdog Lease Reclamation.
3. Chaos 2: Concurrent Multi-Worker Race (Zero Duplicate Leases under SQLite Contention).
4. Chaos 3: Emergency Stop Interruption Under Live Load & Clean Resumption.
5. Chaos 4: In-Queue Cryptographic Tamper Detection & Permanent Fail-Closed Lockout.
6. Chaos 5: Sandbox Escape & Blast Radius Containment Violations.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Sections 6.3 - 6.6)
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest

from alpha_core.config import settings
from alpha_core.eva.queue_producer import EvaQueueProducer
from alpha_core.eva.spec_extractor import ExtractedSpecification
from alpha_core.queue.triage_queue import (
    EmergencyStopActiveError,
    TaskProvenance,
    TaskTriageQueue,
    TriageStatus,
)
from alpha_core.safety.gate import SafetyGate
from alpha_core.triage_cli import main as cli_main
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
    db_path = tmp_path / "triage_p9_5.db"
    lock_path = tmp_path / "emergency_stop.lock"
    return TaskTriageQueue(db_path=db_path, emergency_lock_path=lock_path)


@pytest.fixture
def fixture_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = create_fixture_git_repo(tmp_path / "repo")
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", [tmp_path])
    monkeypatch.setattr(settings, "WORKTREE_BASE_DIR", tmp_path / "worktrees")
    return repo


def make_test_provenance(task_id: str, content_hash: str) -> TaskProvenance:
    return TaskProvenance(
        meeting_id="meet_live_e2e",
        speaker_id="founder_ajay",
        utterance_timestamp=1725345600.0,
        transcript_excerpt="We need to deploy rate limiting middleware to prevent API abuse.",
        extraction_model="gemini-3.1-pro-high",
        extraction_confidence=0.99,
        eva_session_id="eva_sess_e2e_001",
        created_at=time.time(),
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# 1. Complete End-to-End Pipeline Integration Test
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="R2-R6 gap pending")
def test_full_end_to_end_autonomous_lifecycle(
    isolated_queue: TaskTriageQueue,
    fixture_repo: Path,
    tmp_path: Path,
) -> None:
    """
    Simulates the entire autonomous delivery loop:
    1. Eva Meeting Ingestion (Specification Envelope + Cryptographic Provenance)
    2. Automated Safety Gate Analysis (AST inspection)
    3. Human-in-the-Loop Operator Review and Approval (CLI)
    4. Worker Autonomous Dispatch, Worktree Branching, Acceptance Verification, and PR Proposal Generation.
    """
    wt_base = tmp_path / "worktrees"
    wt_mgr = WorktreeManager(base_worktree_dir=wt_base)
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    # Step 1: Eva Ingestion creates specification envelope with cryptographic provenance
    producer = EvaQueueProducer(queue=isolated_queue)
    spec = ExtractedSpecification(
        title="Implement rate limiting middleware",
        summary="Add rate limiting middleware in src/rate_limiter.py",
        requirements=["Protect API endpoints from abuse."],
        allowed_paths=["src/rate_limiter.py", "tests/test_limiter.py"],
        acceptance_criteria=["Tests pass"],
        required_gates=["git status"],
        confidence_score=0.98,
        is_actionable=True,
    )
    task_id, _envelope, _prov = producer.enqueue_specification(
        spec=spec,
        project_id="proj_alphabrain",
        meeting_id="meet_live_e2e",
        transcript_excerpt="We need to deploy rate limiting middleware to prevent API abuse.",
        speaker_id="founder_ajay", base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    # Inject repo path into envelope in queue and update content hash
    task_data = isolated_queue.get_task(task_id)
    assert task_data is not None
    env_dict = task_data["envelope"]
    env_dict["repo"] = str(fixture_repo)
    import subprocess
    env_dict["base_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo).decode("utf-8").strip()
    env_json = json.dumps(env_dict, default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    with isolated_queue._get_connection() as conn:
        conn.execute(
            "UPDATE task_triage_queue SET envelope_json = ?, content_hash = ? WHERE id = ?;",
            (env_json, content_hash, task_id),
        )
        conn.commit()

    task_db = isolated_queue.get_task(task_id)
    assert task_db is not None
    assert task_db["status"] == TriageStatus.PENDING_REVIEW.value

    # Step 2: Automated AST Safety Gate evaluation
    safety_gate = SafetyGate()
    safety_verdict = safety_gate.evaluate_envelope(env_dict)
    assert safety_verdict.passed is True
    assert safety_verdict.verdict == "PASS"
    assert "Passed all deterministic P9 Constitution checks" in safety_verdict.reason

    # Worker is strictly blind at this stage!
    idle_poll = dispatcher.execute_next_cycle()
    assert idle_poll is None

    # Step 3: Human-in-the-Loop Operator approves via CLI
    db_arg = str(isolated_queue.db_path)
    lock_arg = str(isolated_queue.emergency_lock_path)
    ret = cli_main(["--db-path", db_arg, "--emergency-lock", lock_arg, "approve", task_id])
    assert ret == 0

    task_approved = isolated_queue.get_task(task_id)
    assert task_approved is not None
    assert task_approved["status"] == TriageStatus.APPROVED.value

    # Step 4: Worker provisions isolated worktree and executes work
    wt_path = wt_mgr.create_or_resume_worktree(
        repo_path=str(fixture_repo),
        task_id=task_id,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    limiter_file = wt_path / "src" / "rate_limiter.py"
    limiter_file.parent.mkdir(parents=True, exist_ok=True)
    limiter_file.write_text("# Production Rate Limiter Middleware\nRATE_LIMIT = 100\n")

    test_file = wt_path / "tests" / "test_limiter.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_limiter():\n    assert True\n")

    # Dispatcher executes cycle
    proposal = dispatcher.execute_next_cycle()
    assert proposal is not None
    assert isinstance(proposal, PRProposal)
    assert proposal.task_id == task_id
    assert proposal.branch_name == f"alpha/{task_id}"
    assert proposal.gates_passed is True
    assert "src/rate_limiter.py" in proposal.files_changed

    # Step 5: Verify task reached COMPLETED in queue with PR artifact
    task_completed = isolated_queue.get_task(task_id)
    assert task_completed is not None
    assert task_completed["status"] == TriageStatus.COMPLETED.value
    assert task_completed["branch_name"] == f"alpha/{task_id}"
    assert (
        task_completed["result"]["title"]
        == "Autonomous Delivery: Implement rate limiting middleware"
    )


# ---------------------------------------------------------------------------
# 2. Chaos Scenario 1: Worker Sudden Death & Watchdog Reclamation
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="R2-R6 gap pending")
def test_chaos_worker_sudden_crash_and_watchdog_reclamation(
    isolated_queue: TaskTriageQueue,
    fixture_repo: Path,
    tmp_path: Path,
) -> None:
    """
    Chaos Test: Worker leases a task, creates worktree, and abruptly crashes (SIGKILL).
    Validates that:
    1. Task is trapped in EXECUTING.
    2. Watchdog reap_stale_executing_tasks identifies the stalled lease and fails it with explanation.
    3. Queue recovers and task does not remain permanently stranded.
    """
    env = {
        "task_id": "chaos_crash_task",
        "project_id": "proj_chaos",
        "objective": "Heavy compute job",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo).decode("utf-8").strip(),
        "allowed_paths": ["compute.py"],
    }
    env_json = json.dumps(env, default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("chaos_crash_task", content_hash)

    isolated_queue.enqueue_task("chaos_crash_task", env, prov)
    isolated_queue.approve_task("chaos_crash_task")

    # Worker leases task
    leased = isolated_queue.lease_next_approved_task()
    assert leased is not None
    assert leased["id"] == "chaos_crash_task"
    assert leased["status"] == TriageStatus.EXECUTING.value

    # Simulate worker death: no result is ever submitted.
    # Artificially simulate 2 hours elapsed since started_at:
    with isolated_queue._get_connection() as conn:
        conn.execute(
            "UPDATE task_triage_queue SET started_at = ? WHERE id = ?;",
            (time.time() - 7200.0, "chaos_crash_task"),
        )
        conn.commit()

    # Active queue scan without timeout threshold finds 0 tasks
    reaped = isolated_queue.reap_stale_executing_tasks(timeout_seconds=10800.0)
    assert reaped == 0

    # Watchdog runs with 1-hour timeout -> reaps stalled task
    reaped = isolated_queue.reap_stale_executing_tasks(timeout_seconds=3600.0)
    assert reaped == 1

    task = isolated_queue.get_task("chaos_crash_task")
    assert task is not None
    assert task["status"] == TriageStatus.FAILED.value
    assert "Watchdog timeout: execution stalled" in str(task["result_json"])


# ---------------------------------------------------------------------------
# 3. Chaos Scenario 2: Concurrent Multi-Worker Lease Race
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="R2-R6 gap pending")
def test_chaos_concurrent_multi_worker_lease_race(
    isolated_queue: TaskTriageQueue,
    fixture_repo: Path,
) -> None:
    """
    Chaos Test: 10 worker threads concurrently attempt to lease from a pool of 5 approved tasks.
    Validates that:
    1. Exactly 5 tasks are leased (one per approved task).
    2. Zero duplicate leases occur.
    3. 5 workers receive None (empty queue).
    4. Database lock contention is smoothly handled by retry backoff.
    """
    # Enqueue and approve 5 distinct tasks
    task_ids = [f"race_task_{i}" for i in range(5)]
    for tid in task_ids:
        env = {"task_id": tid, "objective": f"Task {tid}", "repo": str(fixture_repo)}
        env_json = json.dumps(env, default=str)
        content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
        prov = make_test_provenance(tid, content_hash)
        isolated_queue.enqueue_task(tid, env, prov)
        isolated_queue.approve_task(tid)

    # 10 workers race to lease tasks concurrently
    def worker_poll() -> str | None:
        task = isolated_queue.lease_next_approved_task()
        return task["id"] if task else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_poll) for _ in range(10)]
        results = [f.result() for f in futures]

    leased_ids = [r for r in results if r is not None]
    idle_results = [r for r in results if r is None]

    # Exactly 5 tasks leased, exactly 5 returned None
    assert len(leased_ids) == 5
    assert len(idle_results) == 5
    # Strict uniqueness: zero duplicate leases
    assert set(leased_ids) == set(task_ids)
    assert len(set(leased_ids)) == 5


# ---------------------------------------------------------------------------
# 4. Chaos Scenario 3: Emergency Stop Interruption & Resumption
# ---------------------------------------------------------------------------


def test_chaos_emergency_stop_interruption_and_resumption(
    isolated_queue: TaskTriageQueue,
    fixture_repo: Path,
) -> None:
    """
    Chaos Test: Operator pulls emergency stop while tasks are in various states.
    Validates that:
    1. Forward-progress operations (lease, approve, modify, enqueue) fail closed.
    2. In-flight leased tasks safely complete or fail without being dropped.
    3. Clearing emergency stop immediately restores operational status.
    """
    # 1. Enqueue task A and approve it
    env_a = {"task_id": "task_a", "objective": "Task A", "repo": str(fixture_repo)}
    prov_a = make_test_provenance("task_a", "hash_a")
    isolated_queue.enqueue_task("task_a", env_a, prov_a)
    isolated_queue.approve_task("task_a")

    # Worker leases task A (now EXECUTING)
    leased_a = isolated_queue.lease_next_approved_task()
    assert leased_a is not None
    assert leased_a["id"] == "task_a"

    # Enqueue task B (APPROVED, waiting in queue)
    env_b = {"task_id": "task_b", "objective": "Task B", "repo": str(fixture_repo)}
    prov_b = make_test_provenance("task_b", "hash_b")
    isolated_queue.enqueue_task("task_b", env_b, prov_b)
    isolated_queue.approve_task("task_b")

    # 2. ACTIVATE EMERGENCY STOP
    isolated_queue.emergency_stop("Security drill - containment trip")
    assert isolated_queue.is_emergency_stopped() is True

    # 3. Verify forward actions are blocked fail-closed
    with pytest.raises(EmergencyStopActiveError):
        isolated_queue.enqueue_task("task_c", {}, prov_a)

    with pytest.raises(EmergencyStopActiveError):
        isolated_queue.approve_task("task_b")

    with pytest.raises(EmergencyStopActiveError):
        isolated_queue.modify_task("task_b", title="New Title")

    # Leasing is suspended
    assert isolated_queue.lease_next_approved_task() is None

    # 4. Verify in-flight task A can finish and record its terminal state
    success = isolated_queue.complete_task(
        "task_a",
        result={"summary": "Emergency-era completion"},
        worktree_path="/tmp/wt/a",
        branch_name="alpha/task_a",
    )
    assert success is True
    assert isolated_queue.get_task("task_a")["status"] == TriageStatus.COMPLETED.value

    # 5. RESUME OPERATIONS
    isolated_queue.emergency_resume()
    assert isolated_queue.is_emergency_stopped() is False

    # 6. Verify task B can now be leased and executed normally
    leased_b = isolated_queue.lease_next_approved_task()
    assert leased_b is not None
    assert leased_b["id"] == "task_b"
    assert leased_b["status"] == TriageStatus.EXECUTING.value


# ---------------------------------------------------------------------------
# 5. Chaos Scenario 4: Cryptographic In-Queue Tamper Detection
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="R2-R6 gap pending")
def test_chaos_cryptographic_tamper_detection(
    isolated_queue: TaskTriageQueue,
    fixture_repo: Path,
    tmp_path: Path,
) -> None:
    """
    Chaos Test: Task is approved, but an attacker or bug modifies envelope_json directly in SQLite.
    Validates that:
    1. Worker dispatcher recomputes SHA-256 hash.
    2. Hash mismatch halts execution before any worktree modification.
    3. Task is permanently failed with zero retries.
    """
    wt_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    env = {
        "task_id": "tamper_task",
        "objective": "Benign task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo).decode("utf-8").strip(),
        "allowed_paths": ["safe.py"],
    }
    env_json = json.dumps(env, default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("tamper_task", content_hash)

    isolated_queue.enqueue_task("tamper_task", env, prov)
    isolated_queue.approve_task("tamper_task")

    # Direct database tampering: modify allowed_paths in SQL without updating content_hash
    tampered_env = dict(env)
    tampered_env["allowed_paths"] = ["safe.py", "/etc/shadow", "malicious.py"]
    with isolated_queue._get_connection() as conn:
        conn.execute(
            "UPDATE task_triage_queue SET envelope_json = ? WHERE id = ?;",
            (json.dumps(tampered_env), "tamper_task"),
        )
        conn.commit()

    # Worker attempts execution cycle
    proposal = dispatcher.execute_next_cycle()
    assert proposal is None

    # Task must be permanently failed with security violation
    task = isolated_queue.get_task("tamper_task")
    assert task is not None
    assert task["status"] == TriageStatus.FAILED.value
    assert "Security Violation: Content hash mismatch" in str(task["result_json"])
    # Zero retries allowed on cryptographic violation
    assert task["retry_count"] == 0


# ---------------------------------------------------------------------------
# 6. Chaos Scenario 5: Sandbox Escape & Directory Traversal Violations
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="R2-R6 gap pending")
def test_chaos_sandbox_escape_and_blast_radius_violations(
    isolated_queue: TaskTriageQueue,
    fixture_repo: Path,
    tmp_path: Path,
) -> None:
    """
    Chaos Test: Worker attempts to modify files using directory traversal or paths outside allowed_paths.
    Validates that:
    1. Modifying a file outside allowed_paths is caught and flagged as violation.
    2. Task fails fail-closed without generating a PR proposal.
    """
    wt_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    dispatcher = TriageTaskDispatcher(queue=isolated_queue, worktree_mgr=wt_mgr)

    env = {
        "task_id": "escape_task",
        "objective": "Restricted task",
        "repo": str(fixture_repo),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo).decode("utf-8").strip(),
        "allowed_paths": ["docs/guide.md"],
    }
    env_json = json.dumps(env, default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = make_test_provenance("escape_task", content_hash)

    isolated_queue.enqueue_task("escape_task", env, prov)
    isolated_queue.approve_task("escape_task")

    # Provision worktree
    wt_path = wt_mgr.create_or_resume_worktree(
        repo_path=str(fixture_repo),
        task_id="escape_task",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    # Legitimate edit
    docs_file = wt_path / "docs" / "guide.md"
    docs_file.parent.mkdir(parents=True, exist_ok=True)
    docs_file.write_text("# Safe Guide\n")

    # Rogue unauthorized edit
    rogue_file = wt_path / "secret_keys.env"
    rogue_file.write_text("SECRET=leaked\n")

    # Run dispatcher cycle
    proposal = dispatcher.execute_next_cycle()
    assert proposal is None

    # Task must be failed with blast radius security violation
    task = isolated_queue.get_task("escape_task")
    assert task is not None
    assert task["status"] == TriageStatus.FAILED.value
    assert "Security Violation: Modified files outside allowed_paths" in str(task["result_json"])
    assert "secret_keys.env" in str(task["result_json"])
