"""Regression tests for fail-closed AlphaBrain self-development admission."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from alpha_core.config import settings
from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import ApprovalRecord, ProjectRecord, TaskRecord
from alpha_core.self_development import (
    SelfImprovementRequest,
    admit_self_improvement,
    create_self_improvement_task,
)
from alpha_protocol import AcceptancePlan, GateCommand, GateType, RiskClass, TaskStatus
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

    async with get_session_factory()() as session:
        plan = AcceptancePlan(
            require_independent_review=True,
            required_gates=[
                GateType.INDEPENDENT_REVIEW,
                GateType.CODE_REVIEW_GRAPH,
                GateType.LINT,
                GateType.UNIT_TEST,
            ],
            commands=[
                GateCommand(
                    gate_type=GateType.LINT, executable="ruff", args=["check", "alpha_core"]
                ),
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["testscript/test_self_development_admission.py"],
                ),
            ],
        )
        task = await create_self_improvement_task(
            session,
            _request(repo, allowed_paths=("alpha_core", "testscript")),
            project_id="prj_alphabrain_self",
            task_id="tsk_alphabrain_self_001",
            objective="Add one bounded self-development capability",
            acceptance_plan=plan,
        )

        assert task.status == TaskStatus.WAITING_APPROVAL.value
        assert task.base_commit != "HEAD"
        assert task.details_json["allowed_paths"] == ["alpha_core", "testscript"]
        assert task.details_json["base_commit"] == task.base_commit
        assert task.details_json["requires_approval"] is True
        assert "SELF-DEVELOPMENT SAFETY CONTRACT" in task.details_json["detailed_instructions"]
        assert task.details_json["acceptance_plan"] == plan.model_dump(mode="json")
        assert task.packet_sha256 is not None

        from sqlalchemy import select

        appr = await session.scalar(select(ApprovalRecord).where(ApprovalRecord.task_id == task.id))
        assert appr is not None
        assert appr.scope_sha256 == task.packet_sha256


@pytest.mark.parametrize(
    "invalid_plan, expected_error",
    [
        (
            AcceptancePlan(require_independent_review=True, required_gates=[], commands=[]),
            "nonempty required_gates",
        ),
        (
            AcceptancePlan(
                require_independent_review=False,
                required_gates=[GateType.INDEPENDENT_REVIEW, GateType.CODE_REVIEW_GRAPH],
                commands=[],
            ),
            "require_independent_review=True",
        ),
        (
            AcceptancePlan(
                require_independent_review=True,
                required_gates=[GateType.CODE_REVIEW_GRAPH],
                commands=[],
            ),
            "must include INDEPENDENT_REVIEW",
        ),
        (
            AcceptancePlan(
                require_independent_review=True,
                required_gates=[GateType.INDEPENDENT_REVIEW],
                commands=[],
            ),
            "must include INDEPENDENT_REVIEW",
        ),
        (
            AcceptancePlan(
                require_independent_review=True,
                required_gates=[
                    GateType.INDEPENDENT_REVIEW,
                    GateType.CODE_REVIEW_GRAPH,
                    GateType.LINT,
                ],
                commands=[],
            ),
            "no matching GateCommand",
        ),
        (
            AcceptancePlan(
                require_independent_review=True,
                required_gates=[
                    GateType.INDEPENDENT_REVIEW,
                    GateType.CODE_REVIEW_GRAPH,
                    GateType.SECURITY_SCAN,
                ],
                commands=[],
            ),
            "no matching GateCommand",
        ),
        (
            AcceptancePlan(
                require_independent_review=True,
                required_gates=[GateType.INDEPENDENT_REVIEW, GateType.CODE_REVIEW_GRAPH],
                commands=[
                    GateCommand(
                        gate_type=GateType.LINT,
                        executable="ruff",
                        args=["check", "."],
                    )
                ],
            ),
            "must be declared in required_gates",
        ),
        (
            AcceptancePlan(
                require_independent_review=True,
                required_gates=[GateType.INDEPENDENT_REVIEW, GateType.CODE_REVIEW_GRAPH],
                commands=[
                    GateCommand(
                        gate_type=GateType.INDEPENDENT_REVIEW,
                        executable="ruff",
                        args=["check", "."],
                    )
                ],
            ),
            "cannot be a shell command gate",
        ),
        (
            AcceptancePlan(
                require_independent_review=True,
                required_gates=[GateType.INDEPENDENT_REVIEW, GateType.CODE_REVIEW_GRAPH],
                commands=[
                    GateCommand(
                        gate_type=GateType.CODE_REVIEW_GRAPH,
                        executable="ruff",
                        args=["check", "."],
                    )
                ],
            ),
            "cannot be a shell command gate",
        ),
        (
            AcceptancePlan(
                require_independent_review=True,
                required_gates=[
                    GateType.INDEPENDENT_REVIEW,
                    GateType.CODE_REVIEW_GRAPH,
                    GateType.LINT,
                ],
                commands=[
                    GateCommand(
                        gate_type=GateType.LINT,
                        executable="unauthorized_tool",
                        args=["run"],
                    )
                ],
            ),
            "not in ALLOWED_GATE_EXECUTABLES",
        ),
    ],
)
@pytest.mark.asyncio
async def test_invalid_self_acceptance_plan_raises_and_creates_zero_rows(
    tmp_path, monkeypatch, invalid_plan, expected_error
):
    from sqlalchemy import select

    repo = _clean_git_repo(tmp_path)
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    project_id = "prj_invalid_plan_test"
    task_id = "tsk_invalid_plan_test"

    async with get_session_factory()() as session:
        with pytest.raises(ValueError, match=expected_error):
            await create_self_improvement_task(
                session,
                _request(repo, allowed_paths=("alpha_core",)),
                project_id=project_id,
                task_id=task_id,
                objective="Test invalid plan validation",
                acceptance_plan=invalid_plan,
            )

        # Assert zero rows created in ProjectRecord, TaskRecord, ApprovalRecord for this target
        proj = await session.scalar(select(ProjectRecord).where(ProjectRecord.id == project_id))
        assert proj is None

        task = await session.scalar(select(TaskRecord).where(TaskRecord.id == task_id))
        assert task is None

        appr = await session.scalar(select(ApprovalRecord).where(ApprovalRecord.task_id == task_id))
        assert appr is None
