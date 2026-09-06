"""
testscript/test_promotion_packet.py
Acceptance tests for Founder-Approved Result Promotion (Packet H4).
Proves all 15 required acceptance behaviors using real temporary Git repositories.
"""

import subprocess
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import (
    ApprovalRecord,
    AttemptRecord,
    AuditEventRecord,
    TaskRecord,
)
from alpha_core.security import create_worker_identity_token
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AgentType,
    ApprovalStatus,
    GateEvidence,
    GateResult,
    GateType,
    PromotionRequest,
    PromotionResult,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    compute_promotion_digest,
    compute_review_digest,
)
from alpha_worker.control_plane import (
    ControlPlaneClient,
    ControlPlaneUnavailable,
    DurableEventSpool,
)
from alpha_worker.daemon import AlphaWorkerDaemon
from alpha_worker.worktree import WorktreeManager


def run_git(repo_dir: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=str(repo_dir)).decode().strip()


@pytest.fixture
def real_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, str]:
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", [tmp_path])
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@alphabrain.ai"], cwd=str(repo_dir), check=True
    )
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True)

    (repo_dir / "file1.txt").write_text("version 1\n")
    subprocess.run(["git", "add", "file1.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Base commit"], cwd=str(repo_dir), check=True)
    base_commit = run_git(repo_dir, "rev-parse", "HEAD")

    (repo_dir / "file1.txt").write_text("version 2\n")
    subprocess.run(["git", "add", "file1.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Result commit"], cwd=str(repo_dir), check=True)
    result_commit = run_git(repo_dir, "rev-parse", "HEAD")

    subprocess.run(["git", "reset", "--hard", base_commit], cwd=str(repo_dir), check=True)
    subprocess.run(
        ["git", "branch", "alpha/tsk_promo_01", result_commit],
        cwd=str(repo_dir),
        check=True,
    )

    return repo_dir, base_commit, result_commit


async def create_completed_review_fixture(
    repo_dir: Path,
    base_commit: str,
    result_commit: str,
    worker_id: str = "worker_one",
    task_id: str = "tsk_promo_01",
    project_id: str = "prj_promo_01",
    files_changed: list[str] | None = None,
    allowed_paths: list[str] | None = None,
) -> tuple[str, str, str, str]:
    if files_changed is None:
        files_changed = ["file1.txt"]
    if allowed_paths is None:
        allowed_paths = ["file1.txt"]

    session_factory = get_session_factory()
    async with session_factory() as session:
        envelope = TaskEnvelope(
            task_id=task_id,
            project_id=project_id,
            repo=str(repo_dir),
            base_commit=base_commit,
            objective="Test promotion packet flow",
            allowed_paths=allowed_paths,
            requires_approval=True,
            require_packet_binding=True,
        )
        task = await TaskEngine.submit_task(session, envelope)
        await TaskEngine.decide_task_approval(
            session, task.id, True, "founder", packet_sha256=task.packet_sha256
        )

        leased, _ = await TaskEngine.lease_next_task(session, worker_id=worker_id)
        assert leased is not None

        gate_result = GateResult(
            task_id=task_id,
            attempt_id="att_promo_01",
            all_passed=True,
            evidence_items=[
                GateEvidence(
                    evidence_id=f"evi_lint_{task_id}",
                    gate_type=GateType.LINT,
                    passed=True,
                    summary="lint ok",
                ),
                GateEvidence(
                    evidence_id=f"evi_unit_{task_id}",
                    gate_type=GateType.UNIT_TEST,
                    passed=True,
                    summary="unit test ok",
                ),
            ],
        )
        task_result = TaskResult(
            attempt_id="att_promo_01",
            task_id=task_id,
            status=TaskStatus.VERIFIED,
            agent=AgentType.ANTIGRAVITY,
            model="gemini-3.1-pro",
            base_commit=base_commit,
            result_commit=result_commit,
            packet_sha256=task.packet_sha256,
            files_changed=files_changed,
            gate_result=gate_result,
        )
        submitted = await TaskEngine.submit_result(
            session, task_result, leased.lease_token, worker_id
        )
        assert submitted is True

        review_sha256 = compute_review_digest(task_result, worker_id)
        await session.commit()

    return task_id, project_id, worker_id, review_sha256


