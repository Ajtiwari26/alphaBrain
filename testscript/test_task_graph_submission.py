"""Atomic project task-graph admission and API boundary tests."""

from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import ApprovalRecord, AuditEventRecord, ProjectRecord, TaskRecord
from alpha_core.security import PrincipalRole, create_scoped_principal_token
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import TaskDependency, TaskEnvelope, TaskStatus


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
        await session.rollback()


def make_task(
    task_id: str,
    *,
    project_id: str,
    repo: Path,
    dependencies: tuple[str, ...] = (),
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        project_id=project_id,
        repo=str(repo),
        objective=f"Complete {task_id}",
        allowed_paths=["src", "testscript"],
        dependencies=[TaskDependency(task_id=dependency) for dependency in dependencies],
        requires_approval=True,
    )


@pytest.mark.asyncio
async def test_graph_persists_out_of_order_dag_with_frozen_packets(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_graph_order"
    await TaskEngine.create_project(db_session, project_id, "Graph", str(repo))
    build = make_task("tsk_graph_build", project_id=project_id, repo=repo)
    qa = make_task(
        "tsk_graph_qa",
        project_id=project_id,
        repo=repo,
        dependencies=(build.task_id,),
    )

    records = await TaskEngine.submit_task_graph(
        db_session,
        [qa, build],
        project_id=project_id,
    )

    assert [record.id for record in records] == [qa.task_id, build.task_id]
    assert all(record.status == TaskStatus.WAITING_APPROVAL.value for record in records)
    assert all(record.packet_sha256 and len(record.packet_sha256) == 64 for record in records)
    graph_events = (
        (
            await db_session.execute(
                select(AuditEventRecord).where(
                    AuditEventRecord.event_type == "task_graph_submitted"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(graph_events) == 1
    assert graph_events[0].details_json == {
        "task_ids": [qa.task_id, build.task_id],
        "edge_count": 1,
    }


@pytest.mark.asyncio
async def test_cycle_rejection_leaves_no_partial_tasks(tmp_path: Path, db_session: AsyncSession):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_graph_cycle"
    await TaskEngine.create_project(db_session, project_id, "Graph", str(repo))
    first = make_task(
        "tsk_cycle_first",
        project_id=project_id,
        repo=repo,
        dependencies=("tsk_cycle_second",),
    )
    second = make_task(
        "tsk_cycle_second",
        project_id=project_id,
        repo=repo,
        dependencies=(first.task_id,),
    )

    with pytest.raises(ValueError, match="dependency cycle"):
        await TaskEngine.submit_task_graph(
            db_session,
            [first, second],
            project_id=project_id,
        )

    task_count = (
        await db_session.execute(
            select(func.count(TaskRecord.id)).where(TaskRecord.project_id == project_id)
        )
    ).scalar_one()
    assert task_count == 0


@pytest.mark.asyncio
async def test_missing_external_dependency_rejected_before_persistence(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_graph_missing"
    await TaskEngine.create_project(db_session, project_id, "Graph", str(repo))
    task = make_task(
        "tsk_graph_waiting",
        project_id=project_id,
        repo=repo,
        dependencies=("tsk_missing",),
    )

    with pytest.raises(ValueError, match="missing dependencies: tsk_missing"):
        await TaskEngine.submit_task_graph(db_session, [task], project_id=project_id)

    assert await db_session.get(TaskRecord, task.task_id) is None


@pytest.mark.asyncio
async def test_graph_rejects_task_without_explicit_approval(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_graph_approval"
    await TaskEngine.create_project(db_session, project_id, "Graph", str(repo))
    task = make_task("tsk_graph_unapproved", project_id=project_id, repo=repo)
    unsafe_task = task.model_copy(update={"requires_approval": False})

    with pytest.raises(ValueError, match="must require explicit execution approval"):
        await TaskEngine.submit_task_graph(db_session, [unsafe_task], project_id=project_id)

    assert await db_session.get(TaskRecord, task.task_id) is None


@pytest.mark.asyncio
async def test_duplicate_task_and_dependency_rejections_leave_no_partial_tasks(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_graph_duplicates"
    await TaskEngine.create_project(db_session, project_id, "Graph", str(repo))
    first = make_task("tsk_graph_duplicate", project_id=project_id, repo=repo)

    with pytest.raises(ValueError, match="Duplicate task ID"):
        await TaskEngine.submit_task_graph(
            db_session,
            [first, first],
            project_id=project_id,
        )

    duplicate_dependency = make_task(
        "tsk_graph_duplicate_dependency",
        project_id=project_id,
        repo=repo,
        dependencies=(first.task_id, first.task_id),
    )
    with pytest.raises(ValueError, match="contains duplicate dependencies"):
        await TaskEngine.submit_task_graph(
            db_session,
            [first, duplicate_dependency],
            project_id=project_id,
        )

    task_count = (
        await db_session.execute(
            select(func.count(TaskRecord.id)).where(TaskRecord.project_id == project_id)
        )
    ).scalar_one()
    assert task_count == 0


@pytest.mark.asyncio
async def test_cross_project_and_repo_bindings_fail_closed(
    tmp_path: Path, db_session: AsyncSession
):
    repo = tmp_path / "project"
    other_repo = tmp_path / "other-project"
    repo.mkdir()
    other_repo.mkdir()
    project_id = "prj_graph_binding"
    await TaskEngine.create_project(db_session, project_id, "Graph", str(repo))

    wrong_project = make_task(
        "tsk_graph_wrong_project",
        project_id="prj_other",
        repo=repo,
    )
    with pytest.raises(ValueError, match="project does not match"):
        await TaskEngine.submit_task_graph(
            db_session,
            [wrong_project],
            project_id=project_id,
        )

    wrong_repo = make_task(
        "tsk_graph_wrong_repo",
        project_id=project_id,
        repo=other_repo,
    )
    with pytest.raises(ValueError, match="repository does not match"):
        await TaskEngine.submit_task_graph(
            db_session,
            [wrong_repo],
            project_id=project_id,
        )

    assert await db_session.get(TaskRecord, wrong_project.task_id) is None
    assert await db_session.get(TaskRecord, wrong_repo.task_id) is None


@pytest.mark.asyncio
async def test_nonterminal_external_dependency_rejected(tmp_path: Path, db_session: AsyncSession):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_graph_external_state"
    await TaskEngine.create_project(db_session, project_id, "Graph", str(repo))
    prerequisite = make_task(
        "tsk_graph_external_pending",
        project_id=project_id,
        repo=repo,
    ).model_copy(update={"requires_approval": False})
    await TaskEngine.submit_task(db_session, prerequisite, project_id=project_id)
    dependent = make_task(
        "tsk_graph_external_dependent",
        project_id=project_id,
        repo=repo,
        dependencies=(prerequisite.task_id,),
    )

    with pytest.raises(ValueError, match="is not verified or completed"):
        await TaskEngine.submit_task_graph(
            db_session,
            [dependent],
            project_id=project_id,
        )

    assert await db_session.get(TaskRecord, dependent.task_id) is None


@pytest.mark.asyncio
async def test_exact_graph_resubmission_is_idempotent(tmp_path: Path, db_session: AsyncSession):
    repo = tmp_path / "project"
    repo.mkdir()
    project_id = "prj_graph_idempotent"
    await TaskEngine.create_project(db_session, project_id, "Graph", str(repo))
    task = make_task("tsk_graph_idempotent", project_id=project_id, repo=repo)

    first = await TaskEngine.submit_task_graph(db_session, [task], project_id=project_id)
    second = await TaskEngine.submit_task_graph(db_session, [task], project_id=project_id)

    assert first[0].id == second[0].id
    approval_count = (
        await db_session.execute(
            select(func.count(ApprovalRecord.id)).where(ApprovalRecord.task_id == task.task_id)
        )
    ).scalar_one()
    graph_event_count = (
        await db_session.execute(
            select(func.count(AuditEventRecord.id)).where(
                AuditEventRecord.event_type == "task_graph_submitted",
                AuditEventRecord.project_id == project_id,
            )
        )
    ).scalar_one()
    assert approval_count == 1
    assert graph_event_count == 1


@pytest.mark.asyncio
async def test_founder_can_submit_registered_project_graph_atomically(
    tmp_path: Path, monkeypatch, api_headers
):
    allowed_root = tmp_path / "clientProjects"
    allowed_root.mkdir()
    repo = allowed_root / "status-board"
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))
    project_id = "prj_graph_api"
    first = make_task("tsk_graph_api_build", project_id=project_id, repo=repo)
    second = make_task(
        "tsk_graph_api_qa",
        project_id=project_id,
        repo=repo,
        dependencies=(first.task_id,),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthenticated = await client.post(
            f"/api/projects/{project_id}/task-graph",
            json={"tasks": [first.model_dump(mode="json")]},
        )
        registration = await client.post(
            "/api/projects",
            headers=api_headers,
            json={"project_id": project_id, "name": "Status board", "repo_path": str(repo)},
        )
        response = await client.post(
            f"/api/projects/{project_id}/task-graph",
            headers=api_headers,
            json={
                "tasks": [
                    second.model_dump(mode="json"),
                    first.model_dump(mode="json"),
                ]
            },
        )

    assert unauthenticated.status_code == 401
    assert registration.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert [task["task_id"] for task in body["tasks"]] == [second.task_id, first.task_id]
    assert all(task["status"] == TaskStatus.WAITING_APPROVAL.value for task in body["tasks"])
    assert all(len(task["packet_sha256"]) == 64 for task in body["tasks"])


@pytest.mark.asyncio
async def test_service_principal_cannot_submit_task_graph(tmp_path: Path, monkeypatch, api_headers):
    allowed_root = tmp_path / "clientProjects"
    allowed_root.mkdir()
    repo = allowed_root / "service-denied"
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (allowed_root,))
    project_id = "prj_graph_service_denied"
    task = make_task("tsk_graph_service_denied", project_id=project_id, repo=repo)
    service_token = create_scoped_principal_token(
        subject="internal-service",
        role=PrincipalRole.SERVICE,
        project_ids=[project_id],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        registration = await client.post(
            "/api/projects",
            headers=api_headers,
            json={"project_id": project_id, "name": "Service denied", "repo_path": str(repo)},
        )
        response = await client.post(
            f"/api/projects/{project_id}/task-graph",
            headers={"Authorization": f"Bearer {service_token}"},
            json={"tasks": [task.model_dump(mode="json")]},
        )

    assert registration.status_code == 200
    assert response.status_code == 403
    assert response.json() == {"detail": "Task graph submission requires founder access"}

    session_factory = get_session_factory()
    async with session_factory() as session:
        assert await session.get(ProjectRecord, project_id) is not None
        assert await session.get(TaskRecord, task.task_id) is None
