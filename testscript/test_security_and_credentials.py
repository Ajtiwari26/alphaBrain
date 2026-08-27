"""
testscript/test_security_and_credentials.py
Tests worktree path isolation, repository allowlist enforcement, Keychain credential boundaries, and redaction.
"""

import subprocess

import pytest

from alpha_core.config import settings
from alpha_worker.credentials import KeychainError, MacOSKeychain
from alpha_worker.daemon import AlphaWorkerDaemon
from alpha_worker.worktree import WorktreeManager


def test_worktree_manager_rejects_path_traversal_and_unallowlisted_roots(monkeypatch, tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))

    # Valid path inside allowed root (must be a valid git repository)
    valid_repo = allowed_root / "valid_project"
    valid_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(valid_repo), capture_output=True, check=True)
    assert WorktreeManager.validate_repo_path(str(valid_repo)) == valid_repo.resolve()

    # Traversal attempt outside allowed root
    with pytest.raises(ValueError, match="outside allowed roots"):
        WorktreeManager.validate_repo_path(str(tmp_path / "other" / "project"))

    with pytest.raises(ValueError, match="outside allowed roots"):
        WorktreeManager.validate_repo_path("/etc/passwd")

    with pytest.raises(ValueError, match="outside allowed roots"):
        WorktreeManager.validate_repo_path(str(allowed_root / ".." / "outside"))


def test_validation_of_task_identifiers():
    # Valid task IDs
    WorktreeManager.validate_task_id("tsk_123_valid")
    WorktreeManager.validate_task_id("task-abc.123")

    # Invalid task IDs
    with pytest.raises(ValueError, match="Invalid task ID"):
        WorktreeManager.validate_task_id("tsk/unsafe/..")

    with pytest.raises(ValueError, match="Invalid task ID"):
        WorktreeManager.validate_task_id("-leading_dash_invalid")

    with pytest.raises(ValueError, match="Invalid task ID"):
        WorktreeManager.validate_task_id("task with spaces")


def test_keychain_service_fail_closed(monkeypatch):
    monkeypatch.setattr(
        "alpha_worker.credentials.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [],
            44,
            stdout="",
            stderr="security: SecKeychainSearchCopyNext: The specified item could not be found in the keychain.",
        ),
    )
    keychain = MacOSKeychain("com.deploymate.alphabrain.test")
    with pytest.raises(KeychainError, match="Missing Keychain credential"):
        keychain.get("worker-token")


def test_production_daemon_fails_if_keychain_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "WORKER_CONTROL_PLANE_URL", "https://control.deploymate.ai")
    monkeypatch.setattr(settings, "WORKER_USE_KEYCHAIN", False)
    monkeypatch.setattr(settings, "WORKER_STATE_DIR", tmp_path / "state")

    with pytest.raises(RuntimeError, match="Production worker requires WORKER_USE_KEYCHAIN=true"):
        AlphaWorkerDaemon()


def test_escalation_redacts_auth_and_api_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "WORKER_STATE_DIR", tmp_path / "worker")
    daemon = AlphaWorkerDaemon(worker_id="worker-redaction-test")

    raw_detail = (
        "Failed with Bearer ALPHA_API_TOKEN=supersecret123 and GEMINI_API_KEY=AIzaSySecretApiKey456"
    )
    daemon._record_escalation("tsk_redact_01", "auth_failed", raw_detail)

    escalations_path = tmp_path / "worker" / "escalations.jsonl"
    assert escalations_path.exists()
    content = escalations_path.read_text(encoding="utf-8")

    assert "supersecret123" not in content
    assert "AIzaSySecretApiKey456" not in content
    assert "[REDACTED]" in content
    # File permissions must be 0600
    assert (escalations_path.stat().st_mode & 0o777) == 0o600
