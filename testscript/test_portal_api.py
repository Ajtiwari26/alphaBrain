from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app
from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_core.security import AuthPrincipal, PrincipalRole


@pytest.fixture
def mock_queue():
    queue = MagicMock(spec=TaskTriageQueue)
    # mock get_stats
    queue.get_stats.return_value = {"total_tasks": 10, "completed": 5}

    # mock get_task
    queue.get_task.return_value = {
        "id": "tsk_123",
        "envelope": {"project_id": "prj_alpha"},
        "provenance": {"meeting_id": "meet_123"},
        "result": {"senior_review": {"approved": True}},
    }

    # mock get_task_telemetry
    queue.get_task_telemetry.return_value = {"transition_count": 5}

    return queue


@pytest.fixture
def client(mock_queue):
    app.dependency_overrides[TaskTriageQueue] = lambda: mock_queue
    from alpha_core.api.app import get_triage_queue

    app.dependency_overrides[get_triage_queue] = lambda: mock_queue

    def override_require_api_principal():
        return AuthPrincipal(subject="test_admin", role=PrincipalRole.ADMIN)

    from alpha_core.security import require_api_principal

    app.dependency_overrides[require_api_principal] = override_require_api_principal

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_portal_overview(client, mock_queue):
    response = client.get("/api/portal/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stats"] == {"total_tasks": 10, "completed": 5}


def test_portal_task_trace(client, mock_queue):
    response = client.get("/api/portal/tasks/tsk_123/trace")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["task_id"] == "tsk_123"
    assert data["provenance"] == {"meeting_id": "meet_123"}
    # attestation might be redacted, but for our mock there are no secrets so it should be same
    assert data["attestation"] == {"approved": True}
    assert data["telemetry"] == {"transition_count": 5}


def test_portal_task_trace_invalid_id(client, mock_queue):
    response = client.get("/api/portal/tasks/invalid!id/trace")
    assert response.status_code == 422


def test_portal_task_trace_not_found(client, mock_queue):
    mock_queue.get_task.return_value = None
    response = client.get("/api/portal/tasks/tsk_404/trace")
    assert response.status_code == 404


def test_portal_overview_unauthorized():
    with TestClient(app) as unauth_client:
        response = unauth_client.get("/api/portal/overview")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_portal_stream(mock_queue):
    from alpha_core.api.app import app, get_triage_queue
    from alpha_core.security import (
        AuthPrincipal,
        PrincipalRole,
        create_scoped_stream_token,
        require_api_principal,
    )

    app.dependency_overrides[TaskTriageQueue] = lambda: mock_queue
    app.dependency_overrides[get_triage_queue] = lambda: mock_queue
    app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
        subject="test_admin", role=PrincipalRole.ADMIN
    )

    token = create_scoped_stream_token("portal-stream:prj_test", ttl_seconds=3600)

    async def mock_generator(project_id, last_event_id):
        yield "event: heartbeat\ndata: {}\n\n"

    with patch("alpha_core.api.app.portal_stream_generator", side_effect=mock_generator):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            async with ac.stream(
                "GET", f"/api/portal/projects/prj_test/stream?token={token}"
            ) as response:
                assert response.status_code == 200
                lines = []
                async for line in response.aiter_lines():
                    if line.strip():
                        lines.append(line)

                assert lines[0] == "event: heartbeat"
                assert lines[1] == "data: {}"

    app.dependency_overrides.clear()
