"""
testscript/test_worktree_manager.py
Automated tests for Git worktree creation, change detection, commits, and cleanup.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from alpha_core.config import settings
from alpha_worker.worktree import WorktreeManager


@pytest.fixture
def temp_git_repo():
    repo_dir = Path("/tmp/test_alpha_repo")
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Initialize git repo and make first commit
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@alphabrain.ai"], cwd=str(repo_dir), check=True)

    init_file = repo_dir / "README.md"
    init_file.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)

    yield repo_dir

    # Cleanup
    shutil.rmtree(repo_dir, ignore_errors=True)


def test_worktree_lifecycle(temp_git_repo, monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (temp_git_repo.parent,))
    mgr = WorktreeManager(base_worktree_dir=Path("/tmp/test_alpha_worktrees"))
    task_id = "tsk_worktree_test_1"

    # 1. Create worktree
    worktree_path = mgr.create_worktree(
        repo_path=str(temp_git_repo),
        task_id=task_id,
        base_commit="HEAD",
    )
    assert worktree_path.exists()
    assert (worktree_path / "README.md").exists()

    # 2. Modify files in worktree
    new_file = worktree_path / "new_feature.py"
    new_file.write_text("def hello(): return 'world'\n")

    changed = mgr.get_changed_files(worktree_path)
    assert "new_feature.py" in changed

    # 3. Commit changes in worktree
    commit_hash = mgr.commit_changes(worktree_path, "Add new_feature.py")
    assert commit_hash is not None

    # 4. Remove worktree safely
    mgr.remove_worktree(str(temp_git_repo), task_id)
    assert not worktree_path.exists()
