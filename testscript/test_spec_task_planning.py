"""Durable spec approval and bounded non-executable task-planning tests."""

from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import ApprovalRecord, AuditEventRecord, TaskRecord
from alpha_core.security import PrincipalRole, create_scoped_principal_token
from alpha_core.state.spec_engine import (
    SpecEngine,
    TaskGraphPlanningConstraints,
    compute_spec_digest,
)
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AcceptancePlan,
    ApprovalStatus,
    GateCommand,
    GateType,
    OpenQuestion,
    Requirement,
    SpecVersion,
    TaskStatus,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
        await session.rollback()


def make_spec(project_id: str, *, version: int = 1, unresolved: bool = False) -> SpecVersion:
    return SpecVersion(
        version=version,
        project_id=project_id,
        title="Approved delivery scope",
        summary="Build and verify two bounded features",
        requirements=[
            Requirement(
                req_id="req_auth",
                title="Authentication",
                description="Add authenticated project access",
                acceptance_criteria=["Unauthenticated access returns 401"],
                priority="must_have",
            ),
            Requirement(
                req_id="req_status",
                title="Status view",
                description="Show verified project progress",
                acceptance_criteria=["Completed and blocked work are distinct"],
                priority="must_have",
            ),
        ],
        open_questions=(
            [
                OpenQuestion(
                    question_id="q_host",
                    question="Which production host?",
                    context="Deployment target is not approved",
                )
            ]
            if unresolved
            else []
        ),
    )


def make_constraints() -> TaskGraphPlanningConstraints:
    return TaskGraphPlanningConstraints(
        base_commit="a" * 40,
        allowed_paths=["src", "testscript"],
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST],
            commands=[
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["-q", "testscript"],
                )
            ],
        ),
    )


