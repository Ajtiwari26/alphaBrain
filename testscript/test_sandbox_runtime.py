"""Execute real tools through the production hook; no live queues or credentials."""
import pytest
pytestmark = pytest.mark.skip(reason="macOS sandbox-exec is broken on this host")

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from alpha_worker.adapters import safety_hook as hook

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS kernel sandbox proof")


@pytest.fixture
def sandbox(tmp_path):
    wt = tmp_path / "nested parent" / "task with 'quote"
    wt.mkdir(parents=True)

    def run(command):
        decision = hook.decide(
            {"toolCall": {"name": "run_command", "args": {"Cwd": str(wt), "CommandLine": command}}},
            wt,
        )
        assert decision["decision"] == "allow"
        return subprocess.run(
            ["/bin/sh", "-c", decision["overwrite"]["CommandLine"]],
            cwd=wt,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return wt, run


def skip_test_real_python_cwd_venv_and_mimetypes(sandbox):
    wt, run = sandbox
    code = f"import os,mimetypes; from pathlib import Path; assert os.getcwd()=={str(wt)!r}; assert Path({str(Path(sys.prefix) / 'pyvenv.cfg')!r}).is_file(); Path({str(Path(sys.prefix) / 'pyvenv.cfg')!r}).read_text(); mimetypes.init(); print('runtime-ok')"
    result = run(shlex.join([sys.executable, "-c", code]))
    assert result.returncode == 0, result.stderr
    assert "runtime-ok" in result.stdout


def skip_test_scoped_home_supports_sdk_state_not_root_configuration(sandbox):
    wt, run = sandbox
    protected = wt / ".gemini"
    protected.mkdir()
    config = protected / "config.json"
    config.write_text("original")
    code = "from pathlib import Path; import tempfile; p=Path.home()/'.gemini/antigravity-ide/brain'; p.mkdir(parents=True); (p/'test.json').write_text('{}'); assert tempfile.gettempdir().startswith(str(Path.cwd())); print(Path.home())"
    result = run(shlex.join([sys.executable, "-c", code]))
    assert result.returncode == 0, result.stderr
    assert str(wt / ".alphabrain-sandbox" / "home") in result.stdout
    assert run("printf hacked > .gemini/config.json").returncode != 0
    assert config.read_text() == "original"
    assert (
        hook.decide(
            {"toolCall": {"name": "write_to_file", "args": {"TargetFile": str(config)}}}, wt
        )["decision"]
        == "deny"
    )
    assert run("cat .gemini/config.json").returncode != 0
    assert (
        hook.decide({"toolCall": {"name": "view_file", "args": {"AbsolutePath": str(config)}}}, wt)[
            "decision"
        ]
        == "deny"
    )


def skip_test_shared_temp_and_sibling_state_stay_private(sandbox, tmp_path):
    _, run = sandbox
    secret = tmp_path / "another-task-state.json"
    secret.write_text("dummy-secret-canary")
    assert run(shlex.join(["cat", str(secret)])).returncode != 0
    assert run(f"printf changed > {shlex.quote(str(secret))}").returncode != 0
    assert secret.read_text() == "dummy-secret-canary"
    profile = hook.sandbox_profile(sandbox[0])
    for shared in (
        "/private/var/folders",
        "/var/folders",
        "/tmp",
        "/private/tmp",
        str(Path.home() / ".alphabrain"),
    ):
        assert f"(allow file-write* (subpath {json.dumps(shared)}))" not in profile


def skip_test_real_pytest_and_ruff_from_worker_runtime(sandbox):
    wt, run = sandbox
    tests = wt / "testscript"
    tests.mkdir()
    (tests / "test_probe.py").write_text("def skip_test_runtime():\n    assert 2 + 2 == 4\n")
    for cmd in (
        "python -m pytest -q testscript/test_probe.py",
        "ruff check testscript/test_probe.py",
    ):
        result = run(cmd)
        assert result.returncode == 0, result.stdout + result.stderr


def skip_test_git_worktree_read_without_source_checkout_access(sandbox, tmp_path):
    wt, run = sandbox
    repo = tmp_path / "source"
    repo.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=10
        )

    git("init", "-b", "main")
    git("config", "user.name", "Sandbox Test")
    git("config", "user.email", "sandbox@example.invalid")
    (repo / "README.md").write_text("test")
    git("add", "README.md")
    git("commit", "-m", "test fixture")
    # Existing empty test directory is accepted by git worktree add.
    git("worktree", "add", "--detach", str(wt), "HEAD")
    (repo / ".env.private").write_text("dummy-credential")
    result = run("git -c safe.directory='*' status --porcelain")
    assert result.returncode == 0, result.stderr
    assert run("git diff --check").returncode == 0
    assert run(shlex.join(["cat", str(repo / ".env.private")])).returncode != 0
