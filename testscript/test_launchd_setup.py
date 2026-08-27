"""
testscript/test_launchd_setup.py
Tests launchd configuration templates, preflight checks, and plist linting for dedicated Mac worker service.
"""

import platform
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_launchd_plist_template_integrity():
    template_path = (
        PROJECT_ROOT / "ops" / "launchd" / "com.deploymate.alphabrain.worker.plist.template"
    )
    assert template_path.exists(), "Launchd plist template must exist"

    content = template_path.read_text(encoding="utf-8")
    assert "<key>Label</key><string>com.deploymate.alphabrain.worker</string>" in content
    assert "<key>RunAtLoad</key><true/>" in content
    assert "<key>KeepAlive</key><true/>" in content
    assert "<key>ProcessType</key><string>Background</string>" in content
    assert "/ABSOLUTE/PATH/TO/alphaBrain/.venv/bin/python" in content
    assert "alpha_worker" in content
    assert "StandardOutPath" in content
    assert "StandardErrorPath" in content


def test_launchd_plist_generation_and_plutil_lint(tmp_path):
    template_path = (
        PROJECT_ROOT / "ops" / "launchd" / "com.deploymate.alphabrain.worker.plist.template"
    )
    content = template_path.read_text(encoding="utf-8")

    # Perform substitution as install_worker.sh does
    substituted = (
        content.replace(
            "/ABSOLUTE/PATH/TO/alphaBrain/.venv/bin/python",
            str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        )
        .replace("/ABSOLUTE/PATH/TO/alphaBrain", str(PROJECT_ROOT))
        .replace("WORKER_USER", "alphaworker")
    )

    generated_plist = tmp_path / "com.deploymate.alphabrain.worker.plist"
    generated_plist.write_text(substituted, encoding="utf-8")
    generated_plist.chmod(0o600)

    assert (generated_plist.stat().st_mode & 0o777) == 0o600

    # On macOS, validate with plutil
    if platform.system() == "Darwin":
        res = subprocess.run(
            ["plutil", "-lint", str(generated_plist)], capture_output=True, text=True
        )
        assert res.returncode == 0, f"plutil -lint failed: {res.stderr}"
        assert "OK" in res.stdout or res.returncode == 0


def test_install_worker_script_preflight_guards():
    script_path = PROJECT_ROOT / "ops" / "launchd" / "install_worker.sh"
    assert script_path.exists(), "install_worker.sh must exist"
    content = script_path.read_text(encoding="utf-8")

    # Script must enforce production prerequisites
    assert 'ENV:-development}" = production' in content or "ENV=production" in content
    assert "WORKER_USE_KEYCHAIN:-false}" in content or "WORKER_USE_KEYCHAIN=true" in content
    assert "WORKER_ALLOW_LOCAL_DB:-true}" in content or "WORKER_ALLOW_LOCAL_DB=false" in content
    assert "chmod 600" in content
    assert "plutil -lint" in content
    assert "launchctl bootstrap" in content