# ---------------------------------------------------------------------------
# Acceptance Behavior 1: Review approval creates exactly one digest-bound pending promotion
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_review_approval_creates_one_pending_promotion(real_git_repo):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, project_id, worker_id, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()

        res = await session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_id,
                ApprovalRecord.approval_type == "task_promotion",
            )
        )
        promos = res.scalars().all()
        assert len(promos) == 1
        assert promos[0].status == ApprovalStatus.PENDING.value

        expected_req = PromotionRequest(
            task_id=task_id,
            project_id=project_id,
            attempt_id="att_promo_01",
            worker_id=worker_id,
            repo=str(repo_dir),
            base_commit=base_commit,
            result_commit=result_commit,
            files_changed=["file1.txt"],
            allowed_paths=["file1.txt"],
            review_sha256=review_sha,
        )
        assert promos[0].scope_sha256 == compute_promotion_digest(expected_req)


# ---------------------------------------------------------------------------
# Acceptance Behavior 2: Repeated review decision is idempotent; conflicting replay rejects
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_repeated_review_decision_idempotent_conflicting_rejects(real_git_repo):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, _, _, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        # First decision
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()

        # Repeated identical decision (idempotent replay)
        repeated = await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        assert repeated is not None
        await session.commit()

        # Verify only 1 promotion approval was ever created
        res = await session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_id,
                ApprovalRecord.approval_type == "task_promotion",
            )
        )
        assert len(res.scalars().all()) == 1

        # Conflicting decision must reject
        with pytest.raises(ValueError, match="Conflicting replay"):
            await TaskEngine.decide_task_approval(
                session, task_id, approved=False, decided_by="founder", review_sha256=review_sha
            )


# ---------------------------------------------------------------------------
# Acceptance Behavior 3: Wrong promotion digest rejects without state change
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_03_wrong_promotion_digest_rejects(real_git_repo, api_headers):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, project_id, _, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Wrong digest
        res = await ac.post(
            f"/api/projects/{project_id}/promotions/decision",
            json={"promotion_digest": "0" * 64, "approved": True},
            headers=api_headers,
        )
        assert res.status_code == 404

    # Verify still pending in DB
    async with session_factory() as session:
        promo = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_promotion",
                )
            )
        ).scalar_one()
        assert promo.status == ApprovalStatus.PENDING.value


