"""Regression tests for fail-closed AlphaBrain self-development admission."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from alpha_core.config import settings
from alpha_core.db.connection import Base, get_engine, get_session_factory
from alpha_core.self_development import (
    SelfImprovementRequest,
    admit_self_improvement,
    create_self_improvement_task,
)
from alpha_protocol import RiskClass, TaskStatus
from testscript.run_self_improvement_proof import main


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _clean_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "alpha-repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "README.md").write_text("proof\n")
    _git(repo, "add", "README.md")
    _git(
        repo,
        "-c",
        "user.name=Alpha Test",
        "-c",
        "user.email=alpha@example.test",
        "commit",
        "-m",
        "init",
    )
    return repo


def _request(repo: Path, **overrides: object) -> SelfImprovementRequest:
    defaults: dict[str, object] = {
        "source_repo": repo,
        "allowed_paths": ("docs",),
        "founder_identity": "Ajay Tiwari",
        "requires_approval": True,
        "risk_class": RiskClass.LOW,
    }
    defaults.update(overrides)
    return SelfImprovementRequest(**defaults)  # type: ignore[arg-type]


def test_admission_accepts_clean_founder_approved_repo(tmp_path, monkeypatch):
    repo = _clean_git_repo(tmp_path)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    decision = admit_self_improvement(_request(repo))

    assert decision.admitted is True
    assert decision.base_commit
    assert decision.source_repo == repo.resolve()


def test_admission_rejects_dirty_repo(tmp_path, monkeypatch):
    repo = _clean_git_repo(tmp_path)
    (repo / "README.md").write_text("dirty\n")
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    decision = admit_self_improvement(_request(repo))

    assert decision.admitted is False
    assert "uncommitted changes" in decision.reason


def test_admission_rejects_outside_root_and_missing_founder(tmp_path, monkeypatch):
    repo = _clean_git_repo(tmp_path)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path / "other",))

    outside = admit_self_improvement(_request(repo))
    missing_founder = admit_self_improvement(_request(repo, founder_identity="  "))

    assert outside.admitted is False
    assert "outside allowed roots" in outside.reason
    assert missing_founder.admitted is False
    assert "Founder identity" in missing_founder.reason


def test_runner_defaults_to_zero_side_effect_dry_run(capsys):
    assert main([]) == 0
    assert "Dry run only" in capsys.readouterr().out


def test_runner_rejects_live_without_identity(tmp_path, monkeypatch, capsys):
    repo = _clean_git_repo(tmp_path)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))

    assert main(["--live", "--source-repo", str(repo), "--allowed-path", "docs"]) == 1
    assert "Founder identity" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_create_self_task_freezes_clean_base_and_waits_for_execution_approval(
    tmp_path, monkeypatch
):
    repo = _clean_git_repo(tmp_path)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with get_session_factory()() as session:
            task = await create_self_improvement_task(
                session,
                _request(repo, allowed_paths=("alpha_core", "testscript")),
                project_id="prj_alphabrain_self",
                task_id="tsk_alphabrain_self_001",
                objective="Add one bounded self-development capability",
            )

            assert task.status == TaskStatus.WAITING_APPROVAL.value
            assert task.base_commit != "HEAD"
            assert task.details_json["allowed_paths"] == ["alpha_core", "testscript"]
            assert task.details_json["base_commit"] == task.base_commit
            assert task.details_json["requires_approval"] is True
            assert "SELF-DEVELOPMENT SAFETY CONTRACT" in task.details_json["detailed_instructions"]
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
