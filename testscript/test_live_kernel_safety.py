import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

import pytest

from testscript.run_live_kernel_proof import (
    create_safe_project_dir,
    is_safe_subpath,
    main,
    perform_cleanup,
    setup_git_repository,
    validate_prefix,
)


def test_is_safe_subpath(tmp_path):
    root = tmp_path / "root"
    root.mkdir()

    # 1. Direct child
    child = root / "child"
    assert is_safe_subpath(child, root) is True

    # 2. Sibling prefix escape
    sibling = tmp_path / "root-sibling"
    sibling.mkdir()
    assert is_safe_subpath(sibling, root) is False

    # 3. Path traversal
    escape = root / ".." / "root-sibling"
    assert is_safe_subpath(escape, root) is False

    # 4. Symlink escape (if platform permits)
    symlink_child = root / "sym"
    # creating symlink pointing outside
    try:
        os.symlink(str(sibling), str(symlink_child))
        assert is_safe_subpath(symlink_child, root) is False
    except OSError:
        pass


def test_create_safe_project_dir_containment(tmp_path, monkeypatch):
    monkeypatch.setattr("testscript.run_live_kernel_proof.CLIENT_PROJECTS_ROOT", tmp_path)

    # Test valid creation
    proj_dir = create_safe_project_dir("test-prefix")
    assert proj_dir.exists()
    assert is_safe_subpath(proj_dir, tmp_path)

    marker_file = proj_dir / ".alpha_live_run"
    assert marker_file.exists()

    with marker_file.open("r") as f:
        marker_data = json.load(f)
    assert marker_data["schema"] == "1.0"
    assert "run_id" in marker_data
    assert marker_data["resolved_path"] == str(proj_dir.resolve(strict=False))


def test_perform_cleanup_ownership_protection(tmp_path, monkeypatch):
    monkeypatch.setattr("testscript.run_live_kernel_proof.CLIENT_PROJECTS_ROOT", tmp_path)

    proj_dir = create_safe_project_dir("test-cleanup")

    # Create another dir without marker
    unsafe_dir = tmp_path / "important_data"
    unsafe_dir.mkdir()

    # Cleaning dir without marker should fail
    with pytest.raises(
        ValueError, match="Security error: Refusing to clean directory without ownership marker"
    ):
        perform_cleanup(unsafe_dir)
    assert unsafe_dir.exists()

    # Cleaning dir outside root should fail
    outside_dir = tmp_path.parent / "outside"
    outside_dir.mkdir(exist_ok=True)
    try:
        with pytest.raises(ValueError, match="Security error: Refusing to clean path outside root"):
            perform_cleanup(outside_dir)
        assert outside_dir.exists()
    finally:
        shutil.rmtree(outside_dir)

    # Cleaning valid dir should work
    perform_cleanup(proj_dir)
    assert not proj_dir.exists()


def test_perform_cleanup_marker_validation(tmp_path, monkeypatch):
    monkeypatch.setattr("testscript.run_live_kernel_proof.CLIENT_PROJECTS_ROOT", tmp_path)

    proj_dir = create_safe_project_dir("test-marker-validation")
    marker_path = proj_dir / ".alpha_live_run"

    # 1. Malformed JSON
    marker_path.write_text("{bad json")
    with pytest.raises(
        ValueError,
        match="Security error: Refusing to clean directory with malformed ownership marker",
    ):
        perform_cleanup(proj_dir)

    # 2. Mismatched schema
    marker_path.write_text(
        json.dumps(
            {"schema": "2.0", "run_id": "123", "resolved_path": str(proj_dir.resolve(strict=False))}
        )
    )
    with pytest.raises(
        ValueError,
        match="Security error: Refusing to clean directory with mismatched marker schema",
    ):
        perform_cleanup(proj_dir)

    # 3. Mismatched path
    marker_path.write_text(
        json.dumps({"schema": "1.0", "run_id": "123", "resolved_path": "/fake/path"})
    )
    with pytest.raises(
        ValueError,
        match="Security error: Refusing to clean directory with mismatched path in marker",
    ):
        perform_cleanup(proj_dir)


def test_default_preservation(tmp_path, monkeypatch):
    # Ensures create_safe_project_dir doesn't delete existing things
    monkeypatch.setattr("testscript.run_live_kernel_proof.CLIENT_PROJECTS_ROOT", tmp_path)
    existing_dir = tmp_path / "existing-dir"
    existing_dir.mkdir()

    proj_dir = create_safe_project_dir("test-preserve")

    assert existing_dir.exists()
    assert proj_dir.exists()


def test_validate_prefix():
    # Valid
    validate_prefix("valid-slug_123")
    validate_prefix("A")

    # Empty
    with pytest.raises(ValueError, match="Project ID prefix cannot be empty"):
        validate_prefix("")

    # Too long
    with pytest.raises(ValueError, match="exceeds maximum length"):
        validate_prefix("a" * 65)

    # Malicious or invalid chars
    invalid_cases = [
        "../escape",
        "escape/slash",
        "escape\\backslash",
        "escape space",
        "escape\nline",
        ".hidden",
        "escape\x00null",
    ]
    for invalid in invalid_cases:
        with pytest.raises(ValueError, match="contains invalid characters"):
            validate_prefix(invalid)


