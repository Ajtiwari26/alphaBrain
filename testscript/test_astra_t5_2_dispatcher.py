import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_protocol import GateType
from alpha_worker.triage_dispatcher import TriageTaskDispatcher


def get_head_sha(repo_path):
    cwd = os.getcwd()
    os.chdir(repo_path)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    os.chdir(cwd)
    return sha


@pytest.fixture
def temp_repo():
    d = tempfile.mkdtemp()
    cwd = os.getcwd()
    os.chdir(d)
    os.system("git init")
    os.system("git config user.email 'test@example.com'")
    os.system("git config user.name 'Test User'")
    with open("README.md", "w") as f:
        f.write("Initial commit")
    os.system("git add README.md")
    os.system("git commit -m 'Initial'")
    yield d
    os.chdir(cwd)
    shutil.rmtree(d)


class MockQueue(TaskTriageQueue):
    def __init__(self):
        self.failed_tasks = []
        self.completed_tasks = []

    def is_emergency_stopped(self):
        return False

    def lease_next_approved_task(self):
        return None

    def fail_task(self, task_id, error_details=None, allow_retry=False):
        self.failed_tasks.append(
            {"task_id": task_id, "error": error_details.get("error") if error_details else None}
        )

    def complete_task(self, task_id, result, worktree_path, branch_name, *args, **kwargs):
        self.completed_tasks.append(task_id)
        return True


class MockWorktreeManager:
    def create_or_resume_worktree(self, repo_path, task_id, base_commit):
        return Path(repo_path)

    @staticmethod
    def find_disallowed_changes(changed_files, allowed_paths):
        violations = []
        for f in changed_files:
            if f not in allowed_paths:
                violations.append(f)
        return violations


def test_validate_acceptance_plan():
    dispatcher = TriageTaskDispatcher(queue=MockQueue(), enable_agent_execution=False)

    # Test empty plan rejection when required_gates exist
    res = dispatcher.validate_acceptance_plan({"required_gates": ["unit_test"], "commands": []})
    assert res == "Ambiguous empty plan: required_gates present but commands is empty."

    # Test unknown gate_type rejection
    res = dispatcher.validate_acceptance_plan(
        {"commands": [{"gate_type": "magic_gate", "executable": "echo"}]}
    )
    assert "Unknown or missing gate type" in res

    # Test duplicate gate_type
    res = dispatcher.validate_acceptance_plan(
        {
            "commands": [
                {"gate_type": GateType.UNIT_TEST.value, "executable": "echo"},
                {"gate_type": GateType.UNIT_TEST.value, "executable": "ls"},
            ]
        }
    )
    assert "Duplicate command definition" in res

    # Test missing executable
    res = dispatcher.validate_acceptance_plan(
        {"commands": [{"gate_type": GateType.UNIT_TEST.value, "executable": ""}]}
    )
    assert "Command missing executable" in res

    # Valid plan
    res = dispatcher.validate_acceptance_plan(
        {"commands": [{"gate_type": GateType.UNIT_TEST.value, "executable": "pytest"}]}
    )
    assert res is None


def build_task(task_id, envelope):
    import hashlib
    import json

    env_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str)
    ch = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
    return {
        "id": task_id,
        "envelope": envelope,
        "content_hash": ch,
        "attempt_id": f"att_{task_id}_1",
        "worker_id": "test_worker_1",
        "lease_id": "test_lease_1",
        "fencing_epoch": 1,
        "provenance": {
            "lease_metadata": {
                "attempt_id": f"att_{task_id}_1",
                "worker_id": "test_worker_1",
                "lease_id": "test_lease_1",
                "fencing_epoch": 1,
            }
        },
    }


def test_post_commit_symlink_rejection(temp_repo):
    q = MockQueue()
    wm = MockWorktreeManager()
    base_commit = get_head_sha(temp_repo)
    dispatcher = TriageTaskDispatcher(
        queue=q, worktree_mgr=wm, default_base_commit=base_commit, enable_agent_execution=False
    )

    cwd = os.getcwd()
    os.chdir(temp_repo)
    os.symlink("README.md", "link.md")
    os.system("git add link.md")
    os.chdir(cwd)

    envelope = {
        "repo": temp_repo,
        "base_commit": base_commit,
        "allowed_paths": ["link.md"],
        "acceptance_plan": {
            "commands": [{"gate_type": GateType.UNIT_TEST.value, "executable": "echo"}]
        },
    }

    dispatcher.execute_task(build_task("t1", envelope))
    assert len(q.failed_tasks) > 0
    assert "Symlink or submodule added/modified" in q.failed_tasks[0]["error"]


