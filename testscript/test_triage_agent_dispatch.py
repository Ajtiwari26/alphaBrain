"""
testscript/test_triage_agent_dispatch.py
Unit tests for AGY coding agent dispatch integration in TriageTaskDispatcher.
"""

import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alpha_core.config import settings
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue
from alpha_worker.adapters.antigravity_live import AGYAttemptStatus, AntigravityDispatch
from alpha_worker.triage_dispatcher import TriageTaskDispatcher


def create_test_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, check=True)
    (path / "README.md").write_text("Hello")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True)
    return path


def test_triage_dispatcher_invokes_agy_live_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proves that TriageTaskDispatcher invokes AntigravityLiveBridge when enabled."""
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", [tmp_path])
    monkeypatch.setattr(settings, "WORKTREE_BASE_DIR", tmp_path / "worktrees")

    repo = create_test_git_repo(tmp_path / "repo")
    db_path = tmp_path / "queue.db"
    queue = TaskTriageQueue(db_path=db_path)

    mock_bridge = MagicMock()
    mock_bridge.check_readiness.return_value = (True, "Ready")

    async def fake_dispatch(task, worktree_path, attempt_id, session_dir):
        (worktree_path / "agent_output.py").write_text("# Autonomously created by AGY\n")
        return AntigravityDispatch(
            conversation_id="conv_123",
            completed=True,
            blocked_reason=None,
            tool_names=("write_to_file",),
            final_message="Done",
            transcript_path=None,
            status=AGYAttemptStatus.SUCCEEDED,
            changed_files=("agent_output.py",),
        )

    mock_bridge.dispatch.side_effect = fake_dispatch

    dispatcher = TriageTaskDispatcher(
        queue=queue,
        live_bridge=mock_bridge,
        enable_agent_execution=True,
    )

    env = {
        "task_id": "task_agy_1",
        "project_id": "test_proj",
        "repo": str(repo),
        "base_commit": "HEAD",
        "objective": "Auto-code feature",
        "allowed_paths": ["agent_output.py"],
        "acceptance_plan": {"commands": [{"executable": "python3", "args": ["-c", "exit(0)"]}]},
    }
    env_json = json.dumps(env, default=str)
    content_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    prov = TaskProvenance(
        meeting_id="meet_1",
        speaker_id="founder",
        utterance_timestamp=100.0,
        transcript_excerpt="do it",
        extraction_model="pro",
        extraction_confidence=1.0,
        eva_session_id="eva_1",
        created_at=100.0,
        content_hash=content_hash,
    )

    queue.enqueue_task("task_agy_1", env, prov)
    queue.approve_task("task_agy_1")

    proposal = dispatcher.execute_next_cycle()

    assert proposal is not None
    assert proposal.task_id == "task_agy_1"
    assert "agent_output.py" in proposal.files_changed
    assert proposal.gates_passed is True
    assert mock_bridge.dispatch.called


def test_triage_dispatcher_eva_hash_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proves that TriageTaskDispatcher accepts Eva semantic content hash format."""
    from alpha_core.eva.queue_producer import EvaQueueProducer

    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", [tmp_path])
    monkeypatch.setattr(settings, "WORKTREE_BASE_DIR", tmp_path / "worktrees")

    repo = create_test_git_repo(tmp_path / "repo2")
    db_path = tmp_path / "queue2.db"
    queue = TaskTriageQueue(db_path=db_path)

    dispatcher = TriageTaskDispatcher(
        queue=queue,
        enable_agent_execution=False,
    )

    title = "Semantic Task Title"
    crit = ["criterion 1"]
    paths = ["file.txt"]
    eva_hash = EvaQueueProducer.compute_content_hash(
        title=title, acceptance_criteria=crit, allowed_paths=paths
    )

    env = {
        "task_id": "task_eva_hash_1",
        "project_id": "test_proj",
        "repo": str(repo),
        "base_commit": "HEAD",
        "title": title,
        "acceptance_criteria": crit,
        "allowed_paths": paths,
        "acceptance_plan": {"commands": [{"executable": "python3", "args": ["-c", "exit(0)"]}]},
    }
    prov = TaskProvenance(
        meeting_id="meet_1",
        speaker_id="founder",
        utterance_timestamp=100.0,
        transcript_excerpt="excerpt",
        extraction_model="pro",
        extraction_confidence=1.0,
        eva_session_id="eva_1",
        created_at=100.0,
        content_hash=eva_hash,
    )

    queue.enqueue_task("task_eva_hash_1", env, prov)
    queue.approve_task("task_eva_hash_1")

    # Manually stage file in worktree for this test (since agent execution is False)
    branch_name = "alpha/task_eva_hash_1"
    subprocess.run(["git", "branch", branch_name, "HEAD"], cwd=repo, check=True)
    wt = tmp_path / "worktrees" / "task_eva_hash_1"
    wt.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "worktree", "add", str(wt), branch_name], cwd=repo, check=True)
    (wt / "file.txt").write_text("modified")

    proposal = dispatcher.execute_next_cycle()
    assert proposal is not None
    assert proposal.task_id == "task_eva_hash_1"
    assert "file.txt" in proposal.files_changed
