"""
testscript/test_worktree_manager.py
Automated tests for Git worktree creation, change detection, commits, and cleanup.
"""

import subprocess

import pytest

from alpha_core.config import settings
from alpha_worker.worktree import WorktreeManager


@pytest.fixture
def temp_git_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Initialize git repo and make first commit
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@alphabrain.ai"], cwd=str(repo_dir), check=True
    )

    init_file = repo_dir / "README.md"
    init_file.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)

    yield repo_dir


def test_worktree_lifecycle(temp_git_repo, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (temp_git_repo.parent,))
    mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    task_id = "tsk_worktree_test_1"

    # 1. Create worktree
    worktree_path = mgr.create_worktree(
        repo_path=str(temp_git_repo),
        task_id=task_id,
        base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_git_repo).decode("utf-8").strip(),
    )
    assert worktree_path.exists()
    assert (worktree_path / "README.md").exists()
    assert (
        mgr.create_or_resume_worktree(
            repo_path=str(temp_git_repo), task_id=task_id, base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_git_repo).decode("utf-8").strip()
        )
        == worktree_path
    )

    # 2. Modify files in worktree
    new_file = worktree_path / "new_feature.py"
    new_file.write_text("def hello(): return 'world'\n")

    uncommitted = mgr.get_uncommitted_files(worktree_path)
    assert "new_feature.py" in uncommitted

    # 3. Commit changes in worktree
    base_commit = mgr.get_head_commit(worktree_path)
    commit_hash = mgr.commit_changes(worktree_path, "Add new_feature.py")
    assert commit_hash is not None

    changed = mgr.get_changed_files(worktree_path, base_commit)
    assert "new_feature.py" in changed

    # 4. Remove worktree safely
    mgr.remove_worktree(str(temp_git_repo), task_id)
    assert not worktree_path.exists()


def test_worktree_refuses_dirty_source_and_dirty_cleanup(temp_git_repo, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (temp_git_repo.parent,))
    mgr = WorktreeManager(base_worktree_dir=tmp_path / "worktrees")
    (temp_git_repo / "dirty.txt").write_text("source dirty\n")
    with pytest.raises(RuntimeError, match="uncommitted"):
        mgr.create_worktree(str(temp_git_repo), "tsk_dirty_source")
    (temp_git_repo / "dirty.txt").unlink()

    worktree_path = mgr.create_worktree(str(temp_git_repo), "tsk_dirty_cleanup")
    (worktree_path / "pending.txt").write_text("preserve me\n")
    with pytest.raises(RuntimeError, match="uncommitted"):
        mgr.remove_worktree(str(temp_git_repo), "tsk_dirty_cleanup")
    assert worktree_path.exists()