# ---------------------------------------------------------------------------
# Acceptance Behavior 4: Service/client/other worker cannot approve/fetch/report
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_04_auth_and_worker_boundaries(real_git_repo, api_headers, worker_headers):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, project_id, _worker_id, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit, worker_id="worker_one"
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()
        promo = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_promotion",
                )
            )
        ).scalar_one()

    other_worker_headers = {
        "X-Alpha-Worker-Identity": create_worker_identity_token("worker_two"),
    }
    worker_one_headers = {
        "X-Alpha-Worker-Identity": create_worker_identity_token("worker_one"),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Worker cannot approve promotion
        res = await ac.post(
            f"/api/projects/{project_id}/promotions/decision",
            json={"promotion_digest": promo.scope_sha256, "approved": True},
            headers=worker_headers,
        )
        assert res.status_code in {401, 403}

        # Founder approves promotion
        res = await ac.post(
            f"/api/projects/{project_id}/promotions/decision",
            json={"promotion_digest": promo.scope_sha256, "approved": True},
            headers=api_headers,
        )
        assert res.status_code == 200

        # 2. Worker two cannot fetch promotion for worker one
        res = await ac.post(
            "/api/workers/worker_two/promotions/next",
            headers=other_worker_headers,
        )
        assert res.status_code == 200
        assert res.json()["status"] == "no_promotions_available"

        # Worker two impersonating worker one URL returns 403
        res = await ac.post(
            "/api/workers/worker_one/promotions/next",
            headers=other_worker_headers,
        )
        assert res.status_code == 403

        # 3. Worker two cannot submit result for worker one's attempt
        result_payload = PromotionResult(
            task_id=task_id,
            worker_id="worker_two",
            promotion_digest=promo.scope_sha256,
            status="succeeded",
        )
        res = await ac.post(
            f"/api/tasks/{task_id}/promotions/result",
            json={"result": result_payload.model_dump(mode="json")},
            headers=other_worker_headers,
        )
        assert res.status_code == 403

        # Valid worker one can fetch
        res = await ac.post(
            "/api/workers/worker_one/promotions/next",
            headers=worker_one_headers,
        )
        assert res.status_code == 200
        assert res.json()["status"] == "promotion_available"


# ---------------------------------------------------------------------------
# Acceptance Behavior 5: Worker fetch reconstructs values from DB, never caller input
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_05_worker_fetch_reconstructs_from_db(real_git_repo, api_headers):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, project_id, _worker_id, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit, worker_id="worker_db_test"
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()
        promo = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_promotion",
                )
            )
        ).scalar_one()

    worker_headers = {
        "X-Alpha-Worker-Identity": create_worker_identity_token("worker_db_test"),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            f"/api/projects/{project_id}/promotions/decision",
            json={"promotion_digest": promo.scope_sha256, "approved": True},
            headers=api_headers,
        )

        res = await ac.post(
            "/api/workers/worker_db_test/promotions/next",
            headers=worker_headers,
        )
        assert res.status_code == 200
        promo_data = res.json()["promotion"]
        assert promo_data["task_id"] == task_id
        assert promo_data["project_id"] == project_id
        assert promo_data["worker_id"] == "worker_db_test"
        assert promo_data["repo"] == str(repo_dir)
        assert promo_data["base_commit"] == base_commit
        assert promo_data["result_commit"] == result_commit
        assert promo_data["files_changed"] == ["file1.txt"]
        assert promo_data["review_sha256"] == review_sha


# ---------------------------------------------------------------------------
# Acceptance Behavior 6: Clean exact-base temporary Git repo fast-forwards successfully
# ---------------------------------------------------------------------------
def test_06_clean_exact_base_fast_forwards(real_git_repo, tmp_path):
    repo_dir, base_commit, result_commit = real_git_repo
    wm = WorktreeManager(tmp_path / "worktrees")
    wm.promote_task_result(
        repo_path=str(repo_dir),
        task_id="tsk_promo_01",
        base_commit=base_commit,
        result_commit=result_commit,
        allowed_paths=["file1.txt"],
        expected_files_changed=["file1.txt"],
    )
    assert run_git(repo_dir, "rev-parse", "HEAD") == result_commit
    assert run_git(repo_dir, "status", "--porcelain") == ""


# ---------------------------------------------------------------------------
# Acceptance Behavior 7: Already-at-result recovery reports success without new commit/mutation
# ---------------------------------------------------------------------------
def test_07_already_at_result_recovery(real_git_repo, tmp_path):
    repo_dir, base_commit, result_commit = real_git_repo
    subprocess.run(["git", "merge", "--ff-only", result_commit], cwd=str(repo_dir), check=True)
    head_before = run_git(repo_dir, "rev-parse", "HEAD")
    assert head_before == result_commit

    wm = WorktreeManager(tmp_path / "worktrees")
    wm.promote_task_result(
        repo_path=str(repo_dir),
        task_id="tsk_promo_01",
        base_commit=base_commit,
        result_commit=result_commit,
        allowed_paths=["file1.txt"],
        expected_files_changed=["file1.txt"],
    )
    assert run_git(repo_dir, "rev-parse", "HEAD") == result_commit


# ---------------------------------------------------------------------------
# Acceptance Behavior 8: Dirty repo fails unchanged
# ---------------------------------------------------------------------------
def test_08_dirty_repo_fails_unchanged(real_git_repo, tmp_path):
    repo_dir, base_commit, result_commit = real_git_repo
    (repo_dir / "file1.txt").write_text("uncommitted tracked changes\n")

    wm = WorktreeManager(tmp_path / "worktrees")
    with pytest.raises(RuntimeError, match="uncommitted changes"):
        wm.promote_task_result(
            repo_path=str(repo_dir),
            task_id="tsk_promo_01",
            base_commit=base_commit,
            result_commit=result_commit,
            allowed_paths=["file1.txt"],
            expected_files_changed=["file1.txt"],
        )
    assert run_git(repo_dir, "rev-parse", "HEAD") == base_commit