def test_post_commit_uncommitted_residue(temp_repo):
    q = MockQueue()
    wm = MockWorktreeManager()
    base_commit = get_head_sha(temp_repo)
    dispatcher = TriageTaskDispatcher(
        queue=q, worktree_mgr=wm, default_base_commit=base_commit, enable_agent_execution=False
    )

    cwd = os.getcwd()
    os.chdir(temp_repo)
    with open("allowed.txt", "w") as f:
        f.write("hello")
    os.system("git add allowed.txt")
    os.chdir(cwd)

    original_create_git_commit = dispatcher.create_git_commit

    def mock_create_git_commit(
        worktree_path,
        commit_message,
        author_name="AlphaBrain Autonomous Worker",
        author_email="worker@alphabrain.ai",
    ):
        head = original_create_git_commit(worktree_path, commit_message, author_name, author_email)
        with open(worktree_path / "residue.txt", "w") as f:
            f.write("dirt")
        return head

    dispatcher.create_git_commit = mock_create_git_commit

    envelope = {
        "repo": temp_repo,
        "base_commit": base_commit,
        "allowed_paths": ["allowed.txt"],
        "acceptance_plan": {
            "commands": [{"gate_type": GateType.UNIT_TEST.value, "executable": "echo"}]
        },
    }

    dispatcher.execute_task(build_task("t2", envelope))
    assert any("Dirty uncommitted residue" in ft["error"] for ft in q.failed_tasks)


def test_diff_budget_max_changed_files(temp_repo):
    q = MockQueue()
    wm = MockWorktreeManager()
    base_commit = get_head_sha(temp_repo)
    dispatcher = TriageTaskDispatcher(
        queue=q, worktree_mgr=wm, default_base_commit=base_commit, enable_agent_execution=False
    )

    cwd = os.getcwd()
    os.chdir(temp_repo)
    with open("f1.txt", "w") as f:
        f.write("1")
    with open("f2.txt", "w") as f:
        f.write("2")
    os.system("git add f1.txt f2.txt")
    os.chdir(cwd)

    envelope = {
        "repo": temp_repo,
        "base_commit": base_commit,
        "allowed_paths": ["f1.txt", "f2.txt"],
        "max_changed_files": 1,
        "acceptance_plan": {
            "commands": [{"gate_type": GateType.UNIT_TEST.value, "executable": "echo"}]
        },
    }
    dispatcher.execute_task(build_task("t3", envelope))
    assert any("exceeds max_changed_files" in ft["error"] for ft in q.failed_tasks)


def test_diff_budget_max_diff_lines(temp_repo):
    q = MockQueue()
    wm = MockWorktreeManager()
    base_commit = get_head_sha(temp_repo)
    dispatcher = TriageTaskDispatcher(
        queue=q, worktree_mgr=wm, default_base_commit=base_commit, enable_agent_execution=False
    )

    cwd = os.getcwd()
    os.chdir(temp_repo)
    with open("f3.txt", "w") as f:
        f.write("1\n2\n3\n4\n5\n")
    os.system("git add f3.txt")
    os.chdir(cwd)

    envelope = {
        "repo": temp_repo,
        "base_commit": base_commit,
        "allowed_paths": ["f3.txt"],
        "max_diff_lines": 2,
        "acceptance_plan": {
            "commands": [{"gate_type": GateType.UNIT_TEST.value, "executable": "echo"}]
        },
    }
    dispatcher.execute_task(build_task("t4", envelope))
    assert any("exceeds max_diff_lines" in ft["error"] for ft in q.failed_tasks)


def test_out_of_scope_rejection(temp_repo):
    q = MockQueue()
    wm = MockWorktreeManager()
    base_commit = get_head_sha(temp_repo)
    dispatcher = TriageTaskDispatcher(
        queue=q, worktree_mgr=wm, default_base_commit=base_commit, enable_agent_execution=False
    )

    cwd = os.getcwd()
    os.chdir(temp_repo)
    with open("outofscope.txt", "w") as f:
        f.write("bad")
    os.system("git add outofscope.txt")
    os.chdir(cwd)

    envelope = {
        "repo": temp_repo,
        "base_commit": base_commit,
        "allowed_paths": ["allowed.txt"],
        "acceptance_plan": {
            "commands": [{"gate_type": GateType.UNIT_TEST.value, "executable": "echo"}]
        },
    }
    dispatcher.execute_task(build_task("t5", envelope))
    assert any("outside allowed_paths" in ft["error"] for ft in q.failed_tasks)


def test_successful_execution(temp_repo):
    q = MockQueue()
    wm = MockWorktreeManager()
    base_commit = get_head_sha(temp_repo)
    dispatcher = TriageTaskDispatcher(
        queue=q, worktree_mgr=wm, default_base_commit=base_commit, enable_agent_execution=False
    )

    cwd = os.getcwd()
    os.chdir(temp_repo)
    with open("allowed.txt", "w") as f:
        f.write("good")
    os.system("git add allowed.txt")
    os.chdir(cwd)

    envelope = {
        "repo": temp_repo,
        "base_commit": base_commit,
        "allowed_paths": ["allowed.txt"],
        "acceptance_plan": {
            "commands": [
                {"gate_type": GateType.UNIT_TEST.value, "executable": "echo", "args": ["hello"]}
            ]
        },
    }
    pr = dispatcher.execute_task(build_task("t6", envelope))
    assert pr is not None
    assert pr.task_id == "t6"
    assert "allowed.txt" in pr.files_changed
    assert len(q.failed_tasks) == 0
