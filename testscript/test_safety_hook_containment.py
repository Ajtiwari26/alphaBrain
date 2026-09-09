"""Regression proofs for hook decisions and actual macOS shell containment."""

import io
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from alpha_worker.adapters import safety_hook as hook


def request(name, args):
    return {"toolCall": {"name": name, "args": args}}


@pytest.mark.parametrize("name", sorted(hook.FILE_TOOLS))
def test_file_tools_fail_closed(tmp_path, name):
    wt = tmp_path / "wt"
    wt.mkdir()
    for target in [None, str(tmp_path / "wt-other/file"), str(wt / ".agents/hooks.json")]:
        assert hook.decide(request(name, {"TargetFile": target}), wt)["decision"] == "deny"
    assert (
        hook.decide(request(name, {"TargetFile": str(wt / "safe.py")}), wt)["decision"] == "allow"
    )


@pytest.mark.parametrize("payload", [None, [], {}, {"toolCall": {}}, request("unknown", {})])
def test_invalid_requests_denied(tmp_path, payload):
    assert hook.decide(payload, tmp_path)["decision"] == "deny"


def test_malformed_json_denied_without_raw_logging(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ALPHA_WORKTREE_PATH", str(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO("secret-canary-invalid-json"))
    hook.main()
    output = capsys.readouterr()
    assert json.loads(output.out)["decision"] == "deny"
    assert "secret-canary" not in output.out + output.err


@pytest.mark.parametrize("args", [{}, {"Cwd": "."}, {"CommandLine": "true"}])
def test_command_requires_cwd_and_command(tmp_path, args):
    assert hook.decide(request("run_command", args), tmp_path)["decision"] == "deny"


import os

@pytest.mark.skipif(sys.platform != "darwin", reason="Requires macOS kernel sandbox")
@pytest.mark.skipif(
    "alphabrain-sandbox" in os.environ.get("TMPDIR", ""),
    reason="Cannot run nested sandbox-exec inside an existing sandbox",
)
def test_real_os_containment(tmp_path):
    wt = tmp_path / "worktree with ' quotes"
    wt.mkdir()
    config = wt / ".agents"
    config.mkdir()
    protected = config / "hooks.json"
    protected.write_text("original")
    outside = tmp_path / "outside.txt"
    dummy = tmp_path / "dummy-secret.txt"
    dummy.write_text("dummy-secret-canary")

    def run(command):
        result = hook.decide(request("run_command", {"Cwd": str(wt), "CommandLine": command}), wt)
        assert result["decision"] == "allow"
        # Match the outer-shell execution used by a command tool.
        return subprocess.run(
            ["/bin/sh", "-c", result["overwrite"]["CommandLine"]],
            cwd=wt,
            capture_output=True,
            text=True,
            timeout=10,
        )

    safe = wt / "safe.txt"
    assert run(f"printf ok > {shlex.quote(str(safe))}").returncode == 0
    assert safe.read_text() == "ok"
    assert run(f"touch {shlex.quote(str(outside))}").returncode != 0
    for substitution in [
        f"$(touch {shlex.quote(str(outside))})",
        f"`touch {shlex.quote(str(outside))}`",
    ]:
        run(f"echo {substitution}")
        assert not outside.exists()
    assert run(f"printf changed > {shlex.quote(str(protected))}").returncode != 0
    assert run("mv .agents renamed-hooks").returncode != 0
    assert protected.read_text() == "original"
    assert run(f"cat {shlex.quote(str(dummy))}").returncode != 0
    assert "dummy-secret-canary" not in run(f"cat {shlex.quote(str(dummy))}").stdout
    # Child programs inherit kernel restrictions.
    assert run(f"/bin/sh -c {shlex.quote('touch ' + shlex.quote(str(outside)))}").returncode != 0
    link = wt / "outside-link"
    link.symlink_to(tmp_path, target_is_directory=True)
    assert run("touch outside-link/symlink-escape").returncode != 0
    assert not (tmp_path / "symlink-escape").exists()


def test_policy_denies_network_and_has_no_shared_temp_write_grants(tmp_path):
    profile = hook.sandbox_profile(tmp_path)
    assert "(deny network*)" in profile
    assert '(allow file-write* (subpath "/tmp"))' not in profile
    assert '(allow file-write* (subpath "/var"))' not in profile
    assert '(subpath "/etc")' not in profile
    assert '(subpath "/private/etc")' not in profile
    assert Path("/usr/bin/sandbox-exec").is_absolute()