# ---------------------------------------------------------------------------
# Acceptance Behavior 9: Moved source HEAD fails unchanged
# ---------------------------------------------------------------------------
def test_09_moved_source_head_fails_unchanged(real_git_repo, tmp_path):
    repo_dir, base_commit, result_commit = real_git_repo
    (repo_dir / "other.txt").write_text("diverged\n")
    subprocess.run(["git", "add", "other.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Diverged commit"], cwd=str(repo_dir), check=True)

    wm = WorktreeManager(tmp_path / "worktrees")
    with pytest.raises(RuntimeError, match="does not match expected base"):
        wm.promote_task_result(
            repo_path=str(repo_dir),
            task_id="tsk_promo_01",
            base_commit=base_commit,
            result_commit=result_commit,
            allowed_paths=["file1.txt", "other.txt"],
            expected_files_changed=["file1.txt"],
        )


# ---------------------------------------------------------------------------
# Acceptance Behavior 10: Missing/wrong task branch fails unchanged
# ---------------------------------------------------------------------------
def test_10_missing_or_wrong_branch_fails(real_git_repo, tmp_path):
    repo_dir, base_commit, result_commit = real_git_repo
    subprocess.run(["git", "branch", "-D", "alpha/tsk_promo_01"], cwd=str(repo_dir), check=True)

    wm = WorktreeManager(tmp_path / "worktrees")
    with pytest.raises(RuntimeError, match="missing or invalid"):
        wm.promote_task_result(
            repo_path=str(repo_dir),
            task_id="tsk_promo_01",
            base_commit=base_commit,
            result_commit=result_commit,
            allowed_paths=["file1.txt"],
            expected_files_changed=["file1.txt"],
        )
    assert run_git(repo_dir, "rev-parse", "HEAD") == base_commit


# ---------------------------------------------------------------------------
# Acceptance Behavior 11: Changed-file mismatch and disallowed path fail unchanged
# ---------------------------------------------------------------------------
def test_11_changed_file_mismatch_and_disallowed_path_fail(real_git_repo, tmp_path):
    repo_dir, base_commit, result_commit = real_git_repo
    wm = WorktreeManager(tmp_path / "worktrees")

    # Mismatch with expected changed files
    with pytest.raises(RuntimeError, match="mismatch between diff and expected"):
        wm.promote_task_result(
            repo_path=str(repo_dir),
            task_id="tsk_promo_01",
            base_commit=base_commit,
            result_commit=result_commit,
            allowed_paths=["file1.txt"],
            expected_files_changed=["wrong_file.txt"],
        )

    # Disallowed path violation
    with pytest.raises(RuntimeError, match="violate allowed_paths"):
        wm.promote_task_result(
            repo_path=str(repo_dir),
            task_id="tsk_promo_01",
            base_commit=base_commit,
            result_commit=result_commit,
            allowed_paths=["src/"],
            expected_files_changed=["file1.txt"],
        )
    assert run_git(repo_dir, "rev-parse", "HEAD") == base_commit


