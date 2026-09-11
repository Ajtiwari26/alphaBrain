import pytest
from fastapi import Header
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from alpha_core.api.app import app
from alpha_core.db.connection import get_session_factory, init_db
from alpha_core.db.models import ProjectRecord, TaskRecord
from alpha_core.security import (
    PrincipalRole,
    create_scoped_principal_token,
    require_worker_principal,
    verify_scoped_principal_token,
)


def mock_require_worker_principal(x_alpha_worker_identity: str | None = Header(default=None)):
    if not x_alpha_worker_identity:
        raise Exception("Missing token")
    return verify_scoped_principal_token(x_alpha_worker_identity)

app.dependency_overrides[require_worker_principal] = mock_require_worker_principal

@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(delete(TaskRecord).where(TaskRecord.id.in_(["task_1", "task_2"])))
        await session.execute(delete(ProjectRecord).where(ProjectRecord.id.in_(["prj_1", "prj_2"])))
        await session.commit()

    yield

    async with session_factory() as session:
        await session.execute(delete(TaskRecord).where(TaskRecord.id.in_(["task_1", "task_2"])))
        await session.execute(delete(ProjectRecord).where(ProjectRecord.id.in_(["prj_1", "prj_2"])))
        await session.commit()

@pytest.mark.asyncio
async def test_tenant_isolation():
    session_factory = get_session_factory()
    async with session_factory() as session:
        prj1 = ProjectRecord(id="prj_1", name="Project 1", repo_path="/tmp/prj1")
        prj2 = ProjectRecord(id="prj_2", name="Project 2", repo_path="/tmp/prj2")
        task1 = TaskRecord(id="task_1", project_id="prj_1", objective="t1", repo="foo", details_json={"task_id": "task_1", "project_id": "prj_1", "objective": "t1", "repo": "foo", "base_commit": "1e4a4f0a751b6ac3f2da938cb9a09053b6259814", "risk_class": "low", "requires_approval": False, "dependencies": [], "allowed_paths": ["foo"], "acceptance_plan": {"test_commands": []}, "concurrency_policy": {"max_per_project": 2}})
        task2 = TaskRecord(id="task_2", project_id="prj_2", objective="t2", repo="foo", details_json={"task_id": "task_2", "project_id": "prj_2", "objective": "t2", "repo": "foo", "base_commit": "1e4a4f0a751b6ac3f2da938cb9a09053b6259814", "risk_class": "low", "requires_approval": False, "dependencies": [], "allowed_paths": ["foo"], "acceptance_plan": {"test_commands": []}, "concurrency_policy": {"max_per_project": 2}})
        session.add_all([prj1, prj2, task1, task2])
        await session.commit()

    token1 = create_scoped_principal_token("client1", PrincipalRole.CLIENT, ["prj_1"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.get("/api/tasks/task_1", headers={"Authorization": f"Bearer {token1}"})
        assert res1.status_code == 200, f"res1 got {res1.status_code}"

        res2 = await client.get("/api/tasks/task_2", headers={"Authorization": f"Bearer {token1}"})
        assert res2.status_code == 403, f"Expected 403, got {res2.status_code}"

        # Test task_heartbeat (which requires worker principal)
        worker_token = create_scoped_principal_token("worker1", PrincipalRole.WORKER, ["prj_1"])
        res_heartbeat = await client.post("/api/tasks/task_2/heartbeat", headers={"Authorization": f"Bearer {worker_token}", "x-alpha-worker-identity": f"{worker_token}"}, json={"lease_token": "token"})
        assert res_heartbeat.status_code == 403, f"Expected 403, got {res_heartbeat.status_code}"

        # Test trace endpoint
        res_trace = await client.get("/api/portal/tasks/task_2/trace", headers={"Authorization": f"Bearer {token1}"})
        assert res_trace.status_code == 403, f"Expected 403, got {res_trace.status_code}"

        # Triage modify endpoint
        res_triage_modify = await client.post("/api/triage/tasks/task_2/modify", headers={"Authorization": f"Bearer {token1}"}, json={})
        assert res_triage_modify.status_code == 403, f"Expected 403, got {res_triage_modify.status_code}"


        # Test list triage tasks
        res_triage_list = await client.get("/api/triage/tasks", headers={"Authorization": f"Bearer {token1}"})
        # token1 (CLIENT) should get 403 because it requires FOUNDER or ADMIN
        assert res_triage_list.status_code == 403, f'Expected 403 due to require_triage_access, got {res_triage_list.status_code}'

        founder_token = create_scoped_principal_token("founder1", PrincipalRole.FOUNDER, ["prj_1"])
        res_triage_list_founder = await client.get("/api/triage/tasks", headers={"Authorization": f"Bearer {founder_token}"})
        assert res_triage_list_founder.status_code == 200, f'Expected 200, got {res_triage_list_founder.status_code}'

        # Test Head-of-Line blocking resolution for lease_task
        # Worker 2 is only authorized for prj_2.
        # task_1 (prj_1) is older and queued.
        # But Worker 2 should still successfully lease task_2 (prj_2) and skip task_1.
        worker2_token = create_scoped_principal_token("worker2", PrincipalRole.WORKER, ["prj_2"])
        res_lease = await client.post(
            "/api/tasks/lease",
            headers={"Authorization": f"Bearer {worker2_token}", "x-alpha-worker-identity": f"{worker2_token}"},
            json={"worker_id": "worker2"}
        )
        assert res_lease.status_code == 200, f"Expected 200, got {res_lease.status_code}"
        lease_data = res_lease.json()
        assert lease_data.get("status") == "leased", f"Failed to lease task: {lease_data}"
        assert lease_data["task"]["task_id"] == "task_2", f"Should have leased task_2, but got {lease_data['task'].get('task_id')}"
