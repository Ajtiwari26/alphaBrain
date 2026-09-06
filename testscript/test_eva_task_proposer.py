"""
testscript/test_eva_task_proposer.py
Unit tests verifying Alpha Protocol TaskEnvelope generation and commit verification.
"""

import subprocess
from pathlib import Path

import pytest

from alpha_core.eva.spec_extractor import ExtractedSpecification
from alpha_core.eva.task_proposer import EvaTaskProposer, verify_and_resolve_repo_commit
from alpha_protocol.enums import AgentType, GateType


@pytest.fixture
def git_repo(tmp_path: Path) -> tuple[Path, str]:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@alphabrain.ai"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Alpha Test"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    (repo_dir / "README.md").write_text("initial commit\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo_dir, head_sha


def test_verify_and_resolve_repo_commit_real_supplied(git_repo: tuple[Path, str]) -> None:
    repo_dir, head_sha = git_repo
    resolved = verify_and_resolve_repo_commit(repo_dir, head_sha)
    assert resolved == head_sha


def test_verify_and_resolve_repo_commit_omitted(git_repo: tuple[Path, str]) -> None:
    repo_dir, head_sha = git_repo
    assert verify_and_resolve_repo_commit(repo_dir, None) == head_sha
    assert verify_and_resolve_repo_commit(repo_dir, "") == head_sha
    assert verify_and_resolve_repo_commit(repo_dir, "HEAD") == head_sha


def test_verify_and_resolve_repo_commit_nonexistent(git_repo: tuple[Path, str]) -> None:
    repo_dir, _ = git_repo
    fake_sha = "f" * 40
    with pytest.raises(ValueError, match="does not exist in repository"):
        verify_and_resolve_repo_commit(repo_dir, fake_sha)


def test_verify_and_resolve_repo_commit_malformed(git_repo: tuple[Path, str]) -> None:
    repo_dir, _ = git_repo
    for bad in ["not-a-sha", "123", "a" * 39, "g" * 40, ""]:
        if not bad:
            continue
        with pytest.raises(ValueError, match="must be a 40-character hexadecimal SHA"):
            verify_and_resolve_repo_commit(repo_dir, bad)


def test_verify_and_resolve_repo_commit_invalid_repo(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist"
    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        verify_and_resolve_repo_commit(non_existent, "a" * 40)


def test_build_task_envelope_success_with_real_commit(git_repo: tuple[Path, str]) -> None:
    repo_dir, head_sha = git_repo
    proposer = EvaTaskProposer(default_repo=str(repo_dir), default_branch="main")

    spec = ExtractedSpecification(
        title="Add Stripe Idempotency Key Header",
        summary="Prevent duplicate payment charges by attaching Idempotency-Key.",
        requirements=["Include Idempotency-Key header on all charge calls"],
        acceptance_criteria=["Return existing charge if key already seen"],
        allowed_paths=["stripe_client.py", "tests/test_stripe.py"],
        is_actionable=True,
        confidence_score=0.9,
    )

    envelope = proposer.build_task_envelope(
        spec=spec,
        project_id="prj_stripe_001",
        repo=str(repo_dir),
        base_commit=head_sha,
    )

    assert envelope.task_id.startswith("tsk_eva_")
    assert envelope.project_id == "prj_stripe_001"
    assert envelope.base_commit == head_sha
    assert envelope.repo == str(repo_dir)
    assert envelope.objective == "Add Stripe Idempotency Key Header"
    assert "Idempotency-Key" in (envelope.detailed_instructions or "")
    assert envelope.allowed_paths == ["stripe_client.py", "tests/test_stripe.py"]
    assert GateType.UNIT_TEST in envelope.acceptance_plan.required_gates
    assert GateType.LINT in envelope.acceptance_plan.required_gates
    assert envelope.preferred_agent == AgentType.ANTIGRAVITY
    assert envelope.requires_approval is True


def test_build_task_envelope_success_with_omitted_commit(git_repo: tuple[Path, str]) -> None:
    repo_dir, head_sha = git_repo
    proposer = EvaTaskProposer(default_repo=str(repo_dir), default_branch="main")

    spec = ExtractedSpecification(
        title="Add Stripe Webhook Signature",
        summary="Verify stripe-signature on incoming webhook endpoints.",
        requirements=["Check signature header against secret"],
        acceptance_criteria=["Reject forged signatures with 401"],
        allowed_paths=["webhook.py"],
        is_actionable=True,
        confidence_score=0.95,
    )

    envelope = proposer.build_task_envelope(
        spec=spec,
        project_id="prj_stripe_002",
        repo=str(repo_dir),
        base_commit=None,
    )

    assert envelope.base_commit == head_sha


def test_build_task_envelope_rejects_nonexistent_commit(git_repo: tuple[Path, str]) -> None:
    repo_dir, _ = git_repo
    proposer = EvaTaskProposer(default_repo=str(repo_dir))

    spec = ExtractedSpecification(
        title="Valid spec",
        summary="Some summary",
        is_actionable=True,
    )

    with pytest.raises(ValueError, match="does not exist in repository"):
        proposer.build_task_envelope(
            spec=spec,
            project_id="prj_test",
            repo=str(repo_dir),
            base_commit="0" * 40,
        )


def test_build_task_envelope_rejects_malformed_commit(git_repo: tuple[Path, str]) -> None:
    repo_dir, _ = git_repo
    proposer = EvaTaskProposer(default_repo=str(repo_dir))

    spec = ExtractedSpecification(
        title="Valid spec",
        summary="Some summary",
        is_actionable=True,
    )

    with pytest.raises(ValueError, match="must be a 40-character hexadecimal SHA"):
        proposer.build_task_envelope(
            spec=spec,
            project_id="prj_test",
            repo=str(repo_dir),
            base_commit="invalid_commit_sha",
        )


def test_build_task_envelope_rejects_non_actionable() -> None:
    proposer = EvaTaskProposer()

    spec = ExtractedSpecification(
        title="Casual Chat",
        summary="Greeting only",
        is_actionable=False,
    )

    with pytest.raises(ValueError, match="Cannot propose a task"):
        proposer.build_task_envelope(
            spec=spec,
            project_id="prj_test",
        )
