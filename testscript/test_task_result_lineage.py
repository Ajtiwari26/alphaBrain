"""
testscript/test_task_result_lineage.py
Idiomatic pytest suite verifying the immutable task result lineage contract:
- Valid matching gate IDs and complete lineage persistence
- Negative rejection leaves zero attempts and zero review approvals
- Positive success no-op (result_commit == base_commit with empty files_changed)
- Real repo/worktree retry preservation across attempts
- Disallowed precommit inspection and security rejection
- Commit failure fails closed (raises RuntimeError)
- Inspection failure fails closed (raises RuntimeError)
- Base ancestry violation detection via git merge-base
"""

import subprocess
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.config import settings
from alpha_core.db.models import ApprovalRecord, AttemptRecord, Base, GateEvidenceRecord, TaskRecord
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    GateCommand,
    GateEvidence,
    GateResult,
    GateType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    compute_packet_digest,
)
from alpha_worker.adapters.antigravity import AntigravityAdapter
from alpha_worker.worktree import WorktreeManager


@pytest_asyncio.fixture
async def async_db() -> AsyncSession:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true", echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
def git_identity_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    env = {
        "GIT_AUTHOR_NAME": "Alpha Test",
        "GIT_AUTHOR_EMAIL": "alpha@example.test",
        "GIT_COMMITTER_NAME": "Alpha Test",
        "GIT_COMMITTER_EMAIL": "alpha@example.test",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return env


@pytest.fixture
def temp_git_repo(tmp_path: Path, git_identity_env: dict[str, str]) -> tuple[Path, str]:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Alpha Test"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "alpha@example.test"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    readme = repo_dir / "README.md"
    readme.write_text("# Initial Repository\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    base_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo_dir, base_commit


def build_gate_result(
    task_id: str,
    attempt_id: str,
    all_passed: bool = True,
    evidence_items: list[GateEvidence] | None = None,
) -> GateResult:
    items = evidence_items or [
        GateEvidence(
            evidence_id="evi_lint_01",
            gate_type=GateType.LINT,
            passed=all_passed,
            summary="Lint check",
            metrics={"command_argv": ["ruff", "check"], "exit_code": 0 if all_passed else 1},
        ),
        GateEvidence(
            evidence_id="evi_unit_01",
            gate_type=GateType.UNIT_TEST,
            passed=all_passed,
            summary="Unit tests",
            metrics={"command_argv": ["pytest"], "exit_code": 0 if all_passed else 1},
        ),
    ]
    return GateResult(
        task_id=task_id,
        attempt_id=attempt_id,
        all_passed=all_passed,
        evidence_items=items,
    )


# ---------------------------------------------------------------------------
# 1. Valid matching gate IDs
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_valid_matching_gate_ids(async_db: AsyncSession, temp_git_repo: tuple[Path, str]):
    repo_dir, base_commit = temp_git_repo
    task_id = "tsk_lin_valid_01"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="prj_lin",
        repo=str(repo_dir),
        objective="Verify valid matching gate IDs",
        base_commit=base_commit,
        allowed_paths=["src/"],
        require_packet_binding=True,
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST, GateType.LINT],
            commands=[
                GateCommand(gate_type=GateType.LINT, executable="ruff", args=["check"]),
                GateCommand(gate_type=GateType.UNIT_TEST, executable="pytest", args=[]),
            ],
        ),
    )
    await TaskEngine.submit_task(async_db, envelope, "prj_lin")
    lease = await TaskEngine.lease_next_task(async_db, "worker-1")
    assert lease is not None
    task_rec, _ = lease

    attempt_id = "att_lin_valid_01"
    digest = compute_packet_digest(envelope)
    gate_res = build_gate_result(task_id, attempt_id, all_passed=True)

    result = TaskResult(
        task_id=task_id,
        attempt_id=attempt_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="antigravity-flash",
        base_commit=base_commit,
        result_commit="commit_hash_12345",
        files_changed=["src/feature.py"],
        diff_summary="1 file changed, 10 insertions(+)",
        gate_result=gate_res,
        packet_sha256=digest,
    )

    success = await TaskEngine.submit_result(async_db, result, task_rec.lease_token, "worker-1")
    assert success is True

    att = await async_db.scalar(select(AttemptRecord).where(AttemptRecord.id == attempt_id))
    assert att is not None
    assert att.result_commit == "commit_hash_12345"
    assert att.files_changed_json == ["src/feature.py"]

    evs = (
        (
            await async_db.execute(
                select(GateEvidenceRecord).where(GateEvidenceRecord.task_id == task_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(evs) == 2
    assert {e.gate_type for e in evs} == {"lint", "unit_test"}


# ---------------------------------------------------------------------------
# 2. Negative rejection leaves zero attempts and zero review approvals
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_negative_rejection_leaves_zero_attempts_and_approvals(
    async_db: AsyncSession, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo

    async def run_negative_case(task_id: str, build_bad_result):
        worker_id = f"worker_{task_id}"
        envelope = TaskEnvelope(
            task_id=task_id,
            project_id="prj_lin_neg",
            repo=str(repo_dir),
            objective="Negative lineage rejection test",
            base_commit=base_commit,
            allowed_paths=["."],
            require_packet_binding=True,
        )
        await TaskEngine.submit_task(async_db, envelope, "prj_lin_neg")
        lease = await TaskEngine.lease_next_task(async_db, worker_id)
        assert lease is not None
        task_rec, _ = lease
        token = task_rec.lease_token

        bad_result = build_bad_result(envelope, task_rec)
        rejected = not await TaskEngine.submit_result(async_db, bad_result, token, worker_id)
        assert rejected is True

        # Assert zero attempts recorded
        att_count = await async_db.scalar(
            select(func.count(AttemptRecord.id)).where(AttemptRecord.task_id == task_id)
        )
        assert att_count == 0

        # Assert zero review approvals recorded
        appr_count = await async_db.scalar(
            select(func.count(ApprovalRecord.id)).where(
                ApprovalRecord.task_id == task_id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
        assert appr_count == 0

    digest_fn = compute_packet_digest

    # Case A: Missing result_commit on successful COMPLETED
    await run_negative_case(
        "tsk_neg_no_result_commit",
        lambda env, tr: TaskResult(
            task_id=env.task_id,
            attempt_id="att_neg_a",
            status=TaskStatus.COMPLETED,
            agent=AgentType.ANTIGRAVITY,
            model="model",
            base_commit=base_commit,
            result_commit="",
            files_changed=[],
            packet_sha256=digest_fn(env),
            gate_result=build_gate_result(env.task_id, "att_neg_a"),
        ),
    )

    # Case B: Base commit mismatch
    await run_negative_case(
        "tsk_neg_base_mismatch",
        lambda env, tr: TaskResult(
            task_id=env.task_id,
            attempt_id="att_neg_b",
            status=TaskStatus.COMPLETED,
            agent=AgentType.ANTIGRAVITY,
            model="model",
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            result_commit="commit_new",
            files_changed=["src/a.py"],
            packet_sha256=digest_fn(env),
            gate_result=build_gate_result(env.task_id, "att_neg_b"),
        ),
    )

    # Case C: Files changed but result_commit == base_commit
    await run_negative_case(
        "tsk_neg_files_without_commit_change",
        lambda env, tr: TaskResult(
            task_id=env.task_id,
            attempt_id="att_neg_c",
            status=TaskStatus.COMPLETED,
            agent=AgentType.ANTIGRAVITY,
            model="model",
            base_commit=base_commit,
            result_commit=base_commit,
            files_changed=["src/changed.py"],
            packet_sha256=digest_fn(env),
            gate_result=build_gate_result(env.task_id, "att_neg_c"),
        ),
    )

    # Case D: Non-base result_commit but files_changed is empty
    await run_negative_case(
        "tsk_neg_commit_change_without_files",
        lambda env, tr: TaskResult(
            task_id=env.task_id,
            attempt_id="att_neg_d",
            status=TaskStatus.COMPLETED,
            agent=AgentType.ANTIGRAVITY,
            model="model",
            base_commit=base_commit,
            result_commit="new_commit_hash_abc",
            files_changed=[],
            packet_sha256=digest_fn(env),
            gate_result=build_gate_result(env.task_id, "att_neg_d"),
        ),
    )

    # Case E: Packet digest mismatch
    await run_negative_case(
        "tsk_neg_digest_mismatch",
        lambda env, tr: TaskResult(
            task_id=env.task_id,
            attempt_id="att_neg_e",
            status=TaskStatus.COMPLETED,
            agent=AgentType.ANTIGRAVITY,
            model="model",
            base_commit=base_commit,
            result_commit=base_commit,
            files_changed=[],
            packet_sha256="0" * 64,
            gate_result=build_gate_result(env.task_id, "att_neg_e"),
        ),
    )


# ---------------------------------------------------------------------------
# 3. Positive success no-op
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_positive_success_no_op(async_db: AsyncSession, temp_git_repo: tuple[Path, str]):
    repo_dir, base_commit = temp_git_repo
    task_id = "tsk_lin_noop_01"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="prj_lin",
        repo=str(repo_dir),
        objective="Execute verification-only no-op task",
        base_commit=base_commit,
        allowed_paths=["."],
        require_packet_binding=True,
    )
    await TaskEngine.submit_task(async_db, envelope, "prj_lin")
    lease = await TaskEngine.lease_next_task(async_db, "worker-1")
    assert lease is not None
    task_rec, _ = lease

    attempt_id = "att_lin_noop_01"
    digest = compute_packet_digest(envelope)
    gate_res = build_gate_result(task_id, attempt_id, all_passed=True)

    result = TaskResult(
        task_id=task_id,
        attempt_id=attempt_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="antigravity-flash",
        base_commit=base_commit,
        result_commit=base_commit,
        files_changed=[],
        diff_summary="",
        gate_result=gate_res,
        packet_sha256=digest,
    )

    success = await TaskEngine.submit_result(async_db, result, task_rec.lease_token, "worker-1")
    assert success is True

    att = await async_db.scalar(select(AttemptRecord).where(AttemptRecord.id == attempt_id))
    assert att is not None
    assert att.result_commit == base_commit
    assert att.files_changed_json == []

    updated_task = await async_db.get(TaskRecord, task_id)
    assert updated_task is not None
    assert updated_task.status == TaskStatus.VERIFIED.value


# ---------------------------------------------------------------------------
# 4. Real repo/worktree retry preservation
# ---------------------------------------------------------------------------
def test_real_repo_worktree_retry_preservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    wt_base = tmp_path / "worktrees"
    wm = WorktreeManager(base_worktree_dir=wt_base)
    task_id = "tsk_retry_preserve_01"

    # 1. Create worktree
    wt_path = wm.create_worktree(str(repo_dir), task_id, base_commit)
    assert wt_path.exists()

    # 2. Attempt 1 makes and commits file changes
    feature_file = wt_path / "feature.txt"
    feature_file.write_text("lineage feature v1\n")
    uncommitted = wm.get_uncommitted_files(wt_path)
    assert "feature.txt" in uncommitted

    commit_1 = wm.commit_changes(wt_path, "alpha(task): Attempt 1 [tsk_retry_preserve_01]")
    assert commit_1 is not None
    assert commit_1 != base_commit

    head_1 = wm.get_head_commit(wt_path)
    assert head_1 == commit_1
    changed_1 = wm.get_changed_files(wt_path, base_commit)
    assert changed_1 == ["feature.txt"]
    diff_1 = wm.get_diff_summary(wt_path, base_commit)
    assert "feature.txt" in diff_1

    # 3. Simulate retry on resumed worktree where no new uncommitted changes exist
    resumed_wt = wm.create_or_resume_worktree(str(repo_dir), task_id, base_commit)
    assert resumed_wt == wt_path

    uncommitted_retry = wm.get_uncommitted_files(resumed_wt)
    assert uncommitted_retry == []

    head_retry = wm.get_head_commit(resumed_wt)
    changed_retry = wm.get_changed_files(resumed_wt, base_commit)
    diff_retry = wm.get_diff_summary(resumed_wt, base_commit)

    # Retains prior task commit, files changed, and diff summary
    assert head_retry == commit_1
    assert changed_retry == ["feature.txt"]
    assert diff_retry == diff_1


# ---------------------------------------------------------------------------
# 5. Disallowed precommit inspection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_disallowed_precommit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    adapter = AntigravityAdapter()
    adapter.worktree_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    adapter.memory_graph_path = tmp_path / "memory_graph"

    task = TaskEnvelope(
        task_id="tsk_precommit_disallowed",
        project_id="prj_sec",
        repo=str(repo_dir),
        objective="Restricted edit",
        base_commit=base_commit,
        allowed_paths=["allowed_dir/"],
        acceptance_plan=AcceptancePlan(required_gates=[]),
    )

    wt_path = adapter.worktree_mgr.create_worktree(str(repo_dir), task.task_id, base_commit)

    # Write a disallowed file before commit
    disallowed_file = wt_path / "forbidden.txt"
    disallowed_file.write_text("disallowed content\n")

    mock_dispatch = MagicMock()
    mock_dispatch.completed = True
    mock_dispatch.blocked_reason = None
    mock_dispatch.conversation_id = "conv_sec_01"
    mock_dispatch.tool_names = set()
    mock_dispatch.transcript_path = None
    adapter.live_bridge.dispatch = AsyncMock(return_value=mock_dispatch)  # type: ignore[method-assign]

    result = await adapter.execute(task, wt_path, base_commit)

    assert result.status == TaskStatus.RETRYABLE_FAILED
    assert result.gate_result is not None
    assert result.gate_result.all_passed is False

    sec_ev = [e for e in result.gate_result.evidence_items if e.gate_type == GateType.SECURITY_SCAN]
    assert len(sec_ev) == 1
    assert sec_ev[0].passed is False
    assert "forbidden.txt" in sec_ev[0].artifacts_created

    # Commit was not created; HEAD is still base_commit
    assert result.result_commit == base_commit
    assert result.files_changed == []


# ---------------------------------------------------------------------------
# 5b. Disallowed precommitted inspection (agent creates its own commit)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_disallowed_precommit_scan_after_agent_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    adapter = AntigravityAdapter()
    adapter.worktree_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    adapter.memory_graph_path = tmp_path / "memory_graph"

    task = TaskEnvelope(
        task_id="tsk_precommit_agent_disallowed",
        project_id="prj_sec",
        repo=str(repo_dir),
        objective="Restricted edit",
        base_commit=base_commit,
        allowed_paths=["allowed_dir/"],
        acceptance_plan=AcceptancePlan(required_gates=[]),
    )

    wt_path = adapter.worktree_mgr.create_worktree(str(repo_dir), task.task_id, base_commit)

    # Write a disallowed file and commit it *before* adapter runs execute
    disallowed_file = wt_path / "forbidden.txt"
    disallowed_file.write_text("disallowed content\n")
    subprocess.run(["git", "add", "forbidden.txt"], cwd=str(wt_path), check=True)
    subprocess.run(
        ["git", "commit", "-m", "junior agent sneak commit"], cwd=str(wt_path), check=True
    )

    mock_dispatch = MagicMock()
    mock_dispatch.completed = True
    mock_dispatch.blocked_reason = None
    mock_dispatch.conversation_id = "conv_sec_02"
    mock_dispatch.tool_names = set()
    mock_dispatch.transcript_path = None
    adapter.live_bridge.dispatch = AsyncMock(return_value=mock_dispatch)  # type: ignore[method-assign]

    result = await adapter.execute(task, wt_path, base_commit)

    assert result.status == TaskStatus.RETRYABLE_FAILED
    assert result.gate_result is not None
    assert result.gate_result.all_passed is False

    sec_ev = [e for e in result.gate_result.evidence_items if e.gate_type == GateType.SECURITY_SCAN]
    assert len(sec_ev) == 1
    assert sec_ev[0].passed is False
    assert "forbidden.txt" in sec_ev[0].artifacts_created

    # Commit *was* created by agent, so it's not base_commit
    assert result.result_commit != base_commit
    assert "forbidden.txt" in result.files_changed


# ---------------------------------------------------------------------------
# 5c. Allowed precommitted retry (agent creates commit with allowed files)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_allowed_precommitted_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    adapter = AntigravityAdapter()
    adapter.worktree_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    adapter.memory_graph_path = tmp_path / "memory_graph"

    task = TaskEnvelope(
        task_id="tsk_precommit_agent_allowed",
        project_id="prj_sec",
        repo=str(repo_dir),
        objective="Allowed edit",
        base_commit=base_commit,
        allowed_paths=["allowed_dir/"],
        acceptance_plan=AcceptancePlan(required_gates=[]),
    )

    wt_path = adapter.worktree_mgr.create_worktree(str(repo_dir), task.task_id, base_commit)

    allowed_dir = wt_path / "allowed_dir"
    allowed_dir.mkdir()
    allowed_file = allowed_dir / "safe.txt"
    allowed_file.write_text("allowed content\n")
    subprocess.run(["git", "add", "allowed_dir/safe.txt"], cwd=str(wt_path), check=True)
    subprocess.run(
        ["git", "commit", "-m", "junior agent allowed commit"], cwd=str(wt_path), check=True
    )

    mock_dispatch = MagicMock()
    mock_dispatch.completed = True
    mock_dispatch.blocked_reason = None
    mock_dispatch.conversation_id = "conv_sec_03"
    mock_dispatch.tool_names = set()
    mock_dispatch.transcript_path = None
    adapter.live_bridge.dispatch = AsyncMock(return_value=mock_dispatch)  # type: ignore[method-assign]

    result = await adapter.execute(task, wt_path, base_commit)

    assert result.status == TaskStatus.COMPLETED
    assert result.gate_result is not None
    assert result.gate_result.all_passed is True

    # Ensure no security scan failure
    sec_ev = [e for e in result.gate_result.evidence_items if e.gate_type == GateType.SECURITY_SCAN]
    assert len(sec_ev) == 0

    # Commit *was* created by agent, so it's not base_commit
    assert result.result_commit != base_commit
    assert "allowed_dir/safe.txt" in result.files_changed


# ---------------------------------------------------------------------------
# 5d. Disallowed mixed committed and uncommitted inspection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_disallowed_mixed_committed_and_uncommitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    adapter = AntigravityAdapter()
    adapter.worktree_mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    adapter.memory_graph_path = tmp_path / "memory_graph"

    task = TaskEnvelope(
        task_id="tsk_precommit_mixed_disallowed",
        project_id="prj_sec",
        repo=str(repo_dir),
        objective="Restricted edit with mixed violations",
        base_commit=base_commit,
        allowed_paths=["allowed_dir/"],
        acceptance_plan=AcceptancePlan(required_gates=[]),
    )

    wt_path = adapter.worktree_mgr.create_worktree(str(repo_dir), task.task_id, base_commit)

    # 1. Precommit forbidden_committed.txt
    committed_file = wt_path / "forbidden_committed.txt"
    committed_file.write_text("committed disallowed content\n")
    subprocess.run(["git", "add", "forbidden_committed.txt"], cwd=str(wt_path), check=True)
    subprocess.run(
        ["git", "commit", "-m", "precommitted disallowed file"], cwd=str(wt_path), check=True
    )
    precommit_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(wt_path),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    # 2. Leave forbidden_uncommitted.txt dirty
    uncommitted_file = wt_path / "forbidden_uncommitted.txt"
    uncommitted_file.write_text("uncommitted dirty disallowed content\n")

    mock_dispatch = MagicMock()
    mock_dispatch.completed = True
    mock_dispatch.blocked_reason = None
    mock_dispatch.conversation_id = "conv_sec_04"
    mock_dispatch.tool_names = set()
    mock_dispatch.transcript_path = None
    adapter.live_bridge.dispatch = AsyncMock(return_value=mock_dispatch)  # type: ignore[method-assign]

    result = await adapter.execute(task, wt_path, base_commit)

    assert result.status == TaskStatus.RETRYABLE_FAILED
    assert result.gate_result is not None
    assert result.gate_result.all_passed is False

    sec_ev = [e for e in result.gate_result.evidence_items if e.gate_type == GateType.SECURITY_SCAN]
    assert len(sec_ev) == 1
    assert sec_ev[0].passed is False
    assert "forbidden_committed.txt" in sec_ev[0].artifacts_created
    assert "forbidden_uncommitted.txt" in sec_ev[0].artifacts_created

    # result_commit is non-base (the precommit hash)
    assert result.result_commit == precommit_hash
    assert result.result_commit != base_commit

    # files_changed includes only committed file
    assert result.files_changed == ["forbidden_committed.txt"]
    assert "forbidden_uncommitted.txt" not in result.files_changed

    # dirty file remains uncommitted in worktree
    uncommitted_after = adapter.worktree_mgr.get_uncommitted_files(wt_path)
    assert "forbidden_uncommitted.txt" in uncommitted_after


# ---------------------------------------------------------------------------
# 6. Commit failure fails closed
# ---------------------------------------------------------------------------
def test_commit_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    wm = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    wt_path = wm.create_worktree(str(repo_dir), "tsk_commit_fail", base_commit)

    # Nothing to commit -> git commit returns exit code 1 -> raises RuntimeError
    with pytest.raises(RuntimeError):
        wm.commit_changes(wt_path, "Should fail because worktree is clean")


# ---------------------------------------------------------------------------
# 7. Inspection failure fails closed
# ---------------------------------------------------------------------------
def test_inspection_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    wm = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    wt_path = wm.create_worktree(str(repo_dir), "tsk_inspect_fail", base_commit)

    # Corrupt git link
    git_file = wt_path / ".git"
    git_file.unlink()

    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    with pytest.raises(RuntimeError):
        wm.get_uncommitted_files(wt_path)

    with pytest.raises(RuntimeError):
        wm.get_changed_files(wt_path, base_commit)

    with pytest.raises(RuntimeError):
        wm.get_head_commit(wt_path)


# ---------------------------------------------------------------------------
# 8. Base ancestry violation
# ---------------------------------------------------------------------------
def test_base_ancestry_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, temp_git_repo: tuple[Path, str]
):
    repo_dir, base_commit = temp_git_repo
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    wm = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    wt_path = wm.create_worktree(str(repo_dir), "tsk_ancestry_fail", base_commit)

    unrelated_commit = "0" * 40

    with pytest.raises(RuntimeError):
        wm.assert_base_commit_ancestor(wt_path, unrelated_commit)

    with pytest.raises(RuntimeError):
        wm.get_changed_files(wt_path, unrelated_commit)

    with pytest.raises(RuntimeError):
        wm.get_diff_summary(wt_path, unrelated_commit)