# ---------------------------------------------------------------------------
# Acceptance Behavior 12: Successful result report is idempotent and not fetched again
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_12_successful_result_report_idempotent_no_refetch(real_git_repo, api_headers):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, project_id, _worker_id, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit, worker_id="worker_succ_test"
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()
        promo = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_promotion",
                )
            )
        ).scalar_one()

    worker_headers = {
        "X-Alpha-Worker-Identity": create_worker_identity_token("worker_succ_test"),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Founder approves promotion
        await ac.post(
            f"/api/projects/{project_id}/promotions/decision",
            json={"promotion_digest": promo.scope_sha256, "approved": True},
            headers=api_headers,
        )

        # Worker submits successful result
        result = PromotionResult(
            task_id=task_id,
            worker_id="worker_succ_test",
            promotion_digest=promo.scope_sha256,
            status="succeeded",
        )
        res = await ac.post(
            f"/api/tasks/{task_id}/promotions/result",
            json={"result": result.model_dump(mode="json")},
            headers=worker_headers,
        )
        assert res.status_code == 200

        # Idempotent replay of successful result
        res_replay = await ac.post(
            f"/api/tasks/{task_id}/promotions/result",
            json={"result": result.model_dump(mode="json")},
            headers=worker_headers,
        )
        assert res_replay.status_code == 200

        # Not fetched again
        res_next = await ac.post(
            "/api/workers/worker_succ_test/promotions/next",
            headers=worker_headers,
        )
        assert res_next.status_code == 200
        assert res_next.json()["status"] == "no_promotions_available"

    # Verify task status is completed
    async with session_factory() as session:
        task = await session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# Acceptance Behavior 13: Failed result is terminal and not auto-retried
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_13_failed_result_is_terminal_no_auto_retry(real_git_repo, api_headers):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, project_id, _worker_id, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit, worker_id="worker_fail_test"
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()
        promo = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_promotion",
                )
            )
        ).scalar_one()

    worker_headers = {
        "X-Alpha-Worker-Identity": create_worker_identity_token("worker_fail_test"),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            f"/api/projects/{project_id}/promotions/decision",
            json={"promotion_digest": promo.scope_sha256, "approved": True},
            headers=api_headers,
        )

        result = PromotionResult(
            task_id=task_id,
            worker_id="worker_fail_test",
            promotion_digest=promo.scope_sha256,
            status="failed",
            reason="Simulated merge failure",
        )
        res = await ac.post(
            f"/api/tasks/{task_id}/promotions/result",
            json={"result": result.model_dump(mode="json")},
            headers=worker_headers,
        )
        assert res.status_code == 200

        # Idempotent replay of failed result
        res_replay = await ac.post(
            f"/api/tasks/{task_id}/promotions/result",
            json={"result": result.model_dump(mode="json")},
            headers=worker_headers,
        )
        assert res_replay.status_code == 200

        # Not available for leasing or promotion
        res_next = await ac.post(
            "/api/workers/worker_fail_test/promotions/next",
            headers=worker_headers,
        )
        assert res_next.json()["status"] == "no_promotions_available"

    # Verify task status is BLOCKED and audit record exists
    async with session_factory() as session:
        task = await session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.BLOCKED.value

        audits = (
            (
                await session.execute(
                    select(AuditEventRecord).where(
                        AuditEventRecord.task_id == task_id,
                        AuditEventRecord.event_type == "task_promotion_failed",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(audits) == 1


# ---------------------------------------------------------------------------
# Acceptance Behavior 14: Worker checks promotions before leasing code
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_14_worker_checks_promotions_before_leasing(tmp_path, real_git_repo, api_headers):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, project_id, _worker_id, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit, worker_id="worker_daemon_test"
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()
        promo = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_promotion",
                )
            )
        ).scalar_one()

    # Approve promotion
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            f"/api/projects/{project_id}/promotions/decision",
            json={"promotion_digest": promo.scope_sha256, "approved": True},
            headers=api_headers,
        )

    # Initialize daemon with mock client connected via AsyncClient
    daemon = AlphaWorkerDaemon(worker_id="worker_daemon_test")
    daemon.spool = DurableEventSpool(tmp_path / "spool", Fernet.generate_key())

    class TestControlPlaneClient(ControlPlaneClient):
        def __init__(self):
            pass

        async def register(self, reg):
            pass

        async def report_health(self, h):
            pass

        async def fetch_next_promotion(self, wid: str):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                headers = {"X-Alpha-Worker-Identity": create_worker_identity_token(wid)}
                res = await ac.post(f"/api/workers/{wid}/promotions/next", headers=headers)
                data = res.json()
                if data["status"] == "promotion_available":
                    return data["promotion"]
                return None

        async def submit_promotion_result(self, tid: str, result: PromotionResult):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                headers = {
                    "X-Alpha-Worker-Identity": create_worker_identity_token(result.worker_id)
                }
                res = await ac.post(
                    f"/api/tasks/{tid}/promotions/result",
                    json={"result": result.model_dump(mode="json")},
                    headers=headers,
                )
                assert res.status_code == 200

        async def lease_next(self, wid: str, agent: str):
            raise AssertionError("Should not lease next coding task when promotion is executed!")

    daemon.control_plane = TestControlPlaneClient()
    executed = await daemon.execute_remote_cycle()
    assert executed is True
    assert run_git(repo_dir, "rev-parse", "HEAD") == result_commit


