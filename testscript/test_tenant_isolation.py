import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from alpha_core.api.app import app
from alpha_core.db.connection import get_session_factory, init_db
from alpha_core.db.models import ProjectRecord, TaskRecord
from alpha_core.security import PrincipalRole, create_scoped_principal_token


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    session_factory = get_session_factory()
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
        task1 = TaskRecord(id="task_1", project_id="prj_1", objective="t1", repo="foo", details_json={})
        task2 = TaskRecord(id="task_2", project_id="prj_2", objective="t2", repo="foo", details_json={})
        session.add_all([prj1, prj2, task1, task2])
        await session.commit()

    token1 = create_scoped_principal_token("client1", PrincipalRole.CLIENT, ["prj_1"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.get("/api/tasks/task_1", headers={"Authorization": f"Bearer {token1}"})
        assert res1.status_code in (200, 404), f"res1 got {res1.status_code}"

        res2 = await client.get("/api/tasks/task_2", headers={"Authorization": f"Bearer {token1}"})
        assert res2.status_code == 403, f"Expected 403, got {res2.status_code}"