@pytest.mark.asyncio
async def test_spec_submission_is_digest_bound_and_idempotent(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_spec_submit"
    await TaskEngine.create_project(db_session, project_id, "Spec", str(repo))
    spec = make_spec(project_id)

    first, first_digest = await SpecEngine.submit_spec(db_session, spec, actor="founder")
    second, second_digest = await SpecEngine.submit_spec(db_session, spec, actor="founder")

    assert first.id == second.id
    assert first_digest == second_digest == compute_spec_digest(spec)
    assert first.status == ApprovalStatus.PENDING.value
    approvals = (
        (await db_session.execute(select(ApprovalRecord).where(ApprovalRecord.spec_id == first.id)))
        .scalars()
        .all()
    )
    events = (
        (
            await db_session.execute(
                select(AuditEventRecord).where(
                    AuditEventRecord.event_type == "spec_submitted",
                    AuditEventRecord.project_id == project_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(approvals) == 1
    assert approvals[0].scope_sha256 == first_digest
    assert len(events) == 1


@pytest.mark.asyncio
async def test_spec_submission_rejects_claimed_approval_and_duplicate_ids(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_spec_invalid"
    await TaskEngine.create_project(db_session, project_id, "Spec", str(repo))
    spec = make_spec(project_id)

    with pytest.raises(ValueError, match="cannot contain approval claims"):
        await SpecEngine.submit_spec(
            db_session,
            spec.model_copy(update={"founder_approved": True}),
            actor="founder",
        )

    duplicate = spec.model_copy(
        update={"requirements": [spec.requirements[0], spec.requirements[0]]}
    )
    with pytest.raises(ValueError, match="duplicate requirement IDs"):
        await SpecEngine.submit_spec(db_session, duplicate, actor="founder")

    oversized = spec.model_copy(update={"summary": "x" * 263_000})
    with pytest.raises(ValueError, match="exceeds 256 KiB"):
        await SpecEngine.submit_spec(db_session, oversized, actor="founder")


@pytest.mark.asyncio
async def test_approval_rejects_wrong_digest_without_state_change(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_spec_digest"
    await TaskEngine.create_project(db_session, project_id, "Spec", str(repo))
    record, _ = await SpecEngine.submit_spec(db_session, make_spec(project_id), actor="founder")

    with pytest.raises(ValueError, match="digest mismatch"):
        await SpecEngine.decide_founder_approval(
            db_session,
            record.id,
            approved=True,
            actor="founder",
            scope_sha256="0" * 64,
        )

    await db_session.refresh(record)
    assert record.status == ApprovalStatus.PENDING.value
    assert record.founder_approved is False


@pytest.mark.asyncio
async def test_spec_tampering_fails_approval_and_post_approval_planning(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_spec_tamper"
    await TaskEngine.create_project(db_session, project_id, "Spec", str(repo))
    record, digest = await SpecEngine.submit_spec(
        db_session, make_spec(project_id), actor="founder"
    )
    original_json = dict(record.spec_json)
    tampered_json = dict(original_json)
    tampered_json["summary"] = "Tampered after digest creation"
    record.spec_json = tampered_json
    await db_session.flush()

    with pytest.raises(ValueError, match="digest mismatch"):
        await SpecEngine.decide_founder_approval(
            db_session,
            record.id,
            approved=True,
            actor="founder",
            scope_sha256=digest,
        )

    record.spec_json = original_json
    await db_session.flush()
    await SpecEngine.decide_founder_approval(
        db_session,
        record.id,
        approved=True,
        actor="founder",
        scope_sha256=digest,
    )
    record.spec_json = tampered_json
    await db_session.flush()
    with pytest.raises(ValueError, match="no longer matches frozen content"):
        await SpecEngine.draft_task_graph(db_session, record.id, make_constraints())


@pytest.mark.asyncio
async def test_approved_spec_drafts_stable_graph_without_persisting_tasks(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_spec_graph"
    await TaskEngine.create_project(db_session, project_id, "Spec", str(repo))
    record, digest = await SpecEngine.submit_spec(
        db_session, make_spec(project_id), actor="founder"
    )
    await SpecEngine.decide_founder_approval(
        db_session,
        record.id,
        approved=True,
        actor="founder",
        scope_sha256=digest,
    )

    first = await SpecEngine.draft_task_graph(db_session, record.id, make_constraints())
    second = await SpecEngine.draft_task_graph(db_session, record.id, make_constraints())

    assert first == second
    assert first.spec_sha256 == digest
    assert len(first.tasks) == 1
    assert len(first.task_packet_sha256) == 1
    assert all(task.requires_approval for task in first.tasks)
    assert all(task.require_packet_binding for task in first.tasks)
    assert first.tasks[0].objective == "Implement and verify exact approved specification"
    assert "req_auth" in (first.tasks[0].detailed_instructions or "")
    assert "req_status" in (first.tasks[0].detailed_instructions or "")
    assert first.tasks[0].dependencies == []
    assert first.tasks[0].acceptance_plan.require_independent_review is True
    task_count = (
        await db_session.execute(
            select(func.count(TaskRecord.id)).where(TaskRecord.project_id == project_id)
        )
    ).scalar_one()
    assert task_count == 0


@pytest.mark.asyncio
async def test_draft_is_compatible_with_atomic_graph_admission(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_spec_admit"
    await TaskEngine.create_project(db_session, project_id, "Spec", str(repo))
    record, digest = await SpecEngine.submit_spec(
        db_session, make_spec(project_id), actor="founder"
    )
    await SpecEngine.decide_founder_approval(
        db_session,
        record.id,
        approved=True,
        actor="founder",
        scope_sha256=digest,
    )
    draft = await SpecEngine.draft_task_graph(db_session, record.id, make_constraints())

    tasks = await TaskEngine.submit_task_graph(
        db_session,
        draft.tasks,
        project_id=project_id,
        actor="founder",
    )

    assert len(tasks) == 1
    assert all(task.status == TaskStatus.WAITING_APPROVAL.value for task in tasks)
    assert {task.id: task.packet_sha256 for task in tasks} == draft.task_packet_sha256


@pytest.mark.asyncio
async def test_planning_rejects_pending_spec_and_unresolved_questions(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_spec_blocked"
    await TaskEngine.create_project(db_session, project_id, "Spec", str(repo))
    pending, pending_digest = await SpecEngine.submit_spec(
        db_session, make_spec(project_id), actor="founder"
    )

    with pytest.raises(ValueError, match="requires founder approval"):
        await SpecEngine.draft_task_graph(db_session, pending.id, make_constraints())

    await SpecEngine.decide_founder_approval(
        db_session,
        pending.id,
        approved=False,
        actor="founder",
        scope_sha256=pending_digest,
    )
    second, second_digest = await SpecEngine.submit_spec(
        db_session,
        make_spec(project_id, version=2, unresolved=True),
        actor="founder",
    )
    await SpecEngine.decide_founder_approval(
        db_session,
        second.id,
        approved=True,
        actor="founder",
        scope_sha256=second_digest,
    )
    with pytest.raises(ValueError, match="unresolved open questions: q_host"):
        await SpecEngine.draft_task_graph(db_session, second.id, make_constraints())


def test_planning_constraints_fail_closed_on_broad_or_unverifiable_scope():
    plan = make_constraints().acceptance_plan
    with pytest.raises(ValidationError, match="bounded paths"):
        TaskGraphPlanningConstraints(
            base_commit="a" * 40,
            allowed_paths=[".", "testscript"],
            acceptance_plan=plan,
        )
    with pytest.raises(ValidationError, match="testscript directory"):
        TaskGraphPlanningConstraints(
            base_commit="a" * 40,
            allowed_paths=["src"],
            acceptance_plan=plan,
        )
    with pytest.raises(ValidationError, match="typed gate commands"):
        TaskGraphPlanningConstraints(
            base_commit="a" * 40,
            allowed_paths=["src", "testscript"],
            acceptance_plan=AcceptancePlan(required_gates=[GateType.UNIT_TEST]),
        )
    with pytest.raises(ValidationError, match="safe relative paths"):
        TaskGraphPlanningConstraints(
            base_commit="a" * 40,
            allowed_paths=["../src", "testscript"],
            acceptance_plan=plan,
        )
    with pytest.raises(ValidationError, match="lack typed commands: security_scan"):
        TaskGraphPlanningConstraints(
            base_commit="a" * 40,
            allowed_paths=["src", "testscript"],
            acceptance_plan=AcceptancePlan(
                required_gates=[GateType.UNIT_TEST, GateType.SECURITY_SCAN],
                commands=plan.commands,
            ),
        )


@pytest.mark.asyncio
async def test_founder_api_runs_spec_to_draft_without_task_side_effects(
    tmp_path: Path, monkeypatch, api_headers
):
    allowed_root = tmp_path / "clientProjects"
    allowed_root.mkdir()
    repo = allowed_root / "spec-api"
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))
    project_id = "prj_spec_api"
    spec = make_spec(project_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        registration = await client.post(
            "/api/projects",
            headers=api_headers,
            json={"project_id": project_id, "name": "Spec API", "repo_path": str(repo)},
        )
        submission = await client.post(
            f"/api/projects/{project_id}/specs",
            headers=api_headers,
            json=spec.model_dump(mode="json"),
        )
        submitted = submission.json()
        approval = await client.post(
            f"/api/projects/{project_id}/specs/{submitted['spec_id']}/approval",
            headers=api_headers,
            json={"approved": True, "scope_sha256": submitted["scope_sha256"]},
        )
        draft = await client.post(
            f"/api/projects/{project_id}/specs/{submitted['spec_id']}/task-graph-draft",
            headers=api_headers,
            json=make_constraints().model_dump(mode="json"),
        )

    assert registration.status_code == 200
    assert submission.status_code == 200
    assert approval.status_code == 200
    assert draft.status_code == 200
    assert len(draft.json()["tasks"]) == 1
    session_factory = get_session_factory()
    async with session_factory() as session:
        task_count = (
            await session.execute(
                select(func.count(TaskRecord.id)).where(TaskRecord.project_id == project_id)
            )
        ).scalar_one()
    assert task_count == 0


@pytest.mark.asyncio
async def test_service_principal_cannot_submit_or_plan_spec(
    tmp_path: Path, monkeypatch, api_headers
):
    allowed_root = tmp_path / "clientProjects"
    allowed_root.mkdir()
    repo = allowed_root / "spec-service"
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))
    project_id = "prj_spec_service"
    spec = make_spec(project_id)
    service_token = create_scoped_principal_token(
        subject="eva-service",
        role=PrincipalRole.SERVICE,
        project_ids=[project_id],
    )
    headers = {"Authorization": f"Bearer {service_token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/projects",
            headers=api_headers,
            json={"project_id": project_id, "name": "Spec service", "repo_path": str(repo)},
        )
        response = await client.post(
            f"/api/projects/{project_id}/specs",
            headers=headers,
            json=spec.model_dump(mode="json"),
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Specification submission requires founder access"}