@pytest.mark.asyncio
async def test_main_live_fails_without_approve_as(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        await main(["--live"])

    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert (
        "Error: --live requires --approve-as <identity> for explicit approval provenance"
        in captured.out
    )


@pytest.mark.asyncio
async def test_main_live_fails_with_empty_approve_as(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        await main(["--live", "--approve-as", "   "])

    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert (
        "Error: --live requires --approve-as <identity> for explicit approval provenance"
        in captured.out
    )


@pytest.mark.asyncio
async def test_main_live_with_approve_as_called_correctly(monkeypatch, capsys):
    from unittest.mock import AsyncMock, MagicMock

    from testscript import run_live_kernel_proof

    mock_engine = AsyncMock()
    mock_engine_cls = MagicMock(return_value=mock_engine)
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock()
    mock_engine.begin = MagicMock(return_value=mock_conn)
    monkeypatch.setattr(run_live_kernel_proof, "create_async_engine", mock_engine_cls)
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_session_factory = MagicMock(return_value=mock_session)
    monkeypatch.setattr(run_live_kernel_proof, "async_sessionmaker", mock_session_factory)
    from testscript import run_live_kernel_proof

    # Mock everything to just test the approval delegation
    monkeypatch.setattr(
        run_live_kernel_proof, "create_safe_project_dir", MagicMock(return_value=Path("/fake/path"))
    )
    monkeypatch.setattr(run_live_kernel_proof, "setup_git_repository", MagicMock())

    mock_daemon = MagicMock()
    mock_daemon.execute_task_cycle = AsyncMock()
    mock_adapter = MagicMock()
    mock_adapter.check_readiness.return_value = (True, "")
    mock_daemon.select_adapter.return_value = mock_adapter
    monkeypatch.setattr(
        run_live_kernel_proof, "AlphaWorkerDaemon", MagicMock(return_value=mock_daemon)
    )

    mock_task_engine = MagicMock()
    mock_task_engine.create_project = AsyncMock(return_value=MagicMock(id="p1"))
    mock_task_engine.submit_task = AsyncMock(
        return_value=MagicMock(id="t1", status="WAITING_APPROVAL")
    )
    mock_task_engine.decide_task_approval = AsyncMock()

    monkeypatch.setattr(run_live_kernel_proof, "TaskEngine", mock_task_engine)

    await main(["--live", "--approve-as", "ajaytiwari@example.com"])

    mock_task_engine.decide_task_approval.assert_called_once_with(
        unittest.mock.ANY, "t1", approved=True, decided_by="ajaytiwari@example.com"
    )

    # Assert envelope commands
    submit_call = mock_task_engine.submit_task.call_args
    assert submit_call is not None
    submitted_envelope = submit_call[0][1]
    cmds = submitted_envelope.acceptance_plan.commands
    assert len(cmds) == 1
    assert cmds[0].gate_type.value == "lint"
    assert cmds[0].executable == "node"
    assert cmds[0].args == ["-e", "require('fs').readFileSync('docs/getting_started.md')"]

    mock_engine_cls.assert_called_once_with(
        "sqlite+aiosqlite:////fake/path/live_kernel.db", echo=False
    )
    mock_session_factory.assert_called_once_with(mock_engine, expire_on_commit=False)
    captured = capsys.readouterr()
    assert "Provenance: Task t1 explicitly approved by ajaytiwari@example.com" in captured.out


def test_setup_git_repository_success(tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()

    # Put something inside that would normally cause dirtiness
    (project_path / ".alpha_live_run").write_text("{}")
    (project_path / "live_kernel.db").write_text("sqlite")
    (project_path / "live_kernel.db-journal").write_text("j")
    (project_path / "live_kernel.db-wal").write_text("w")
    (project_path / "live_kernel.db-shm").write_text("s")

    setup_git_repository(project_path)

    # verify
    assert (project_path / ".gitignore").exists()
    assert (project_path / ".git").exists()

    # check that HEAD exists and tree is clean
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""

    res = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project_path, capture_output=True, text=True, check=True
    )
    assert res.stdout.strip() != ""


def test_setup_git_repository_failure_clean_status(tmp_path):
    project_path = tmp_path / "project_fail"
    project_path.mkdir()

    # We write a random un-ignored file so status is NOT clean
    (project_path / "random.txt").write_text("hello")

    with pytest.raises(RuntimeError, match="Git status is not clean after init:"):
        setup_git_repository(project_path)


def test_setup_git_repository_failure_commit(tmp_path, monkeypatch):
    project_path = tmp_path / "project_fail_commit"
    project_path.mkdir()

    original_run = subprocess.run

    def mock_run(args, **kwargs):
        if args[:2] == ["git", "commit"]:
            raise subprocess.CalledProcessError(1, args, stderr="Commit failed")
        return original_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)

    with pytest.raises(
        RuntimeError,
        match=r"Git setup failed: command 'git commit -m Initial commit from live proof harness' returned 1. stderr: Commit failed",
    ):
        setup_git_repository(project_path)
