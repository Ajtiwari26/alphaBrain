"""
Test suite for codex-switch multi-account session manager.
"""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def codex_switch_bin() -> str:
    path = Path.home() / ".local" / "bin" / "codex-switch"
    if not path.exists():
        pytest.skip(f"codex-switch binary not found at {path}")
    return str(path)


def test_codex_switch_list(codex_switch_bin: str) -> None:
    res = subprocess.run([codex_switch_bin, "list"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Stored ChatGPT / Codex Accounts:" in res.stdout
    assert "rt108044@gmail.com" in res.stdout
    assert "tiwariajay033@gmail.com" in res.stdout


def test_codex_switch_whoami(codex_switch_bin: str) -> None:
    res = subprocess.run([codex_switch_bin, "whoami"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Active Account Details:" in res.stdout
    assert "Email:" in res.stdout


def test_codex_switch_toggle(codex_switch_bin: str) -> None:
    # Switch to tiwariajay033
    res1 = subprocess.run([codex_switch_bin, "use", "tiwariajay033"], capture_output=True, text=True)
    assert res1.returncode == 0
    assert "tiwariajay033@gmail.com" in res1.stdout

    # Verify whoami
    whoami1 = subprocess.run([codex_switch_bin, "whoami"], capture_output=True, text=True)
    assert "tiwariajay033@gmail.com" in whoami1.stdout

    # Switch back to rt108044
    res2 = subprocess.run([codex_switch_bin, "use", "rt108044"], capture_output=True, text=True)
    assert res2.returncode == 0
    assert "rt108044@gmail.com" in res2.stdout

    # Verify whoami
    whoami2 = subprocess.run([codex_switch_bin, "whoami"], capture_output=True, text=True)
    assert "rt108044@gmail.com" in whoami2.stdout