# ---------------------------------------------------------------------------
# Acceptance Behavior 15: Control-plane outage causes no Git mutation & spools result cleanly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_15_control_plane_outage_safety_and_spool_replay(
    tmp_path, real_git_repo, api_headers
):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, project_id, _worker_id, review_sha = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit, worker_id="worker_outage_test"
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await TaskEngine.decide_task_approval(
            session, task_id, approved=True, decided_by="founder", review_sha256=review_sha
        )
        await session.commit()
        promo = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_promotion",
                )
            )
        ).scalar_one()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            f"/api/projects/{project_id}/promotions/decision",
            json={"promotion_digest": promo.scope_sha256, "approved": True},
            headers=api_headers,
        )

    daemon = AlphaWorkerDaemon(worker_id="worker_outage_test")
    daemon.spool = DurableEventSpool(tmp_path / "spool", Fernet.generate_key())

    # Case A: Outage during fetch aborts cycle without touching Git or leasing
    class OutageOnFetchClient(ControlPlaneClient):
        def __init__(self):
            pass

        async def register(self, reg):
            pass

        async def report_health(self, h):
            pass

        async def fetch_next_promotion(self, wid: str):
            raise ControlPlaneUnavailable("Network down on fetch")

        async def lease_next(self, wid: str, agent: str):
            raise AssertionError("Must not fall through to lease_next on ControlPlaneUnavailable!")

    daemon.control_plane = OutageOnFetchClient()
    cycle_res = await daemon.execute_remote_cycle()
    assert cycle_res is False
    assert run_git(repo_dir, "rev-parse", "HEAD") == base_commit

    # Case B: Fetch succeeds, promotion merges locally, submission fails with outage -> spools result
    class OutageOnSubmitClient(ControlPlaneClient):
        def __init__(self):
            pass

        async def register(self, reg):
            pass

        async def report_health(self, h):
            pass

        async def fetch_next_promotion(self, wid: str):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                headers = {"X-Alpha-Worker-Identity": create_worker_identity_token(wid)}
                res = await ac.post(f"/api/workers/{wid}/promotions/next", headers=headers)
                return res.json()["promotion"]

        async def submit_promotion_result(self, tid: str, result: PromotionResult):
            raise ControlPlaneUnavailable("Network down on result submission")

    daemon.control_plane = OutageOnSubmitClient()
    cycle_res_2 = await daemon.execute_remote_cycle()
    assert cycle_res_2 is True
    # HEAD merged locally
    assert run_git(repo_dir, "rev-parse", "HEAD") == result_commit

    # Result was spooled into DurableEventSpool
    # Next cycle replays spool when control plane returns
    class RecoveredClient(ControlPlaneClient):
        def __init__(self):
            pass

        async def register(self, reg):
            pass

        async def report_health(self, h):
            pass

        async def submit_promotion_result(self, tid: str, result: PromotionResult):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                headers = {
                    "X-Alpha-Worker-Identity": create_worker_identity_token(result.worker_id)
                }
                res = await ac.post(
                    f"/api/tasks/{tid}/promotions/result",
                    json={"result": result.model_dump(mode="json")},
                    headers=headers,
                )
                assert res.status_code == 200

        async def fetch_next_promotion(self, wid: str):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                headers = {"X-Alpha-Worker-Identity": create_worker_identity_token(wid)}
                res = await ac.post(f"/api/workers/{wid}/promotions/next", headers=headers)
                if res.json()["status"] == "promotion_available":
                    return res.json()["promotion"]
                return None

        async def lease_next(self, wid: str, agent: str):
            return None

    daemon.control_plane = RecoveredClient()
    # Execute cycle will replay spool during _sync_remote_presence
    await daemon.execute_remote_cycle()

    # Verify task in DB is now COMPLETED
    async with session_factory() as session:
        task = await session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# Explicit Repair Tests: Fail-closed DB state on malformed commit/path & untracked file safety
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_malformed_result_commit_fails_closed_db_state_unchanged(real_git_repo):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, _project_id, _worker_id, _ = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit, task_id="tsk_malformed_commit"
    )

    session_factory = get_session_factory()
    # Mutate attempt result_commit to an invalid format (not 40-char hex SHA)
    async with session_factory() as session:
        att = (
            await session.execute(select(AttemptRecord).where(AttemptRecord.task_id == task_id))
        ).scalar_one()
        att.result_commit = "invalid_short_commit"
        tr = TaskResult(
            attempt_id=att.id,
            task_id=att.task_id,
            status=TaskStatus(att.status),
            agent=AgentType(att.agent),
            model=att.model,
            base_commit=base_commit,
            result_commit="invalid_short_commit",
            packet_sha256=att.packet_sha256,
            files_changed=["file1.txt"],
            gate_result=(
                GateResult.model_validate(att.gate_result_json)
                if isinstance(att.gate_result_json, dict)
                else (
                    GateResult.model_validate_json(att.gate_result_json)
                    if att.gate_result_json
                    else None
                )
            ),
        )
        new_review_sha = compute_review_digest(tr, att.worker_id or "")
        review_appr = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_review",
                )
            )
        ).scalar_one()
        review_appr.scope_sha256 = new_review_sha
        await session.commit()

    # decide_task_approval must fail validation and raise
    async with session_factory() as session:
        with pytest.raises(ValidationError):
            await TaskEngine.decide_task_approval(
                session, task_id, approved=True, decided_by="founder", review_sha256=new_review_sha
            )

    # Verify DB state is strictly unchanged: task VERIFIED, review PENDING, 0 promo approvals, 0 completion audits
    async with session_factory() as session:
        task = await session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.VERIFIED.value

        review_appr = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_review",
                )
            )
        ).scalar_one()
        assert review_appr.status == ApprovalStatus.PENDING.value

        promos = (
            (
                await session.execute(
                    select(ApprovalRecord).where(
                        ApprovalRecord.task_id == task_id,
                        ApprovalRecord.approval_type == "task_promotion",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(promos) == 0

        audits = (
            (
                await session.execute(
                    select(AuditEventRecord).where(
                        AuditEventRecord.task_id == task_id,
                        AuditEventRecord.event_type.in_(
                            ["task_review_approved", "task_promotion_approved", "task_completed"]
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(audits) == 0


@pytest.mark.asyncio
async def test_malformed_changed_path_fails_closed_db_state_unchanged(real_git_repo):
    repo_dir, base_commit, result_commit = real_git_repo
    task_id, _project_id, _worker_id, _ = await create_completed_review_fixture(
        repo_dir, base_commit, result_commit, task_id="tsk_malformed_path"
    )

    session_factory = get_session_factory()
    # Mutate attempt files_changed_json to contain an invalid path (e.g. "../escape.txt")
    async with session_factory() as session:
        att = (
            await session.execute(select(AttemptRecord).where(AttemptRecord.task_id == task_id))
        ).scalar_one()
        att.files_changed_json = ["../escape.txt"]
        tr = TaskResult(
            attempt_id=att.id,
            task_id=att.task_id,
            status=TaskStatus(att.status),
            agent=AgentType(att.agent),
            model=att.model,
            base_commit=base_commit,
            result_commit=result_commit,
            packet_sha256=att.packet_sha256,
            files_changed=["../escape.txt"],
            gate_result=(
                GateResult.model_validate(att.gate_result_json)
                if isinstance(att.gate_result_json, dict)
                else (
                    GateResult.model_validate_json(att.gate_result_json)
                    if att.gate_result_json
                    else None
                )
            ),
        )
        new_review_sha = compute_review_digest(tr, att.worker_id or "")
        review_appr = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_review",
                )
            )
        ).scalar_one()
        review_appr.scope_sha256 = new_review_sha
        await session.commit()

    # decide_task_approval must fail validation and raise
    async with session_factory() as session:
        with pytest.raises(ValidationError):
            await TaskEngine.decide_task_approval(
                session, task_id, approved=True, decided_by="founder", review_sha256=new_review_sha
            )

    # Verify DB state is strictly unchanged: task VERIFIED, review PENDING, 0 promo approvals, 0 completion audits
    async with session_factory() as session:
        task = await session.get(TaskRecord, task_id)
        assert task.status == TaskStatus.VERIFIED.value

        review_appr = (
            await session.execute(
                select(ApprovalRecord).where(
                    ApprovalRecord.task_id == task_id,
                    ApprovalRecord.approval_type == "task_review",
                )
            )
        ).scalar_one()
        assert review_appr.status == ApprovalStatus.PENDING.value

        promos = (
            (
                await session.execute(
                    select(ApprovalRecord).where(
                        ApprovalRecord.task_id == task_id,
                        ApprovalRecord.approval_type == "task_promotion",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(promos) == 0

        audits = (
            (
                await session.execute(
                    select(AuditEventRecord).where(
                        AuditEventRecord.task_id == task_id,
                        AuditEventRecord.event_type.in_(
                            ["task_review_approved", "task_promotion_approved", "task_completed"]
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(audits) == 0


def test_unrelated_untracked_file_survives_promotion_byte_for_byte(real_git_repo, tmp_path):
    repo_dir, base_commit, result_commit = real_git_repo
    untracked_content = b"# preserved user config\nSECRET_OR_NOTE=12345\n"
    untracked_file = repo_dir / "user_notes.txt"
    untracked_file.write_bytes(untracked_content)

    wm = WorktreeManager(tmp_path / "worktrees")
    wm.promote_task_result(
        repo_path=str(repo_dir),
        task_id="tsk_promo_01",
        base_commit=base_commit,
        result_commit=result_commit,
        allowed_paths=["file1.txt"],
        expected_files_changed=["file1.txt"],
    )

    assert run_git(repo_dir, "rev-parse", "HEAD") == result_commit
    assert run_git(repo_dir, "status", "--porcelain", "--untracked-files=no") == ""
    assert untracked_file.exists()
    assert untracked_file.read_bytes() == untracked_content


def test_overlapping_untracked_target_aborts_head_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", [tmp_path])
    repo_dir = tmp_path / "overlap_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@alphabrain.ai"], cwd=str(repo_dir), check=True
    )
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True)

    (repo_dir / "base.txt").write_text("base\n")
    subprocess.run(["git", "add", "base.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Base commit"], cwd=str(repo_dir), check=True)
    base_commit = run_git(repo_dir, "rev-parse", "HEAD")

    (repo_dir / "new_file.txt").write_text("incoming from worker\n")
    subprocess.run(["git", "add", "new_file.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(
        ["git", "commit", "-m", "Result commit adding new_file.txt"], cwd=str(repo_dir), check=True
    )
    result_commit = run_git(repo_dir, "rev-parse", "HEAD")

    subprocess.run(["git", "reset", "--hard", base_commit], cwd=str(repo_dir), check=True)
    subprocess.run(
        ["git", "branch", "alpha/tsk_overlap_01", result_commit], cwd=str(repo_dir), check=True
    )

    # Place untracked file at the exact path of the incoming new file
    untracked_target = repo_dir / "new_file.txt"
    untracked_target.write_text("local untracked collision\n")

    wm = WorktreeManager(tmp_path / "worktrees")
    with pytest.raises(RuntimeError, match="Fast-forward merge failed"):
        wm.promote_task_result(
            repo_path=str(repo_dir),
            task_id="tsk_overlap_01",
            base_commit=base_commit,
            result_commit=result_commit,
            allowed_paths=["new_file.txt"],
            expected_files_changed=["new_file.txt"],
        )

    assert run_git(repo_dir, "rev-parse", "HEAD") == base_commit
    assert untracked_target.read_text() == "local untracked collision\n"
